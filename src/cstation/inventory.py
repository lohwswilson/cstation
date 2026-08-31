#!/usr/bin/env python3
"""
Inventory Management Module for CStation CLI

This module handles host inventory management using simple YAML files,
replacing the dependency on Ansible inventory.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.console import Console
from .config import get_config

console = Console()


class InventoryManager:
    """
    Manages host inventory stored in YAML format.

    Expected format:
    groups:
      web:
        hosts:
          - web01
          - web02
      db:
        hosts:
          - db01
    hosts:
      web01:
        ansible_host: 192.168.1.10
        ansible_user: admin
      web02:
        ansible_host: 192.168.1.11
    """

    def __init__(self, inventory_path: Optional[str] = None):
        self.inventory_path = self._find_inventory(inventory_path)
        self.data = self._load_inventory()

    def _find_inventory(self, provided_path: Optional[str]) -> Path:
        if provided_path:
            path = Path(provided_path)
            if path.exists():
                return path

        # Check config for inventory path
        config = get_config()
        config_path = config.get_config_value("inventory.path")
        if config_path:
            path = Path(config_path)
            if path.exists():
                return path

        # Search in standard paths
        search_paths = [
            Path.cwd() / "etc" / "inventory.yml",
            Path.cwd() / "etc" / "inventory.yaml",
            Path.home() / ".config" / "cstation" / "inventory.yml",
            Path("/etc/cstation/inventory.yml"),
        ]

        for path in search_paths:
            if path.exists():
                return path

        # Return default path even if it doesn't exist
        return Path("/etc/cstation/inventory.yml")

    def _load_inventory(self) -> Dict[str, Any]:
        if not self.inventory_path.exists():
            return {"groups": {}, "hosts": {}}

        try:
            with open(self.inventory_path, "r") as f:
                return yaml.safe_load(f) or {"groups": {}, "hosts": {}}
        except Exception as e:
            console.print(f"[red]Error loading inventory {self.inventory_path}: {e}[/red]")
            return {"groups": {}, "hosts": {}}

    def get_all_hosts(self) -> List[str]:
        return list(self.data.get("hosts", {}).keys())

    def get_host_info(self, hostname: str) -> Dict[str, Any]:
        return self.data.get("hosts", {}).get(hostname, {})

    def get_hosts_by_group(self) -> Dict[str, List[str]]:
        groups = {}
        for group_name, group_data in self.data.get("groups", {}).items():
            groups[group_name] = group_data.get("hosts", [])
        return groups

    def find_host_groups(self, hostname: str) -> List[str]:
        host_groups = []
        for group_name, group_data in self.data.get("groups", {}).items():
            if hostname in group_data.get("hosts", []):
                host_groups.append(group_name)
        return host_groups

    def host_exists(self, hostname: str) -> bool:
        return hostname in self.data.get("hosts", {})


def get_inventory(inventory_path: Optional[str] = None) -> InventoryManager:
    return InventoryManager(inventory_path)
