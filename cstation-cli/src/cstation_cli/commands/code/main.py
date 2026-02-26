import typer
import subprocess
from rich.console import Console
from ...core.ssh import RemoteHost
from ...core.config import resolve_host

app = typer.Typer(help="GitHub repository management for both Local and VPS.")
console = Console()

@app.callback(invoke_without_command=True)
def code_callback(ctx: typer.Context):
    """GitHub repository management for both Local and VPS."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

# --- Local Operations ---

@app.command()
def pull():
    """Pull the latest changes from GitHub to the local machine (Current Directory)."""
    console.print("[bold blue]Local:[/bold blue] Pulling latest changes...")
    try:
        result = subprocess.run(["git", "pull"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print(f"[green]✓ Local pull successful:[/green]\n{result.stdout}")
        else:
            console.print(f"[red]✗ Local pull failed:[/red]\n{result.stderr}")
    except FileNotFoundError:
        console.print("[red]✗ Git command not found locally.[/red]")

@app.command()
def push(message: str = typer.Option(None, "--message", "-m", help="Commit message")):
    """Commit all changes and push from local to GitHub."""
    try:
        # Check for changes
        status = subprocess.run(["git", "status", "--short"], capture_output=True, text=True).stdout.strip()
        if not status:
            console.print("[yellow]No local changes to push.[/yellow]")
            return

        console.print("[bold blue]Local:[/bold blue] Adding and pushing changes...")
        subprocess.run(["git", "add", "."], check=True)
        
        commit_msg = message or "Update via cstation-cli"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        
        result = subprocess.run(["git", "push"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("[green]✓ Local push successful![/green]")
        else:
            console.print(f"[red]✗ Local push failed:[/red]\n{result.stderr}")
            
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Git operation failed: {e}[/red]")

# --- VPS (Remote) Operations ---

@app.command(name="vps-auth")
def vps_auth(host_name: str):
    """Generate a deploy key on the VPS and show it."""
    host_info = resolve_host(host_name)
    remote = RemoteHost(host_info)
    remote.run("ssh-keygen -t ed25519 -N '' -f ~/.ssh/github_deploy_key", hide=True)
    res = remote.run("cat ~/.ssh/github_deploy_key.pub", hide=True)
    pub_key = res.stdout.strip() if res else "Failed to retrieve key"
    
    console.print(f"[bold blue]Deploy Key Generated for {host_info.name}[/bold blue]")
    console.print(f"Add this to your GitHub Repository Deploy Keys:")
    console.print(f"\n[bold cyan]{pub_key}[/bold cyan]\n")

@app.command(name="vps-clone")
def vps_clone(host_name: str, repo_url: str, path: str = "/opt/cstation/apps"):
    """Clone a repository from GitHub to the remote VPS."""
    host_info = resolve_host(host_name)
    console.print(f"[bold blue]Cloning repo:[/bold blue] {repo_url} on {host_info.name}")
    remote = RemoteHost(host_info)
    remote.run(f"mkdir -p {path} && cd {path} && git clone {repo_url}", sudo=True)
    console.print(f"[bold green]✓ Repo cloned to {path}![/bold green]")

@app.command(name="vps-update")
def vps_update(host_name: str, path: str):
    """Pull the latest changes from GitHub for an existing repo on the VPS."""
    host_info = resolve_host(host_name)
    console.print(f"[bold blue]Updating repo at:[/bold blue] {path} on {host_info.name}")
    remote = RemoteHost(host_info)
    remote.run(f"cd {path} && git pull origin main", sudo=True)
    console.print(f"[bold green]✓ Code updated on VPS![/bold green]")
