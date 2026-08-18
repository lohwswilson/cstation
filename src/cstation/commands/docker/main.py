from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from cstation.ssh import SSHManager
from cstation.config import get_vps_secrets
from cstation.models import VPSConfig, ContainerConfig
from cstation.output import OutputFormat, print_formatted
from cstation.commands.vps.main import _resolve_vps_dir, _load_vps_config, _ssh_from_config
from .services.registry import get_service, available_services
from .services.image_service import ImageService
from .services import TraefikService, PortainerService  # noqa: F401 — auto-register

console = Console()

class _CStationYamlDumper(yaml.SafeDumper):
    pass


def _yaml_represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.nodes.ScalarNode:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_CStationYamlDumper.add_representer(str, _yaml_represent_str)


docker_app = typer.Typer(
    name="docker",
    help="Docker container service management",
    invoke_without_command=True,
)


def _discover_fragments(vps_dir: Path) -> list[Path]:
    return sorted(p for p in vps_dir.glob("*.yaml") if p.name != "vps.yaml")


def _load_fragments(vps_dir: Path, container_filter: Optional[str] = None) -> list[tuple[str, ContainerConfig, str]]:
    from pydantic import ValidationError
    fragments = []
    for frag_path in _discover_fragments(vps_dir):
        with frag_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            continue
        kind = data.get("kind", "")
        if kind not in ("Container", "Stack"):
            continue
        
        try:
            config = ContainerConfig(**data)
            name = config.name
            if container_filter and name != container_filter:
                continue
            
            status = "enabled" if config.enabled else "disabled"
            fragments.append((name, config, status))
        except ValidationError as e:
            console.print(f"[red]✗[/red] Schema validation failed for {frag_path}:")
            for error in e.errors():
                loc = ".".join(str(l) for l in error["loc"])
                msg = error["msg"]
                console.print(f"  - [bold]{loc}[/bold]: {msg}")
            # Skip invalid fragments instead of crashing
            continue
            
    return fragments


def _preflight_check(ssh: SSHManager, vps_data: VPSConfig) -> bool:
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
    
    required_network = vps_data.docker.networks[0] if vps_data.docker.networks else "PW_NET"
    if required_network not in networks:
        console.print(f"[red]✗[/red] Docker network {required_network} does not exist on the VPS.")
        console.print("[dim]Run 'cstation vps apply <vps>' first.[/dim]")
        return False
    return True


def _check_port_collisions(ssh: SSHManager, fragments: list[tuple[str, ContainerConfig, str]]) -> list[str]:
    declared_ports: dict[str, str] = {}
    for name, config, status in fragments:
        if status == "disabled":
            continue
        for port_spec in config.ports:
            parts = port_spec.split(":")
            host_port = parts[-2] if len(parts) >= 2 else parts[0]
            if host_port in declared_ports:
                return [f"Port {host_port} declared by both {declared_ports[host_port]} and {name}"]
            declared_ports[host_port] = name
    return []


def _get_service_instance(name: str, kind: str, config: ContainerConfig | dict | None = None):
    if isinstance(config, dict):
        from .services.image_service import _ensure_config
        config = _ensure_config(config)

    try:
        svc_cls = get_service(name)
        return svc_cls()
    except ValueError:
        pass

    if config and config.image:
        image_lower = config.image.lower()
        for svc_name in available_services():
            if svc_name in image_lower:
                try:
                    svc_cls = get_service(svc_name)
                    svc = svc_cls()
                    svc.name = name
                    svc.kind = kind
                    return svc
                except ValueError:
                    pass

    if config and config.odoo_conf:
        from .services.odoo import OdooService
        svc = OdooService()
    else:
        from .services.image_service import ImageService
        svc = ImageService()

    svc.name = name
    svc.kind = kind
    return svc


def _resolve_secrets(vps_name: str, fragments: list[tuple[str, ContainerConfig, str]]) -> list[tuple[str, ContainerConfig, str]]:
    resolved_fragments = []
    for name, config, status in fragments:
        if status == "enabled" and config.secrets:
            secrets = get_vps_secrets(vps_name, name)
            if secrets:
                # Store resolved secrets for the apply/plan phase
                # We use a custom attribute that won't interfere with Pydantic validation
                setattr(config, "_resolved_secrets", secrets)
        resolved_fragments.append((name, config, status))
    return resolved_fragments


