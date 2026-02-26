import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from ...core.config import Config, Host, get_config_path

app = typer.Typer(help="CLI configuration and inventory management.")
console = Console()

@app.callback(invoke_without_command=True)
def config_callback(ctx: typer.Context):
    """CLI configuration and inventory management."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

@app.command()
def init():
    """Initialize local CLI config folder and inventory file."""
    path = get_config_path()
    if path.exists() and not Confirm.ask(f"Config already exists at {path}. Overwrite?"):
        return
    
    config = Config()
    config.save(path)
    console.print(f"[bold green]✓ Initialized config at {path}[/bold green]")

@app.command()
def add_vps():
    """Wizard to add a new VPS to your inventory."""
    name = Prompt.ask("Give your VPS a name (e.g. prod-vps)")
    host_ip = Prompt.ask("Enter the IP or Hostname")
    user = Prompt.ask("Enter the SSH user", default="root")
    port = int(Prompt.ask("Enter the SSH port", default="22"))
    groups_str = Prompt.ask("Enter groups (comma-separated)", default="default")
    groups = [g.strip() for g in groups_str.split(",") if g.strip()]

    path = get_config_path()
    config = Config.load(path)
    
    # Check if host already exists
    if any(h.name == name for h in config.inventory.hosts):
        if not Confirm.ask(f"Host '{name}' already exists. Update it?"):
            return
        config.inventory.hosts = [h for h in config.inventory.hosts if h.name != name]

    config.inventory.hosts.append(Host(name=name, host=host_ip, user=user, port=port, groups=groups))
    config.save(path)

    console.print(f"[bold green]✓ VPS '{name}' added to groups: {', '.join(groups)}[/bold green]")

@app.command()
def show():
    """Display the current configuration and managed hosts organized by group."""
    path = get_config_path()
    config = Config.load(path)
    
    if not config.inventory.hosts:
        console.print("[yellow]Inventory is empty.[/yellow]")
        return

    groups = config.inventory.get_all_groups()
    
    for group in groups:
        table = Table(title=f"Group: [bold magenta]{group}[/bold magenta]", header_style="bold blue")
        table.add_column("Name", style="cyan")
        table.add_column("Connection", style="green")
        table.add_column("Port", style="yellow")
        
        hosts = config.inventory.get_hosts_by_group(group)
        for h in hosts:
            table.add_row(h.name, f"{h.user}@{h.host}", str(h.port))
        
        console.print(table)
        console.print()
