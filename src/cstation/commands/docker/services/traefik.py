from __future__ import annotations

import yaml
from typing import Any

from rich.console import Console

from cstation.ssh import SSHManager

from .registry import register_service
from .image_service import ImageService
from ..compose.render import render_compose

console = Console()


class TraefikService(ImageService):
    name = "traefik"
    subdirs = ["etc", "conf", "letsencrypt", "logs"]

    def _render_compose(self, config: dict) -> str:
        network = config.get("network", "PW_NET")
        service_def: dict[str, Any] = {
            "image": config.get("image", "traefik:latest"),
            "container_name": config.get("container_name", "traefik"),
            "restart": config.get("restart_policy", "unless-stopped"),
            "ports": config.get("ports", []),
            "volumes": config.get("volumes", []),
            "command": ["--configFile=/etc/traefik/traefik.yml"],
            "networks": [network],
        }
        compose = {
            "services": {"traefik": service_def},
            "networks": {network: {"external": True}},
        }
        return render_compose(compose)

    def _write_static_configs(self, ssh: SSHManager, config: dict) -> list[str]:
        static_config = config.get("static_config")
        if not static_config:
            return []
        traefik_yml_path = f"{self.service_dir}/etc/traefik.yml"
        content = yaml.dump(static_config, sort_keys=False, default_flow_style=False)
        ssh.run(f"bash -c 'cat > {traefik_yml_path} << \"CSCONFIG\"\n{content}\nCSCONFIG'", sudo=True)
        console.print(f"  [green]✓[/green] wrote {traefik_yml_path}")
        return [traefik_yml_path]

    def _plan_static_configs(self, ssh: SSHManager, config: dict) -> list[str]:
        static_config = config.get("static_config")
        if not static_config:
            return []
        traefik_yml_path = f"{self.service_dir}/etc/traefik.yml"
        desired = yaml.dump(static_config, sort_keys=False, default_flow_style=False)
        result = ssh.run(f"cat {traefik_yml_path} 2>/dev/null", hide=True, sudo=True)
        current = getattr(result, "stdout", "").strip() if result else ""
        if current != desired:
            return [f"would write {traefik_yml_path}"]
        return []


register_service("traefik", TraefikService)