@docker_app.command("plan")
def docker_plan(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    container: Optional[str] = typer.Option(None, "--container", "-c", "--service", "-s", help="Plan a single container"),
) -> None:
    """Dry-run: show what would change for container services."""
    vps_dir = _resolve_vps_dir(Path(vps))
    vps_data = _load_vps_config(vps_dir)

    identity_name = vps_dir.name
    console.print(f"\n[bold]Docker Plan: {identity_name}[/bold] [dim]({vps_dir}/)[/dim]\n")

    ssh = _ssh_from_config(vps_data)

    if not _preflight_check(ssh, vps_data):
        raise typer.Exit(1)

    fragments = _load_fragments(vps_dir, container)
    fragments = _resolve_secrets(identity_name, fragments)
    if not fragments:
        console.print("[dim]No enabled container fragments found.[/dim]")
        raise typer.Exit(0)

    collisions = _check_port_collisions(ssh, fragments)
    if collisions:
        for c in collisions:
            console.print(f"[red]✗[/red] Port collision: {c}")
        raise typer.Exit(1)

    for name, data, status in fragments:
        if status == "enabled" and 'traefik' in name.lower():
            svc = _get_service_instance(name, data.kind, data)
            if hasattr(svc, '_resolve_and_cache_traefik_conf_dir'):
                svc._resolve_and_cache_traefik_conf_dir(data)
            break

    has_changes = False
    for name, data, status in fragments:
        if status == "disabled":
            console.print(f"[dim]{name}: disabled (skipped)[/dim]")
            continue
        kind = data.kind
        svc = _get_service_instance(name, kind, data)
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

    ImageService.reset_traefik_conf_dir()
    console.print(f"\n[dim]Run 'cstation docker apply {identity_name}' to deploy changes.[/dim]")


