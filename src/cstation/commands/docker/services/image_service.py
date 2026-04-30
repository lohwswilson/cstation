from __future__ import annotations

import json as jsonlib
from typing import Any

import yaml
from rich.console import Console

from cstation.ssh import SSHManager

from .registry import register_service
from ..compose.render import render_compose
from ..compose.env_writer import render_env, render_secrets_env

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
        if config.get("env_file"):
            service_def["env_file"] = config["env_file"]
        if config.get("ulimits"):
            service_def["ulimits"] = config["ulimits"]
        if config.get("command"):
            service_def["command"] = config["command"]
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
        subdirs = config.get("subdirs", self.subdirs)
        for sd in subdirs:
            dirs.append(f"{self.service_dir}/{sd}")
        for d in config.get("extra_dirs", []):
            dirs.append(d)
        return dirs

    def _write_static_configs(self, ssh: SSHManager, config: dict) -> list[str]:
        written = []
        traefik_config = config.get("traefik")
        if traefik_config:
            traefik_conf_path = f"/var/lib/traefik/conf/{self.name}.yml"
            content = yaml.dump(traefik_config, sort_keys=False, default_flow_style=False)
            ssh.run(
                f"bash -c 'cat > {traefik_conf_path} << \"CSCONFIG\"\n{content}\nCSCONFIG'",
                sudo=True,
            )
            console.print(f"  [green]✓[/green] wrote {traefik_conf_path}")
            written.append(traefik_conf_path)
        return written

    def _plan_static_configs(self, ssh: SSHManager, config: dict) -> list[str]:
        actions = []
        traefik_config = config.get("traefik")
        if traefik_config:
            traefik_conf_path = f"/var/lib/traefik/conf/{self.name}.yml"
            desired = yaml.dump(traefik_config, sort_keys=False, default_flow_style=False).strip()
            result = ssh.run(f"cat {traefik_conf_path} 2>/dev/null", hide=True, sudo=True)
            current = getattr(result, "stdout", "").strip() if result else ""
            if current != desired:
                actions.append(f"would write {traefik_conf_path}")
        return actions

    def _render_secrets_env(self, config: dict) -> str | None:
        resolved = config.get("_resolved_secrets")
        if resolved:
            return render_secrets_env(resolved)
        secrets_keys = config.get("secrets", [])
        if secrets_keys:
            return render_secrets_env({k: "REPLACE_ME" for k in secrets_keys})
        return None

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
        secrets_env = self._render_secrets_env(config)
        desired_env = secrets_env if secrets_env is not None else desired_env
        if desired_env is not None:
            result = ssh.run(f"cat {self.env_path} 2>/dev/null", hide=True)
            current_env = getattr(result, "stdout", "").strip() if result else ""
            if current_env != desired_env:
                actions.append(f"would write {self.env_path}")

        secrets_keys = config.get("secrets", [])
        resolved = config.get("_resolved_secrets", {})
        if secrets_keys and not resolved:
            result = ssh.run(f"cat {self.env_path} 2>/dev/null", hide=True)
            env_content = getattr(result, "stdout", "") if result else ""
            missing = [k for k in secrets_keys if f"{k}=REPLACE_ME" in env_content or k not in env_content]
            if missing:
                actions.append(f"[yellow]⚠[/yellow] secrets not configured in config.yaml: {', '.join(missing)}")

        static_actions = self._plan_static_configs(ssh, config)
        actions.extend(static_actions)

        owner = config.get("owner")
        if owner:
            actions.append(f"would chown -R {owner} {self.service_dir}")

        result = ssh.run(f"docker compose -f {self.compose_path} ps -q 2>/dev/null", hide=True, sudo=True)
        running = getattr(result, "stdout", "").strip() if result else ""
        if not running:
            actions.append(f"would run: docker compose up -d ({self.name})")

        return actions

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
        secrets_env = self._render_secrets_env(config)
        desired_env = secrets_env if secrets_env is not None else desired_env
        if desired_env is not None:
            ssh.run(f"bash -c 'cat > {self.env_path} << \"CSENV\"\n{desired_env}\nCSENV'", sudo=True)
            resolved = config.get("_resolved_secrets", {})
            if resolved:
                console.print(f"  [green]✓[/green] wrote {self.env_path} (secrets from config)")
            elif config.get("secrets"):
                console.print(f"  [green]✓[/green] wrote {self.env_path} (secrets template — set values in config.yaml)")
            else:
                console.print(f"  [green]✓[/green] wrote {self.env_path}")

        self._write_static_configs(ssh, config)

        owner = config.get("owner")
        if owner:
            ssh.run(f"chown -R {owner} {self.service_dir}", sudo=True)
            console.print(f"  [green]✓[/green] chown {self.service_dir} to {owner}")

        ssh.run(f"docker compose -f {self.compose_path} up -d", sudo=True)
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
        ssh.run(f"docker compose -f {self.compose_path} stop", sudo=True)
        console.print(f"  [green]✓[/green] stopped {self.name}")

    def restart(self, ssh: SSHManager, config: dict) -> None:
        ssh.run(f"docker compose -f {self.compose_path} restart", sudo=True)
        console.print(f"  [green]✓[/green] restarted {self.name}")

    def remove(self, ssh: SSHManager, config: dict, purge: bool = False) -> None:
        flag = "-v" if purge else ""
        ssh.run(f"docker compose -f {self.compose_path} down {flag}", sudo=True)
        if purge:
            ssh.run(f"rm -rf {self.service_dir}", sudo=True)
            console.print(f"  [green]✓[/green] removed {self.name} (purge)")
        else:
            console.print(f"  [green]✓[/green] removed {self.name}")

    def upgrade(self, ssh: SSHManager, config: dict) -> None:
        ssh.run(f"docker compose -f {self.compose_path} pull", sudo=True)
        ssh.run(f"docker compose -f {self.compose_path} up -d", sudo=True)
        console.print(f"  [green]✓[/green] upgraded {self.name}")