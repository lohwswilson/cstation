from __future__ import annotations

from typing import Protocol

from cstation.ssh import SSHManager


class ContainerService(Protocol):
    name: str
    kind: str

    def plan(self, ssh: SSHManager, config: dict) -> list[str]:
        ...

    def apply(self, ssh: SSHManager, config: dict) -> None:
        ...

    def status(self, ssh: SSHManager, config: dict) -> dict:
        ...

    def stop(self, ssh: SSHManager, config: dict) -> None:
        ...

    def restart(self, ssh: SSHManager, config: dict) -> None:
        ...

    def remove(self, ssh: SSHManager, config: dict, purge: bool = False) -> None:
        ...

    def upgrade(self, ssh: SSHManager, config: dict) -> None:
        ...