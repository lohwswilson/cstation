from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from cstation.ssh import SSHManager
    from cstation.models import ContainerConfig


class ContainerService(Protocol):
    name: str
    kind: str

    def plan(self, ssh: SSHManager, config: ContainerConfig) -> list[str]: ...

    def apply(self, ssh: SSHManager, config: ContainerConfig) -> None: ...

    def status(self, ssh: SSHManager, config: ContainerConfig) -> dict: ...

    def stop(self, ssh: SSHManager, config: ContainerConfig) -> None: ...

    def restart(self, ssh: SSHManager, config: ContainerConfig) -> None: ...

    def remove(self, ssh: SSHManager, config: ContainerConfig, purge: bool = False) -> None: ...

    def upgrade(self, ssh: SSHManager, config: ContainerConfig) -> None: ...
