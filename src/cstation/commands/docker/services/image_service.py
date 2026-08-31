from __future__ import annotations

import base64
import json as jsonlib
from typing import Any, Union

import yaml
from rich.console import Console

from cstation.ssh import SSHManager
from cstation.models import ContainerConfig

from .registry import register_service
from ..compose.render import render_compose
from ..compose.env_writer import render_env, render_secrets_env

console = Console()

_COMPOSE_BASE_DIR = "/var/lib"


def _ensure_config(config: Union[ContainerConfig, dict]) -> ContainerConfig:
    if isinstance(config, ContainerConfig):
        return config
    if isinstance(config, dict):
        c = config.copy()
        resolved = c.pop("_resolved_secrets", None)
        model = ContainerConfig(**c)
        if resolved is not None:
            setattr(model, "_resolved_secrets", resolved)
        return model
    return config


class ImageService:
    kind: str = "Container"
    name: str = ""
    subdirs: list[str] = []
    compose_subdir: str = ""
    _traefik_conf_dir: str | None = None

    def __post_init_subclass__(self) -> None:
        if self.name:
            register_service(self.name, self.__class__)

    @classmethod
    def set_traefik_conf_dir(cls, path: str) -> None:
        cls._traefik_conf_dir = path

    @classmethod
    def reset_traefik_conf_dir(cls) -> None:
        cls._traefik_conf_dir = None

    @staticmethod
    def _resolve_host_path(config: Union[ContainerConfig, dict], container_path: str) -> str | None:
        cfg = _ensure_config(config)
        best_host = None
        best_cont_len = 0
        for volume in cfg.volumes:
            if not isinstance(volume, str) or ':' not in volume:
                continue
            host, cont = volume.split(':', 1)
            if cont == container_path:
                return host
            if container_path.startswith(cont + '/'):
                if len(cont) > best_cont_len:
                    best_cont_len = len(cont)
                    best_host = host + container_path[len(cont):]
        return best_host

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

    def _data_volume_path(self, config: Union[ContainerConfig, dict]) -> str | None:
        cfg = _ensure_config(config)
        for vol in cfg.volumes:
            if isinstance(vol, str) and ":/var/lib/odoo" in vol:
                return vol.split(":")[0]
        return None

    def _render_compose(self, config: Union[ContainerConfig, dict]) -> str:
        cfg = _ensure_config(config)
        network = cfg.network or "PW_NET"
        service_def: dict[str, Any] = {
            "image": cfg.image,
        }
        if cfg.container_name or True:
            service_def["container_name"] = cfg.container_name or self.name
        if cfg.restart or cfg.restart_policy:
            service_def["restart"] = cfg.restart_policy or cfg.restart
        if cfg.ports:
            service_def["ports"] = cfg.ports
        if cfg.volumes:
            service_def["volumes"] = cfg.volumes
        if cfg.env:
            if isinstance(cfg.env, dict):
                service_def["environment"] = {
                    k: str(v).lower() if isinstance(v, bool) else str(v)
                    for k, v in cfg.env.items()
                }
            elif isinstance(cfg.env, list):
                service_def["environment"] = cfg.env

        if getattr(cfg, "privileged", None) is not None:
            service_def["privileged"] = cfg.privileged

        if cfg.env_file:
            service_def["env_file"] = cfg.env_file
        elif cfg.secrets or cfg.env:
            service_def["env_file"] = ".env"

        if cfg.command:
            service_def["command"] = cfg.command

        if cfg.labels:
            service_def["labels"] = cfg.labels

        service_def["networks"] = [network]
        compose = {
            "services": {self.name: service_def},
            "networks": {network: {"external": True}},
        }
        return render_compose(compose)

    def _render_env(self, config: Union[ContainerConfig, dict]) -> str | None:
        cfg = _ensure_config(config)
        env = cfg.env or {}
        resolved = getattr(cfg, "_resolved_secrets", {})
        if resolved:
            merged = {**env, **resolved}
        else:
            if cfg.secrets:
                merged = {**env, **{k: "REPLACE_ME" for k in cfg.secrets}}
            elif env:
                merged = env
            else:
                return None
        return render_env(merged)

    def _create_dirs(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> list[str]:
        cfg = _ensure_config(config)
        dirs = [self.compose_subdir or self.service_dir]
        subdirs = cfg.subdirs or self.subdirs
        for sd in subdirs:
            dirs.append(f"{self.service_dir}/{sd}")
        for d in cfg.extra_dirs:
            dirs.append(d)
        return dirs

    def _traefik_conf_path(self, config: Union[ContainerConfig, dict]) -> str:
        cfg = _ensure_config(config)
        name = cfg.container_name or self.name
        if ImageService._traefik_conf_dir:
            return f"{ImageService._traefik_conf_dir}/{name}.yml"
        return f"/var/lib/traefik/conf/{name}.yml"

    def _write_static_configs(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> list[str]:
        cfg = _ensure_config(config)
        written = []
        if cfg.traefik:
            traefik_conf_path = self._traefik_conf_path(cfg)
            content = yaml.dump(cfg.traefik, sort_keys=False, default_flow_style=False)
            encoded = base64.b64encode(content.encode()).decode()
            ssh.run(
                f"echo {encoded} | base64 -d | sudo tee {traefik_conf_path} > /dev/null",
            )
            console.print(f"  [green]✓[/green] wrote {traefik_conf_path}")
            written.append(traefik_conf_path)
        return written

    def _plan_static_configs(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> list[str]:
        cfg = _ensure_config(config)
        actions = []
        if cfg.traefik:
            traefik_conf_path = self._traefik_conf_path(cfg)
            desired = yaml.dump(cfg.traefik, sort_keys=False, default_flow_style=False).strip()
            result = ssh.run(f"cat {traefik_conf_path} 2>/dev/null", hide=True, sudo=True)
            current = getattr(result, "stdout", "").strip() if result else ""
            if current != desired:
                actions.append(f"would write {traefik_conf_path}")
        return actions

    def _render_secrets_env(self, config: Union[ContainerConfig, dict]) -> str | None:
        cfg = _ensure_config(config)
        resolved = getattr(cfg, "_resolved_secrets", {})
        if not resolved and not cfg.secrets:
            return None
        if resolved:
            return render_secrets_env(resolved)
        return render_secrets_env({k: "REPLACE_ME" for k in cfg.secrets})

    def plan(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> list[str]:
        cfg = _ensure_config(config)
        if getattr(cfg, "compose_dir", None):
            self.compose_subdir = cfg.compose_dir
        actions: list[str] = []
        dirs = self._create_dirs(ssh, cfg)
        for d in dirs:
            result = ssh.run(f"test -d {d} && echo exists || echo missing", hide=True)
            status = getattr(result, "stdout", "").strip() if result else "missing"
            if status != "exists":
                actions.append(f"would create directory {d}")

        desired_compose = self._render_compose(cfg)
        result = ssh.run(f"cat {self.compose_path} 2>/dev/null", hide=True, sudo=True)
        current_compose = getattr(result, "stdout", "").strip() if result else ""
        if current_compose != desired_compose:
            actions.append(f"would write {self.compose_path}")

        desired_env = self._render_env(cfg)
        secrets_env = self._render_secrets_env(cfg)
        desired_env = secrets_env if secrets_env is not None else desired_env
        if desired_env is not None:
            result = ssh.run(f"cat {self.env_path} 2>/dev/null", hide=True)
            current_env = getattr(result, "stdout", "").strip() if result else ""
            if current_env != desired_env:
                actions.append(f"would write {self.env_path}")

        resolved = getattr(cfg, "_resolved_secrets", {})
        if cfg.secrets and not resolved:
            result = ssh.run(f"cat {self.env_path} 2>/dev/null", hide=True)
            env_content = getattr(result, "stdout", "") if result else ""
            missing = [k for k in cfg.secrets if f"{k}=REPLACE_ME" in env_content or k not in env_content]
            if missing:
                actions.append(f"[yellow]⚠[/yellow] secrets not configured in config.yaml: {', '.join(missing)}")

        static_actions = self._plan_static_configs(ssh, cfg)
        actions.extend(static_actions)

        if cfg.owner:
            actions.append(f"would chown -R {cfg.owner} {self.service_dir}")

        if cfg.chmod:
            data_path = self._data_volume_path(cfg)
            if data_path:
                actions.append(f"would chmod -R {cfg.chmod} {data_path}")

        result = ssh.run(f"docker compose -f {self.compose_path} ps -q 2>/dev/null", hide=True, sudo=True)
        running = getattr(result, "stdout", "").strip() if result else ""
        if not running:
            actions.append(f"would run: docker compose up -d ({self.name})")

        return actions

    def _start(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> None:
        result = ssh.run(f"docker compose -f {self.compose_path} up -d", sudo=True)
        if result and getattr(result, "exited", 0) == 0:
            console.print(f"  [green]✓[/green] docker compose up -d ({self.name})")
        else:
            stderr = getattr(result, "stderr", "") or getattr(result, "stdout", "") or ""
            console.print(f"  [red]✗[/red] docker compose up -d failed ({self.name}){': ' + stderr.strip() if stderr else ''}")

    def apply(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> None:
        cfg = _ensure_config(config)
        if getattr(cfg, "compose_dir", None):
            self.compose_subdir = cfg.compose_dir
        console.print(f"  [bold]Applying {self.name}[/bold] (kind: Container)")

        dirs = self._create_dirs(ssh, cfg)
        for d in dirs:
            ssh.run(f"mkdir -p {d}", sudo=True)
            console.print(f"  [green]✓[/green] created directory {d}")

        desired_compose = self._render_compose(cfg)
        encoded_compose = base64.b64encode(desired_compose.encode()).decode()
        ssh.run(f"echo {encoded_compose} | base64 -d | sudo tee {self.compose_path} > /dev/null", sudo=True)
        console.print(f"  [green]✓[/green] wrote {self.compose_path}")

        desired_env = self._render_env(cfg)
        secrets_env = self._render_secrets_env(cfg)
        desired_env = secrets_env if secrets_env is not None else desired_env
        if desired_env is not None:
            encoded_env = base64.b64encode(desired_env.encode()).decode()
            ssh.run(f"echo {encoded_env} | base64 -d | sudo tee {self.env_path} > /dev/null", sudo=True)
            resolved = getattr(cfg, "_resolved_secrets", {})
            if resolved:
                console.print(f"  [green]✓[/green] wrote {self.env_path} (secrets from config)")
            elif cfg.secrets:
                console.print(f"  [green]✓[/green] wrote {self.env_path} (secrets template — set values in config.yaml)")
            else:
                console.print(f"  [green]✓[/green] wrote {self.env_path}")

        self._write_static_configs(ssh, cfg)

        if cfg.owner:
            ssh.run(f"chown -R {cfg.owner} {self.service_dir}", sudo=True)
            console.print(f"  [green]✓[/green] chown {self.service_dir} to {cfg.owner}")

        if cfg.chmod:
            data_path = self._data_volume_path(cfg)
            if data_path:
                ssh.run(f"chmod -R {cfg.chmod} {data_path}", sudo=True)
                console.print(f"  [green]✓[/green] chmod {cfg.chmod} {data_path}")

        self._start(ssh, cfg)

    def status(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> dict:
        cfg = _ensure_config(config)
        if getattr(cfg, "compose_dir", None):
            self.compose_subdir = cfg.compose_dir
        # 1. Try docker compose first (managed state)
        result = ssh.run(f"docker compose -f {self.compose_path} ps --format json 2>/dev/null", hide=True, sudo=True)
        containers = []
        if result and getattr(result, "stdout", "").strip():
            for line in result.stdout.strip().splitlines():
                try:
                    containers.append(jsonlib.loads(line))
                except (jsonlib.JSONDecodeError, ValueError):
                    pass

        if containers:
            running_count = sum(1 for c in containers if c.get("State") in ("running", "Up"))
            state = "running" if running_count > 0 else "stopped"
            return {
                "name": self.name,
                "kind": self.kind,
                "enabled": cfg.enabled,
                "state": state,
                "containers": len(containers),
                "running": running_count,
                "managed": True
            }

        # 2. Fallback to raw docker inspect (imported/unmanaged state)
        c_name = cfg.container_name or self.name
        result = ssh.run(f"docker inspect --format '{{{{.State.Status}}}}' {c_name} 2>/dev/null", hide=True, sudo=True)
        raw_state = getattr(result, "stdout", "").strip() if result else ""

        if raw_state:
            state = "running" if raw_state == "running" else "stopped"
            return {
                "name": self.name,
                "kind": self.kind,
                "enabled": cfg.enabled,
                "state": f"{state} (unmanaged)",
                "containers": 1,
                "running": 1 if state == "running" else 0,
                "managed": False
            }

        return {
            "name": self.name,
            "kind": self.kind,
            "enabled": cfg.enabled,
            "state": "missing",
            "containers": 0,
            "running": 0,
            "managed": False
        }

    def stop(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> None:
        ssh.run(f"docker compose -f {self.compose_path} stop", sudo=True)
        console.print(f"  [green]✓[/green] stopped {self.name}")

    def restart(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> None:
        ssh.run(f"docker compose -f {self.compose_path} restart", sudo=True)
        console.print(f"  [green]✓[/green] restarted {self.name}")

    def remove(self, ssh: SSHManager, config: Union[ContainerConfig, dict], purge: bool = False) -> None:
        flag = "-v" if purge else ""
        ssh.run(f"docker compose -f {self.compose_path} down {flag}", sudo=True)
        if purge:
            ssh.run(f"rm -rf {self.service_dir}", sudo=True)
            console.print(f"  [green]✓[/green] removed {self.name} (purge)")
        else:
            console.print(f"  [green]✓[/green] removed {self.name}")

    def upgrade(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> None:
        ssh.run(f"docker compose -f {self.compose_path} pull", sudo=True)
        ssh.run(f"docker compose -f {self.compose_path} up -d", sudo=True)
        console.print(f"  [green]✓[/green] upgraded {self.name}")