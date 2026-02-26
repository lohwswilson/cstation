from fabric import Connection
from rich.console import Console
from typing import Optional, Any, Union
from .config import Host

console = Console()

class RemoteHost:
    def __init__(self, target: Union[str, Host], user: Optional[str] = None, port: Optional[int] = None, key_filename: Optional[str] = None):
        if isinstance(target, Host):
            self.host = target.host
            self.user = target.user
            self.port = target.port
        else:
            self.host = target
            self.user = user or "root"
            self.port = port or 22
            
        self.key_filename = key_filename
        self.conn = Connection(
            host=self.host,
            user=self.user,
            port=self.port,
            connect_kwargs={"key_filename": key_filename} if key_filename else {}
        )

    def run(self, command: str, sudo: bool = False, hide: bool = False) -> Any:
        try:
            if sudo:
                return self.conn.sudo(command, hide=hide)
            return self.conn.run(command, hide=hide)
        except Exception as e:
            console.print(f"[red]Error on {self.host}: {e}[/red]")
            return None

    def put(self, local_path: str, remote_path: str):
        try:
            return self.conn.put(local_path, remote_path)
        except Exception as e:
            console.print(f"[red]Error uploading to {self.host}: {e}[/red]")
            return None

    def get(self, remote_path: str, local_path: str):
        try:
            return self.conn.get(remote_path, local_path)
        except Exception as e:
            console.print(f"[red]Error downloading from {self.host}: {e}[/red]")
            return None
