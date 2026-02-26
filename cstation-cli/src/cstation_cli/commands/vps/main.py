import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from ...core.ssh import RemoteHost
from ...core.config import resolve_host

app = typer.Typer(help="VPS management: bootstrap, health, and listing.")
console = Console()

@app.callback(invoke_without_command=True)
def vps_callback(ctx: typer.Context):
    """VPS management: bootstrap, health, and listing."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

@app.command()
def bootstrap(host_name: str = typer.Argument(..., help="Hostname from inventory or IP")):
    """Bootstrap a fresh Ubuntu VPS with Docker and latest patches."""
    host_info = resolve_host(host_name)
    console.print(f"[bold blue]Bootstrapping VPS:[/bold blue] {host_info.name} ({host_info.host})")
    
    remote = RemoteHost(host_info)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        # Task 1: Update system
        progress.add_task(description="Updating system patches...", total=None)
        remote.run("apt-get update && apt-get upgrade -y", sudo=True, hide=True)
        
        # Task 2: Install Docker
        progress.add_task(description="Installing Docker and dependencies...", total=None)
        remote.run("curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh", sudo=True, hide=True)
        remote.run("systemctl enable docker && systemctl start docker", sudo=True, hide=True)

        # Task 3: Setup Firewall
        progress.add_task(description="Configuring UFW (allow SSH, HTTP, HTTPS)...", total=None)
        remote.run("ufw allow ssh && ufw allow 80/tcp && ufw allow 443/tcp && yes | ufw enable", sudo=True, hide=True)

    console.print("[bold green]✓ VPS Bootstrapped successfully![/bold green]")

@app.command()
def info(host_name: str):
    """View system health and resource usage."""
    host_info = resolve_host(host_name)
    remote = RemoteHost(host_info)
    
    uptime_res = remote.run("uptime -p", hide=True)
    uptime = uptime_res.stdout.strip() if uptime_res else "N/A"
    
    mem_res = remote.run("free -h | grep Mem", hide=True)
    mem = mem_res.stdout.strip() if mem_res else "N/A"
    
    console.print(f"[bold cyan]Host Info for {host_info.name}[/bold cyan]")
    console.print(f"Address: {host_info.user}@{host_info.host}:{host_info.port}")
    console.print(f"Groups:  {', '.join(host_info.groups)}")
    console.print(f"Uptime:  {uptime}")
    console.print(f"Memory:  {mem}")
