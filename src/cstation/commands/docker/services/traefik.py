from __future__ import annotations

import yaml
from typing import Any, Union, TYPE_CHECKING

from rich.console import Console

from cstation.ssh import SSHManager
from cstation.models import ContainerConfig

from .registry import register_service
from .image_service import ImageService, _ensure_config

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

    def _resolve_traefik_yml_path(self, config: Union[ContainerConfig, dict]) -> str:
        cfg = _ensure_config(config)
        # 1. Explicit file mount for /etc/traefik/traefik.yml (US02-style)
        for volume in cfg.volumes:
            if isinstance(volume, str) and ':' in volume:
                host, cont = volume.split(':', 1)
                if cont == "/etc/traefik/traefik.yml":
                    return host

        # 2. Directory mount for /etc/traefik, derive traefik.yml path (SG06/SG07-style)
        host_dir = self._resolve_host_path(cfg, "/etc/traefik")
        if host_dir:
            return f"{host_dir}/traefik.yml"

        # 3. Fallback
        return f"{self.service_dir}/etc/traefik.yml"

    def _resolve_and_cache_traefik_conf_dir(self, config: Union[ContainerConfig, dict]) -> str:
        cfg = _ensure_config(config)
        host_conf = self._resolve_host_path(cfg, "/etc/traefik/conf")
        if host_conf:
            ImageService.set_traefik_conf_dir(host_conf)
            return host_conf
        host_dir = self._resolve_host_path(cfg, "/etc/traefik")
        if host_dir:
            conf_dir = f"{host_dir}/conf"
            ImageService.set_traefik_conf_dir(conf_dir)
            return conf_dir
        fallback = "/var/lib/traefik/conf"
        ImageService.set_traefik_conf_dir(fallback)
        return fallback

    def _render_compose(self, config: Union[ContainerConfig, dict]) -> str:
        cfg = _ensure_config(config)
        if not cfg.command and not cfg.static_config:
            cfg.command = TRAEFIK_DEFAULT_ARGS
        return super()._render_compose(cfg)

    def _write_static_configs(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> list[str]:
        cfg = _ensure_config(config)
        written = super()._write_static_configs(ssh, cfg)
        if cfg.static_config:
            traefik_yml_path = self._resolve_traefik_yml_path(cfg)
            content = yaml.dump(cfg.static_config, sort_keys=False, default_flow_style=False)
            ssh.run(f"bash -c 'cat > {traefik_yml_path} << \"CSCONFIG\"\n{content}\nCSCONFIG'", sudo=True)
            console.print(f"  [green]✓[/green] wrote {traefik_yml_path}")
            written.append(traefik_yml_path)
        return written

    def _plan_static_configs(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> list[str]:
        cfg = _ensure_config(config)
        actions = super()._plan_static_configs(ssh, cfg)
        if cfg.static_config:
            traefik_yml_path = self._resolve_traefik_yml_path(cfg)
            desired = yaml.dump(cfg.static_config, sort_keys=False, default_flow_style=False).strip()
            result = ssh.run(f"cat {traefik_yml_path} 2>/dev/null", hide=True, sudo=True)
            current = getattr(result, "stdout", "").strip() if result else ""
            if current != desired:
                actions.append(f"would write {traefik_yml_path}")
        return actions


register_service("traefik", TraefikService)