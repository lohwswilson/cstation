from __future__ import annotations

from cstation.commands.docker.services.odoo import _render_odoo_conf, OdooService, ODOO_CONF_DEFAULTS


def _make_config(**overrides):
    base = {
        "image": "synercatalyst/odoo.18.0:latest",
        "container_name": "US02_DEV8_US02DB",
        "network": "PW_NET",
        "volumes": [
            "/var/lib/perfectwork/PW_ADDONS.18.0:/mnt",
            "/var/lib/perfectwork/PW.18.0:/usr/lib/python3/dist-packages/odoo",
            "/var/lib/perfectwork/US02/CONTAINERS/US02_DEV8_US02DB:/var/lib/odoo",
        ],
        "env": {
            "HOST": "US02_DB",
            "USER": "us02_dev8_us02db",
            "ODOO_RC": "/var/lib/odoo/odoo.conf",
        },
        "secrets": ["DB_PASSWORD"],
        "_resolved_secrets": {"PASSWORD": "Wengseng1@"},
        "restart_policy": "always",
        "odoo_conf": {
            "db_host": "US02_DB",
            "db_port": 5432,
            "db_user": "us02_dev8_us02db",
            "dbfilter": "^%d$",
            "admin_passwd": "Wengseng1@",
            "db_maxconn": 32,
            "addons_path": "/mnt, /mnt/ENTERPRISE, /mnt/OCA, /mnt/customers",
            "server_wide_modules": "web",
            "log_level": "info",
            "workers": 5,
            "max_cron_threads": 2,
            "limit_memory_soft": 1677721600,
            "limit_memory_hard": 1073741824,
            "limit_request": 8192,
            "limit_time_cpu": 1800,
            "limit_time_real": 3600,
        },
        "owner": "101:102",
        "chmod": "766",
        "traefik": {
            "http": {
                "routers": {
                    "us02-dev8": {
                        "rule": "HostRegexp(`{subdomain:[a-z0-9]+}.dev8.perfectwork.app`)",
                        "entryPoints": ["websecure"],
                        "middlewares": ["compress", "sslheader"],
                        "tls": {
                            "certResolver": "le_dns_resolver",
                            "domains": [{"main": "dev8.perfectwork.app", "sans": ["*.dev8.perfectwork.app"]}],
                        },
                        "service": "us02-dev8-main",
                    }
                },
                "services": {
                    "us02-dev8-main": {
                        "loadBalancer": {"servers": [{"url": "http://US02_DEV8_US02DB:8069"}]}
                    }
                },
            }
        },
    }
    base.update(overrides)
    return base


def test_render_odoo_conf_basic():
    odoo_conf = {
        "db_host": "US02_DB",
        "db_port": 5432,
        "db_user": "us02_dev8_us02db",
        "dbfilter": "^%d$",
        "admin_passwd": "Wengseng1@",
        "workers": 5,
    }
    result = _render_odoo_conf(odoo_conf)
    assert result.startswith("[options]")
    assert "db_host = US02_DB" in result
    assert "dbfilter = ^%d$" in result
    assert "workers = 5" in result


def test_render_odoo_conf_includes_db_name_false():
    result = _render_odoo_conf({"db_host": "US02_DB"})
    assert "db_name = False" in result


def test_render_odoo_conf_allows_custom_db_name():
    result = _render_odoo_conf({"db_host": "SG07_DB", "db_name": "SEQ8"})
    assert "db_name = SEQ8" in result


def test_render_odoo_conf_excludes_db_password():
    result = _render_odoo_conf({"db_host": "US02_DB", "db_password": "secret123"})
    assert "db_password" not in result


def test_render_odoo_conf_defaults_merged():
    result = _render_odoo_conf({"db_host": "SG07_DB"})
    assert "proxy_mode = True" in result
    assert "data_dir = /var/lib/odoo" in result
    assert "http_port = 8069" in result
    assert "longpolling_port = 8072" in result


def test_render_odoo_conf_user_overrides_defaults():
    result = _render_odoo_conf({"db_host": "SG07_DB", "workers": 10})
    assert "workers = 10" in result


def test_render_odoo_conf_excludes_underscore_keys():
    result = _render_odoo_conf({"db_host": "SG07_DB", "_internal": "should_not_appear"})
    assert "_internal = " not in result


def test_render_odoo_conf_ordering():
    result = _render_odoo_conf({
        "db_host": "SG07_DB",
        "addons_path": "/mnt/ansis",
        "dbfilter": "SEQ*",
    })
    lines = result.strip().splitlines()
    addons_idx = next(i for i, l in enumerate(lines) if l.startswith("addons_path"))
    dbfilter_idx = next(i for i, l in enumerate(lines) if l.startswith("dbfilter"))
    assert addons_idx < dbfilter_idx


def test_odoo_data_volume_path_found():
    svc = OdooService()
    svc.name = "US02_DEV8_US02DB"
    config = _make_config()
    path = svc._data_volume_path(config)
    assert path == "/var/lib/perfectwork/US02/CONTAINERS/US02_DEV8_US02DB"


