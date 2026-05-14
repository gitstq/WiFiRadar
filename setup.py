"""
WiFiRadar - Lightweight Wi-Fi Signal Intelligent Analysis & Visualization CLI.

Setup script for package installation with console_scripts entry point.
"""

from setuptools import setup, find_packages

setup(
    name="wifiradar",
    version="0.1.0",
    description="Lightweight Wi-Fi Signal Intelligent Analysis & Visualization CLI",
    long_description=open("README.md", encoding="utf-8").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="WiFiRadar Contributors",
    license="MIT",
    python_requires=">=3.8",
    packages=find_packages(include=["src", "src.*"]),
    package_dir={"": "."},
    entry_points={
        "console_scripts": [
            "wifiradar=wifiradar:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Networking",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
)
