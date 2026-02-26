import typer
from rich.console import Console
from ...core.ssh import RemoteHost
from ...core.config import resolve_host

app = typer.Typer(help="Docker container orchestration (traefik, postgres, odoo).")
console = Console()

@app.callback(invoke_without_command=True)
def stack_callback(ctx: typer.Context):
    """Docker container orchestration (traefik, postgres, odoo)."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

@app.command()
def deploy(host_name: str, template: str = typer.Argument(..., help="Template name (e.g. traefik, odoo)")):
    """Deploy pre-configured Docker stacks (traefik, postgres, odoo, etc.)."""
    host_info = resolve_host(host_name)
    console.print(f"[bold blue]Deploying stack:[/bold blue] {template} to {host_info.name}")
    
    remote = RemoteHost(host_info)
    remote.run(f"mkdir -p /opt/cstation/stacks/{template}", sudo=True)
    
    # Placeholder for actual deployment logic
    # remote.run(f"docker compose -f /opt/cstation/stacks/{template}/docker-compose.yml up -d", sudo=True)
    console.print(f"[bold green]✓ Stack {template} deployment initialized on {host_info.name}![/bold green]")

@app.command()
def ps(host_name: str):
    """View running containers on the remote host."""
    host_info = resolve_host(host_name)
    remote = RemoteHost(host_info)
    res = remote.run("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}'", hide=True)
    output = res.stdout if res else "Failed to get container status"
    
    console.print(f"[bold cyan]Active Containers on {host_info.name}[/bold cyan]")
    console.print(output)