def test_odoo_data_volume_path_missing():
    svc = OdooService()
    svc.name = "test"
    config = {"volumes": ["/some/path:/other"]}
    path = svc._data_volume_path(config)
    assert path is None


def test_odoo_conf_path():
    svc = OdooService()
    svc.name = "US02_DEV8_US02DB"
    config = _make_config()
    path = svc._odoo_conf_path(config)
    assert path == "/var/lib/perfectwork/US02/CONTAINERS/US02_DEV8_US02DB/odoo.conf"


def test_odoo_conf_path_missing_volume():
    svc = OdooService()
    svc.name = "test"
    config = {"volumes": ["/some/path:/other"]}
    path = svc._odoo_conf_path(config)
    assert path is None


def test_render_odoo_conf_from_service():
    svc = OdooService()
    svc.name = "US02_DEV8_US02DB"
    config = _make_config()
    result = svc._render_odoo_conf(config)
    assert result is not None
    assert "[options]" in result
    assert "db_host = US02_DB" in result
    assert "dbfilter = ^%d$" in result


def test_render_odoo_conf_none_when_no_odoo_conf():
    svc = OdooService()
    svc.name = "test"
    config = {"image": "nginx:latest"}
    result = svc._render_odoo_conf(config)
    assert result is None


def test_db_container_from_env():
    svc = OdooService()
    config = _make_config()
    assert svc._db_container(config) == "US02_DB"


def test_db_user_from_odoo_conf():
    svc = OdooService()
    config = _make_config()
    assert svc._db_user(config) == "us02_dev8_us02db"


def test_db_user_from_env():
    svc = OdooService()
    config = {"env": {"HOST": "US02_DB", "USER": "fallback_user"}}
    assert svc._db_user(config) == "fallback_user"


def test_db_password_from_secrets():
    svc = OdooService()
    config = _make_config()
    assert svc._db_password(config) == "Wengseng1@"


def test_db_password_from_env():
    svc = OdooService()
    config = {"env": {"HOST": "US02_DB", "PASSWORD": "env_pass"}}
    assert svc._db_password(config) == "env_pass"


def test_db_password_none():
    svc = OdooService()
    config = {"env": {"HOST": "US02_DB"}}
    assert svc._db_password(config) is None


def test_odoo_compose_includes_labels():
    import yaml
    from cstation.commands.docker.services.image_service import ImageService
    svc = ImageService()
    svc.name = "SG07_SEQ8"
    config = {
        "image": "synercatalyst/perfectwork7.0:latest",
        "network": "PW_NET",
        "labels": {
            "traefik.enable": "true",
            "traefik.http.routers.SG07_SEQ8.rule": "Host(`example.com`)",
        },
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert compose["services"]["SG07_SEQ8"]["labels"]["traefik.enable"] == "true"


def test_compose_labels_absent_when_not_set():
    import yaml
    from cstation.commands.docker.services.image_service import ImageService
    svc = ImageService()
    svc.name = "test"
    config = {"image": "nginx:latest", "network": "PW_NET"}
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert "labels" not in compose["services"]["test"]


def test_compose_privileged_true():
    import yaml
    from cstation.commands.docker.services.image_service import ImageService
    svc = ImageService()
    svc.name = "test"
    config = {"image": "nginx:latest", "network": "PW_NET", "privileged": True}
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert compose["services"]["test"]["privileged"] is True


def test_compose_privileged_absent_by_default():
    import yaml
    from cstation.commands.docker.services.image_service import ImageService
    svc = ImageService()
    svc.name = "test"
    config = {"image": "nginx:latest", "network": "PW_NET"}
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert "privileged" not in compose["services"]["test"]


def test_chmod_in_apply():
    from cstation.commands.docker.services.image_service import ImageService
    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)
            return type('R', (), {'stdout': '', 'stderr': '', 'exited': 0})()

    svc = ImageService()
    svc.name = "test"
    config = {
        "image": "nginx:latest",
        "network": "PW_NET",
        "volumes": [
            "/data/app:/var/lib/odoo",
        ],
        "owner": "101:102",
        "chmod": "766",
    }
    ssh = MockSSH()
    svc.apply(ssh, config)
    chmod_commands = [c for c in recorded_commands if "chmod" in c and "766" in c]
    assert len(chmod_commands) == 1
    assert "/data/app" in chmod_commands[0]


def test_chmod_in_plan():
    from cstation.commands.docker.services.image_service import ImageService
    svc = ImageService()
    svc.name = "test"
    config = {
        "image": "nginx:latest",
        "network": "PW_NET",
        "volumes": ["/data/app:/var/lib/odoo"],
        "owner": "101:102",
        "chmod": "766",
    }

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            return type('R', (), {'stdout': '', 'stderr': '', 'exited': 0})()

    actions = svc.plan(MockSSH(), config)
    chmod_actions = [a for a in actions if "chmod" in a and "766" in a]
    assert len(chmod_actions) == 1


