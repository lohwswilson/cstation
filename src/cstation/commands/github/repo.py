#!/usr/bin/env python3
"""
GitHub repository management commands
"""

import os
import subprocess
import tempfile
import shutil
import typer
import yaml
from pathlib import Path
from typing import Optional, List
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from pydantic import ValidationError

from cstation.models import GitHubConfig, GitHubRepoConfig

console = Console()

DEFAULT_CONFIG_PATH = str(Path.home() / ".config" / "cstation" / "github" / "odoo_repos.sync.yml")

repo_app = typer.Typer(
    name="repo",
    help="Manage GitHub repositories: list, clone, sync configurations",
    invoke_without_command=True,
)


@repo_app.command("list")
def repo_list(
    config_file: Optional[str] = typer.Option(
        DEFAULT_CONFIG_PATH,
        "-c", "--config",
        help="GitHub repositories configuration file"
    ),
):
    """List configured repositories."""
    config = _load_github_config(config_file or DEFAULT_CONFIG_PATH)
    _list_repositories(config)


@repo_app.command("sync")
def repo_sync(
    repo_name: Optional[str] = typer.Argument(None, help="Repository name to sync (optional, syncs all auto_sync repos by default)"),
    config_file: Optional[str] = typer.Option(
        DEFAULT_CONFIG_PATH,
        "-c", "--config",
        help="GitHub repositories configuration file"
    ),
    target_dir: Optional[str] = typer.Option(
        None,
        "-d", "--directory",
        help="Target directory for cloning if not present"
    ),
    user: Optional[str] = typer.Option(
        None,
        "-u", "--user",
        help="GitHub username (uses config if not provided)"
    ),
):
    """Sync repositories (fetch upstream, merge, pull origin, push to fork)."""
    config = _load_github_config(config_file or DEFAULT_CONFIG_PATH)
    _sync_repositories(config, repo_name, target_dir, user)


@repo_app.command("clone")
def repo_clone(
    repo_name: Optional[str] = typer.Argument(None, help="Repository name to clone (optional, interactive selection by default)"),
    config_file: Optional[str] = typer.Option(
        DEFAULT_CONFIG_PATH,
        "-c", "--config",
        help="GitHub repositories configuration file"
    ),
    target_dir: Optional[str] = typer.Option(
        None,
        "-d", "--directory",
        help="Target directory for cloning"
    ),
    user: Optional[str] = typer.Option(
        None,
        "-u", "--user",
        help="GitHub username (uses config if not provided)"
    ),
):
    """Clone configured repositories."""
    config = _load_github_config(config_file or DEFAULT_CONFIG_PATH)
    _clone_selective_repositories(config, repo_name, target_dir, user)


@repo_app.callback()
def repo_callback(ctx: typer.Context):
    """Manage GitHub repositories: list, clone, sync configurations"""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


def manage_repo(
    ctx: typer.Context,
    action: Optional[str] = typer.Argument(None, help="Action: list, sync, clone"),
    repo_name: Optional[str] = typer.Argument(None, help="Repository name (for sync/clone action)"),
    config_file: Optional[str] = typer.Option(
        DEFAULT_CONFIG_PATH,
        "-c", "--config",
        help="GitHub repositories configuration file"
    ),
    target_dir: Optional[str] = typer.Option(
        None,
        "-d", "--directory",
        help="Target directory for cloning (default: current directory)"
    ),
    github_user: Optional[str] = typer.Option(
        None,
        "-u", "--user",
        help="GitHub username (will use config if not provided)"
    )
):
    """Manage GitHub repositories: list, clone, sync configurations"""
    if action is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)
    
    if action not in ["list", "sync", "clone"]:
        console.print(f"[red]Invalid action: {action}[/red]")
        console.print("[yellow]Available actions: list, sync, clone[/yellow]")
        raise typer.Exit(1)
    
    config = _load_github_config(config_file or DEFAULT_CONFIG_PATH)
    
    if action == "list":
        _list_repositories(config)
    elif action == "sync":
        _sync_repositories(config, repo_name, target_dir, github_user)
    elif action == "clone":
        _clone_selective_repositories(config, repo_name, target_dir, github_user)

