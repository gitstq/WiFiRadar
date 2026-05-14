"""
WiFiRadar - Scan History Tracking Module

Provides SQLite-based persistent storage for Wi-Fi scan results, enabling
historical analysis, signal strength trend tracking, and network change
detection between scans.

Uses sqlite3 from Python standard library (zero external dependencies).

Database Schema:
    scans:       Scan session metadata (timestamp, interface, network count)
    networks:    Individual network records per scan
    trends:      Pre-computed signal strength trends per BSSID

Usage:
    from history import ScanHistory

    db = ScanHistory('/path/to/wifiradar.db')
    scan_id = db.save_scan(scan_result)
    history = db.query_by_date('2025-01-01', '2025-01-31')
    trends = db.get_signal_trends('AA:BB:CC:DD:EE:FF')
    changes = db.detect_changes(scan_id, previous_scan_id)

Zero external dependencies - uses only Python standard library.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

from visualizer import NetworkInfo, ScanResult


# ---------------------------------------------------------------------------
# Database Schema
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = 1

_CREATE_TABLES_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Scan sessions
CREATE TABLE IF NOT EXISTS scans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT NOT NULL,
    interface     TEXT NOT NULL,
    network_count INTEGER NOT NULL DEFAULT 0,
    metadata      TEXT DEFAULT '{}',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Individual network records per scan
CREATE TABLE IF NOT EXISTS networks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id       INTEGER NOT NULL,
    ssid          TEXT NOT NULL DEFAULT '',
    bssid         TEXT NOT NULL,
    signal_dbm    INTEGER NOT NULL,
    channel       INTEGER NOT NULL,
    band          TEXT NOT NULL DEFAULT '2.4GHz',
    security      TEXT NOT NULL DEFAULT 'UNKNOWN',
    encryption    TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);

-- Pre-computed signal strength trends per BSSID
CREATE TABLE IF NOT EXISTS trends (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    bssid         TEXT NOT NULL,
    ssid          TEXT NOT NULL DEFAULT '',
    scan_id       INTEGER NOT NULL,
    signal_dbm    INTEGER NOT NULL,
    recorded_at   TEXT NOT NULL,
    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_networks_scan_id ON networks(scan_id);
CREATE INDEX IF NOT EXISTS idx_networks_bssid ON networks(bssid);
CREATE INDEX IF NOT EXISTS idx_networks_ssid ON networks(ssid);
CREATE INDEX IF NOT EXISTS idx_scans_timestamp ON scans(timestamp);
CREATE INDEX IF NOT EXISTS idx_trends_bssid ON trends(bssid);
CREATE INDEX IF NOT EXISTS idx_trends_recorded_at ON trends(recorded_at);
"""


# ---------------------------------------------------------------------------
# Scan History
# ---------------------------------------------------------------------------

