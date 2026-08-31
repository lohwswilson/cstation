from __future__ import annotations

from typing import Union
from rich.console import Console

from cstation.ssh import SSHManager
from cstation.models import ContainerConfig

from .registry import register_service
from .image_service import ImageService, _ensure_config

console = Console()

ODOO_CONF_DEFAULTS = {
    "app_store": "install",
    "csv_internal_sep": ",",
    "data_dir": "/var/lib/odoo",
    "db_name": "False",
    "db_sslmode": "prefer",
    "db_template": "template1",
    "http_enable": "True",
    "http_interface": "",
    "http_port": "8069",
    "longpolling_port": "8072",
    "list_db": "True",
    "log_db": "False",
    "log_db_level": "warning",
    "log_handler": ":INFO",
    "logrotate": "True",
    "proxy_mode": "True",
    "transient_age_limit": "1.0",
    "unaccent": "False",
    "without_demo": "False",
}

ODOO_CONF_ORDER = [
    "addons_path",
    "app_store",
    "csv_internal_sep",
    "data_dir",
    "db_host",
    "db_port",
    "db_user",
    "db_name",
    "db_maxconn",
    "db_sslmode",
    "db_template",
    "dbfilter",
    "admin_passwd",
    "http_enable",
    "http_interface",
    "http_port",
    "longpolling_port",
    "list_db",
    "log_db",
    "log_db_level",
    "log_handler",
    "log_level",
    "logrotate",
    "max_cron_threads",
    "proxy_mode",
    "server_wide_modules",
    "unaccent",
    "without_demo",
    "workers",
    "limit_memory_soft",
    "limit_memory_hard",
    "limit_request",
    "limit_time_cpu",
    "limit_time_real",
    "transient_age_limit",
]

EXCLUDED_ODOO_KEYS = {"db_password"}


def _render_odoo_conf(odoo_conf: dict) -> str:
    merged = {**ODOO_CONF_DEFAULTS, **{k: v for k, v in odoo_conf.items() if k not in EXCLUDED_ODOO_KEYS and not k.startswith("_")}}
    if "db_name" not in odoo_conf:
        merged["db_name"] = "False"

    user_keys = [k for k in odoo_conf if k not in EXCLUDED_ODOO_KEYS and not k.startswith("_")]
    ordered_keys = []
    seen = set()
    for k in user_keys:
        if k not in seen:
            ordered_keys.append(k)
            seen.add(k)
    for k in ODOO_CONF_ORDER:
        if k not in seen:
            ordered_keys.append(k)
            seen.add(k)
    for k in merged:
        if k not in seen:
            ordered_keys.append(k)
            seen.add(k)

    lines = ["[options]"]
    for k in ordered_keys:
        if k in merged:
            lines.append(f"{k} = {merged[k]}")
    return "\n".join(lines) + "\n"


