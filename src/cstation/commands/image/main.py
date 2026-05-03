from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from cstation.models import DockerImageConfig
from cstation.config import get_config

console = Console()

IMAGES_DIR = Path("config/images")


def _discover_images(name_filter: Optional[str] = None) -> list[tuple[DockerImageConfig, Path]]:
    if not IMAGES_DIR.exists():
        return []
    images = []
    for image_yaml in sorted(IMAGES_DIR.glob("*/image.yaml")):
        with image_yaml.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict) or data.get("kind") != "DockerImage":
            continue
        try:
            config = DockerImageConfig(**data)
        except Exception as e:
            console.print(f"[red]✗[/red] Invalid {image_yaml}: {e}")
            continue
        if name_filter and config.name != name_filter:
            continue
        images.append((config, image_yaml))
    return images


def _get_docker_hub_creds() -> tuple[Optional[str], Optional[str]]:
    cfg = get_config().config_data
    hub = cfg.get("docker_hub", {})
    return hub.get("username"), hub.get("token") or hub.get("password")


def _detect_runtime() -> str:
    if shutil.which("docker"):
        return "docker"
    if shutil.which("podman"):
        return "podman"
    return ""


def _podman_login() -> bool:
    username, token = _get_docker_hub_creds()
    if not username or not token:
        console.print("[yellow]⚠[/yellow] No docker_hub credentials in config.yaml — relying on existing login")
        return True
    result = subprocess.run(
        ["podman", "login", "-u", username, "--password-stdin", "docker.io"],
        input=token.encode(),
    )
    if result.returncode != 0:
        console.print("[red]✗[/red] podman login failed")
        return False
    console.print(f"[green]✓[/green] Logged in to Docker Hub as {username}")
    return True


def _docker_login() -> bool:
    username, token = _get_docker_hub_creds()
    if not username or not token:
        console.print("[yellow]⚠[/yellow] No docker_hub credentials in config.yaml — relying on existing login")
        return True
    result = subprocess.run(
        ["docker", "login", "-u", username, "--password-stdin"],
        input=token.encode(),
    )
    if result.returncode != 0:
        console.print("[red]✗[/red] docker login failed")
        return False
    console.print(f"[green]✓[/green] Logged in to Docker Hub as {username}")
    return True


image_app = typer.Typer(
    name="image",
    help="Docker image build management",
    invoke_without_command=True,
)


@image_app.command("list")
def image_list() -> None:
    """List declared Docker images."""
    images = _discover_images()
    if not images:
        console.print("[dim]No Docker image definitions found in config/images/[/dim]")
        raise typer.Exit(0)

    table = Table(title="Docker Images")
    table.add_column("Name", style="cyan")
    table.add_column("Image")
    table.add_column("Directory")
    table.add_column("Platforms")
    for config, path in images:
        table.add_row(
            config.name,
            config.image,
            str(path.parent),
            ", ".join(config.platforms),
        )
    console.print(table)


