#!/usr/bin/env python3
"""
CStation - Infrastructure Management CLI Package

A DevOps CLI tool for managing infrastructure using Ansible.
"""

from .config import initialize_configuration, get_config
from .main import app

__version__ = "1.0.0"
__author__ = "WS Loh"
__email__ = "wsloh@perfectwork.com"

__all__ = ["app", "initialize_configuration", "get_config"]