class OdooService(ImageService):

    def _render_odoo_conf(self, config: Union[ContainerConfig, dict]) -> str | None:
        cfg = _ensure_config(config)
        if not cfg.odoo_conf:
            return None
        return _render_odoo_conf(cfg.odoo_conf)

    def _odoo_conf_path(self, config: Union[ContainerConfig, dict]) -> str | None:
        cfg = _ensure_config(config)
        data_path = self._data_volume_path(cfg)
        if data_path:
            return f"{data_path}/odoo.conf"
        return None

    def _db_container(self, config: Union[ContainerConfig, dict]) -> str | None:
        cfg = _ensure_config(config)
        return cfg.env.get("HOST")

    def _db_user(self, config: Union[ContainerConfig, dict]) -> str | None:
        cfg = _ensure_config(config)
        if cfg.odoo_conf and cfg.odoo_conf.get("db_user"):
            return cfg.odoo_conf["db_user"]
        return cfg.env.get("USER")

    def _db_password(self, config: Union[ContainerConfig, dict]) -> str | None:
        cfg = _ensure_config(config)
        resolved = getattr(cfg, "_resolved_secrets", {})
        if resolved.get("PASSWORD"):
            return resolved["PASSWORD"]
        if cfg.env.get("PASSWORD"):
            return cfg.env["PASSWORD"]
        return None

    def _create_db_user(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> None:
        cfg = _ensure_config(config)
        db_container = self._db_container(cfg)
        db_user = self._db_user(cfg)
        db_password = self._db_password(cfg)
        if not db_container or not db_user:
            console.print("  [yellow]⚠[/yellow] skipping DB user creation: missing HOST or USER")
            return
        escaped_password = (db_password or "").replace("'", "''")
        sql = (
            f"DO $$ BEGIN "
            f"CREATE USER \"{db_user}\" WITH PASSWORD '{escaped_password}' SUPERUSER; "
            f"EXCEPTION WHEN duplicate_object THEN NULL; "
            f"END $$;"
        )
        escaped_sql = sql.replace("$$", "\\$\\$")
        ssh.run(
            f"docker exec {db_container} psql -U postgres -c \"{escaped_sql}\"",
            sudo=True,
        )
        console.print(f"  [green]✓[/green] created DB user {db_user}")

    def _create_db_database(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> None:
        cfg = _ensure_config(config)
        if not cfg.odoo_db:
            return
        db_container = self._db_container(cfg)
        dbname = cfg.odoo_db.get("name") if isinstance(cfg.odoo_db, dict) else cfg.odoo_db
        owner = cfg.odoo_db.get("owner", self._db_user(cfg)) if isinstance(cfg.odoo_db, dict) else self._db_user(cfg)
        if not db_container or not dbname:
            return
        # Auto-refresh template1 collation to avoid version mismatch errors on PG15+
        ssh.run(
            f'docker exec {db_container} psql -U postgres -d template1 -c "ALTER DATABASE template1 REFRESH COLLATION VERSION;" 2>/dev/null || true',
            sudo=True,
            hide=True,
        )
        ssh.run(
            f'docker exec {db_container} psql -U postgres -c "SELECT \'CREATE DATABASE \\"{dbname}\\" OWNER \\"{owner}\\"\' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname=\'{dbname}\')\\gexec"',
            sudo=True,
        )
        console.print(f"  [green]✓[/green] created DB {dbname} owned by {owner}")

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

        odoo_conf_content = self._render_odoo_conf(cfg)
        if odoo_conf_content:
            odoo_conf_path = self._odoo_conf_path(cfg)
            if odoo_conf_path:
                result = ssh.run(f"cat {odoo_conf_path} 2>/dev/null", hide=True, sudo=True)
                current = getattr(result, "stdout", "").strip() if result else ""
                if current != odoo_conf_content.strip():
                    actions.append(f"would write {odoo_conf_path}")

            db_user = self._db_user(cfg)
            db_container = self._db_container(cfg)
            if db_container and db_user:
                result = ssh.run(
                    f'docker exec {db_container} psql -U postgres -c "SELECT 1 FROM pg_roles WHERE rolname=\'{db_user}\'" -t 2>/dev/null',
                    hide=True, sudo=True,
                )
                output = getattr(result, "stdout", "").strip() if result else ""
                if "1" not in output:
                    actions.append(f"would create DB user {db_user}")

            if cfg.odoo_db:
                dbname = cfg.odoo_db.get("name") if isinstance(cfg.odoo_db, dict) else cfg.odoo_db
                db_container = self._db_container(cfg)
                if db_container and dbname:
                    result = ssh.run(
                        f'docker exec {db_container} psql -U postgres -c "SELECT 1 FROM pg_database WHERE datname=\'{dbname}\'" -t 2>/dev/null',
                        hide=True, sudo=True,
                    )
                    output = getattr(result, "stdout", "").strip() if result else ""
                    if "1" not in output:
                        actions.append(f"would create DB database {dbname}")

        if cfg.owner:
            actions.append(f"would chown -R {cfg.owner} {self.service_dir}")
            data_path = self._data_volume_path(cfg)
            if data_path:
                actions.append(f"would chown -R {cfg.owner} {data_path}")

        if cfg.chmod:
            data_path = self._data_volume_path(cfg)
            if data_path:
                actions.append(f"would chmod -R {cfg.chmod} {data_path}")

        result = ssh.run(f"docker compose -f {self.compose_path} ps -q 2>/dev/null", hide=True, sudo=True)
        running = getattr(result, "stdout", "").strip() if result else ""
        if not running:
            actions.append(f"would run: docker compose up -d ({self.name})")

        return actions

    def apply(self, ssh: SSHManager, config: Union[ContainerConfig, dict]) -> None:
        cfg = _ensure_config(config)
        if getattr(cfg, "compose_dir", None):
            self.compose_subdir = cfg.compose_dir
        console.print(f"  [bold]Applying {self.name}[/bold] (kind: Container, service: Odoo)")

        dirs = self._create_dirs(ssh, cfg)
        for d in dirs:
            ssh.run(f"mkdir -p {d}", sudo=True)
            console.print(f"  [green]✓[/green] created directory {d}")

        desired_compose = self._render_compose(cfg)
        ssh.run(f"bash -c 'cat > {self.compose_path} << \"CSCOMPOSE\"\n{desired_compose}\nCSCOMPOSE'", sudo=True)
        console.print(f"  [green]✓[/green] wrote {self.compose_path}")

        desired_env = self._render_env(cfg)
        secrets_env = self._render_secrets_env(cfg)
        desired_env = secrets_env if secrets_env is not None else desired_env
        if desired_env is not None:
            ssh.run(f"bash -c 'cat > {self.env_path} << \"CSENV\"\n{desired_env}\nCSENV'", sudo=True)
            resolved = getattr(cfg, "_resolved_secrets", {})
            if resolved:
                console.print(f"  [green]✓[/green] wrote {self.env_path} (secrets from config)")
            elif cfg.secrets:
                console.print(f"  [green]✓[/green] wrote {self.env_path} (secrets template — set values in config.yaml)")
            else:
                console.print(f"  [green]✓[/green] wrote {self.env_path}")

        self._write_static_configs(ssh, cfg)

        odoo_conf_content = self._render_odoo_conf(cfg)
        if odoo_conf_content:
            odoo_conf_path = self._odoo_conf_path(cfg)
            data_path = self._data_volume_path(cfg)
            if odoo_conf_path and data_path:
                ssh.run(f"mkdir -p {data_path}", sudo=True)
                ssh.run(
                    f"bash -c 'cat > {odoo_conf_path} << \"CSODOOCONF\"\n{odoo_conf_content}CSODOOCONF'",
                    sudo=True,
                )
                console.print(f"  [green]✓[/green] wrote {odoo_conf_path}")

                if cfg.owner:
                    ssh.run(f"chown {cfg.owner} {odoo_conf_path}", sudo=True)

        self._create_db_user(ssh, cfg)
        self._create_db_database(ssh, cfg)

        if cfg.owner:
            ssh.run(f"chown -R {cfg.owner} {self.service_dir}", sudo=True)
            console.print(f"  [green]✓[/green] chown {self.service_dir} to {cfg.owner}")
            data_path = self._data_volume_path(cfg)
            if data_path:
                ssh.run(f"chown -R {cfg.owner} {data_path}", sudo=True)
                console.print(f"  [green]✓[/green] chown {data_path} to {cfg.owner}")

        if cfg.chmod:
            data_path = self._data_volume_path(cfg)
            if data_path:
                ssh.run(f"chmod -R {cfg.chmod} {data_path}", sudo=True)
                console.print(f"  [green]✓[/green] chmod {cfg.chmod} {data_path}")

        ssh.run(f"docker compose -f {self.compose_path} up -d", sudo=True)
        console.print(f"  [green]✓[/green] docker compose up -d ({self.name})")


register_service("odoo", OdooService)