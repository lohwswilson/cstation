from __future__ import annotations

import json as jsonlib
from typing import Any

import yaml
from rich.console import Console

from cstation.ssh import SSHManager

from .registry import register_service
from ..compose.render import render_compose
from ..compose.env_writer import render_env

console = Console()

_COMPOSE_BASE_DIR = "/var/lib"


class ImageService:
    kind: str = "Container"
    name: str = ""
    subdirs: list[str] = []
    compose_subdir: str = ""

    def __post_init_subclass__(self) -> None:
        if self.name:
            register_service(self.name, self.__class__)

    @property
    def service_dir(self) -> str:
        return f"{_COMPOSE_BASE_DIR}/{self.name}"

    @property
    def compose_path(self) -> str:
        d = self.compose_subdir or self.service_dir
        return f"{d}/docker-compose.yml"

    @property
    def env_path(self) -> str:
        d = self.compose_subdir or self.service_dir
        return f"{d}/.env"

    def _render_compose(self, config: dict) -> str:
        network = config.get("network", "PW_NET")
        service_def: dict[str, Any] = {
            "image": config.get("image", f"{self.name}:latest"),
        }
        if config.get("container_name") or True:
            service_def["container_name"] = config.get("container_name", self.name)
        if config.get("restart_policy"):
            service_def["restart"] = config["restart_policy"]
        if config.get("ports"):
            service_def["ports"] = config["ports"]
        if config.get("volumes"):
            service_def["volumes"] = config["volumes"]
        if config.get("env"):
            service_def["environment"] = config["env"]
        service_def["networks"] = [network]
        compose = {
            "services": {self.name: service_def},
            "networks": {network: {"external": True}},
        }
        return render_compose(compose)

    def _render_env(self, config: dict) -> str | None:
        env = config.get("env")
        if not env:
            return None
        return render_env(env)

    def _create_dirs(self, ssh: SSHManager, config: dict) -> list[str]:
        dirs = [self.compose_subdir or self.service_dir]
        for sd in self.subdirs:
            dirs.append(f"{self.service_dir}/{sd}")
        for d in config.get("extra_dirs", []):
            dirs.append(d)
        return dirs

    def _write_static_configs(self, ssh: SSHManager, config: dict) -> list[str]:
        return []

    def plan(self, ssh: SSHManager, config: dict) -> list[str]:
        actions: list[str] = []
        dirs = self._create_dirs(ssh, config)
        for d in dirs:
            result = ssh.run(f"test -d {d} && echo exists || echo missing", hide=True)
            status = getattr(result, "stdout", "").strip() if result else "missing"
            if status != "exists":
                actions.append(f"would create directory {d}")

        desired_compose = self._render_compose(config)
        result = ssh.run(f"cat {self.compose_path} 2>/dev/null", hide=True, sudo=True)
        current_compose = getattr(result, "stdout", "").strip() if result else ""
        if current_compose != desired_compose:
            actions.append(f"would write {self.compose_path}")

        desired_env = self._render_env(config)
        if desired_env is not None:
            result = ssh.run(f"cat {self.env_path} 2>/dev/null", hide=True)
            current_env = getattr(result, "stdout", "").strip() if result else ""
            if current_env != desired_env:
                actions.append(f"would write {self.env_path}")

        static_actions = self._plan_static_configs(ssh, config)
        actions.extend(static_actions)

        result = ssh.run(f"docker compose -f {self.compose_path} ps -q 2>/dev/null", hide=True, sudo=True)
        running = getattr(result, "stdout", "").strip() if result else ""
        if not running:
            actions.append(f"would run: docker compose up -d ({self.name})")

        return actions

    def _plan_static_configs(self, ssh: SSHManager, config: dict) -> list[str]:
        return []

    def apply(self, ssh: SSHManager, config: dict) -> None:
        console.print(f"  [bold]Applying {self.name}[/bold] (kind: Container)")

        dirs = self._create_dirs(ssh, config)
        for d in dirs:
            ssh.run(f"mkdir -p {d}", sudo=True)
            console.print(f"  [green]✓[/green] created directory {d}")

        desired_compose = self._render_compose(config)
        ssh.run(f"bash -c 'cat > {self.compose_path} << \"CSCOMPOSE\"\n{desired_compose}\nCSCOMPOSE'", sudo=True)
        console.print(f"  [green]✓[/green] wrote {self.compose_path}")

        desired_env = self._render_env(config)
        if desired_env is not None:
            ssh.run(f"bash -c 'cat > {self.env_path} << \"CSENV\"\n{desired_env}\nCSENV'", sudo=True)
            console.print(f"  [green]✓[/green] wrote {self.env_path}")

        self._write_static_configs(ssh, config)

        compose_dir = self.compose_subdir or self.service_dir
        ssh.run(f"cd {compose_dir} && docker compose up -d", sudo=True)
        console.print(f"  [green]✓[/green] docker compose up -d ({self.name})")

    def status(self, ssh: SSHManager, config: dict) -> dict:
        result = ssh.run(f"docker compose -f {self.compose_path} ps --format json 2>/dev/null", hide=True, sudo=True)
        containers = []
        if result and getattr(result, "stdout", "").strip():
            for line in result.stdout.strip().splitlines():
                try:
                    containers.append(jsonlib.loads(line))
                except (jsonlib.JSONDecodeError, ValueError):
                    pass
        running_count = sum(1 for c in containers if c.get("State") == "running")
        state = "running" if running_count > 0 else "stopped" if containers else "missing"
        return {
            "name": self.name,
            "kind": self.kind,
            "enabled": config.get("enabled", True),
            "state": state,
            "containers": len(containers),
            "running": running_count,
        }

    def stop(self, ssh: SSHManager, config: dict) -> None:
        compose_dir = self.compose_subdir or self.service_dir
        ssh.run(f"cd {compose_dir} && docker compose stop", sudo=True)
        console.print(f"  [green]✓[/green] stopped {self.name}")

    def restart(self, ssh: SSHManager, config: dict) -> None:
        compose_dir = self.compose_subdir or self.service_dir
        ssh.run(f"cd {compose_dir} && docker compose restart", sudo=True)
        console.print(f"  [green]✓[/green] restarted {self.name}")

    def remove(self, ssh: SSHManager, config: dict, purge: bool = False) -> None:
        compose_dir = self.compose_subdir or self.service_dir
        flag = "-v" if purge else ""
        ssh.run(f"cd {compose_dir} && docker compose down {flag}", sudo=True)
        if purge:
            ssh.run(f"rm -rf {self.service_dir}", sudo=True)
            console.print(f"  [green]✓[/green] removed {self.name} (purge)")
        else:
            console.print(f"  [green]✓[/green] removed {self.name}")

    def upgrade(self, ssh: SSHManager, config: dict) -> None:
        compose_dir = self.compose_subdir or self.service_dir
        ssh.run(f"cd {compose_dir} && docker compose pull", sudo=True)
        ssh.run(f"cd {compose_dir} && docker compose up -d", sudo=True)
        console.print(f"  [green]✓[/green] upgraded {self.name}")