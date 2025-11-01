#!/usr/bin/env python3
"""
CStation - Infrastructure Management CLI Package

A DevOps CLI tool for managing infrastructure using Ansible.
"""

from .config import initialize_configuration, get_config
from .main import app

__version__ = "0.1.0"
__author__ = "DevOps Team"
__email__ = "devops@example.com"

__all__ = ["app", "initialize_configuration", "get_config"]