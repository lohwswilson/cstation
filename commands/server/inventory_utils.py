#!/usr/bin/env python3
"""
Ansible inventory utilities for CStation server commands
Provides functions to interact with Ansible inventory using ansible-inventory command
"""

import json
import subprocess
from typing import Dict, List, Optional, Any
from rich.console import Console

console = Console()

def get_inventory_data(inventory_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get complete inventory data using ansible-inventory command
    
    Args:
        inventory_path: Optional path to inventory directory/file
    
    Returns:
        Dictionary containing the complete inventory data
    """
    try:
        cmd = ["ansible-inventory", "--list"]
        if inventory_path:
            cmd.extend(["-i", inventory_path])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        return json.loads(result.stdout)
    
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error running ansible-inventory: {e}[/red]")
        if e.stderr:
            console.print(f"[red]Error details: {e.stderr}[/red]")
        return {}
    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing ansible-inventory output: {e}[/red]")
        return {}
    except FileNotFoundError:
        console.print(f"[red]ansible-inventory command not found. Please install Ansible.[/red]")
        return {}
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        return {}

def get_all_hosts(inventory_path: Optional[str] = None) -> List[str]:
    """
    Get list of all hosts from inventory
    
    Args:
        inventory_path: Optional path to inventory directory/file
    
    Returns:
        List of host names
    """
    inventory_data = get_inventory_data(inventory_path)
    
    hosts = []
    for group_name, group_data in inventory_data.items():
        if group_name == "_meta":
            continue
        if isinstance(group_data, dict) and "hosts" in group_data:
            hosts.extend(group_data["hosts"])
    
    return list(set(hosts))  # Remove duplicates

def get_host_info(hostname: str, inventory_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get detailed information for a specific host
    
    Args:
        hostname: Name of the host
        inventory_path: Optional path to inventory directory/file
    
    Returns:
        Dictionary containing host information and variables
    """
    try:
        cmd = ["ansible-inventory", "--host", hostname]
        if inventory_path:
            cmd.extend(["-i", inventory_path])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        return json.loads(result.stdout)
    
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error getting host info for {hostname}: {e}[/red]")
        return {}
    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing host info: {e}[/red]")
        return {}
    except Exception as e:
        console.print(f"[red]Unexpected error getting host info: {e}[/red]")
        return {}

def get_hosts_by_group(inventory_path: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Get hosts organized by groups
    
    Args:
        inventory_path: Optional path to inventory directory/file
    
    Returns:
        Dictionary mapping group names to lists of hosts
    """
    inventory_data = get_inventory_data(inventory_path)
    
    groups = {}
    for group_name, group_data in inventory_data.items():
        if group_name == "_meta":
            continue
        if isinstance(group_data, dict) and "hosts" in group_data:
            groups[group_name] = group_data["hosts"]
    
    return groups

def find_host_groups(hostname: str, inventory_path: Optional[str] = None) -> List[str]:
    """
    Find which groups a host belongs to
    
    Args:
        hostname: Name of the host to search for
        inventory_path: Optional path to inventory directory/file
    
    Returns:
        List of group names that contain the host
    """
    groups_data = get_hosts_by_group(inventory_path)
    
    host_groups = []
    for group_name, hosts in groups_data.items():
        if hostname in hosts:
            host_groups.append(group_name)
    
    return host_groups

def host_exists(hostname: str, inventory_path: Optional[str] = None) -> bool:
    """
    Check if a host exists in the inventory
    
    Args:
        hostname: Name of the host to check
        inventory_path: Optional path to inventory directory/file
    
    Returns:
        True if host exists, False otherwise
    """
    all_hosts = get_all_hosts(inventory_path)
    return hostname in all_hosts