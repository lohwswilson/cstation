#!/usr/bin/env python3
"""
Server add command for CStation CLI
Adds server entries to Ansible inventory
"""

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console

console = Console()


def server_add(
    server_name: str = typer.Argument(..., help="Name of the server to add to inventory"),
    host: str = typer.Option(..., "--host", "-H", help="Target IP address or FQDN"),
    group: str = typer.Option("all", "--group", "-g", help="Ansible inventory group name"),
    user: str = typer.Option("root", "--user", "-u", help="Ansible SSH user"),
    port: int = typer.Option(22, "--port", "-p", help="Ansible SSH port"),
    inventory_path: Optional[str] = typer.Option(
        None, "-i", "--inventory", help="Custom inventory directory or file path"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite if server already exists in group"),
) -> None:
    """
    Add a server entry to the Ansible inventory.

    Examples:
      cstation server add prod-db --host 10.0.0.5 --group databases
      cstation server add web-01 --host 198.51.100.10 --user ubuntu
    """
    inv_dir = Path(inventory_path) if inventory_path else Path("/etc/cstation/ansible/inventory")
    target_file = inv_dir / f"{group}.yml" if inv_dir.is_dir() else inv_dir

    if not target_file.parent.exists():
        target_file.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if target_file.exists():
        try:
            with open(target_file, "r") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            console.print(f"[red]Error reading inventory file {target_file}: {e}[/red]")
            raise typer.Exit(1)

    if group not in data:
        data[group] = {"hosts": {}}
    elif "hosts" not in data[group] or data[group]["hosts"] is None:
        data[group]["hosts"] = {}

    if server_name in data[group]["hosts"] and not force:
        console.print(
            f"[yellow]Server '{server_name}' already exists in group '{group}'. Use --force to overwrite.[/yellow]"
        )
        raise typer.Exit(1)

    data[group]["hosts"][server_name] = {
        "ansible_host": host,
        "ansible_user": user,
        "ansible_port": port,
    }

    try:
        with open(target_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        console.print(
            f"[green]✓[/green] Added server [bold]{server_name}[/bold] ({host}:{port}) to group '[cyan]{group}[/cyan]' in {target_file}"
        )
    except Exception as e:
        console.print(f"[red]Error writing inventory file {target_file}: {e}[/red]")
        raise typer.Exit(1)
