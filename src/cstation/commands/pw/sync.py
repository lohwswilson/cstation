#!/usr/bin/env python3
"""
PerfectWork sync implementation using direct rsync calls for performance.

This module handles the actual file synchronization operations using subprocess
calls to rsync, providing much better performance than Ansible for large file operations.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.progress import Progress, TaskID
from rich import print as rprint

from ...config import ConfigManager
from .config import (
    get_pw_config, validate_version, get_source_path, get_addons_path,
    get_remote_pw_path, get_remote_addons_path, get_remote_host,
    get_rsync_command_base
)


class PWSync:
    """PerfectWork file synchronization manager."""
    
    def __init__(self, config: ConfigManager, console: Console):
        self.config = config
        self.console = console
        self.temp_dir = Path(tempfile.gettempdir()) / "cstation_pw_sync"
        self.temp_dir.mkdir(exist_ok=True)
    
    def sync_files(
        self,
        host: str,
        version: str,
        port: int = 22,
        dry_run: bool = False,
        verbose: bool = False,
        exclude_cache: bool = True,
        progress: Optional[Progress] = None
    ) -> bool:
        """
        Sync PW and PW_ADDONS files to remote server.
        
        Args:
            host: Target hostname
            version: PW version (e.g., "3.0")
            port: SSH port
            dry_run: If True, show what would be done without executing
            verbose: Enable verbose output
            exclude_cache: Exclude __pycache__ directories
            progress: Rich progress instance for status updates
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Step 1: Prepare local files
            if progress:
                task1 = progress.add_task("Preparing local PW files...", total=None)
            
            local_pw_path = self._prepare_pw_files(version, exclude_cache, verbose)
            if not local_pw_path:
                return False
            
            if progress:
                progress.update(task1, description="✓ Local PW files prepared")
                progress.remove_task(task1)
                task2 = progress.add_task("Syncing PW files to server...", total=None)
            
            # Step 2: Sync PW files
            success = self._sync_pw_to_server(
                local_pw_path, host, version, port, dry_run, verbose
            )
            
            if not success:
                return False
            
            if progress:
                progress.update(task2, description="✓ PW files synced")
                progress.remove_task(task2)
                task3 = progress.add_task("Syncing PW_ADDONS to server...", total=None)
            
            # Step 3: Sync PW_ADDONS
            success = self._sync_addons_to_server(
                host, version, port, dry_run, verbose, exclude_cache
            )
            
            if progress:
                progress.update(task3, description="✓ PW_ADDONS synced")
                progress.remove_task(task3)
                task4 = progress.add_task("Cleaning up temporary files...", total=None)
            
            # Step 4: Cleanup
            self._cleanup_temp_files(version)
            
            if progress:
                progress.update(task4, description="✓ Cleanup completed")
                progress.remove_task(task4)
            
            return success
            
        except Exception as e:
            rprint(f"[red]Sync error:[/red] {str(e)}")
            return False
    
    def _prepare_pw_files(self, version: str, exclude_cache: bool, verbose: bool) -> Optional[Path]:
        """Prepare PW files for syncing by copying and reorganizing them."""
        source_path = Path(f"/opt/PW/PW.{version}")
        temp_pw_path = self.temp_dir / f"PW.{version}"
        
        if not source_path.exists():
            rprint(f"[red]Error:[/red] Source path {source_path} does not exist")
            return None
        
        # Remove existing temp directory
        if temp_pw_path.exists():
            shutil.rmtree(temp_pw_path)
        
        try:
            # Build rsync command for local copy
            rsync_cmd = [
                "rsync", "-avz", "--delete",
                "--exclude", ".*"  # Exclude hidden files
            ]
            
            if exclude_cache:
                rsync_cmd.extend(["--exclude", "__pycache__"])
            
            rsync_cmd.extend([f"{source_path}/", str(temp_pw_path)])
            
            if verbose:
                rprint(f"[dim]Running: {' '.join(rsync_cmd)}[/dim]")
            
            result = subprocess.run(rsync_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                rprint(f"[red]Error copying PW files:[/red] {result.stderr}")
                return None
            
            # Reorganize addon files
            self._reorganize_addons(temp_pw_path, verbose)
            
            # Clean __pycache__ directories if requested
            if exclude_cache:
                self._clean_pycache(temp_pw_path, verbose)
            
            return temp_pw_path
            
        except Exception as e:
            rprint(f"[red]Error preparing PW files:[/red] {str(e)}")
            return None
    
    def _reorganize_addons(self, pw_path: Path, verbose: bool):
        """Reorganize addon directory structure."""
        odoo_addons_path = pw_path / "odoo" / "addons"
        addons_path = pw_path / "addons"
        
        if odoo_addons_path.exists() and addons_path.exists():
            # Move odoo/addons/* to addons/
            for item in odoo_addons_path.iterdir():
                target = addons_path / item.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                shutil.move(str(item), str(target))
            
            # Remove empty odoo/addons directory
            odoo_addons_path.rmdir()
            
            # Move addons to odoo/
            final_addons_path = pw_path / "odoo" / "addons"
            shutil.move(str(addons_path), str(final_addons_path))
            
            if verbose:
                rprint("[dim]✓ Reorganized addon directory structure[/dim]")
    
    def _clean_pycache(self, path: Path, verbose: bool):
        """Remove __pycache__ directories recursively."""
        pycache_dirs = list(path.rglob("__pycache__"))
        
        for pycache_dir in pycache_dirs:
            shutil.rmtree(pycache_dir)
            if verbose:
                rprint(f"[dim]✓ Removed {pycache_dir}[/dim]")
    
    def _sync_pw_to_server(
        self, local_path: Path, host: str, version: str, port: int, dry_run: bool, verbose: bool
    ) -> bool:
        """Sync prepared PW files to remote server."""
        remote_path = f"root@{host}.ansis.com.sg:/var/lib/perfectwork/PW.{version}"
        odoo_path = local_path / "odoo"
        
        if not odoo_path.exists():
            rprint(f"[red]Error:[/red] Odoo directory not found in {local_path}")
            return False
        
        rsync_cmd = [
            "rsync", "-avz", "--delete",
            "--exclude", ".*",
            f"-e", f"ssh -p{port}"
        ]
        
        if dry_run:
            rsync_cmd.append("--dry-run")
        
        rsync_cmd.extend([f"{odoo_path}/", remote_path])
        
        if verbose or dry_run:
            rprint(f"[dim]Running: {' '.join(rsync_cmd)}[/dim]")
        
        try:
            result = subprocess.run(rsync_cmd, capture_output=True, text=True)
            
            if verbose:
                if result.stdout:
                    rprint(f"[dim]{result.stdout}[/dim]")
            
            if result.returncode != 0:
                rprint(f"[red]Error syncing PW files:[/red] {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            rprint(f"[red]Error during PW sync:[/red] {str(e)}")
            return False
    
    def _sync_addons_to_server(
        self, host: str, version: str, port: int, dry_run: bool, verbose: bool, exclude_cache: bool
    ) -> bool:
        """Sync PW_ADDONS to remote server."""
        source_path = Path(f"/opt/PW/PW_ADDONS.{version}")
        remote_path = f"root@{host}.ansis.com.sg:/var/lib/perfectwork/PW_ADDONS.{version}"
        
        if not source_path.exists():
            rprint(f"[red]Error:[/red] PW_ADDONS source path {source_path} does not exist")
            return False
        
        # Clean __pycache__ in source if needed
        if exclude_cache:
            self._clean_pycache(source_path, verbose)
        
        rsync_cmd = [
            "rsync", "-avz", "--copy-links", "--delete",
            "--exclude", ".*",
            f"-e", f"ssh -p{port}"
        ]
        
        if dry_run:
            rsync_cmd.append("--dry-run")
        
        rsync_cmd.extend([f"{source_path}/", remote_path])
        
        if verbose or dry_run:
            rprint(f"[dim]Running: {' '.join(rsync_cmd)}[/dim]")
        
        try:
            result = subprocess.run(rsync_cmd, capture_output=True, text=True)
            
            if verbose:
                if result.stdout:
                    rprint(f"[dim]{result.stdout}[/dim]")
            
            if result.returncode != 0:
                rprint(f"[red]Error syncing PW_ADDONS:[/red] {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            rprint(f"[red]Error during PW_ADDONS sync:[/red] {str(e)}")
            return False
    
    def _cleanup_temp_files(self, version: str):
        """Clean up temporary files for specific version."""
        temp_pw_path = self.temp_dir / f"PW.{version}"
        if temp_pw_path.exists():
            shutil.rmtree(temp_pw_path)
    
    def check_status(self, host: str, version: str, port: int) -> Optional[Dict[str, Any]]:
        """Check the status of PW files on remote server."""
        try:
            # Check if PW directory exists and get basic info
            ssh_cmd = [
                "ssh", f"-p{port}", f"root@{host}.ansis.com.sg",
                f"ls -la /var/lib/perfectwork/PW.{version}/ 2>/dev/null | head -5"
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return {
                    "status": "available",
                    "path": f"/var/lib/perfectwork/PW.{version}/",
                    "details": result.stdout.strip()
                }
            else:
                return None
                
        except subprocess.TimeoutExpired:
            rprint(f"[yellow]Warning:[/yellow] Connection to {host} timed out")
            return None
        except Exception as e:
            rprint(f"[red]Error checking status:[/red] {str(e)}")
            return None
    
    def clean_temp_files(self, version: Optional[str] = None, all_versions: bool = False) -> List[str]:
        """Clean temporary sync files."""
        cleaned = []
        
        try:
            if all_versions:
                if self.temp_dir.exists():
                    for item in self.temp_dir.iterdir():
                        if item.is_dir() and item.name.startswith("PW."):
                            shutil.rmtree(item)
                            cleaned.append(str(item))
            elif version:
                temp_pw_path = self.temp_dir / f"PW.{version}"
                if temp_pw_path.exists():
                    shutil.rmtree(temp_pw_path)
                    cleaned.append(str(temp_pw_path))
            
            return cleaned
            
        except Exception as e:
            rprint(f"[red]Error cleaning temp files:[/red] {str(e)}")
            return []