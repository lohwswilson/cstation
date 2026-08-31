#!/usr/bin/env python3
"""
SSH Management Module for CStation CLI

This module handles remote execution and SSH management using fabric/paramiko,
replacing the dependency on Ansible.
"""

import subprocess
from fabric import Connection
from invoke import UnexpectedExit
from typing import Dict, Optional, Any
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
            # Add timeout to prevent hanging on unreachable hosts
            self._conn = Connection(
                host=self.host,
                user=self.user,
                port=self.port,
                connect_kwargs={
                    "key_filename": self.key_filename,
                    "timeout": 10,
                    "banner_timeout": 10,
                    "auth_timeout": 10,
                }
                if self.key_filename
                else {
                    "timeout": 10,
                    "banner_timeout": 10,
                    "auth_timeout": 10,
                },
            )
        return self._conn

    def run(self, command: str, hide: bool = True, sudo: bool = False) -> Any:
        """Execute a single command."""
        try:
            if sudo and self.user != "root" and self.host not in ("127.0.0.1", "localhost"):
                return self.connection.sudo(command, hide=hide, warn=True)
            return self.connection.run(command, hide=hide, warn=True)
        except UnexpectedExit as e:
            msg = f"ERROR: Command failed on {self.host}: {e.result.stderr or e.result.stdout}"
            console.print(f"[red]{msg}[/red]")
            return e.result
        except Exception as e:
            msg = f"ERROR: SSH connection/execution failed for {self.host}: {e}"
            console.print(f"[red]{msg}[/red]")
            return None

    def run_batch(self, commands: Dict[str, str], sudo: bool = False) -> Dict[str, str]:
        """
        Execute multiple commands in a single SSH round-trip.
        Returns a mapping of key -> stdout.
        """
        # Shorter, safer separator
        separator = "==CS_SEP=="
        keys = list(commands.keys())

        # Build a single shell command without subshells for maximum compatibility
        # We use '|| true' to ensure the sequence continues and we get our separators
        parts = []
        for cmd in commands.values():
            # Ensure each command returns 0 so the chain continues and Result.ok is True
            parts.append(f"{{ {cmd} ; }} 2>&1")

        bundled_cmd = f" ; echo '{separator}' ; ".join(parts)

        result = self.run(bundled_cmd, sudo=sudo)

        if result is None:
            return {key: "" for key in keys}

        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""
        exited = getattr(result, "exited", -1)

        if not stdout and exited != 0:
            return {key: "" for key in keys}

        if not stdout:
            return {key: "" for key in keys}

        # Split by separator and strip whitespace
        outputs = stdout.split(separator)

        # Ensure we have the same number of outputs as keys
        res = {}
        for i, key in enumerate(keys):
            if i < len(outputs):
                res[key] = outputs[i].strip()
            else:
                res[key] = ""
        return res

    def setup_ssh_key(self, public_key: str, remote_user: str = "root") -> bool:
        """
        Equivalent to ansible.builtin.authorized_key
        """
        try:
            clean_key = public_key.strip()
            if not clean_key:
                return False
            import shlex

            quoted_key = shlex.quote(clean_key)
            # Ensure .ssh exists
            self.run("mkdir -p ~/.ssh && chmod 700 ~/.ssh", sudo=True)
            # Add key only if not already present
            check_cmd = f"grep -qxF {quoted_key} ~/.ssh/authorized_keys 2>/dev/null || echo {quoted_key} >> ~/.ssh/authorized_keys"
            self.run(check_cmd, sudo=True)
            self.run("chmod 600 ~/.ssh/authorized_keys", sudo=True)
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
        """Upload a file to the remote host using scp."""
        try:
            cmd = ["scp"]
            if self.port and self.port != 22:
                cmd.extend(["-P", str(self.port)])
            if self.key_filename:
                cmd.extend(["-i", self.key_filename])
            user_host = f"{self.user}@{self.host}" if self.user else self.host
            cmd.extend([local_path, f"{user_host}:{remote_path}"])
            result = subprocess.run(cmd, timeout=5400)
            if result.returncode != 0:
                console.print(f"[red]Failed to upload {local_path} to {remote_path}[/red]")
                return False
            return True
        except subprocess.TimeoutExpired:
            console.print(f"[red]Upload timed out after 90 minutes: {local_path}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Failed to upload {local_path} to {remote_path}: {e}[/red]")
            return False

    def get(self, remote_path: str, local_path: str) -> bool:
        """Download a file from the remote host using scp."""
        try:
            cmd = ["scp"]
            if self.port and self.port != 22:
                cmd.extend(["-P", str(self.port)])
            if self.key_filename:
                cmd.extend(["-i", self.key_filename])
            user_host = f"{self.user}@{self.host}" if self.user else self.host
            cmd.extend([f"{user_host}:{remote_path}", local_path])
            result = subprocess.run(cmd, timeout=5400)
            if result.returncode != 0:
                console.print(f"[red]Failed to download {remote_path} to {local_path}[/red]")
                return False
            return True
        except subprocess.TimeoutExpired:
            console.print(f"[red]Download timed out after 90 minutes: {remote_path}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Failed to download {remote_path} to {local_path}: {e}[/red]")
            return False

    def write_file(self, content: str, remote_path: str, mode: str = "0600", sudo: bool = False) -> bool:
        """
        Write string content to a remote file.
        If sudo=True, safely uploads to a temporary file first, then uses sudo install to place it.
        """
        try:
            import io
            import uuid

            if sudo:
                tmp_remote = f"/tmp/.cs_tmp_{uuid.uuid4().hex[:12]}"
                f = io.StringIO(content)
                self.connection.put(f, tmp_remote)
                self.run(f"sudo install -m {mode} {tmp_remote} {remote_path} && rm -f {tmp_remote}", sudo=True)
                return True
            else:
                f = io.StringIO(content)
                self.connection.put(f, remote_path)
                self.run(f"chmod {mode} {remote_path}", sudo=False)
                return True
        except Exception as e:
            console.print(f"[red]Failed to write to {remote_path}: {e}[/red]")
            return False
