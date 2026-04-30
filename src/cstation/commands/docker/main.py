from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from cstation.ssh import SSHManager
from cstation.commands.vps.main import _resolve_vps_dir, _load_vps_config, _ssh_from_config
from .services.registry import get_service, available_services
from .services import TraefikService, PortainerService  # noqa: F401 — auto-register

console = Console()

docker_app = typer.Typer(
    name="docker",
    help="Docker container service management",
    invoke_without_command=True,
)


def _discover_fragments(vps_dir: Path) -> list[Path]:
    return sorted(p for p in vps_dir.glob("*.yaml") if p.name != "vps.yaml")


def _load_fragments(vps_dir: Path, service_filter: Optional[str] = None) -> list[tuple[str, dict]]:
    fragments = []
    for frag_path in _discover_fragments(vps_dir):
        with frag_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            continue
        kind = data.get("kind", "")
        if kind not in ("Container", "Stack"):
            continue
        name = data.get("name", frag_path.stem)
        if service_filter and name != service_filter:
            continue
        if not data.get("enabled", True):
            fragments.append((name, data, "disabled"))
        else:
            fragments.append((name, data, "enabled"))
    return fragments


def _preflight_check(ssh: SSHManager) -> bool:
    result = ssh.run("docker info >/dev/null 2>&1 && echo ok || echo missing", hide=True, sudo=True)
    status = getattr(result, "stdout", "").strip() if result else "missing"
    if status != "ok":
        console.print("[red]✗[/red] Docker daemon is not running on the VPS.")
        console.print("[dim]Run 'cstation vps apply <vps>' first.[/dim]")
        return False
    result = ssh.run("docker network ls --format '{{.Name}}' 2>/dev/null", hide=True, sudo=True)
    networks = set()
    if result and getattr(result, "stdout", "").strip():
        networks = {line.strip() for line in result.stdout.strip().splitlines() if line.strip()}
    if "PW_NET" not in networks:
        console.print("[red]✗[/red] Docker network PW_NET does not exist on the VPS.")
        console.print("[dim]Run 'cstation vps apply <vps>' first.[/dim]")
        return False
    return True


def _check_port_collisions(ssh: SSHManager, fragments: list) -> list[str]:
    declared_ports: dict[str, str] = {}
    for name, data, status in fragments:
        if status == "disabled":
            continue
        for port_spec in data.get("ports", []):
            host_port = port_spec.split(":")[0] if ":" in port_spec else port_spec
            if host_port in declared_ports:
                return [f"Port {host_port} declared by both {declared_ports[host_port]} and {name}"]
            declared_ports[host_port] = name
    return []


def _get_service_instance(name: str, kind: str):
    try:
        svc_cls = get_service(name)
        return svc_cls()
    except ValueError:
        console.print(f"[yellow]⚠[/yellow] No built-in service class for '{name}' (kind: {kind}). Using generic ImageService.")
        from .services.image_service import ImageService
        svc = ImageService()
        svc.name = name
        svc.kind = kind
        return svc


@docker_app.command("plan")
def docker_plan(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Plan a single service"),
) -> None:
    """Dry-run: show what would change for container services."""
    vps_dir = _resolve_vps_dir(Path(vps))
    _load_vps_config(vps_dir)

    identity_name = vps_dir.name
    console.print(f"\n[bold]Docker Plan: {identity_name}[/bold] [dim]({vps_dir}/)[/dim]\n")

    ssh = _ssh_from_config(_load_vps_config(vps_dir))

    if not _preflight_check(ssh):
        raise typer.Exit(1)

    fragments = _load_fragments(vps_dir, service)
    if not fragments:
        console.print("[dim]No enabled container fragments found.[/dim]")
        raise typer.Exit(0)

    collisions = _check_port_collisions(ssh, fragments)
    if collisions:
        for c in collisions:
            console.print(f"[red]✗[/red] Port collision: {c}")
        raise typer.Exit(1)

    has_changes = False
    for name, data, status in fragments:
        if status == "disabled":
            console.print(f"[dim]{name}: disabled (skipped)[/dim]")
            continue
        kind = data.get("kind", "Container")
        svc = _get_service_instance(name, kind)
        actions = svc.plan(ssh, data)
        if actions:
            has_changes = True
            console.print(f"[yellow]{name}[/yellow] (kind: {kind}):")
            for a in actions:
                console.print(f"  [yellow]⟳[/yellow] {a}")
        else:
            console.print(f"[green]✓[/green] {name}: already configured")

    if not has_changes:
        console.print("\n[green]✓ All services configured — no changes needed.[/green]")

    console.print(f"\n[dim]Run 'cstation docker apply {identity_name}' to deploy changes.[/dim]")


@docker_app.command("apply")
def docker_apply(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Deploy a single service"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    prune: bool = typer.Option(False, "--prune", help="Remove undeclared running containers"),
) -> None:
    """Deploy container services declared in fragment files."""
    vps_dir = _resolve_vps_dir(Path(vps))
    vps_data = _load_vps_config(vps_dir)

    identity_name = vps_dir.name
    console.print(f"\n[bold]Docker Apply: {identity_name}[/bold] [dim]({vps_dir}/)[/dim]\n")

    ssh = _ssh_from_config(vps_data)

    if not _preflight_check(ssh):
        raise typer.Exit(1)

    fragments = _load_fragments(vps_dir, service)
    if not fragments:
        console.print("[dim]No enabled container fragments found.[/dim]")
        raise typer.Exit(0)

    collisions = _check_port_collisions(ssh, fragments)
    if collisions:
        for c in collisions:
            console.print(f"[red]✗[/red] Port collision: {c}")
        raise typer.Exit(1)

    enabled_fragments = [(n, d) for n, d, s in fragments if s == "enabled"]
    if not enabled_fragments:
        console.print("[dim]No enabled services to deploy.[/dim]")
        raise typer.Exit(0)

    if not yes:
        console.print("[yellow]⚠[/yellow] This will deploy/modify containers on the remote VPS:")
        for name, data in enabled_fragments:
            kind = data.get("kind", "Container")
            image = data.get("image", "unknown")
            console.print(f"  {name} (kind: {kind}, image: {image})")
        confirm = typer.confirm("\nProceed?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)
        console.print()

    for name, data in enabled_fragments:
        kind = data.get("kind", "Container")
        svc = _get_service_instance(name, kind)
        svc.apply(ssh, data)
        console.print()

    console.print(f"[green]✓[/green] Docker apply complete for [bold]{identity_name}[/bold]")


@docker_app.command("status")
def docker_status(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Show a single service"),
) -> None:
    """Show container service state on the VPS."""
    vps_dir = _resolve_vps_dir(Path(vps))
    vps_data = _load_vps_config(vps_dir)

    ssh = _ssh_from_config(vps_data)

    fragments = _load_fragments(vps_dir, service)

    table = Table(title=f"Docker Services: {vps_dir.name}")
    table.add_column("Service", style="cyan")
    table.add_column("Kind")
    table.add_column("Enabled")
    table.add_column("State")
    table.add_column("Image")

    for name, data, status in fragments:
        kind = data.get("kind", "Container")
        enabled = status
        image = data.get("image", "-")
        if status == "disabled":
            table.add_row(name, kind, enabled, "disabled", image)
            continue
        svc = _get_service_instance(name, kind)
        state = svc.status(ssh, data)
        table.add_row(name, kind, enabled, state.get("state", "unknown"), image)

    console.print(table)


@docker_app.callback()
def docker_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        rprint(ctx.get_help())
        raise typer.Exit(0)


def rprint(help_text):
    console.print(help_text)