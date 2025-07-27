#!/usr/bin/env python3
"""
GitHub repository management commands
"""

import os
import subprocess
import typer
import yaml
from pathlib import Path
from typing import Optional, List
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()

def manage_repo(
    ctx: typer.Context,
    action: Optional[str] = typer.Argument(None, help="Action: list, sync"),
    repo_name: Optional[str] = typer.Argument(None, help="Repository name (for sync action)"),
    config_file: Optional[str] = typer.Option(
        "etc/github/repos.yml",
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
    """
    Manage GitHub repositories: list, clone, sync configurations
    """
    
    # Show help when no action is provided
    if action is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)
    
    if action not in ["list", "sync"]:
        console.print(f"[red]Invalid action: {action}[/red]")
        console.print("[yellow]Available actions: list, sync[/yellow]")
        console.print("\n[blue]Use --help for more information[/blue]")
        raise typer.Exit(1)
    
    # Load configuration
    config = _load_github_config(config_file)
    
    if action == "list":
        _list_repositories(config)
    elif action == "sync":
        _sync_repositories(config, repo_name, target_dir, github_user)

def _setup_github_config(config_file: str):
    """Setup GitHub configuration file"""
    
    console.print(Panel.fit(
        "[bold]GitHub Configuration Setup[/bold]\n"
        "This will create a configuration file for managing GitHub repositories.",
        title="GitHub Config",
        border_style="blue"
    ))
    
    # Get GitHub username
    github_user = Prompt.ask("Enter your GitHub username")
    
    # Default configuration
    config = {
        "github": {
            "username": github_user,
            "default_clone_method": "ssh",  # or "https"
            "default_directory": "./repositories"
        },
        "repositories": [
            {
                "name": "example-repo",
                "description": "Example repository configuration",
                "clone_method": "ssh",
                "auto_sync": True,
                "local_path": "./repositories/example-repo"
            }
        ]
    }
    
    # Write configuration file
    try:
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
        console.print(f"[green]Configuration created: {config_file}[/green]")
        console.print("[yellow]Edit the configuration file to add your repositories[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to create configuration: {e}[/red]")
        raise typer.Exit(1)

def _load_github_config(config_file: str) -> dict:
    """Load GitHub configuration from file"""
    
    if not os.path.exists(config_file):
        console.print(f"[red]Configuration file not found: {config_file}[/red]")
        console.print(f"[yellow]Run 'cstation github repo config' to create it[/yellow]")
        raise typer.Exit(1)
    
    try:
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Check if it's an Ansible playbook format (list with vars.repos)
        if isinstance(config_data, list) and len(config_data) > 0:
            playbook_task = config_data[0]
            if 'vars' in playbook_task and 'repos' in playbook_task['vars']:
                # Convert Ansible playbook format to GitHub config format
                repos = playbook_task['vars']['repos']
                converted_repos = []
                
                for repo in repos:
                    converted_repo = {
                        'name': repo.get('name', 'Unknown'),
                        'description': f"Repository: {repo.get('name', 'Unknown')}",
                        'branch': repo.get('branch', 'main'),
                        'category': 'imported',
                        'auto_sync': True,
                        'local_path': repo.get('local_dir', './repositories/' + repo.get('name', 'unknown')),
                        'fork_url': repo.get('fork_url'),
                        'upstream_url': repo.get('upstream_url')
                    }
                    converted_repos.append(converted_repo)
                
                return {
                    'github': {
                        'username': 'imported',
                        'default_clone_method': 'ssh',
                        'default_directory': './repositories'
                    },
                    'repositories': converted_repos
                }
        
        # Return as-is if it's already in the expected format
        return config_data
        
    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")
        raise typer.Exit(1)

def _list_repositories(config: dict):
    """List configured repositories"""
    
    github_config = config.get("github", {})
    repositories = config.get("repositories", [])
    
    console.print(Panel.fit(
        f"[bold]GitHub Repositories[/bold]\n"
        f"Username: {github_config.get('username', 'Not configured')}\n"
        f"Default Method: {github_config.get('default_clone_method', 'ssh')}\n"
        f"Default Directory: {github_config.get('default_directory', './repositories')}",
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
        table.add_row(
            repo.get("name", "N/A"),
            repo.get("description", "N/A")[:40] + "..." if len(repo.get("description", "")) > 40 else repo.get("description", "N/A"),
            repo.get("branch", "main"),
            repo.get("category", "N/A"),
            "Yes" if repo.get("auto_sync", False) else "No",
            repo.get("local_path", "N/A")
        )
    
    console.print(table)

def _clone_repository(config: dict, repo_name: str, target_dir: Optional[str], github_user: Optional[str]):
    """Clone a specific repository"""
    
    github_config = config.get("github", {})
    repositories = config.get("repositories", [])
    
    # Find repository configuration
    repo_config = None
    for repo in repositories:
        if repo.get("name") == repo_name:
            repo_config = repo
            break
    
    if not repo_config:
        console.print(f"[red]Repository '{repo_name}' not found in configuration[/red]")
        console.print("[yellow]Available repositories:[/yellow]")
        for repo in repositories:
            console.print(f"  - {repo.get('name')}")
        raise typer.Exit(1)
    
    # Determine clone method and URL
    clone_method = repo_config.get("clone_method", github_config.get("default_clone_method", "ssh"))
    username = github_user or github_config.get("username")
    organization = github_config.get("organization", username)
    
    # Use fork_url if available, otherwise construct URL
    if repo_config.get("fork_url"):
        clone_url = repo_config.get("fork_url")
    elif repo_config.get("upstream_url") and clone_method == "https":
        clone_url = repo_config.get("upstream_url")
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
        local_path = repo_config.get("local_path", os.path.join("./repositories", repo_name))
    
    # Get additional repository info
    branch = repo_config.get("branch", "main")
    category = repo_config.get("category", "N/A")
    upstream_url = repo_config.get("upstream_url", "N/A")
    
    console.print(Panel.fit(
        f"[bold]Cloning Repository[/bold]\n"
        f"Repository: {repo_name}\n"
        f"Category: {category}\n"
        f"Branch: {branch}\n"
        f"Clone URL: {clone_url}\n"
        f"Upstream: {upstream_url}\n"
        f"Local Path: {local_path}",
        title="Git Clone",
        border_style="green"
    ))
    
    # Create target directory if it doesn't exist
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    # Clone repository with specific branch
    try:
        branch = repo_config.get("branch", "main")
        cmd = ["git", "clone", "-b", branch, clone_url, local_path]
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

def _sync_repositories(config: dict, repo_name: Optional[str], target_dir: Optional[str], github_user: Optional[str]):
    """Sync repositories (fetch from upstream, pull latest changes, and push to GitHub)"""
    
    repositories = config.get("repositories", [])
    
    # Filter repositories to sync
    repos_to_sync = []
    if repo_name:
        for repo in repositories:
            if repo.get("name") == repo_name:
                repos_to_sync.append(repo)
                break
        if not repos_to_sync:
            console.print(f"[red]Repository '{repo_name}' not found in configuration[/red]")
            raise typer.Exit(1)
    else:
        # Sync all repositories with auto_sync enabled
        repos_to_sync = [repo for repo in repositories if repo.get("auto_sync", False)]
    
    if not repos_to_sync:
        console.print("[yellow]No repositories to sync[/yellow]")
        return
    
    console.print(f"[blue]Syncing {len(repos_to_sync)} repositories...[/blue]")
    
    for repo in repos_to_sync:
        repo_name = repo.get("name")
        local_path = repo.get("local_path", os.path.join("./repositories", repo_name))
        
        if not os.path.exists(local_path):
            console.print(f"[yellow]Repository not found locally: {local_path}[/yellow]")
            console.print(f"[blue]Cloning {repo_name}...[/blue]")
            _clone_repository(config, repo_name, target_dir, github_user)
            continue
        
        console.print(f"[blue]Syncing {repo_name}...[/blue]")
        
        try:
            # Get current branch
            branch_cmd = ["git", "-C", local_path, "branch", "--show-current"]
            branch_result = subprocess.run(branch_cmd, capture_output=True, text=True)
            current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else repo.get("branch", "main")
            
            # Fetch and merge from upstream if configured
            upstream_url = repo.get("upstream_url")
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
                
                # Fetch from upstream with shallow fetch and timeout (single branch only)
                fetch_upstream_cmd = ["git", "-C", local_path, "fetch", "upstream", current_branch, "--depth=1"]
                try:
                    fetch_upstream_result = subprocess.run(fetch_upstream_cmd, capture_output=True, text=True, timeout=120)
                    
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
                        
                except subprocess.TimeoutExpired:
                    console.print(f"[yellow]  ⚠ Warning: Upstream fetch timed out after 120 seconds[/yellow]")
                    console.print(f"[yellow]  Failed to fetch from upstream[/yellow]")
            
            # Fetch from origin with timeout
            console.print(f"[cyan]  Fetching from origin...[/cyan]")
            fetch_origin_cmd = ["git", "-C", local_path, "fetch", "origin", "--prune"]
            try:
                fetch_origin_result = subprocess.run(fetch_origin_cmd, capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired:
                console.print(f"[yellow]  ⚠ Warning: Origin fetch timed out after 60 seconds[/yellow]")
                fetch_origin_result = subprocess.CompletedProcess(fetch_origin_cmd, 1, "", "Timeout expired")
            
            if fetch_origin_result.returncode == 0:
                console.print(f"[cyan]  ✓ Fetched from origin[/cyan]")
            else:
                console.print(f"[yellow]  ⚠ Warning: Failed to fetch from origin[/yellow]")
            
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
                console.print(f"[green]✓ {repo_name} synced and pushed to GitHub successfully[/green]")
            else:
                # Check if there are no changes to push
                if "up-to-date" in push_result.stderr.lower() or "everything up-to-date" in push_result.stderr.lower():
                    console.print(f"[green]✓ {repo_name} synced (already up-to-date on GitHub)[/green]")
                elif "non-fast-forward" in push_result.stderr and upstream_synced:
                    # If we synced from upstream and have non-fast-forward, force push
                    console.print(f"[cyan]  Force pushing after upstream sync...[/cyan]")
                    force_push_cmd = ["git", "-C", local_path, "push", "origin", current_branch, "--force"]
                    force_push_result = subprocess.run(force_push_cmd, capture_output=True, text=True)
                    
                    if force_push_result.returncode == 0:
                        console.print(f"[green]✓ {repo_name} synced and force-pushed to GitHub successfully[/green]")
                    else:
                        console.print(f"[yellow]  ⚠ Warning: Failed to force push to GitHub[/yellow]")
                        console.print(f"[yellow]    {force_push_result.stderr.strip()}[/yellow]")
                        console.print(f"[green]✓ {repo_name} synced locally[/green]")
                else:
                    console.print(f"[yellow]  ⚠ Warning: Failed to push to GitHub[/yellow]")
                    console.print(f"[yellow]    {push_result.stderr.strip()}[/yellow]")
                    console.print(f"[green]✓ {repo_name} synced locally[/green]")
                    
        except Exception as e:
            console.print(f"[red]Error syncing {repo_name}: {e}[/red]")
    
    console.print("[green]Sync completed! Repositories are updated locally and on GitHub for production deployment.[/green]")