@image_app.command("build")
def image_build(
    name: str = typer.Argument(..., help="Image name (e.g. synercatalyst-odoo.13.0)"),
    tag: str = typer.Option("latest", "--tag", "-t", help="Image tag"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Override platforms (e.g. linux/arm64)"),
    push: bool = typer.Option(True, "--push/--no-push", help="Push after build"),
    runtime: Optional[str] = typer.Option(None, "--runtime", help="Container runtime: docker or podman (auto-detected)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show command without executing"),
) -> None:
    """Build a Docker image from its declarative definition.

    Uses podman by default on macOS (auto-detected). Falls back to docker.
    Multi-arch builds use 'podman build --manifest' for local multi-platform support.
    """
    images = _discover_images(name)
    if not images:
        console.print(f"[red]✗[/red] No image definition found for '{name}' in config/images/")
        raise typer.Exit(1)

    config, image_yaml = images[0]
    build_dir = image_yaml.parent
    dockerfile_path = build_dir / "Dockerfile"

    if not dockerfile_path.exists():
        console.print(f"[red]✗[/red] Dockerfile not found: {dockerfile_path}")
        raise typer.Exit(1)

    if runtime is None:
        runtime = _detect_runtime()
    if not runtime:
        console.print("[red]✗[/red] Neither docker nor podman found. Install one to continue.")
        raise typer.Exit(1)

    platforms = [platform] if platform else config.platforms
    full_tag = f"{config.image}:{tag}"

    build_args_list = []
    for k, v in config.build_args.items():
        build_args_list.extend(["--build-arg", f"{k}={v}"])

    if dry_run:
        cmd_str = _build_cmd_str(runtime, build_dir, platforms, build_args_list, full_tag, push)
        console.print(f"[bold]Would build ({runtime}):[/bold] {full_tag}")
        console.print(f"  Platforms: {', '.join(platforms)}")
        console.print(f"  Context: {build_dir}")
        console.print(f"  Push: {push}")
        console.print(f"  Command: {cmd_str}")
        return

    if runtime == "podman":
        _build_podman(config, build_dir, platforms, build_args_list, full_tag, push)
    else:
        _build_docker(config, build_dir, platforms, build_args_list, full_tag, push)


def _build_cmd_str(runtime, build_dir, platforms, build_args_list, full_tag, push) -> str:
    if runtime == "podman":
        if len(platforms) > 1:
            manifest_name = full_tag.replace(":", "-manifest-")
            parts = [f"podman manifest create {manifest_name}"]
            for plat in platforms:
                plat_tag = full_tag.replace("/", "-").replace(":", f"-{plat.split('/')[1]}-")
                parts.append(f"podman build --platform {plat} {' '.join(build_args_list)} -t {plat_tag} {build_dir}")
                parts.append(f"podman manifest add {manifest_name} docker-archive:{plat_tag}")
            if push:
                parts.append(f"podman manifest push {manifest_name} docker.io/{full_tag}")
                parts.append(f"podman manifest rm {manifest_name}")
            return " && \\\n  ".join(parts)
        elif push:
            return f"podman build --platform {platforms[0]} {' '.join(build_args_list)} -t {full_tag} {build_dir} && podman push {full_tag} docker.io/{full_tag}"
        else:
            return f"podman build --platform {platforms[0]} {' '.join(build_args_list)} -t {full_tag} {build_dir}"
    else:
        if len(platforms) > 1:
            return f"docker buildx build --platform {','.join(platforms)} {' '.join(build_args_list)} -t {full_tag} {'--push' if push else '--load'} {build_dir}"
        elif push:
            return f"docker buildx build --platform {platforms[0]} {' '.join(build_args_list)} -t {full_tag} --push {build_dir}"
        else:
            return f"docker build --platform {platforms[0]} {' '.join(build_args_list)} -t {full_tag} {build_dir}"


def _build_podman(config, build_dir, platforms, build_args_list, full_tag, push):
    if push and not _podman_login():
        raise typer.Exit(1)

    if len(platforms) > 1:
        _build_podman_multiarch(build_dir, platforms, build_args_list, full_tag, push)
    else:
        cmd = ["podman", "build", "--platform", platforms[0]]
        cmd.extend(build_args_list)
        cmd.extend(["-t", full_tag, str(build_dir)])

        console.print(f"[bold]Building[/bold] {full_tag} ({platforms[0]}) with podman")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            console.print(f"[red]✗[/red] Build failed with exit code {result.returncode}")
            raise typer.Exit(1)

        if push:
            console.print(f"[bold]Pushing[/bold] {full_tag} to docker.io")
            result = subprocess.run(["podman", "push", full_tag, f"docker.io/{full_tag}"])
            if result.returncode != 0:
                console.print(f"[red]✗[/red] Push failed")
                raise typer.Exit(1)

    console.print(f"[green]✓[/green] Built{(' and pushed') if push else ''} {full_tag}")


def _build_podman_multiarch(build_dir, platforms, build_args_list, full_tag, push):
    manifest_name = full_tag.replace(":", "-manifest-")

    subprocess.run(["podman", "manifest", "rm", manifest_name], capture_output=True)

    console.print(f"[bold]Creating manifest[/bold] {manifest_name}")
    result = subprocess.run(["podman", "manifest", "create", manifest_name])
    if result.returncode != 0:
        console.print("[red]✗[/red] Failed to create manifest")
        raise typer.Exit(1)

    built_images = []
    for plat in platforms:
        plat_suffix = plat.replace("/", "-")
        plat_tag = f"{full_tag}-{plat_suffix}"

        cmd = ["podman", "build", "--platform", plat]
        cmd.extend(build_args_list)
        cmd.extend(["-t", plat_tag, str(build_dir)])

        console.print(f"[bold]Building[/bold] {full_tag} ({plat}) with podman")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            console.print(f"[red]✗[/red] Build failed for {plat}")
            subprocess.run(["podman", "manifest", "rm", manifest_name], capture_output=True)
            for img in built_images:
                subprocess.run(["podman", "rmi", img], capture_output=True)
            raise typer.Exit(1)

        result = subprocess.run(
            ["podman", "manifest", "add", manifest_name, f"docker-archive:{plat_tag}"],
            capture_output=True,
        )
        if result.returncode != 0:
            result2 = subprocess.run(
                ["podman", "manifest", "add", manifest_name, plat_tag],
                capture_output=True,
            )
        built_images.append(plat_tag)

    if push:
        console.print(f"[bold]Pushing manifest[/bold] {full_tag} (multi-arch)")
        result = subprocess.run(["podman", "manifest", "push", "--all", manifest_name, f"docker.io/{full_tag}"])
        if result.returncode != 0:
            console.print("[red]✗[/red] Manifest push failed")
            raise typer.Exit(1)

    subprocess.run(["podman", "manifest", "rm", manifest_name], capture_output=True)
    for img in built_images:
        subprocess.run(["podman", "rmi", img], capture_output=True)


def _build_docker(config, build_dir, platforms, build_args_list, full_tag, push):
    if push and not _docker_login():
        raise typer.Exit(1)

    if len(platforms) > 1:
        cmd = ["docker", "buildx", "build",
               "--platform", ",".join(platforms)]
        cmd.extend(build_args_list)
        cmd.extend(["-t", full_tag])
        cmd.append("--push" if push else "--load")
        cmd.append(str(build_dir))
    elif push:
        cmd = ["docker", "buildx", "build",
               "--platform", platforms[0]]
        cmd.extend(build_args_list)
        cmd.extend(["-t", full_tag, "--push", str(build_dir)])
    else:
        cmd = ["docker", "build",
               "--platform", platforms[0]]
        cmd.extend(build_args_list)
        cmd.extend(["-t", full_tag, str(build_dir)])

    console.print(f"[bold]Building[/bold] {full_tag} ({', '.join(platforms)}) with docker")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        console.print(f"[red]✗[/red] Build failed with exit code {result.returncode}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Built{(' and pushed') if push else ''} {full_tag}")


@image_app.callback()
def image_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        from rich import print as rprint
        rprint(ctx.get_help())
        raise typer.Exit(0)