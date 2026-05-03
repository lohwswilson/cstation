from __future__ import annotations

import yaml
from typing import Any, TYPE_CHECKING

from rich.console import Console

from cstation.ssh import SSHManager
if TYPE_CHECKING:
    from cstation.models import ContainerConfig

from .registry import register_service
from .image_service import ImageService

console = Console()


class TraefikService(ImageService):
    name = "traefik"
    subdirs = ["etc", "conf", "letsencrypt", "logs"]

    def _write_static_configs(self, ssh: SSHManager, config: ContainerConfig) -> list[str]:
        written = super()._write_static_configs(ssh, config)
        if config.static_config:
            traefik_yml_path = f"{self.service_dir}/etc/traefik.yml"
            content = yaml.dump(config.static_config, sort_keys=False, default_flow_style=False)
            ssh.run(f"bash -c 'cat > {traefik_yml_path} << \"CSCONFIG\"\n{content}\nCSCONFIG'", sudo=True)
            console.print(f"  [green]✓[/green] wrote {traefik_yml_path}")
            written.append(traefik_yml_path)
        return written

    def _plan_static_configs(self, ssh: SSHManager, config: ContainerConfig) -> list[str]:
        actions = super()._plan_static_configs(ssh, config)
        if config.static_config:
            traefik_yml_path = f"{self.service_dir}/etc/traefik.yml"
            desired = yaml.dump(config.static_config, sort_keys=False, default_flow_style=False).strip()
            result = ssh.run(f"cat {traefik_yml_path} 2>/dev/null", hide=True, sudo=True)
            current = getattr(result, "stdout", "").strip() if result else ""
            if current != desired:
                actions.append(f"would write {traefik_yml_path}")
        return actions


register_service("traefik", TraefikService)