class ScanHistory:
    """SQLite-based scan history storage and query engine.

    Provides persistent storage for Wi-Fi scan results with support for
    historical queries, trend analysis, and change detection.

    Args:
        db_path: Path to the SQLite database file. If the file does not
                 exist, it will be created automatically.
        auto_migrate: If True, automatically runs schema migrations on init.

    Example:
        >>> db = ScanHistory('wifiradar.db')
        >>> scan_id = db.save_scan(scan_result)
        >>> recent = db.query_recent(10)
        >>> trends = db.get_signal_trends('AA:BB:CC:DD:EE:FF')

    Attributes:
        db_path: Absolute path to the database file.
    """

    def __init__(self, db_path: str = 'wifiradar_history.db',
                 auto_migrate: bool = True) -> None:
        self.db_path = os.path.abspath(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        if auto_migrate:
            self._init_db()

    # -- Connection Management -------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a database connection.

        Returns:
            Active sqlite3.Connection with row factory configured.

        Raises:
            sqlite3.Error: If the database cannot be opened.
        """
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._conn.execute('PRAGMA foreign_keys = ON')
            # WAL mode for better concurrent read performance
            self._conn.execute('PRAGMA journal_mode = WAL')
        return self._conn

    def _init_db(self) -> None:
        """Initialize the database schema.

        Creates tables if they do not exist and runs any pending migrations.
        """
        conn = self._get_conn()
        conn.executescript(_CREATE_TABLES_SQL)

        # Check schema version
        try:
            row = conn.execute('SELECT value FROM _meta WHERE key = ?', ('schema_version',)).fetchone()
            current_version = int(row['value']) if row else 0
        except (sqlite3.Error, ValueError, TypeError):
            current_version = 0

        if current_version < _SCHEMA_VERSION:
            self._migrate(current_version, _SCHEMA_VERSION)
            conn.execute(
                'INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)',
                ('schema_version', str(_SCHEMA_VERSION)),
            )
            conn.commit()

    def _migrate(self, from_version: int, to_version: int) -> None:
        """Run database migrations between schema versions.

        Args:
            from_version: Current schema version.
            to_version: Target schema version.
        """
        conn = self._get_conn()
        # Future migrations would go here
        # if from_version < 2:
        #     conn.execute('ALTER TABLE scans ADD COLUMN location TEXT')
        # if from_version < 3:
        #     conn.execute('CREATE INDEX IF NOT EXISTS ...')
        pass

    def close(self) -> None:
        """Close the database connection.

        It is safe to call this method multiple times.
        """
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> 'ScanHistory':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - closes the database connection."""
        self.close()

    # -- Save Scan Results -----------------------------------------------------

    def save_scan(self, scan_result: ScanResult) -> int:
        """Save a complete scan result to the database.

        Stores the scan metadata, all detected networks, and creates
        trend entries for each network.

        Args:
            scan_result: The ScanResult object to persist.

        Returns:
            The scan ID (primary key) of the inserted scan record.

        Raises:
            sqlite3.Error: If the database operation fails.
            ValueError: If scan_result contains no networks.
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Insert scan record
            metadata_json = json.dumps(scan_result.metadata, ensure_ascii=False, default=str)
            cursor.execute(
                '''INSERT INTO scans (timestamp, interface, network_count, metadata)
                   VALUES (?, ?, ?, ?)''',
                (scan_result.timestamp, scan_result.interface,
                 len(scan_result.networks), metadata_json),
            )
            scan_id: int = cursor.lastrowid  # type: ignore[assignment]

            # Insert network records and trend entries
            for net in scan_result.networks:
                cursor.execute(
                    '''INSERT INTO networks
                       (scan_id, ssid, bssid, signal_dbm, channel, band, security, encryption)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (scan_id, net.ssid, net.bssid, net.signal_dbm,
                     net.channel, net.band, net.security, net.encryption),
                )

                # Create trend entry
                cursor.execute(
                    '''INSERT INTO trends (bssid, ssid, scan_id, signal_dbm, recorded_at)
                       VALUES (?, ?, ?, ?, ?)''',
                    (net.bssid, net.ssid, scan_id, net.signal_dbm, scan_result.timestamp),
                )

            conn.commit()
            return scan_id

        except sqlite3.Error:
            conn.rollback()
            raise

    # -- Query Methods ---------------------------------------------------------

    def query_by_date(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Query scan history by date range.

        Args:
            start_date: Start date in ISO format (e.g., '2025-01-01').
            end_date: End date in ISO format (e.g., '2025-01-31').

        Returns:
            List of scan dictionaries with 'networks' key containing
            the list of networks detected in each scan.

        Raises:
            ValueError: If date strings cannot be parsed.
        """
        conn = self._get_conn()

        # Normalize date strings to ISO format with time
        start = self._normalize_date(start_date, is_start=True)
        end = self._normalize_date(end_date, is_start=False)

        rows = conn.execute(
            '''SELECT id, timestamp, interface, network_count, metadata, created_at
               FROM scans
               WHERE timestamp >= ? AND timestamp <= ?
               ORDER BY timestamp DESC''',
            (start, end),
        ).fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            scan_dict = dict(row)
            scan_dict['networks'] = self._get_networks_for_scan(row['id'])
            scan_dict['metadata'] = json.loads(scan_dict.get('metadata', '{}'))
            results.append(scan_dict)

        return results

    def query_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Query the most recent scan results.

        Args:
            limit: Maximum number of scans to return.

        Returns:
            List of scan dictionaries ordered by timestamp (newest first).
        """
        conn = self._get_conn()
        rows = conn.execute(
            '''SELECT id, timestamp, interface, network_count, metadata, created_at
               FROM scans
               ORDER BY timestamp DESC
               LIMIT ?''',
            (limit,),
        ).fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            scan_dict = dict(row)
            scan_dict['networks'] = self._get_networks_for_scan(row['id'])
            scan_dict['metadata'] = json.loads(scan_dict.get('metadata', '{}'))
            results.append(scan_dict)

        return results

    def query_by_bssid(self, bssid: str) -> List[Dict[str, Any]]:
        """Query all scan records containing a specific BSSID.

        Args:
            bssid: MAC address of the access point to search for.

        Returns:
            List of network records (dicts) from all scans containing this BSSID.
        """
        conn = self._get_conn()
        rows = conn.execute(
            '''SELECT n.*, s.timestamp as scan_timestamp, s.interface
               FROM networks n
               JOIN scans s ON n.scan_id = s.id
               WHERE n.bssid = ?
               ORDER BY s.timestamp DESC''',
            (bssid,),
        ).fetchall()

        return [dict(row) for row in rows]

    def query_by_ssid(self, ssid: str) -> List[Dict[str, Any]]:
        """Query all scan records containing a specific SSID.

        Args:
            ssid: Network name to search for.

        Returns:
            List of network records (dicts) from all scans containing this SSID.
        """
        conn = self._get_conn()
        rows = conn.execute(
            '''SELECT n.*, s.timestamp as scan_timestamp, s.interface
               FROM networks n
               JOIN scans s ON n.scan_id = s.id
               WHERE n.ssid = ?
               ORDER BY s.timestamp DESC''',
            (ssid,),
        ).fetchall()

        return [dict(row) for row in rows]

    def get_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        """Get a single scan result by its ID.

        Args:
            scan_id: Primary key of the scan record.

        Returns:
            Scan dictionary with 'networks' key, or None if not found.
        """
        conn = self._get_conn()
        row = conn.execute(
            '''SELECT id, timestamp, interface, network_count, metadata, created_at
               FROM scans WHERE id = ?''',
            (scan_id,),
        ).fetchone()

        if row is None:
            return None

        scan_dict = dict(row)
        scan_dict['networks'] = self._get_networks_for_scan(scan_id)
        scan_dict['metadata'] = json.loads(scan_dict.get('metadata', '{}'))
        return scan_dict

    def get_latest_scan_id(self) -> Optional[int]:
        """Get the ID of the most recent scan.

        Returns:
            Scan ID, or None if no scans exist.
        """
        conn = self._get_conn()
        row = conn.execute(
            'SELECT id FROM scans ORDER BY timestamp DESC LIMIT 1'
        ).fetchone()
        return row['id'] if row else None

    # -- Trend Analysis --------------------------------------------------------

    def get_signal_trends(self, bssid: str,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get signal strength trend data for a specific BSSID.

        Returns historical signal readings ordered by time, suitable
        for time-series visualization.

        Args:
            bssid: MAC address of the access point.
            limit: Maximum number of data points to return.

        Returns:
            List of trend dictionaries with keys: bssid, ssid, signal_dbm,
            recorded_at, scan_id.
        """
        conn = self._get_conn()
        rows = conn.execute(
            '''SELECT bssid, ssid, signal_dbm, recorded_at, scan_id
               FROM trends
               WHERE bssid = ?
               ORDER BY recorded_at DESC
               LIMIT ?''',
            (bssid, limit),
        ).fetchall()

        # Return in chronological order (oldest first)
        return [dict(row) for row in reversed(rows)]

    def get_all_trends(self, min_readings: int = 2) -> Dict[str, List[Dict[str, Any]]]:
        """Get signal trends for all BSSIDs with sufficient data.

        Args:
            min_readings: Minimum number of readings required to include
                          a BSSID in the results.

        Returns:
            Dictionary mapping BSSID to list of trend data points.
        """
        conn = self._get_conn()

        # Find BSSIDs with enough readings
        bssid_rows = conn.execute(
            '''SELECT bssid, COUNT(*) as cnt
               FROM trends
               GROUP BY bssid
               HAVING cnt >= ?
               ORDER BY cnt DESC''',
            (min_readings,),
        ).fetchall()

        result: Dict[str, List[Dict[str, Any]]] = {}
        for row in bssid_rows:
            bssid = row['bssid']
            result[bssid] = self.get_signal_trends(bssid)

        return result

    def calculate_trend_summary(self, bssid: str) -> Optional[Dict[str, Any]]:
        """Calculate summary statistics for a BSSID's signal trend.

        Args:
            bssid: MAC address of the access point.

        Returns:
            Dictionary with trend summary (avg, min, max, trend direction),
            or None if insufficient data.
        """
        trends = self.get_signal_trends(bssid, limit=1000)
        if len(trends) < 2:
            return None

        signals = [t['signal_dbm'] for t in trends]
        avg_signal = sum(signals) / len(signals)
        min_signal = min(signals)
        max_signal = max(signals)

        # Simple linear trend: compare first half avg to second half avg
        mid = len(signals) // 2
        first_half_avg = sum(signals[:mid]) / mid if mid > 0 else signals[0]
        second_half_avg = sum(signals[mid:]) / (len(signals) - mid) if (len(signals) - mid) > 0 else signals[-1]

        diff = second_half_avg - first_half_avg
        if diff > 3:
            direction = 'improving'
        elif diff < -3:
            direction = 'declining'
        else:
            direction = 'stable'

        return {
            'bssid': bssid,
            'ssid': trends[-1]['ssid'],
            'readings': len(trends),
            'avg_signal_dbm': round(avg_signal, 1),
            'min_signal_dbm': min_signal,
            'max_signal_dbm': max_signal,
            'trend_direction': direction,
            'trend_delta_dbm': round(diff, 1),
            'first_reading': trends[0]['recorded_at'],
            'last_reading': trends[-1]['recorded_at'],
        }

    # -- Change Detection ------------------------------------------------------

    def detect_changes(self, scan_id: int,
                       compare_scan_id: Optional[int] = None) -> Dict[str, Any]:
        """Detect network changes between two scans.

        Compares the current scan with a previous scan (or the most recent
        scan before the given scan_id) and identifies new, removed, and
        changed networks.

        Args:
            scan_id: ID of the newer scan.
            compare_scan_id: ID of the older scan to compare against.
                             If None, automatically finds the most recent
                             scan before scan_id.

        Returns:
            Dictionary with keys:
            - 'new_networks': List of networks in scan_id but not in compare.
            - 'removed_networks': List of networks in compare but not in scan_id.
            - 'signal_changes': List of dicts with bssid, ssid, old_signal, new_signal, delta.
            - 'channel_changes': List of dicts with bssid, ssid, old_channel, new_channel.
            - 'scan_id': The newer scan ID.
            - 'compare_scan_id': The older scan ID.
        """
        conn = self._get_conn()

        # Get current scan's networks
        current_nets = self._get_networks_for_scan(scan_id)
        current_map: Dict[str, Dict[str, Any]] = {n['bssid']: n for n in current_nets}

        # Determine comparison scan
        if compare_scan_id is None:
            row = conn.execute(
                '''SELECT id FROM scans
                   WHERE timestamp < (SELECT timestamp FROM scans WHERE id = ?)
                   ORDER BY timestamp DESC LIMIT 1''',
                (scan_id,),
            ).fetchone()
            if row is None:
                return {
                    'scan_id': scan_id,
                    'compare_scan_id': None,
                    'new_networks': [],
                    'removed_networks': [],
                    'signal_changes': [],
                    'channel_changes': [],
                    'message': 'No previous scan available for comparison.',
                }
            compare_scan_id = row['id']

        # Get comparison scan's networks
        compare_nets = self._get_networks_for_scan(compare_scan_id)
        compare_map: Dict[str, Dict[str, Any]] = {n['bssid']: n for n in compare_nets}

        current_bssids = set(current_map.keys())
        compare_bssids = set(compare_map.keys())

        # New networks (in current but not in compare)
        new_bssids = current_bssids - compare_bssids
        new_networks = [current_map[b] for b in new_bssids]

        # Removed networks (in compare but not in current)
        removed_bssids = compare_bssids - current_bssids
        removed_networks = [compare_map[b] for b in removed_bssids]

        # Signal changes (in both, but signal differs)
        signal_changes: List[Dict[str, Any]] = []
        channel_changes: List[Dict[str, Any]] = []
        for bssid in current_bssids & compare_bssids:
            curr = current_map[bssid]
            prev = compare_map[bssid]

            if curr['signal_dbm'] != prev['signal_dbm']:
                signal_changes.append({
                    'bssid': bssid,
                    'ssid': curr['ssid'],
                    'old_signal_dbm': prev['signal_dbm'],
                    'new_signal_dbm': curr['signal_dbm'],
                    'delta_dbm': curr['signal_dbm'] - prev['signal_dbm'],
                })

            if curr['channel'] != prev['channel']:
                channel_changes.append({
                    'bssid': bssid,
                    'ssid': curr['ssid'],
                    'old_channel': prev['channel'],
                    'new_channel': curr['channel'],
                })

        return {
            'scan_id': scan_id,
            'compare_scan_id': compare_scan_id,
            'new_networks': new_networks,
            'removed_networks': removed_networks,
            'signal_changes': signal_changes,
            'channel_changes': channel_changes,
        }

    # -- Export Methods --------------------------------------------------------

    def export_trends_csv(self, output_path: str) -> str:
        """Export all trend data to CSV format.

        Args:
            output_path: File path for the CSV output.

        Returns:
            Absolute path of the saved file.

        Raises:
            OSError: If the file cannot be written.
        """
        import csv as csv_mod
        import io

        conn = self._get_conn()
        rows = conn.execute(
            '''SELECT t.bssid, t.ssid, t.signal_dbm, t.recorded_at, s.interface
               FROM trends t
               JOIN scans s ON t.scan_id = s.id
               ORDER BY t.bssid, t.recorded_at'''
        ).fetchall()

        abs_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(abs_path) if os.path.dirname(abs_path) else '.', exist_ok=True)

        with open(abs_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv_mod.writer(f)
            writer.writerow(['BSSID', 'SSID', 'Signal_dBm', 'Recorded_At', 'Interface'])
            for row in rows:
                writer.writerow([row['bssid'], row['ssid'], row['signal_dbm'],
                                 row['recorded_at'], row['interface']])

        return abs_path

    def export_trends_json(self, output_path: str) -> str:
        """Export all trend data to JSON format.

        Args:
            output_path: File path for the JSON output.

        Returns:
            Absolute path of the saved file.

        Raises:
            OSError: If the file cannot be written.
        """
        all_trends = self.get_all_trends(min_readings=1)

        abs_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(abs_path) if os.path.dirname(abs_path) else '.', exist_ok=True)

        with open(abs_path, 'w', encoding='utf-8') as f:
            json.dump(all_trends, f, indent=2, ensure_ascii=False, default=str)

        return abs_path

    # -- Maintenance Methods ---------------------------------------------------

    def get_scan_count(self) -> int:
        """Get the total number of stored scans.

        Returns:
            Count of scan records in the database.
        """
        conn = self._get_conn()
        row = conn.execute('SELECT COUNT(*) as cnt FROM scans').fetchone()
        return row['cnt']  # type: ignore[return-value]

    def get_network_count(self) -> int:
        """Get the total number of stored network records.

        Returns:
            Count of network records across all scans.
        """
        conn = self._get_conn()
        row = conn.execute('SELECT COUNT(*) as cnt FROM networks').fetchone()
        return row['cnt']  # type: ignore[return-value]

    def get_unique_bssid_count(self) -> int:
        """Get the number of unique BSSIDs ever seen.

        Returns:
            Count of distinct BSSID values.
        """
        conn = self._get_conn()
        row = conn.execute('SELECT COUNT(DISTINCT bssid) as cnt FROM networks').fetchone()
        return row['cnt']  # type: ignore[return-value]

    def prune_old_scans(self, days: int = 90) -> int:
        """Remove scan records older than a specified number of days.

        Cascade-deletes associated network and trend records.

        Args:
            days: Maximum age of scans to keep (in days).

        Returns:
            Number of scan records deleted.
        """
        conn = self._get_conn()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            cursor = conn.cursor()
            cursor.execute(
                '''DELETE FROM scans WHERE timestamp < ?''',
                (cutoff,),
            )
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        except sqlite3.Error:
            conn.rollback()
            raise

    def vacuum(self) -> None:
        """Reclaim unused space in the database file.

        Should be called periodically after large deletions.
        """
        conn = self._get_conn()
        conn.execute('VACUUM')

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics.

        Returns:
            Dictionary with database statistics including scan count,
            network count, unique BSSIDs, and database file size.
        """
        db_size = 0
        if os.path.exists(self.db_path):
            db_size = os.path.getsize(self.db_path)

        return {
            'scan_count': self.get_scan_count(),
            'network_count': self.get_network_count(),
            'unique_bssids': self.get_unique_bssid_count(),
            'database_size_bytes': db_size,
            'database_path': self.db_path,
        }

    # -- Private Helpers -------------------------------------------------------

    def _get_networks_for_scan(self, scan_id: int) -> List[Dict[str, Any]]:
        """Retrieve all network records for a given scan ID.

        Args:
            scan_id: Primary key of the scan.

        Returns:
            List of network dictionaries.
        """
        conn = self._get_conn()
        rows = conn.execute(
            '''SELECT id, scan_id, ssid, bssid, signal_dbm, channel, band, security, encryption
               FROM networks WHERE scan_id = ?
               ORDER BY signal_dbm DESC''',
            (scan_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _normalize_date(date_str: str, is_start: bool = True) -> str:
        """Normalize a date string to ISO format with time component.

        Accepts various date formats and normalizes them for SQLite comparison.

        Args:
            date_str: Date string in various formats (ISO date, ISO datetime, etc.).
            is_start: If True, appends 00:00:00; if False, appends 23:59:59.

        Returns:
            Normalized ISO datetime string.

        Raises:
            ValueError: If the date string cannot be parsed.
        """
        date_str = date_str.strip()

        # Try ISO format with time
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                dt = datetime.strptime(date_str, fmt)
                if is_start:
                    dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                return dt.isoformat()
            except ValueError:
                continue

        raise ValueError(f"Cannot parse date string: '{date_str}'. "
                         f"Expected format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