def _load_github_config(config_file: str) -> GitHubConfig:
    """Load GitHub configuration from file and validate with Pydantic"""
    file_path = Path(config_file)
    if not file_path.exists():
        console.print(f"[red]✗[/red] Configuration file not found: {config_file}")
        console.print(f"[yellow]Run 'cstation github repo config' to create it[/yellow]")
        raise typer.Exit(1)
    
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
             console.print(f"[red]✗[/red] Invalid {config_file}: expected mapping")
             raise typer.Exit(1)

        return GitHubConfig(**data)
    except ValidationError as e:
        console.print(f"[red]✗[/red] Schema validation failed for {config_file}:")
        for error in e.errors():
            loc = ".".join(str(l) for l in error["loc"])
            msg = error["msg"]
            console.print(f"  - [bold]{loc}[/bold]: {msg}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load configuration: {e}")
        raise typer.Exit(1)

def _list_repositories(config: GitHubConfig):
    """List configured repositories"""
    
    github_config = config.github
    repositories = config.repositories
    
    console.print(Panel.fit(
        f"[bold]GitHub Repositories[/bold]\n"
        f"Username: {github_config.username}\n"
        f"Default Method: {github_config.default_clone_method}\n"
        f"Default Directory: {github_config.default_directory}",
        title="GitHub Configuration",
        border_style="blue"
    ))
    
    if not repositories:
        console.print("[yellow]No repositories configured[/yellow]")
        return
    
    table = Table(title="Configured Repositories")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Branch", style="magenta")
    table.add_column("Category", style="green")
    table.add_column("Auto Sync", style="yellow")
    table.add_column("Local Path", style="blue")
    
    for repo in repositories:
        desc = repo.description
        table.add_row(
            repo.name,
            desc[:40] + "..." if len(desc) > 40 else desc,
            repo.branch,
            repo.category,
            "Yes" if repo.auto_sync else "No",
            repo.local_path
        )
    
    console.print(table)

