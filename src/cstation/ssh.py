#!/usr/bin/env python3
"""
SSH Management Module for CStation CLI

This module handles remote execution and SSH management using fabric/paramiko,
replacing the dependency on Ansible.
"""

import os
from fabric import Connection
from invoke import UnexpectedExit
from typing import Dict, List, Optional, Any
from rich.console import Console

console = Console()

class SSHManager:
    """
    Manages SSH connections and remote execution.
    """
    
    def __init__(
        self,
        host: str,
        user: Optional[str] = None,
        key_filename: Optional[str] = None,
        port: Optional[int] = None,
    ):
        self.host = host
        self.user = user
        self.key_filename = key_filename
        self.port = port
        self._conn = None

    @property
    def connection(self):
        if self._conn is None:
            self._conn = Connection(
                host=self.host,
                user=self.user,
                port=self.port,
                connect_kwargs={"key_filename": self.key_filename} if self.key_filename else {}
            )
        return self._conn

    def run(self, command: str, hide: bool = True, sudo: bool = False) -> Any:
        try:
            if sudo:
                return self.connection.sudo(command, hide=hide)
            return self.connection.run(command, hide=hide)
        except UnexpectedExit as e:
            console.print(f"[red]Error executing command on {self.host}: {e.result.stderr}[/red]")
            return e.result
        except Exception as e:
            console.print(f"[red]SSH connection error to {self.host}: {e}[/red]")
            return None

    def setup_ssh_key(self, public_key: str, remote_user: str = "root") -> bool:
        """
        Equivalent to ansible.builtin.authorized_key
        """
        try:
            # Ensure .ssh exists
            self.run(f"mkdir -p ~/.ssh && chmod 700 ~/.ssh", sudo=True)
            # Add key
            self.run(f"echo '{public_key}' >> ~/.ssh/authorized_keys", sudo=True)
            self.run(f"chmod 600 ~/.ssh/authorized_keys", sudo=True)
            return True
        except Exception as e:
            console.print(f"[red]Failed to setup SSH key: {e}[/red]")
            return False

    def ping(self) -> bool:
        """
        Equivalent to ansible.builtin.ping
        """
        try:
            result = self.run("echo pong")
            return result is not None and "pong" in result.stdout
        except:
            return False

    def put(self, local_path: str, remote_path: str) -> bool:
        try:
            self.connection.put(local_path, remote_path)
            return True
        except Exception as e:
            console.print(f"[red]Failed to upload {local_path} to {remote_path}: {e}[/red]")
            return False

    def write_file(self, content: str, remote_path: str, mode: str = '0600', sudo: bool = False) -> bool:
        """
        Write string content to a remote file.
        """
        try:
            import io
            f = io.StringIO(content)
            self.connection.put(f, remote_path)
            self.run(f"chmod {mode} {remote_path}", sudo=sudo)
            return True
        except Exception as e:
            console.print(f"[red]Failed to write to {remote_path}: {e}[/red]")
            return False