@docker_app.command("apply")
def docker_apply(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    container: Optional[str] = typer.Option(None, "--container", "-c", "--service", "-s", help="Deploy a single container"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    prune: bool = typer.Option(False, "--prune", help="Remove undeclared running containers"),
) -> None:
    """Deploy container services declared in fragment files."""
    vps_dir = _resolve_vps_dir(Path(vps))
    vps_data = _load_vps_config(vps_dir)

    identity_name = vps_data.identity.name
    console.print(f"\n[bold]Docker Apply: {identity_name}[/bold] [dim]({vps_dir}/)[/dim]\n")

    ssh = _ssh_from_config(vps_data)

    if not _preflight_check(ssh, vps_data):
        raise typer.Exit(1)

    fragments = _load_fragments(vps_dir, container)
    fragments = _resolve_secrets(identity_name, fragments)
    if not fragments:
        console.print("[dim]No enabled container fragments found.[/dim]")
        raise typer.Exit(0)

    collisions = _check_port_collisions(ssh, fragments)
    if collisions:
        for c in collisions:
            console.print(f"[red]✗[/red] Port collision: {c}")
        raise typer.Exit(1)

    for name, data, status in fragments:
        if status == "enabled" and 'traefik' in name.lower():
            svc = _get_service_instance(name, data.kind, data)
            if hasattr(svc, '_resolve_and_cache_traefik_conf_dir'):
                svc._resolve_and_cache_traefik_conf_dir(data)
            break

    enabled_fragments = [(n, d) for n, d, s in fragments if s == "enabled"]
    if not enabled_fragments:
        console.print("[dim]No enabled services to deploy.[/dim]")
        raise typer.Exit(0)

    if not yes:
        console.print("[yellow]⚠[/yellow] This will deploy/modify containers on the remote VPS:")
        for name, data in enabled_fragments:
            kind = data.kind
            image = data.image
            console.print(f"  {name} (kind: {kind}, image: {image})")
        confirm = typer.confirm("\nProceed?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)
        console.print()

    for name, data in enabled_fragments:
        kind = data.kind
        svc = _get_service_instance(name, kind, data)
        svc.apply(ssh, data)
        console.print()

    ImageService.reset_traefik_conf_dir()
    console.print(f"[green]✓[/green] Docker apply complete for [bold]{identity_name}[/bold]")


@docker_app.command("status")
def docker_status(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    container: Optional[str] = typer.Option(None, "--container", "-c", "--service", "-s", help="Show a single container"),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format: table, json, or yaml",
    ),
) -> None:
    """Show container service state on the VPS."""
    vps_dir = _resolve_vps_dir(Path(vps))
    vps_data = _load_vps_config(vps_dir)

    ssh = _ssh_from_config(vps_data)
    fragments = _load_fragments(vps_dir, container)

    services_data = []
    for name, data, status in fragments:
        kind = data.kind
        enabled = status
        image = data.image
        if status == "disabled":
            state_val = "disabled"
        else:
            svc = _get_service_instance(name, kind, data)
            state_res = svc.status(ssh, data)
            state_val = state_res.get("state", "unknown") if isinstance(state_res, dict) else str(state_res)
        
        services_data.append({
            "service": name,
            "kind": kind,
            "enabled": enabled,
            "state": state_val,
            "image": image,
        })

    def render_docker_table():
        table = Table(title=f"Docker Services: {vps_data.identity.name}")
        table.add_column("Service", style="cyan")
        table.add_column("Kind")
        table.add_column("Enabled")
        table.add_column("State")
        table.add_column("Image")
        for s in services_data:
            table.add_row(s["service"], s["kind"], str(s["enabled"]), s["state"], s["image"] or "")
        console.print(table)

    print_formatted(services_data, format_type=output, table_renderer=render_docker_table)


def _import_single_container(
    container: str,
    vps_dir: Path,
    ssh: SSHManager,
    name: Optional[str] = None,
    force: bool = False,
) -> bool:
    import json as jsonlib
    result = ssh.run(f"docker inspect {container}", hide=True, sudo=True)
    if not result or not result.stdout.strip():
        console.print(f"[red]✗[/red] Could not find container '{container}'")
        return False

    try:
        inspect_data = jsonlib.loads(result.stdout)[0]
    except (jsonlib.JSONDecodeError, IndexError, KeyError):
        console.print(f"[red]✗[/red] Failed to parse docker inspect output for '{container}'")
        return False

    c_name = inspect_data.get("Name", "").lstrip("/")
    short_name = name or c_name

    config = inspect_data.get("Config", {})
    host_config = inspect_data.get("HostConfig", {})

    ports = []
    port_bindings = host_config.get("PortBindings", {}) or {}
    for c_port_proto, host_bindings in port_bindings.items():
        if host_bindings:
            host_port = host_bindings[0].get("HostPort")
            c_port = c_port_proto.split("/")[0]
            ports.append(f"{host_port}:{c_port}")

    volumes = []
    mounts = inspect_data.get("Mounts", [])
    for m in mounts:
        src = m.get("Source")
        dst = m.get("Destination")
        if src and dst:
            volumes.append(f"{src}:{dst}")

    env = {}
    env_list = config.get("Env", [])
    for e in env_list:
        if "=" in e:
            k, v = e.split("=", 1)
            if k not in ("PATH", "HOME", "HOSTNAME", "PWD"):
                env[k] = v

    networks = inspect_data.get("NetworkSettings", {}).get("Networks", {})
    network = list(networks.keys())[0] if networks else "PW_NET"

    payload = {
        "apiVersion": "cstation/v1",
        "kind": "Container",
        "name": short_name,
        "enabled": True,
        "image": config.get("Image"),
        "container_name": c_name,
        "network": network,
    }
    if ports:
        payload["ports"] = ports
    if volumes:
        payload["volumes"] = volumes
    if env:
        payload["env"] = env
    if host_config.get("RestartPolicy", {}).get("Name"):
        payload["restart_policy"] = host_config["RestartPolicy"]["Name"]

    out_path = vps_dir / f"{short_name}.yaml"
    if out_path.exists() and not force:
        console.print(f"[yellow]⚠[/yellow] Fragment file already exists: {out_path.name} (use --force to overwrite)")
        return False

    with out_path.open("w", encoding="utf-8") as f:
        yaml.dump(payload, f, sort_keys=False, Dumper=_CStationYamlDumper)

    console.print(f"[green]✓[/green] Imported [bold]{c_name}[/bold] as [bold]{out_path}[/bold]")
    return True


@docker_app.command("import")
def docker_import(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    container: Optional[str] = typer.Argument(None, help="Container name or ID to import"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Name for the generated fragment file"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing fragment file"),
    all: bool = typer.Option(False, "--all", help="Import all running containers"),
) -> None:
    """Import a running container from the VPS as a declarative fragment."""
    vps_dir = _resolve_vps_dir(Path(vps))
    vps_data = _load_vps_config(vps_dir)
    ssh = _ssh_from_config(vps_data)

    if not container:
        result = ssh.run("docker ps --format '{{.Names}}\t{{.Image}}\t{{.ID}}'", hide=True, sudo=True)
        if not result or not result.stdout.strip():
            console.print("[yellow]⚠[/yellow] No running containers found on the VPS.")
            return

        if all:
            console.print("[bold]Importing all containers...[/bold]\n")
            container_names = [line.split("\t")[0] for line in result.stdout.strip().splitlines()]
            imported = []
            skipped = []
            for c in container_names:
                ok = _import_single_container(c, vps_dir, ssh, name=None, force=force)
                if ok:
                    imported.append(c)
                else:
                    skipped.append(c)
            console.print(f"\n[green]✓[/green] Imported [bold]{len(imported)}[/bold] container(s)")
            if skipped:
                console.print(f"[yellow]⚠[/yellow] Skipped [bold]{len(skipped)}[/bold] (use --force to overwrite): {', '.join(skipped)}")
            return

        console.print("\n[bold]Running Containers:[/bold]")
        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("Image")
        table.add_column("ID")
        for line in result.stdout.strip().splitlines():
            table.add_row(*line.split("\t"))
        console.print(table)
        console.print("\n[dim]Run 'cstation docker import <vps> <container_name>' to import one.[/dim]")
        console.print("[dim]Use --all to import all containers at once.[/dim]")
        return

    ok = _import_single_container(container, vps_dir, ssh, name=name, force=force)
    if not ok:
        raise typer.Exit(1)
    console.print("[dim]Review the file to move any sensitive environment variables to 'secrets'.[/dim]")


@docker_app.callback()
def docker_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        rprint(ctx.get_help())
        raise typer.Exit(0)


def rprint(help_text):
    console.print(help_text)
def _remove_container_secrets(vps_name: str, container_name: str) -> bool:
    config_path = Path.home() / ".config" / "cstation" / "config.yaml"
    if not config_path.exists():
        return False
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return False
    vps_secrets = data.get("vps", {}).get("secrets", {}).get(vps_name, {})
    if container_name not in vps_secrets:
        return False
    del vps_secrets[container_name]
    if not vps_secrets:
        data.get("vps", {}).get("secrets", {}).pop(vps_name, None)
    try:
        with config_path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception:
        return False


def _find_container_yaml(vps_dir: Path, container: str) -> Optional[Path]:
    # Exact filename match
    exact = vps_dir / f"{container}.yaml"
    if exact.exists():
        return exact
    exact_disabled = vps_dir / f"{container}.yaml.disabled"
    if exact_disabled.exists():
        return exact_disabled

    # Search by metadata name inside files
    for p in vps_dir.glob("*.yaml*"):
        if p.name == "vps.yaml":
            continue
        try:
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            c_name = raw.get("name") or raw.get("container_name") or p.stem
            if c_name == container or p.stem == container or p.stem.replace(".yaml", "") == container:
                return p
        except Exception:
            continue
    return None


@docker_app.command("rm")
@docker_app.command("remove", hidden=True)
def docker_remove(
    vps: str = typer.Argument(..., help="VPS name or directory path"),
    container: str = typer.Argument(..., help="Container service name to remove"),
    volumes: bool = typer.Option(False, "--volumes", "-v", help="Also remove named volumes associated with the container stack"),
    purge_local: bool = typer.Option(True, "--purge-local/--keep-local", help="Delete local YAML configuration file"),
    archive_local: bool = typer.Option(False, "--archive", help="Rename local YAML to .disabled instead of deleting"),
    clean_secrets: bool = typer.Option(True, "--clean-secrets/--keep-secrets", help="Purge container secrets from config.yaml"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show actions without executing"),
) -> None:
    """
    Stop and remove a container service on the remote VPS, and clean up local configs.
    """
    vps_dir = _resolve_vps_dir(Path(vps))
    vps_data = _load_vps_config(vps_dir)
    identity_name = vps_data.identity.name or vps_dir.name

    console.print(f"\n[bold]Docker Remove: {container} on {identity_name}[/bold]\n")

    yaml_file = _find_container_yaml(vps_dir, container)
    config_obj: Optional[ContainerConfig] = None
    kind = "generic"

    if yaml_file and yaml_file.exists():
        try:
            raw_data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            config_obj = ContainerConfig.model_validate(raw_data)
            kind = config_obj.kind or "generic"
        except Exception:
            pass

    if dry_run:
        console.print("[bold yellow]Dry-run mode — actions that would be performed:[/bold yellow]")
        console.print(f"  • Connect via SSH to {identity_name} ({vps_data.access.host}:{vps_data.access.port})")
        console.print(f"  • Stop and remove container service '{container}' (volumes purge: {volumes})")
        if yaml_file:
            if archive_local:
                console.print(f"  • Archive local file '{yaml_file.name}' to '{yaml_file.stem}.yaml.disabled'")
            elif purge_local:
                console.print(f"  • Delete local file '{yaml_file.name}'")
        if clean_secrets:
            console.print(f"  • Remove secrets for '{container}' from ~/.config/cstation/config.yaml")
        return

    if not yes:
        console.print(f"[yellow]⚠[/yellow] This will stop and remove container [bold]{container}[/bold] on remote VPS [bold]{identity_name}[/bold].")
        if volumes:
            console.print("  [bold red]WARNING: Remote volumes and data will also be purged (-v)![/bold red]")
        if yaml_file and purge_local:
            if archive_local:
                console.print(f"  Local config will be archived to: [dim]{yaml_file.stem}.yaml.disabled[/dim]")
            else:
                console.print(f"  Local config will be deleted: [dim]{yaml_file}[/dim]")
        
        confirm = typer.confirm("\nProceed with removal?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)
        console.print()

    # 1. Remote Teardown
    try:
        ssh = _ssh_from_config(vps_data)
        if config_obj is None:
            # Fallback ContainerConfig if yaml was already gone
            config_obj = ContainerConfig(name=container, kind=kind)

        svc = _get_service_instance(container, kind, config_obj)
        svc.remove(ssh, config_obj, purge=volumes)
    except Exception as e:
        console.print(f"[red]✗[/red] Remote removal encountered an error: {e}")
        if not typer.confirm("Continue with local cleanup anyway?", default=True):
            raise typer.Exit(1)

    # 2. Local YAML Cleanup
    if yaml_file and yaml_file.exists() and purge_local:
        try:
            if archive_local:
                new_path = yaml_file.parent / f"{yaml_file.stem}.yaml.disabled"
                yaml_file.rename(new_path)
                console.print(f"  [green]✓[/green] Archived local file to {new_path.name}")
            else:
                yaml_file.unlink()
                console.print(f"  [green]✓[/green] Deleted local file {yaml_file.name}")
        except Exception as e:
            console.print(f"  [yellow]![/yellow] Could not clean up {yaml_file}: {e}")

    # 3. Clean up Secrets
    if clean_secrets:
        if _remove_container_secrets(identity_name, container):
            console.print(f"  [green]✓[/green] Removed secrets for {container} from config.yaml")

    console.print(f"\n[bold green]✓ Container '{container}' successfully removed from {identity_name}.[/bold green]")