def test_chmod_absent_when_not_set():
    from cstation.commands.docker.services.image_service import ImageService
    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)
            return type('R', (), {'stdout': '', 'stderr': '', 'exited': 0})()

    svc = ImageService()
    svc.name = "test"
    config = {
        "image": "nginx:latest",
        "network": "PW_NET",
        "volumes": ["/data/app:/var/lib/odoo"],
        "owner": "101:102",
    }
    ssh = MockSSH()
    svc.apply(ssh, config)
    chmod_commands = [c for c in recorded_commands if "chmod" in c and "766" not in c]
    data_chmod = [c for c in recorded_commands if "chmod" in c and "/data/app" in c]
    assert len(data_chmod) == 0


def test_odoo_service_in_registry():
    from cstation.commands.docker.services.registry import get_service, available_services
    assert "odoo" in available_services()
    svc = OdooService()
    assert svc.name == ""  # name set at instance level, not class level
    svc.name = "US02_DEV8_US02DB"
    assert svc.name == "US02_DEV8_US02DB"


def test_auto_detect_odoo_service_with_odoo_conf():
    from cstation.commands.docker.main import _get_service_instance
    config = {"odoo_conf": {"db_host": "US02_DB"}}
    svc = _get_service_instance("US02_DEV8_US02DB", "Container", config)
    assert isinstance(svc, OdooService)


def test_auto_detect_generic_without_odoo_conf():
    from cstation.commands.docker.main import _get_service_instance
    from cstation.commands.docker.services.image_service import ImageService
    config = {"image": "nginx:latest"}
    svc = _get_service_instance("myapp", "Container", config)
    assert isinstance(svc, ImageService)
    assert not isinstance(svc, OdooService)


def test_auto_detect_named_service_takes_priority():
    from cstation.commands.docker.main import _get_service_instance
    from cstation.commands.docker.services.traefik import TraefikService
    config = {"odoo_conf": {"db_host": "US02_DB"}}
    svc = _get_service_instance("traefik", "Container", config)
    assert isinstance(svc, TraefikService)


def test_create_db_user_command():
    svc = OdooService()
    svc.name = "US02_DEV8_US02DB"
    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)

    config = _make_config()
    ssh = MockSSH()
    svc._create_db_user(ssh, config)
    db_cmds = [c for c in recorded_commands if "psql" in c and "CREATE USER" in c]
    assert len(db_cmds) == 1
    assert "us02_dev8_us02db" in db_cmds[0]
    assert "US02_DB" in db_cmds[0]


def test_create_db_database_command():
    svc = OdooService()
    svc.name = "US02_DEV8_US02DB"
    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)

    config = _make_config()
    config["odoo_db"] = {"name": "DEV8", "owner": "us02_dev8_us02db"}
    ssh = MockSSH()
    svc._create_db_database(ssh, config)
    db_cmds = [c for c in recorded_commands if "CREATE DATABASE" in c or "pg_database" in c]
    assert len(db_cmds) == 1
    assert "DEV8" in db_cmds[0]


def test_create_db_database_skipped_when_absent():
    svc = OdooService()
    svc.name = "US02_DEV8_US02DB"
    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)

    config = _make_config()
    ssh = MockSSH()
    svc._create_db_database(ssh, config)
    db_cmds = [c for c in recorded_commands if "CREATE DATABASE" in c or "pg_database" in c]
    assert len(db_cmds) == 0


def test_odoo_apply_writes_conf():
    svc = OdooService()
    svc.name = "US02_DEV8_US02DB"
    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)
            return type('R', (), {'stdout': '', 'stderr': '', 'exited': 0})()

    config = _make_config()
    ssh = MockSSH()
    svc.apply(ssh, config)
    conf_cmds = [c for c in recorded_commands if "odoo.conf" in c and "CSODOOCONF" in c]
    assert len(conf_cmds) == 1


def test_odoo_apply_creates_db_user():
    svc = OdooService()
    svc.name = "US02_DEV8_US02DB"
    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)
            return type('R', (), {'stdout': '', 'stderr': '', 'exited': 0})()

    config = _make_config()
    ssh = MockSSH()
    svc.apply(ssh, config)
    db_cmds = [c for c in recorded_commands if "CREATE USER" in c]
    assert len(db_cmds) == 1
    assert "us02_dev8_us02db" in db_cmds[0]


def test_odoo_apply_chowns_conf():
    svc = OdooService()
    svc.name = "US02_DEV8_US02DB"
    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)
            return type('R', (), {'stdout': '', 'stderr': '', 'exited': 0})()

    config = _make_config()
    ssh = MockSSH()
    svc.apply(ssh, config)
    chown_cmds = [c for c in recorded_commands if "chown" in c and "odoo.conf" in c]
    assert len(chown_cmds) == 1
    assert "101:102" in chown_cmds[0]


def test_odoo_plan_checks_conf():
    svc = OdooService()
    svc.name = "US02_DEV8_US02DB"

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            return type('R', (), {'stdout': '', 'stderr': '', 'exited': 0})()

    config = _make_config()
    actions = svc.plan(MockSSH(), config)
    conf_actions = [a for a in actions if "odoo.conf" in a]
    assert len(conf_actions) >= 1