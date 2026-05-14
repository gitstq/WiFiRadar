"""
WiFiRadar Configuration Module.

Manages all configuration for the WiFiRadar CLI application.
Supports layered configuration: defaults -> config file -> environment variables.

Configuration priority (highest to lowest):
    1. Environment variables (WIFIRADAR_ prefix)
    2. Project-level config file (.wifiradar.json)
    3. User-level config file (~/.wifiradar/config.json)
    4. Built-in defaults
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Channel Definitions
# ---------------------------------------------------------------------------

#: 2.4 GHz channel-to-frequency mapping (channel: frequency_MHz)
CHANNEL_FREQ_2GHZ: Dict[int, int] = {
    1: 2412, 2: 2417, 3: 2422, 4: 2427, 5: 2432,
    6: 2437, 7: 2442, 8: 2447, 9: 2452, 10: 2457,
    11: 2462, 12: 2467, 13: 2472, 14: 2484,
}

#: 5 GHz channel-to-frequency mapping (channel: frequency_MHz)
CHANNEL_FREQ_5GHZ: Dict[int, int] = {
    36: 5180, 40: 5200, 44: 5220, 48: 5240,
    52: 5260, 56: 5280, 60: 5300, 64: 5320,
    100: 5500, 104: 5520, 108: 5540, 112: 5560,
    116: 5580, 120: 5600, 124: 5620, 128: 5640,
    132: 5660, 136: 5680, 140: 5700, 144: 5720,
    149: 5745, 153: 5765, 157: 5785, 161: 5805,
    165: 5825, 169: 5845, 173: 5865, 177: 5885,
}

#: Frequency-to-channel mapping (reverse lookup)
FREQ_CHANNEL_MAP: Dict[int, int] = {}
for _ch, _freq in {**CHANNEL_FREQ_2GHZ, **CHANNEL_FREQ_5GHZ}.items():
    FREQ_CHANNEL_MAP[_freq] = _ch

#: Non-overlapping channels for 2.4 GHz (20 MHz channels)
NON_OVERLAPPING_2GHZ: List[int] = [1, 6, 11]

#: Non-overlapping channels for 5 GHz (DFS channels excluded for general use)
NON_OVERLAPPING_5GHZ: List[int] = [
    36, 40, 44, 48, 149, 153, 157, 161, 165,
]


# ---------------------------------------------------------------------------
# Signal Strength Thresholds (dBm)
# ---------------------------------------------------------------------------

class SignalThresholds:
    """Signal strength classification thresholds (in dBm)."""

    EXCELLENT: int = -50   # >= -50 dBm
    GOOD: int = -60        # >= -60 dBm
    FAIR: int = -70        # >= -70 dBm
    POOR: int = -80        # >= -80 dBm
    NO_SIGNAL: int = -90   # Below this is essentially no signal


# ---------------------------------------------------------------------------
# Color Scheme
# ---------------------------------------------------------------------------

class ColorScheme:
    """ANSI color codes for terminal output."""

    # Basic colors
    RESET: str = "\033[0m"
    BOLD: str = "\033[1m"
    DIM: str = "\033[2m"
    UNDERLINE: str = "\033[4m"

    # Foreground colors
    RED: str = "\033[31m"
    GREEN: str = "\033[32m"
    YELLOW: str = "\033[33m"
    BLUE: str = "\033[34m"
    MAGENTA: str = "\033[35m"
    CYAN: str = "\033[36m"
    WHITE: str = "\033[37m"
    GRAY: str = "\033[90m"

    # Bright foreground colors
    BRIGHT_RED: str = "\033[91m"
    BRIGHT_GREEN: str = "\033[92m"
    BRIGHT_YELLOW: str = "\033[93m"
    BRIGHT_BLUE: str = "\033[94m"
    BRIGHT_CYAN: str = "\033[96m"

    # Signal quality colors
    SIGNAL_EXCELLENT: str = BRIGHT_GREEN
    SIGNAL_GOOD: str = GREEN
    SIGNAL_FAIR: str = YELLOW
    SIGNAL_POOR: str = RED
    SIGNAL_NONE: str = GRAY

    # Band colors
    BAND_2GHZ: str = YELLOW
    BAND_5GHZ: str = CYAN
    BAND_UNKNOWN: str = GRAY

    # Security colors
    SECURE: str = GREEN
    INSECURE: str = RED
    WEP: str = YELLOW


# ---------------------------------------------------------------------------
# Default Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    # Scan settings
    "scan_interface": "wlan0",
    "scan_timeout": 15,
    "scan_repeat": 1,

    # Output settings
    "output_format": "table",
    "output_encoding": "utf-8",
    "no_color": False,
    "verbose": False,
    "quiet": False,

    # Analysis settings
    "min_signal_filter": -90,
    "sort_by": "signal",
    "sort_descending": True,
    "top_n": 0,  # 0 means show all

    # Monitor settings
    "monitor_interval": 30,
    "monitor_duration": 0,  # 0 means infinite
    "alert_threshold": -75,

    # History settings
    "history_dir": "~/.wifiradar/history",
    "history_max_entries": 100,
    "history_format": "json",

    # Report settings
    "report_output_dir": ".",
    "report_auto_open": False,

    # Channel width for overlap calculation (MHz)
    "channel_width": 20,

    # Platform-specific scan command
    "scan_command": "",  # Auto-detected
}


# ---------------------------------------------------------------------------
# Configuration Manager
# ---------------------------------------------------------------------------

class Config:
    """
    Manages WiFiRadar configuration with layered overrides.

    Configuration is loaded in the following priority order (highest wins):
        1. Environment variables with WIFIRADAR_ prefix
        2. Project-level .wifiradar.json
        3. User-level ~/.wifiradar/config.json
        4. Built-in defaults

    Examples:
        >>> cfg = Config()
        >>> cfg.get("scan_timeout")
        15
        >>> cfg.get("nonexistent", default=42)
        42
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialize configuration with optional explicit config file path.

        Args:
            config_path: Explicit path to a configuration file.
                         If None, auto-detection is used.
        """
        self._values: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self._config_paths: List[Path] = []
        self._load_config_files(config_path)
        self._load_env_overrides()

    # -- Public API ----------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.

        Args:
            key: Configuration key name.
            default: Default value if key is not found.

        Returns:
            The configuration value, or default if not found.
        """
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value at runtime.

        Args:
            key: Configuration key name.
            value: Value to set.
        """
        self._values[key] = value

    def all(self) -> Dict[str, Any]:
        """Return a shallow copy of all configuration values.

        Returns:
            Dictionary of all configuration key-value pairs.
        """
        return dict(self._values)

    @property
    def config_paths(self) -> List[Path]:
        """Return list of config file paths that were loaded.

        Returns:
            List of Path objects for loaded config files.
        """
        return list(self._config_paths)

    @property
    def user_config_dir(self) -> Path:
        """Return the user configuration directory path.

        Returns:
            Path to ~/.wifiradar/
        """
        return Path.home() / ".wifiradar"

    @property
    def history_dir(self) -> Path:
        """Return the history directory path (expanded).

        Returns:
            Path to the history storage directory.
        """
        raw = self.get("history_dir", "~/.wifiradar/history")
        return Path(raw).expanduser()

    # -- Private methods -----------------------------------------------------

    def _load_config_files(self, explicit_path: Optional[str] = None) -> None:
        """Load configuration from files in priority order.

        Args:
            explicit_path: User-specified config file path.
        """
        # 1. User-level config
        user_config = Path.home() / ".wifiradar" / "config.json"
        self._try_load_file(user_config)

        # 2. Project-level config (current working directory)
        project_config = Path.cwd() / ".wifiradar.json"
        self._try_load_file(project_config)

        # 3. Explicit path (highest file priority)
        if explicit_path:
            self._try_load_file(Path(explicit_path))

    def _try_load_file(self, path: Path) -> None:
        """Attempt to load a JSON config file, silently skip on failure.

        Args:
            path: Path to the JSON config file.
        """
        if not path.is_file():
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._values.update(data)
                self._config_paths.append(path.resolve())
        except (OSError, json.JSONDecodeError, TypeError):
            # Silently skip corrupted or unreadable config files
            pass

    def _load_env_overrides(self) -> None:
        """Load configuration overrides from environment variables.

        Environment variables use the WIFIRADAR_ prefix and map directly
        to configuration keys. For example, WIFIRADAR_SCAN_TIMEOUT=20
        sets scan_timeout to "20" (string, will need conversion by caller).

        Boolean values: "true"/"1"/"yes" (case-insensitive) -> True.
        Integer values: numeric strings -> int.
        """
        prefix = "WIFIRADAR_"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            config_key = key[len(prefix):].lower()
            # Convert value types
            self._values[config_key] = self._convert_env_value(value)

    @staticmethod
    def _convert_env_value(value: str) -> Any:
        """Convert an environment variable string to an appropriate Python type.

        Args:
            value: Raw string value from environment variable.

        Returns:
            Converted value (int, float, bool, or str).
        """
        # Boolean detection
        if value.lower() in ("true", "1", "yes", "on"):
            return True
        if value.lower() in ("false", "0", "no", "off"):
            return False
        # Integer detection
        try:
            return int(value)
        except ValueError:
            pass
        # Float detection
        try:
            return float(value)
        except ValueError:
            pass
        return value


# ---------------------------------------------------------------------------
# Convenience singleton
# ---------------------------------------------------------------------------

_global_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """Get the global Config singleton, creating it if necessary.

    Args:
        config_path: Optional explicit config file path for first initialization.

    Returns:
        The global Config instance.
    """
    global _global_config
    if _global_config is None:
        _global_config = Config(config_path)
    return _global_config


def reset_config() -> None:
    """Reset the global config singleton (useful for testing)."""
    global _global_config
    _global_config = None
