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

TRAEFIK_DEFAULT_ARGS = (
    "--api.dashboard=true --api.insecure=true "
    "--entrypoints.web.address=:80 "
    "--entrypoints.websecure.address=:443 "
    "--entrypoints.web.http.redirections.entrypoint.to=websecure "
    "--entrypoints.web.http.redirections.entrypoint.scheme=https "
    "--entrypoints.web.http.redirections.entrypoint.permanent=true "
    "--entrypoints.web.forwardedHeaders.insecure=true "
    "--entrypoints.web.forwardedHeaders.trustedIPs= "
    "--entrypoints.websecure.forwardedHeaders.insecure=true "
    "--entrypoints.websecure.forwardedHeaders.trustedIPs= "
    "--serversTransport.forwardingTimeouts.dialTimeout=10s "
    "--serversTransport.forwardingTimeouts.responseHeaderTimeout=120s "
    "--providers.file.directory=/etc/traefik/conf "
    "--providers.file.watch=true "
    "--providers.docker=true "
    "--providers.docker.watch=true "
    "--providers.docker.exposedByDefault=false "
    "--providers.docker.network=PW_NET "
    "--providers.docker.endpoint=unix:///var/run/docker.sock "
    "--certificatesresolvers.le_resolver.acme.tlschallenge=true "
    "--certificatesresolvers.le_resolver.acme.email=$CF_API_EMAIL "
    "--certificatesresolvers.le_resolver.acme.storage=/letsencrypt/acme.json "
    "--certificatesresolvers.le_resolver.acme.caserver=https://acme-v02.api.letsencrypt.org/directory "
    "--certificatesresolvers.le_dns_resolver.acme.dnschallenge=true "
    "--certificatesresolvers.le_dns_resolver.acme.dnschallenge.provider=cloudflare "
    "--certificatesresolvers.le_dns_resolver.acme.dnschallenge.delayBeforeCheck=15s "
    "--certificatesresolvers.le_dns_resolver.acme.dnschallenge.resolvers=1.1.1.1:53,1.0.0.1:53 "
    "--certificatesresolvers.le_dns_resolver.acme.email=$CF_API_EMAIL "
    "--certificatesresolvers.le_dns_resolver.acme.storage=/letsencrypt/acme_dns.json "
    "--certificatesresolvers.le_dns_resolver.acme.caserver=https://acme-v02.api.letsencrypt.org/directory "
    "--log.level=$TRAEFIK_LOG_LEVEL "
    "--log.filePath=/etc/traefik/logs/traefik.log "
    "--log.format=json "
    "--accesslog=true "
    "--accesslog.filePath=/etc/traefik/logs/access.log "
    "--accesslog.format=json "
    "--accesslog.bufferingSize=100 "
    "--certificatesresolvers.le_resolver.acme.keyType=EC256 "
    "--certificatesresolvers.le_dns_resolver.acme.keyType=EC256 "
    "--metrics.prometheus=true "
    "--metrics.prometheus.addEntryPointsLabels=true "
    "--metrics.prometheus.addServicesLabels=true "
    "--global.checknewversion=false "
    "--global.sendanonymoususage=false "
    "--ping=true"
)


class TraefikService(ImageService):
    name = "traefik"
    subdirs = ["etc", "conf", "letsencrypt", "logs"]

    def _render_compose(self, config: ContainerConfig) -> str:
        if not config.command:
            config.command = TRAEFIK_DEFAULT_ARGS
        return super()._render_compose(config)

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