def _clone_repository(config: GitHubConfig, repo_name: str, target_dir: Optional[str], github_user: Optional[str]):
    """Clone a specific repository"""
    
    github_config = config.github
    repositories = config.repositories
    
    # Find repository configuration
    repo_config = next((r for r in repositories if r.name == repo_name), None)
    
    if not repo_config:
        console.print(f"[red]Repository '{repo_name}' not found in configuration[/red]")
        console.print("[yellow]Available repositories:[/yellow]")
        for repo in repositories:
            console.print(f"  - {repo.name}")
        raise typer.Exit(1)
    
    # Determine clone method and URL
    clone_method = repo_config.clone_method
    username = github_user or github_config.username
    organization = github_config.organization or username
    
    # Use fork_url if available, otherwise construct URL
    if repo_config.fork_url:
        clone_url = repo_config.fork_url
    elif repo_config.upstream_url and clone_method == "https":
        clone_url = repo_config.upstream_url
    elif repo_config.url:
        clone_url = repo_config.url
    else:
        if not username:
            console.print("[red]GitHub username not configured[/red]")
            raise typer.Exit(1)
        
        if clone_method == "ssh":
            clone_url = f"git@github.com:{organization}/{repo_name}.git"
        else:
            clone_url = f"https://github.com/{organization}/{repo_name}.git"
    
    # Determine target directory
    if target_dir:
        local_path = os.path.join(target_dir, repo_name)
    else:
        local_path = repo_config.local_path
    
    console.print(Panel.fit(
        f"[bold]Cloning Repository[/bold]\n"
        f"Repository: {repo_name}\n"
        f"Category: {repo_config.category}\n"
        f"Branch: {repo_config.branch}\n"
        f"Clone URL: {clone_url}\n"
        f"Upstream: {repo_config.upstream_url or 'N/A'}\n"
        f"Local Path: {local_path}",
        title="Git Clone",
        border_style="green"
    ))
    
    # Create target directory if it doesn't exist
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    # Clone repository with specific branch
    try:
        cmd = ["git", "clone", "-b", repo_config.branch, clone_url, local_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            console.print(f"[green]Repository cloned successfully to: {local_path}[/green]")
        else:
            console.print(f"[red]Failed to clone repository:[/red]")
            console.print(result.stderr)
            raise typer.Exit(1)
    except FileNotFoundError:
        console.print("[red]git command not found. Please install Git.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error cloning repository: {e}[/red]")
        raise typer.Exit(1)

def _clean_stale_git_locks(local_path: str) -> None:
    """Clean up stale .git/*.lock files (e.g. from previous crashed or timed-out processes)."""
    git_dir = Path(local_path) / ".git"
    if not git_dir.exists():
        return
    for lock_file in git_dir.glob("**/*.lock"):
        if lock_file.is_file():
            try:
                lock_file.unlink()
                console.print(f"[dim]  Cleaned stale git lock: {lock_file.name}[/dim]")
            except Exception:
                pass


def _sync_repositories(config: GitHubConfig, repo_name: Optional[str], target_dir: Optional[str], github_user: Optional[str]):
    """Sync repositories (fetch from upstream, pull latest changes, and push to GitHub)"""
    
    repositories = config.repositories
    
    # Filter repositories to sync
    repos_to_sync = []
    if repo_name:
        for repo in repositories:
            if repo.name == repo_name:
                repos_to_sync.append(repo)
                break
        if not repos_to_sync:
            console.print(f"[red]Repository '{repo_name}' not found in configuration[/red]")
            raise typer.Exit(1)
    else:
        # Sync all repositories with auto_sync enabled
        repos_to_sync = [repo for repo in repositories if repo.auto_sync]
    
    if not repos_to_sync:
        console.print("[yellow]No repositories to sync[/yellow]")
        return
    
    console.print(f"[blue]Syncing {len(repos_to_sync)} repositories...[/blue]")
    
    for repo in repos_to_sync:
        r_name = repo.name
        local_path = repo.local_path
        
        if not os.path.exists(local_path):
            console.print(f"[yellow]Repository not found locally: {local_path}[/yellow]")
            console.print(f"[blue]Cloning {r_name}...[/blue]")
            _clone_repository(config, r_name, target_dir, github_user)
            continue
        
        console.print(f"[blue]Syncing {r_name}...[/blue]")
        _clean_stale_git_locks(local_path)
        
        try:
            # Get current branch
            branch_cmd = ["git", "-C", local_path, "branch", "--show-current"]
            branch_result = subprocess.run(branch_cmd, capture_output=True, text=True)
            current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else repo.branch
            
            # Fetch and merge from upstream if configured
            upstream_url = repo.upstream_url
            upstream_synced = False
            
            if upstream_url:
                console.print(f"[cyan]  Fetching from upstream: {upstream_url}[/cyan]")
                
                # First, ensure upstream remote is configured
                check_upstream_cmd = ["git", "-C", local_path, "remote", "get-url", "upstream"]
                check_result = subprocess.run(check_upstream_cmd, capture_output=True, text=True)
                
                if check_result.returncode != 0:
                    # Add upstream remote if it doesn't exist
                    add_upstream_cmd = ["git", "-C", local_path, "remote", "add", "upstream", upstream_url]
                    subprocess.run(add_upstream_cmd, capture_output=True, text=True)
                    console.print(f"[cyan]  Added upstream remote: {upstream_url}[/cyan]")
                
                # Fetch from upstream with shallow fetch, no tags, and extended timeout
                fetch_upstream_cmd = ["git", "-C", local_path, "fetch", "upstream", current_branch, "--depth=1", "--no-tags"]
                try:
                    fetch_upstream_result = subprocess.run(fetch_upstream_cmd, capture_output=True, text=True, timeout=300)
                    
                    if fetch_upstream_result.returncode == 0:
                        console.print(f"[cyan]  ✓ Fetched from upstream[/cyan]")
                        
                        # Merge upstream changes
                        merge_cmd = ["git", "-C", local_path, "merge", f"upstream/{current_branch}"]
                        merge_result = subprocess.run(merge_cmd, capture_output=True, text=True)
                        
                        if merge_result.returncode == 0:
                            console.print(f"[cyan]  ✓ Merged upstream/{current_branch}[/cyan]")
                            upstream_synced = True
                        elif "refusing to merge unrelated histories" in merge_result.stderr:
                            # For unrelated histories, reset to upstream instead of merging
                            console.print(f"[cyan]  Resetting to upstream/{current_branch} (unrelated histories)[/cyan]")
                            reset_cmd = ["git", "-C", local_path, "reset", "--hard", f"upstream/{current_branch}"]
                            reset_result = subprocess.run(reset_cmd, capture_output=True, text=True)
                            
                            if reset_result.returncode == 0:
                                console.print(f"[cyan]  ✓ Reset to upstream/{current_branch}[/cyan]")
                                upstream_synced = True
                            else:
                                console.print(f"[yellow]  ⚠ Warning: Failed to reset to upstream[/yellow]")
                                console.print(f"[yellow]    {reset_result.stderr.strip()}[/yellow]")
                        else:
                            console.print(f"[yellow]  ⚠ Warning: Failed to merge upstream changes[/yellow]")
                            console.print(f"[yellow]    {merge_result.stderr.strip()}[/yellow]")
                    else:
                        console.print(f"[yellow]  ⚠ Warning: Failed to fetch from upstream[/yellow]")
                        console.print(f"[yellow]    {fetch_upstream_result.stderr.strip()}[/yellow]")

                except subprocess.TimeoutExpired:
                    console.print(f"[yellow]  ⚠ Warning: Upstream fetch timed out after 300 seconds[/yellow]")
                    console.print(f"[yellow]  Failed to fetch from upstream[/yellow]")
                    _clean_stale_git_locks(local_path)
            
            # Fetch from origin with timeout
            console.print(f"[cyan]  Fetching from origin...[/cyan]")
            fetch_origin_cmd = ["git", "-C", local_path, "fetch", "origin", "--prune"]
            try:
                fetch_origin_result = subprocess.run(fetch_origin_cmd, capture_output=True, text=True, timeout=180)
            except subprocess.TimeoutExpired:
                console.print(f"[yellow]  ⚠ Warning: Origin fetch timed out after 180 seconds[/yellow]")
                fetch_origin_result = subprocess.CompletedProcess(fetch_origin_cmd, 1, "", "Timeout expired")
                _clean_stale_git_locks(local_path)
            
            # Pull latest changes from origin (if no upstream sync occurred)
            if not upstream_synced:
                console.print(f"[cyan]  Pulling latest changes from origin/{current_branch}...[/cyan]")
                pull_cmd = ["git", "-C", local_path, "pull", "origin", current_branch]
                pull_result = subprocess.run(pull_cmd, capture_output=True, text=True)
                
                if pull_result.returncode != 0:
                    # Try with main/master if current branch fails
                    fallback_branches = ["main", "master"]
                    success = False
                    
                    for fallback_branch in fallback_branches:
                        if fallback_branch != current_branch:
                            console.print(f"[cyan]  Trying fallback branch: {fallback_branch}[/cyan]")
                            fallback_cmd = ["git", "-C", local_path, "pull", "origin", fallback_branch]
                            fallback_result = subprocess.run(fallback_cmd, capture_output=True, text=True)
                            
                            if fallback_result.returncode == 0:
                                console.print(f"[cyan]  ✓ Pulled from origin/{fallback_branch}[/cyan]")
                                success = True
                                break
                    
                    if not success:
                        console.print(f"[yellow]  ⚠ Warning: Failed to pull from origin[/yellow]")
                        console.print(f"[yellow]    {pull_result.stderr.strip()}[/yellow]")
                else:
                    console.print(f"[cyan]  ✓ Pulled from origin/{current_branch}[/cyan]")
            
            # Push changes to GitHub (origin) for production server access
            console.print(f"[cyan]  Pushing changes to GitHub origin/{current_branch}...[/cyan]")
            push_cmd = ["git", "-C", local_path, "push", "origin", current_branch]
            push_result = subprocess.run(push_cmd, capture_output=True, text=True)
            
            if push_result.returncode == 0:
                console.print(f"[green]✓ {r_name} synced and pushed to GitHub successfully[/green]")
            else:
                # Check if there are no changes to push
                if "up-to-date" in push_result.stderr.lower() or "everything up-to-date" in push_result.stderr.lower():
                    console.print(f"[green]✓ {r_name} synced (already up-to-date on GitHub)[/green]")
                elif "non-fast-forward" in push_result.stderr and upstream_synced:
                    # If we synced from upstream and have non-fast-forward, force push
                    console.print(f"[cyan]  Force pushing after upstream sync...[/cyan]")
                    force_push_cmd = ["git", "-C", local_path, "push", "origin", current_branch, "--force"]
                    force_push_result = subprocess.run(force_push_cmd, capture_output=True, text=True)
                    
                    if force_push_result.returncode == 0:
                        console.print(f"[green]✓ {r_name} synced and force-pushed to GitHub successfully[/green]")
                    else:
                        console.print(f"[yellow]  ⚠ Warning: Failed to force push to GitHub[/yellow]")
                        console.print(f"[yellow]    {force_push_result.stderr.strip()}[/yellow]")
                        console.print(f"[green]✓ {r_name} synced locally[/green]")
                else:
                    console.print(f"[yellow]  ⚠ Warning: Failed to push to GitHub[/yellow]")
                    console.print(f"[yellow]    {push_result.stderr.strip()}[/yellow]")
                    console.print(f"[green]✓ {r_name} synced locally[/green]")
                    
        except Exception as e:
            console.print(f"[red]Error syncing {r_name}: {e}[/red]")
    
    console.print("[green]Sync completed! Repositories are updated locally and on GitHub for production deployment.[/green]")

def _clone_selective_repositories(config: GitHubConfig, repo_name: Optional[str], target_dir: Optional[str], github_user: Optional[str]):
    """Clone repositories with selective directory inclusion based on 'includes' field"""
    
    repositories = config.repositories
    
    # Filter repositories to clone
    repos_to_clone = []
    if repo_name:
        for repo in repositories:
            if repo.name == repo_name:
                repos_to_clone.append(repo)
                break
        if not repos_to_clone:
            console.print(f"[red]Repository '{repo_name}' not found in configuration[/red]")
            console.print("[yellow]Available repositories:[/yellow]")
            for repo in repositories:
                console.print(f"  - {repo.name}")
            raise typer.Exit(1)
    else:
        # Clone all repositories
        repos_to_clone = repositories
    
    if not repos_to_clone:
        console.print("[yellow]No repositories to clone[/yellow]")
        return
    
    console.print(f"[blue]Cloning {len(repos_to_clone)} repositories with selective directories...[/blue]")
    
    for repo in repos_to_clone:
        _clone_repository_selective(config, repo, target_dir, github_user)

def _clone_repository_selective(config: GitHubConfig, repo_config: GitHubRepoConfig, target_dir: Optional[str], github_user: Optional[str]):
    """Clone a repository and selectively copy specified directories using optimized sparse-checkout"""
    
    github_config = config.github
    repo_name = repo_config.name
    repo_url = repo_config.url or repo_config.fork_url or repo_config.upstream_url
    branch = repo_config.branch
    local_path = repo_config.local_path
    includes = repo_config.includes
    
    if not repo_url:
        # Try to construct URL if not provided
        username = github_user or github_config.username
        organization = github_config.organization or username
        clone_method = repo_config.clone_method or github_config.default_clone_method
        
        if clone_method == "ssh":
            repo_url = f"git@github.com:{organization}/{repo_name}.git"
        else:
            repo_url = f"https://github.com/{organization}/{repo_name}.git"
    
    if not local_path:
        console.print(f"[red]No local_path specified for repository '{repo_name}'[/red]")
        return
    
    if not includes:
        console.print(f"[yellow]No 'includes' specified for '{repo_name}', skipping selective clone[/yellow]")
        return
    
    console.print(Panel.fit(
        f"[bold]Fast Selective Clone: {repo_name}[/bold]\n"
        f"URL: {repo_url}\n"
        f"Branch: {branch}\n"
        f"Target: {local_path}\n"
        f"Includes: {', '.join(includes)}\n"
        f"[dim]Using sparse-checkout for faster cloning[/dim]",
        title="Optimized Repository Clone",
        border_style="green"
    ))
    
    # Create target directory if it doesn't exist
    os.makedirs(local_path, exist_ok=True)
    
    # Use sparse-checkout for faster cloning
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_repo_path = os.path.join(temp_dir, repo_name)
        
        try:
            console.print(f"[cyan]Initializing sparse checkout for {repo_name}...[/cyan]")
            
            # Step 1: Initialize empty repository
            init_cmd = ["git", "init", temp_repo_path]
            result = subprocess.run(init_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                console.print(f"[red]Failed to initialize repository:[/red]")
                console.print(result.stderr)
                return
            
            # Step 2: Add remote
            original_cwd = os.getcwd()
            os.chdir(temp_repo_path)
            try:
                remote_cmd = ["git", "remote", "add", "origin", repo_url]
                result = subprocess.run(remote_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    console.print(f"[red]Failed to add remote:[/red]")
                    console.print(result.stderr)
                    return
                
                # Step 3: Enable sparse-checkout
                sparse_cmd = ["git", "config", "core.sparseCheckout", "true"]
                result = subprocess.run(sparse_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    console.print(f"[red]Failed to enable sparse-checkout:[/red]")
                    console.print(result.stderr)
                    return
                
                # Step 4: Configure sparse-checkout patterns
                sparse_checkout_file = os.path.join(".git", "info", "sparse-checkout")
                os.makedirs(os.path.dirname(sparse_checkout_file), exist_ok=True)
                
                with open(sparse_checkout_file, 'w') as f:
                    for include_item in includes:
                        f.write(f"{include_item}\n")
                        f.write(f"{include_item}/*\n")  # Include subdirectories
                
                console.print(f"[cyan]Fetching only required directories from {repo_name}...[/cyan]")
                
                # Step 5: Fetch with depth=1 for speed
                fetch_cmd = ["git", "fetch", "--depth=1", "origin", branch]
                result = subprocess.run(fetch_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    console.print(f"[red]Failed to fetch repository:[/red]")
                    console.print(result.stderr)
                    return
                
                # Step 6: Checkout the specific branch
                checkout_cmd = ["git", "checkout", f"origin/{branch}"]
                result = subprocess.run(checkout_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    console.print(f"[red]Failed to checkout branch:[/red]")
                    console.print(result.stderr)
                    return
            finally:
                os.chdir(original_cwd)
            
            # Step 7: Copy the sparse-checked files to target location
            copied_items = []
            missing_items = []
            
            for include_item in includes:
                source_path = os.path.join(temp_repo_path, include_item)
                target_path = os.path.join(local_path, include_item)
                
                if os.path.exists(source_path):
                    # Create parent directory if needed
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    if os.path.isdir(source_path):
                        # Copy directory
                        if os.path.exists(target_path):
                            shutil.rmtree(target_path)
                        shutil.copytree(source_path, target_path)
                        console.print(f"[green]  ✓ Copied directory: {include_item}[/green]")
                    else:
                        # Copy file
                        shutil.copy2(source_path, target_path)
                        console.print(f"[green]  ✓ Copied file: {include_item}[/green]")
                    
                    copied_items.append(include_item)
                else:
                    console.print(f"[yellow]  ⚠ Not found: {include_item}[/yellow]")
                    missing_items.append(include_item)
            
            # Summary
            if copied_items:
                console.print(f"[green]✓ Successfully copied {len(copied_items)} items from {repo_name}[/green]")
                console.print(f"[green]  Target location: {local_path}[/green]")
                console.print(f"[blue]  Used sparse-checkout for faster cloning[/blue]")
            
            if missing_items:
                console.print(f"[yellow]⚠ {len(missing_items)} items not found in repository[/yellow]")
                
        except FileNotFoundError:
            console.print("[red]git command not found. Please install Git.[/red]")
        except Exception as e:
            console.print(f"[red]Error during selective clone: {e}[/red]")
        finally:
            # Change back to original directory
            os.chdir("/Users/wsloh/PythonProject/cstation")
