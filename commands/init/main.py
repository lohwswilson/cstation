import os
import shutil
import stat
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

console = Console()

def init_command(
    force: bool = typer.Option(False, "--force", "-f", help="Force initialization even if /etc/cstation exists"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Create backup of existing /etc/cstation directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without executing"),
    developer: bool = typer.Option(False, "--developer", help="Set permissions to allow regular users to edit configuration files")
):
    """
    Initialize CStation configuration directory at /etc/cstation.
    
    This command sets up the system-wide configuration directory by:
    - Creating /etc/cstation directory structure
    - Copying configuration files from the package
    - Setting proper permissions (root ownership by default, developer-friendly with --developer)
    - Creating backups if requested
    """
    
    # Check if running as root
    if os.geteuid() != 0 and not dry_run:
        console.print("[red]Error: This command must be run as root (use sudo)[/red]")
        console.print("Example: [cyan]sudo cstation init[/cyan]")
        raise typer.Exit(1)
    
    target_dir = Path("/etc/cstation")
    source_dir = Path(__file__).parent.parent.parent / "etc"
    
    # Check if source directory exists
    if not source_dir.exists():
        console.print(f"[red]Error: Source configuration directory not found: {source_dir}[/red]")
        console.print("Make sure CStation is properly installed.")
        raise typer.Exit(1)
    
    # Check if target already exists
    if target_dir.exists() and not force:
        if not dry_run:
            console.print(f"[yellow]Warning: {target_dir} already exists[/yellow]")
            if not Confirm.ask("Do you want to continue? This will overwrite existing files."):
                console.print("[blue]Initialization cancelled[/blue]")
                raise typer.Exit(0)
    
    console.print(Panel.fit(
        "[bold blue]CStation Initialization[/bold blue]\n"
        f"Source: [cyan]{source_dir}[/cyan]\n"
        f"Target: [cyan]{target_dir}[/cyan]",
        border_style="blue"
    ))
    
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            # Step 1: Create backup if requested
            if backup and target_dir.exists() and not dry_run:
                backup_task = progress.add_task("Creating backup...", total=None)
                backup_dir = Path(f"/etc/cstation.backup.{int(__import__('time').time())}")
                if not dry_run:
                    shutil.copytree(target_dir, backup_dir)
                console.print(f"[green]✓[/green] Backup created: {backup_dir}")
                progress.remove_task(backup_task)
            
            # Step 2: Create target directory
            create_task = progress.add_task("Creating directory structure...", total=None)
            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]✓[/green] Created directory: {target_dir}")
            progress.remove_task(create_task)
            
            # Step 3: Copy files
            copy_task = progress.add_task("Copying configuration files...", total=None)
            
            def copy_with_permissions(src: Path, dst: Path):
                """Copy files and set appropriate permissions"""
                if src.is_dir():
                    dst.mkdir(exist_ok=True)
                    if not dry_run:
                        if developer:
                            # Set group ownership and permissions for user access
                            os.chown(dst, 0, 0)  # root:root (keep root ownership for security)
                            os.chmod(dst, 0o755)  # rwxr-xr-x (allow read/execute for all)
                        else:
                            os.chown(dst, 0, 0)  # root:root
                            os.chmod(dst, 0o755)  # rwxr-xr-x
                    
                    for item in src.iterdir():
                        copy_with_permissions(item, dst / item.name)
                else:
                    if not dry_run:
                        shutil.copy2(src, dst)
                        
                        if developer:
                            # Set more permissive permissions for user editing
                            os.chown(dst, 0, 0)  # root:root (keep root ownership)
                            if dst.suffix in ['.yml', '.yaml', '.cfg', '.conf']:
                                os.chmod(dst, 0o666)  # rw-rw-rw- (allow all users to edit)
                            elif dst.suffix in ['.sh']:
                                os.chmod(dst, 0o755)  # rwxr-xr-x (executable)
                            else:
                                os.chmod(dst, 0o666)  # rw-rw-rw-
                        else:
                            # Default restrictive permissions
                            os.chown(dst, 0, 0)  # root:root
                            if dst.suffix in ['.yml', '.yaml', '.cfg', '.conf']:
                                os.chmod(dst, 0o644)  # rw-r--r--
                            elif dst.suffix in ['.sh']:
                                os.chmod(dst, 0o755)  # rwxr-xr-x
                            else:
                                os.chmod(dst, 0o644)  # rw-r--r--
            
            if not dry_run:
                copy_with_permissions(source_dir, target_dir)
            
            # Show what would be copied in dry run
            if dry_run:
                console.print("[yellow]Files that would be copied:[/yellow]")
                for root, dirs, files in os.walk(source_dir):
                    level = root.replace(str(source_dir), '').count(os.sep)
                    indent = ' ' * 2 * level
                    rel_path = Path(root).relative_to(source_dir)
                    target_path = target_dir / rel_path
                    console.print(f"{indent}📁 {target_path}/")
                    
                    subindent = ' ' * 2 * (level + 1)
                    for file in files:
                        file_target = target_path / file
                        console.print(f"{subindent}📄 {file_target}")
            
            console.print(f"[green]✓[/green] Configuration files copied")
            progress.remove_task(copy_task)
            
            # Step 4: Update ansible.cfg with absolute paths
            ansible_cfg_task = progress.add_task("Updating Ansible configuration...", total=None)
            ansible_cfg_path = target_dir / "ansible" / "ansible.cfg"
            
            if not dry_run and ansible_cfg_path.exists():
                # Read current content
                content = ansible_cfg_path.read_text()
                
                # Update paths to absolute
                content = content.replace(
                    "inventory = inventory/hosts.yml",
                    "inventory = /etc/cstation/ansible/inventory/hosts.yml"
                )
                content = content.replace(
                    "roles_path = roles",
                    "roles_path = /etc/cstation/ansible/roles"
                )
                content = content.replace(
                    "collections_path = collections",
                    "collections_path = /etc/cstation/ansible/collections"
                )
                
                # Write back
                ansible_cfg_path.write_text(content)
                os.chown(ansible_cfg_path, 0, 0)
                if developer:
                    os.chmod(ansible_cfg_path, 0o666)  # rw-rw-rw-
                else:
                    os.chmod(ansible_cfg_path, 0o644)  # rw-r--r--
            
            console.print(f"[green]✓[/green] Ansible configuration updated")
            progress.remove_task(ansible_cfg_task)
    
    except PermissionError as e:
        console.print(f"[red]Error: Permission denied - {e}[/red]")
        console.print("Make sure you're running as root (use sudo)")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error during initialization: {e}[/red]")
        raise typer.Exit(1)
    
    # Success message
    if not dry_run:
        console.print("\n[bold green]🎉 CStation initialization completed successfully![/bold green]")
        console.print("\n[blue]Next steps:[/blue]")
        console.print("1. Configure your inventory: [cyan]sudo vim /etc/cstation/ansible/inventory/hosts.yml[/cyan]")
        console.print("2. Set up Ansible vault: [cyan]cd /etc/cstation/ansible && sudo ./setup-vault.sh[/cyan]")
        console.print("3. Test your setup: [cyan]cstation server status[/cyan]")
    else:
        console.print("\n[yellow]Dry run completed. Use --force to proceed with initialization.[/yellow]")

if __name__ == "__main__":
    typer.run(init_command)