#!/usr/bin/env python3
"""
PerfectWork configuration settings for CStation CLI.

This module defines configuration options specific to PW sync operations.
"""

import re
from pathlib import Path
from typing import List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class PWConfig(BaseModel):
    """PerfectWork sync configuration."""
    
    # Source paths
    pw_base_path: Path = Field(default=Path("/opt/PW"), description="Base path for PW installations")
    
    # Valid versions (now accepts any numeric version)
    version_pattern: str = Field(
        default=r"^\d+\.\d+$",
        description="Regex pattern for valid version format (e.g., 3.0, 18.0)"
    )
    
    # Remote settings
    remote_base_path: str = Field(
        default="/var/lib/perfectwork",
        description="Base path on remote server"
    )
    domain_suffix: str = Field(
        default=".ansis.com.sg",
        description="Domain suffix for remote hosts"
    )
    
    # Sync settings
    default_ssh_port: int = Field(default=22, description="Default SSH port")
    cluster_ssh_port: int = Field(default=8288, description="Cluster SSH port")
    
    # Rsync options
    rsync_options: List[str] = Field(
        default=["-avz", "--delete", "--exclude", ".*"],
        description="Default rsync options"
    )
    
    # Exclusion patterns
    exclude_patterns: List[str] = Field(
        default=["__pycache__", "*.pyc", "*.pyo", ".git", ".svn"],
        description="Patterns to exclude during sync"
    )
    
    # Temporary directory settings
    temp_dir_prefix: str = Field(
        default="cstation_pw_sync",
        description="Prefix for temporary directories"
    )
    
    # Timeout settings
    ssh_timeout: int = Field(default=30, description="SSH connection timeout in seconds")
    rsync_timeout: int = Field(default=300, description="Rsync operation timeout in seconds")
    
    model_config = ConfigDict(env_prefix="CSTATION_PW_", case_sensitive=False)


def get_pw_config() -> PWConfig:
    """Get PW configuration instance."""
    return PWConfig()


def validate_version(version: str) -> bool:
    """Validate if the provided version matches the expected format."""
    config = get_pw_config()
    pattern = re.compile(config.version_pattern)
    return bool(pattern.match(version))


def get_source_path(version: str) -> Path:
    """Get the source path for a specific PW version."""
    config = get_pw_config()
    return config.pw_base_path / f"PW.{version}"


def get_addons_path(version: str) -> Path:
    """Get the addons path for a specific PW version."""
    config = get_pw_config()
    return config.pw_base_path / f"PW_ADDONS.{version}"


def get_remote_pw_path(version: str) -> str:
    """Get the remote PW path for a specific version."""
    config = get_pw_config()
    return f"{config.remote_base_path}/PW.{version}"


def get_remote_addons_path(version: str) -> str:
    """Get the remote addons path for a specific version."""
    config = get_pw_config()
    return f"{config.remote_base_path}/PW_ADDONS.{version}"


def get_remote_host(hostname: str) -> str:
    """Get the full remote hostname with domain suffix."""
    config = get_pw_config()
    if config.domain_suffix in hostname:
        return hostname
    return f"{hostname}{config.domain_suffix}"


def get_rsync_command_base(port: int, dry_run: bool = False) -> List[str]:
    """Get base rsync command with common options."""
    config = get_pw_config()
    cmd = ["rsync"] + config.rsync_options + ["-e", f"ssh -p{port}"]
    
    if dry_run:
        cmd.append("--dry-run")
    
    return cmd