#!/usr/bin/env python3
"""
CStation - Infrastructure Management CLI Package

A DevOps CLI tool for managing infrastructure using Ansible.
"""

from importlib.metadata import PackageNotFoundError, version as pkg_version

from .config import initialize_configuration, get_config
from .main import app

try:
    __version__ = pkg_version("cstation")
except PackageNotFoundError:
    __version__ = "dev"

__author__ = "WS Loh"
__email__ = "wsloh@perfectwork.com"

__all__ = ["app", "initialize_configuration", "get_config"]

