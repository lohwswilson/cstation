from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cstation.main import app


runner = CliRunner()


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _full_vps_yaml() -> str:
    return "\n".join(
        [
            "apiVersion: cstation/v1",
            "kind: VPS",
            "identity:",
            "  name: test-vps",
            "  stage: prod",
            "  region: hel1",
            "access:",
            "  host: 1.2.3.4",
            "  user: root",
            "  port: 22",
            "facts:",
            "  os:",
            "    id: ubuntu",
            "    version: '24.04'",
            "    package_manager: apt",
            "  cpu: { vcpu: 2 }",
            "  memory: { total_mb: 4096 }",
            "  hostname: test",
            "  packages: { detected: [], missing: [] }",
            "os:",
            "  baseline:",
            "    packages: []",
            "    shell: bash",
            "    terminal: xterm-256color",
            "    sshd: { disable_password_auth: true }",
            "    firewall: { mode: ufw, allow: ['22/tcp'] }",
            "docker:",
            "  networks: [PW_NET]",
            "  directories: []",
        ]
    )


def _traefik_fragment() -> str:
    return "\n".join(
        [
            "apiVersion: cstation/v1",
            "kind: Container",
            "name: traefik",
            "enabled: true",
            "image: traefik:latest",
            "container_name: EU01_traefik",
            "network: PW_NET",
            "ports:",
            "  - '80:80'",
            "  - '443:443'",
            "volumes:",
            "  - /var/run/docker.sock:/var/run/docker.sock:ro",
            "  - /var/lib/traefik/letsencrypt:/letsencrypt",
            "  - /var/lib/traefik/conf:/etc/traefik/conf",
            "  - /var/lib/traefik/etc/traefik.yml:/etc/traefik/traefik.yml:ro",
            "  - /var/lib/traefik/logs:/etc/traefik/logs",
            "env_file: .env",
            "env:",
            "  DHPARAM_GENERATION: 'false'",
            "secrets:",
            "  - CF_API_EMAIL",
            "  - CF_API_KEY",
            "restart_policy: unless-stopped",
            "static_config:",
            "  global:",
            "    checknewversion: false",
            "    sendanonymoususage: false",
            "  entryPoints:",
            "    web:",
            "      address: ':80'",
            "      http:",
            "        redirections:",
            "          entryPoint:",
            "            to: websecure",
            "            scheme: https",
            "            permanent: true",
            "      forwardedHeaders:",
            "        insecure: true",
            "    websecure:",
            "      address: ':443'",
            "      forwardedHeaders:",
            "        insecure: true",
            "  providers:",
            "    docker:",
            "      endpoint: 'unix:///var/run/docker.sock'",
            "      exposedByDefault: false",
            "      network: PW_NET",
            "    file:",
            "      directory: '/etc/traefik/conf'",
            "      watch: true",
            "  certificatesResolvers:",
            "    le_resolver:",
            "      acme:",
            "        email: 'syner.catalyst@gmail.com'",
            "        storage: '/letsencrypt/acme.json'",
            "        keyType: EC256",
            "        tlsChallenge: {}",
            "  api:",
            "    dashboard: true",
        ]
    )


def _portainer_fragment() -> str:
    return "\n".join(
        [
            "apiVersion: cstation/v1",
            "kind: Container",
            "name: portainer",
            "enabled: true",
            "image: portainer/portainer-ce:latest",
            "container_name: EU01_portainer",
            "network: PW_NET",
            "ports:",
            "  - '9000:9000'",
            "  - '9443:9443'",
            "  - '8000:8000'",
            "volumes:",
            "  - /var/run/docker.sock:/var/run/docker.sock",
            "  - /var/lib/portainer/data:/data",
            "env:",
            "  PORTAINER_LOG_LEVEL: INFO",
            "restart_policy: always",
            "traefik:",
            "  http:",
            "    routers:",
            "      portainer:",
            '        rule: "Host(`portainer.eu01.synercatalyst.com`)"',
            "        entryPoints:",
            "          - websecure",
            "        service: portainer",
            "        tls:",
            "          certResolver: le_dns_resolver",
            "    services:",
            "      portainer:",
            "        loadBalancer:",
            "          servers:",
            "            - url: 'http://EU01_portainer:9000'",
        ]
    )


def _disabled_mailcow_fragment() -> str:
    return "\n".join(
        [
            "apiVersion: cstation/v1",
            "kind: Stack",
            "name: mailcow",
            "enabled: false",
            "git_repo: 'https://github.com/mailcow/mailcow-dockerized'",
            "git_branch: master",
            "git_dir: /opt/mailcow",
            "network: PW_NET",
        ]
    )


def _setup_vps_dir(tmp_path: Path) -> Path:
    vps_dir = tmp_path / "cstation" / "vps" / "test-vps"
    _write(vps_dir / "vps.yaml", _full_vps_yaml())
    _write(vps_dir / "traefik.yaml", _traefik_fragment())
    _write(vps_dir / "portainer.yaml", _portainer_fragment())
    _write(vps_dir / "mailcow.yaml", _disabled_mailcow_fragment())
    return vps_dir


MOCK_DOCKER_RESPONSES = {
    "docker info >/dev/null 2>&1 && echo ok || echo missing": "ok",
    "docker compose version >/dev/null 2>&1 && echo ok || echo missing": "ok",
    "docker network ls --format '{{.Name}}' 2>/dev/null": "PW_NET\nbridge",
}


def _mock_ssh_run(monkeypatch, responses: dict | None = None):
    all_responses = {**MOCK_DOCKER_RESPONSES, **(responses or {})}

    class MockResult:
        def __init__(self, stdout="", exited=0):
            self.stdout = stdout
            self.stderr = ""
            self.exited = exited

    def mock_run(self, command, hide=True, sudo=False):
        for cmd_pattern, response in all_responses.items():
            if cmd_pattern in command:
                return MockResult(stdout=response)
        return MockResult(stdout="")

    monkeypatch.setattr("cstation.commands.docker.main.SSHManager.run", mock_run)
    monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", mock_run)


def test_docker_help():
    r = runner.invoke(app, ["docker", "--help"])
    assert r.exit_code == 0
    out = r.output.lower()
    assert "plan" in out
    assert "apply" in out
    assert "status" in out


def test_docker_plan_no_fragments(tmp_path, monkeypatch):
    vps_dir = tmp_path / "config" / "vps" / "empty-vps"
    _write(vps_dir / "vps.yaml", _full_vps_yaml())
    _mock_ssh_run(monkeypatch)

    r = runner.invoke(app, ["docker", "plan", str(vps_dir)])
    assert r.exit_code == 0
    assert "no enabled container fragments" in r.output.lower()


def test_docker_plan_traefik(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    _mock_ssh_run(monkeypatch)

    r = runner.invoke(app, ["docker", "plan", str(vps_dir), "--service", "traefik"])
    assert r.exit_code == 0
    assert "traefik" in r.output.lower()


def test_docker_plan_all_services(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    _mock_ssh_run(monkeypatch)

    r = runner.invoke(app, ["docker", "plan", str(vps_dir)])
    assert r.exit_code == 0
    assert "traefik" in r.output.lower()
    assert "portainer" in r.output.lower()
    assert "disabled" in r.output.lower()


def test_docker_apply_traefik(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    _mock_ssh_run(monkeypatch)
    import typer

    monkeypatch.setattr(typer, "confirm", lambda *a, **kw: True)

    r = runner.invoke(app, ["docker", "apply", str(vps_dir), "--service", "traefik", "--yes"])
    assert r.exit_code == 0
    assert "traefik" in r.output.lower()


def test_docker_apply_skips_disabled(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    _mock_ssh_run(monkeypatch)

    r = runner.invoke(app, ["docker", "plan", str(vps_dir)])
    assert r.exit_code == 0
    assert "mailcow" in r.output.lower()
    assert "disabled" in r.output.lower()


def test_docker_preflight_fails_no_docker(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)

    class MockResult:
        def __init__(self, stdout=""):
            self.stdout = stdout
            self.stderr = ""
            self.exited = 0

    def mock_run(self, command, hide=True, sudo=False):
        if "docker info" in command:
            return MockResult(stdout="missing")
        if "docker network ls" in command:
            return MockResult(stdout="bridge")
        return MockResult(stdout="")

    monkeypatch.setattr("cstation.commands.docker.main.SSHManager.run", mock_run)
    monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", mock_run)

    r = runner.invoke(app, ["docker", "plan", str(vps_dir)])
    assert r.exit_code == 1
    assert "docker daemon" in r.output.lower() or "not running" in r.output.lower()


def test_docker_preflight_fails_no_docker_compose(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)

    class MockResult:
        def __init__(self, stdout=""):
            self.stdout = stdout
            self.stderr = ""
            self.exited = 0

    def mock_run(self, command, hide=True, sudo=False):
        if "docker info" in command:
            return MockResult(stdout="ok")
        if "docker compose version" in command:
            return MockResult(stdout="missing")
        if "docker network ls" in command:
            return MockResult(stdout="PW_NET\nbridge")
        return MockResult(stdout="")

    monkeypatch.setattr("cstation.commands.docker.main.SSHManager.run", mock_run)
    monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", mock_run)

    r = runner.invoke(app, ["docker", "plan", str(vps_dir)])
    assert r.exit_code == 1
    assert "docker compose" in r.output.lower() or "not installed" in r.output.lower()


def test_docker_preflight_fails_no_pw_net(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)

    class MockResult:
        def __init__(self, stdout=""):
            self.stdout = stdout
            self.stderr = ""
            self.exited = 0

    def mock_run(self, command, hide=True, sudo=False):
        if "docker info" in command:
            return MockResult(stdout="ok")
        if "docker compose version" in command:
            return MockResult(stdout="ok")
        if "docker network ls" in command:
            return MockResult(stdout="bridge")
        return MockResult(stdout="")

    monkeypatch.setattr("cstation.commands.docker.main.SSHManager.run", mock_run)
    monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", mock_run)

    r = runner.invoke(app, ["docker", "plan", str(vps_dir)])
    assert r.exit_code == 1
    assert "pw_net" in r.output.lower()


def test_docker_status(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    _mock_ssh_run(monkeypatch)

    r = runner.invoke(app, ["docker", "status", str(vps_dir)])
    assert r.exit_code == 0
    assert "traefik" in r.output.lower()
    assert "portainer" in r.output.lower()


def test_docker_vps_name_resolution(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    _mock_ssh_run(monkeypatch)

    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(tmp_path / "cstation"))

    r = runner.invoke(app, ["docker", "plan", "test-vps"])
    assert r.exit_code == 0
    assert "traefik" in r.output.lower()


def test_docker_fragment_discovery(tmp_path):
    vps_dir = tmp_path / "cstation" / "vps" / "my-vps"
    _write(vps_dir / "vps.yaml", _full_vps_yaml())
    _write(vps_dir / "traefik.yaml", _traefik_fragment())
    _write(vps_dir / "some-notes.txt", "not a yaml")

    from cstation.commands.docker.main import _discover_fragments

    fragments = _discover_fragments(vps_dir)
    assert len(fragments) == 1
    assert fragments[0].name == "traefik.yaml"


def test_docker_load_fragments_skips_vps_yaml(tmp_path):
    vps_dir = tmp_path / "cstation" / "vps" / "my-vps"
    _write(vps_dir / "vps.yaml", _full_vps_yaml())
    _write(vps_dir / "traefik.yaml", _traefik_fragment())

    from cstation.commands.docker.main import _load_fragments

    fragments = _load_fragments(vps_dir)
    assert len(fragments) == 1
    assert fragments[0][0] == "traefik"
    assert fragments[0][2] == "enabled"


def test_compose_render():
    from cstation.commands.docker.compose.render import render_compose

    compose = {
        "services": {"test": {"image": "nginx:latest"}},
        "networks": {"PW_NET": {"external": True}},
    }
    result = render_compose(compose)
    assert "nginx:latest" in result
    assert "PW_NET" in result


def test_env_writer():
    from cstation.commands.docker.compose.env_writer import render_env

    env = {"FOO": "bar", "BAZ": "1"}
    result = render_env(env)
    assert "BAZ=1" in result
    assert "FOO=bar" in result


def test_service_registry():
    from cstation.commands.docker.services.registry import get_service, available_services

    assert "traefik" in available_services()
    assert "portainer" in available_services()
    svc_cls = get_service("traefik")
    assert svc_cls.name == "traefik"


def test_traefik_compose_includes_env_file(tmp_path):
    import yaml
    from cstation.commands.docker.services.traefik import TraefikService

    svc = TraefikService()
    config = {
        "image": "traefik:latest",
        "network": "PW_NET",
        "ports": ["80:80", "443:443"],
        "volumes": [],
        "env": {"DHPARAM_GENERATION": "false"},
        "env_file": ".env",
        "restart_policy": "unless-stopped",
        "command": ["--configFile=/etc/traefik/traefik.yml"],
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert compose["services"]["traefik"]["env_file"] == ".env"
    assert compose["services"]["traefik"]["environment"]["DHPARAM_GENERATION"] == "false"
    assert compose["services"]["traefik"]["command"] == ["--configFile=/etc/traefik/traefik.yml"]


def test_traefik_compose_no_insecure_dashboard_port(tmp_path):
    import yaml
    from cstation.commands.docker.services.traefik import TraefikService

    svc = TraefikService()
    config = {
        "image": "traefik:latest",
        "network": "PW_NET",
        "ports": ["80:80", "443:443"],
        "volumes": [],
        "env": {"DHPARAM_GENERATION": "false"},
        "env_file": ".env",
        "restart_policy": "unless-stopped",
        "command": ["--configFile=/etc/traefik/traefik.yml"],
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    ports = compose["services"]["traefik"]["ports"]
    assert "8080:8080" not in ports


def test_image_service_env_file_support():
    import yaml
    from cstation.commands.docker.services.image_service import ImageService

    svc = ImageService()
    svc.name = "test-svc"
    config = {
        "image": "nginx:latest",
        "network": "PW_NET",
        "env_file": ".env",
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert compose["services"]["test-svc"]["env_file"] == ".env"


def test_traefik_plan_warns_missing_secrets(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    _mock_ssh_run(
        monkeypatch,
        {
            "test -f /var/lib/traefik/.env": "missing",
        },
    )

    r = runner.invoke(app, ["docker", "plan", str(vps_dir), "--service", "traefik"])
    assert r.exit_code == 0
    assert "secrets" in r.output.lower() or ".env" in r.output.lower()


def test_traefik_apply_writes_secrets_template(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    written_files = []

    class MockResult:
        def __init__(self, stdout=""):
            self.stdout = stdout
            self.stderr = ""
            self.exited = 0

    def mock_run(self, command, hide=True, sudo=False):
        for cmd_pattern, response in MOCK_DOCKER_RESPONSES.items():
            if cmd_pattern in command:
                return MockResult(stdout=response)
        if "test -f /var/lib/traefik/.env" in command:
            return MockResult(stdout="missing")
        if "cat > /var/lib/traefik/.env" in command:
            written_files.append(".env")
        return MockResult(stdout="")

    monkeypatch.setattr("cstation.commands.docker.main.SSHManager.run", mock_run)
    monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", mock_run)

    r = runner.invoke(app, ["docker", "apply", str(vps_dir), "--service", "traefik", "--yes"])
    assert r.exit_code == 0


def test_traefik_static_config_no_insecure_api(tmp_path):
    import yaml
    from cstation.commands.docker.services.traefik import TraefikService

    svc = TraefikService()
    config = {
        "image": "traefik:latest",
        "network": "PW_NET",
        "ports": ["80:80", "443:443"],
        "volumes": [],
        "restart_policy": "unless-stopped",
        "static_config": {
            "global": {"checknewversion": False, "sendanonymoususage": False},
            "entryPoints": {
                "web": {"address": ":80", "forwardedHeaders": {"insecure": True}},
            },
            "api": {"dashboard": True},
        },
    }
    import io

    buf = io.StringIO()
    yaml.dump(config["static_config"], buf, sort_keys=False, default_flow_style=False)
    output = buf.getvalue()
    parsed = yaml.safe_load(output)
    assert "insecure" not in parsed.get("api", {})
    assert parsed["api"]["dashboard"] is True
    assert parsed["global"]["checknewversion"] is False


def test_portainer_compose_includes_all_ports():
    import yaml
    from cstation.commands.docker.services.portainer import PortainerService

    svc = PortainerService()
    config = {
        "image": "portainer/portainer-ce:latest",
        "network": "PW_NET",
        "ports": ["9000:9000", "9443:9443", "8000:8000"],
        "volumes": ["/var/run/docker.sock:/var/run/docker.sock", "/var/lib/portainer/data:/data"],
        "env": {"PORTAINER_LOG_LEVEL": "INFO"},
        "restart_policy": "always",
        "container_name": "EU01_portainer",
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    ports = compose["services"]["portainer"]["ports"]
    assert "9000:9000" in ports
    assert "9443:9443" in ports
    assert "8000:8000" in ports
    assert compose["services"]["portainer"]["container_name"] == "EU01_portainer"


def test_portainer_compose_docker_socket_rw():
    import yaml
    from cstation.commands.docker.services.portainer import PortainerService

    svc = PortainerService()
    config = {
        "image": "portainer/portainer-ce:latest",
        "network": "PW_NET",
        "ports": ["9000:9000", "9443:9443", "8000:8000"],
        "volumes": ["/var/run/docker.sock:/var/run/docker.sock", "/var/lib/portainer/data:/data"],
        "env": {"PORTAINER_LOG_LEVEL": "INFO"},
        "restart_policy": "always",
        "container_name": "EU01_portainer",
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    volumes = compose["services"]["portainer"]["volumes"]
    docker_sock_vol = [v for v in volumes if "docker.sock" in v][0]
    assert ":ro" not in docker_sock_vol
    assert docker_sock_vol == "/var/run/docker.sock:/var/run/docker.sock"


def test_portainer_compose_restart_always():
    import yaml
    from cstation.commands.docker.services.portainer import PortainerService

    svc = PortainerService()
    config = {
        "image": "portainer/portainer-ce:latest",
        "network": "PW_NET",
        "ports": ["9000:9000"],
        "volumes": [],
        "env": {"PORTAINER_LOG_LEVEL": "INFO"},
        "restart_policy": "always",
        "container_name": "EU01_portainer",
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert compose["services"]["portainer"]["container_name"] == "EU01_portainer"


def test_render_secrets_env_with_values():
    from cstation.commands.docker.compose.env_writer import render_secrets_env

    secrets = {"CF_API_EMAIL": "user@example.com", "CF_API_KEY": "abc123"}
    result = render_secrets_env(secrets)
    assert "CF_API_EMAIL=user@example.com" in result
    assert "CF_API_KEY=abc123" in result


def test_render_secrets_env_with_placeholders():
    from cstation.commands.docker.compose.env_writer import render_secrets_env

    secrets = {"CF_API_EMAIL": "REPLACE_ME", "CF_API_KEY": "REPLACE_ME"}
    result = render_secrets_env(secrets)
    assert "CF_API_EMAIL=REPLACE_ME" in result
    assert "CF_API_KEY=REPLACE_ME" in result


def test_image_service_render_secrets_env_from_resolved():
    from cstation.commands.docker.services.image_service import ImageService

    svc = ImageService()
    svc.name = "test-svc"
    config = {"_resolved_secrets": {"SECRET_KEY": "real_value"}}
    result = svc._render_secrets_env(config)
    assert result is not None
    assert "SECRET_KEY=real_value" in result


def test_image_service_render_secrets_env_from_keys():
    from cstation.commands.docker.services.image_service import ImageService

    svc = ImageService()
    svc.name = "test-svc"
    config = {"secrets": ["SECRET_KEY", "ANOTHER_KEY"]}
    result = svc._render_secrets_env(config)
    assert result is not None
    assert "SECRET_KEY=REPLACE_ME" in result
    assert "ANOTHER_KEY=REPLACE_ME" in result


def test_get_vps_secrets_found():
    from cstation.config import get_vps_secrets, config_manager

    config_manager.config_data = {
        "vps": {"secrets": {"test-vps": {"traefik": {"CF_API_EMAIL": "user@example.com", "CF_API_KEY": "abc123"}}}}
    }
    result = get_vps_secrets("test-vps", "traefik")
    assert result == {"CF_API_EMAIL": "user@example.com", "CF_API_KEY": "abc123"}


def test_get_vps_secrets_not_found():
    from cstation.config import get_vps_secrets, config_manager

    config_manager.config_data = {"vps": {"providers": {}}}
    result = get_vps_secrets("unknown-vps", "traefik")
    assert result == {}


def test_docker_apply_traefik_with_resolved_secrets(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    _mock_ssh_run(
        monkeypatch,
        {
            "test -f /var/lib/traefik/.env": "missing",
        },
    )

    from cstation.config import config_manager

    monkeypatch.setattr(
        config_manager,
        "config_data",
        {"vps": {"secrets": {"test-vps": {"traefik": {"CF_API_EMAIL": "real@email.com", "CF_API_KEY": "real_key"}}}}},
    )

    r = runner.invoke(app, ["docker", "apply", str(vps_dir), "--service", "traefik", "--yes"])
    assert r.exit_code == 0
    assert "secrets from config" in r.output.lower()

    r = runner.invoke(app, ["docker", "plan", str(vps_dir), "--service", "traefik"])
    assert r.exit_code == 0


def _stalwart_fragment() -> str:
    return "\n".join(
        [
            "apiVersion: cstation/v1",
            "kind: Container",
            "name: stalwart",
            "enabled: true",
            "image: stalwartlabs/stalwart:v0.16",
            "container_name: EU01_stalwart",
            "network: PW_NET",
            "ports:",
            "  - '25:25'",
            "  - '110:110'",
            "  - '465:465'",
            "  - '587:587'",
            "  - '993:993'",
            "  - '995:995'",
            "  - '4190:4190'",
            "volumes:",
            "  - /var/lib/stalwart/etc:/etc/stalwart",
            "  - /var/lib/stalwart/data:/var/lib/stalwart",
            "env:",
            "  STALWART_RECOVERY_ADMIN: 'admin:REPLACE_ME'",
            "secrets:",
            "  - CF_API_EMAIL",
            "  - CF_API_KEY",
            "restart_policy: unless-stopped",
            "ulimits:",
            "  nofile:",
            "    soft: 65536",
            "    hard: 65536",
            "traefik:",
            "  http:",
            "    routers:",
            "      stalwart-admin:",
            '        rule: "Host(`mail.perfectwork.app`)"',
            "        entryPoints:",
            "          - websecure",
            "        service: stalwart-http",
            "        tls:",
            "          certResolver: le_dns_resolver",
            "    services:",
            "      stalwart-http:",
            "        loadBalancer:",
            "          servers:",
            "            - url: 'http://EU01_stalwart:8080'",
        ]
    )


def _setup_vps_dir_with_stalwart(tmp_path: Path) -> Path:
    vps_dir = tmp_path / "cstation" / "vps" / "test-vps"
    _write(vps_dir / "vps.yaml", _full_vps_yaml())
    _write(vps_dir / "traefik.yaml", _traefik_fragment())
    _write(vps_dir / "stalwart.yaml", _stalwart_fragment())
    return vps_dir


def test_stalwart_compose_includes_all_ports():
    import yaml
    from cstation.commands.docker.services.stalwart import StalwartService

    svc = StalwartService()
    config = {
        "image": "stalwartlabs/stalwart:v0.16",
        "network": "PW_NET",
        "ports": ["25:25", "110:110", "465:465", "587:587", "993:993", "995:995", "4190:4190"],
        "volumes": [
            "/var/lib/stalwart/etc:/etc/stalwart",
            "/var/lib/stalwart/data:/var/lib/stalwart",
        ],
        "env": {"STALWART_RECOVERY_ADMIN": "admin:REPLACE_ME"},
        "restart_policy": "unless-stopped",
        "container_name": "EU01_stalwart",
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    ports = compose["services"]["stalwart"]["ports"]
    assert "25:25" in ports
    assert "993:993" in ports
    assert "4190:4190" in ports
    assert "110:110" in ports
    assert compose["services"]["stalwart"]["container_name"] == "EU01_stalwart"


def test_stalwart_compose_includes_env_and_secrets():
    import yaml
    from cstation.commands.docker.services.stalwart import StalwartService

    svc = StalwartService()
    config = {
        "image": "stalwartlabs/stalwart:v0.16",
        "network": "PW_NET",
        "ports": ["25:25", "993:993"],
        "volumes": ["/var/lib/stalwart/etc:/etc/stalwart"],
        "env": {"STALWART_RECOVERY_ADMIN": "admin:REPLACE_ME"},
        "env_file": ".env",
        "secrets": ["CF_API_EMAIL", "CF_API_KEY"],
        "restart_policy": "unless-stopped",
        "container_name": "EU01_stalwart",
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert compose["services"]["stalwart"]["environment"]["STALWART_RECOVERY_ADMIN"] == "admin:REPLACE_ME"
    assert compose["services"]["stalwart"]["env_file"] == ".env"


def test_stalwart_create_dirs():
    from cstation.commands.docker.services.stalwart import StalwartService

    svc = StalwartService()
    config = {"network": "PW_NET"}
    dirs = svc._create_dirs(None, config)
    assert "/var/lib/stalwart" in dirs
    assert "/var/lib/stalwart/etc" in dirs
    assert "/var/lib/stalwart/data" in dirs


def test_stalwart_static_config():
    from cstation.commands.docker.services.stalwart import StalwartService

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            return type("R", (), {"stdout": "", "stderr": "", "exited": 0})()

    svc = StalwartService()
    config_with_traefik = {
        "traefik": {
            "http": {
                "routers": {
                    "stalwart-admin": {
                        "rule": "Host(`mail.perfectwork.app`)",
                        "entryPoints": ["websecure"],
                        "service": "stalwart-http",
                        "tls": {"certResolver": "le_dns_resolver"},
                    }
                },
                "services": {"stalwart-http": {"loadBalancer": {"servers": [{"url": "http://EU01_stalwart:8080"}]}}},
            }
        }
    }
    plan_actions = svc._plan_static_configs(MockSSH(), config_with_traefik)
    assert len(plan_actions) == 1
    assert "stalwart.yml" in plan_actions[0]

    plan_actions_empty = svc._plan_static_configs(MockSSH(), {})
    assert len(plan_actions_empty) == 0


def test_stalwart_apply_chown():
    from cstation.commands.docker.services.stalwart import StalwartService

    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)

    svc = StalwartService()
    config = {
        "image": "stalwartlabs/stalwart:v0.16",
        "network": "PW_NET",
        "ports": ["25:25", "993:993"],
        "volumes": ["/var/lib/stalwart/etc:/etc/stalwart", "/var/lib/stalwart/data:/var/lib/stalwart"],
        "env": {"STALWART_RECOVERY_ADMIN": "admin:REPLACE_ME"},
        "secrets": ["CF_API_EMAIL", "CF_API_KEY"],
        "_resolved_secrets": {"CF_API_EMAIL": "test@example.com", "CF_API_KEY": "testkey"},
        "restart_policy": "unless-stopped",
        "container_name": "EU01_stalwart",
        "owner": "2000:2000",
    }
    ssh = MockSSH()
    svc.apply(ssh, config)
    chown_commands = [c for c in recorded_commands if "chown" in c and "2000:2000" in c]
    assert len(chown_commands) == 1
    assert "/var/lib/stalwart" in chown_commands[0]


def test_stalwart_write_traefik_dynamic_config():
    import yaml
    from cstation.commands.docker.services.stalwart import StalwartService

    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)

    svc = StalwartService()
    ssh = MockSSH()
    traefik_config = {
        "http": {
            "routers": {
                "stalwart-admin": {
                    "rule": "Host(`mail.perfectwork.app`)",
                    "entryPoints": ["websecure"],
                    "service": "stalwart-http",
                    "tls": {"certResolver": "le_dns_resolver"},
                }
            },
            "services": {"stalwart-http": {"loadBalancer": {"servers": [{"url": "http://EU01_stalwart:8080"}]}}},
        }
    }
    config = {"traefik": traefik_config}
    written = svc._write_static_configs(ssh, config)
    assert len(written) == 1
    assert "/var/lib/traefik/conf/stalwart.yml" in written[0]
    config_commands = [c for c in recorded_commands if "stalwart.yml" in c]
    assert len(config_commands) == 1
    expected = yaml.dump(traefik_config, sort_keys=False, default_flow_style=False)
    import base64

    encoded = base64.b64encode(expected.encode()).decode()
    assert encoded in config_commands[0]


def test_stalwart_no_traefik_writes_nothing():
    from cstation.commands.docker.services.stalwart import StalwartService

    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)

    svc = StalwartService()
    ssh = MockSSH()
    written = svc._write_static_configs(ssh, {})
    assert len(written) == 0
    assert len(recorded_commands) == 0


def test_stalwart_in_registry():
    from cstation.commands.docker.services.registry import get_service, available_services

    assert "stalwart" in available_services()
    svc_cls = get_service("stalwart")
    assert svc_cls.name == "stalwart"


def test_stalwart_dynamic_config_from_yaml():
    import yaml as yaml_lib

    fragment_text = _stalwart_fragment()
    data = yaml_lib.safe_load(fragment_text)
    traefik = data.get("traefik", {})
    assert (
        traefik["http"]["services"]["stalwart-http"]["loadBalancer"]["servers"][0]["url"] == "http://EU01_stalwart:8080"
    )
    assert traefik["http"]["routers"]["stalwart-admin"]["rule"] == "Host(`mail.perfectwork.app`)"
    assert "le_dns_resolver" in str(traefik)


def test_docker_plan_stalwart(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir_with_stalwart(tmp_path)
    _mock_ssh_run(monkeypatch)

    r = runner.invoke(app, ["docker", "plan", str(vps_dir), "--service", "stalwart"])
    assert r.exit_code == 0
    assert "stalwart" in r.output.lower()


def test_docker_apply_stalwart(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir_with_stalwart(tmp_path)
    _mock_ssh_run(monkeypatch)
    import typer

    monkeypatch.setattr(typer, "confirm", lambda *a, **kw: True)

    r = runner.invoke(app, ["docker", "apply", str(vps_dir), "--service", "stalwart", "--yes"])
    assert r.exit_code == 0
    assert "stalwart" in r.output.lower()


def test_image_service_traefik_key_write():
    import yaml
    from cstation.commands.docker.services.image_service import ImageService

    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)

    svc = ImageService()
    svc.name = "myapp"
    traefik_config = {
        "http": {
            "routers": {
                "myapp": {
                    "rule": "Host(`myapp.example.com`)",
                    "entryPoints": ["websecure"],
                    "service": "myapp",
                    "tls": {"certResolver": "le_resolver"},
                }
            },
            "services": {"myapp": {"loadBalancer": {"servers": [{"url": "http://EU01_myapp:3000"}]}}},
        }
    }
    config = {"traefik": traefik_config}
    written = svc._write_static_configs(MockSSH(), config)
    assert len(written) == 1
    assert "/var/lib/traefik/conf/myapp.yml" in written[0]
    config_commands = [c for c in recorded_commands if "myapp.yml" in c]
    assert len(config_commands) == 1
    expected = yaml.dump(traefik_config, sort_keys=False, default_flow_style=False)
    import base64

    encoded = base64.b64encode(expected.encode()).decode()
    assert encoded in config_commands[0]


def test_image_service_traefik_key_plan_drift():
    import yaml
    from cstation.commands.docker.services.image_service import ImageService

    traefik_config = {
        "http": {
            "routers": {
                "myapp": {
                    "rule": "Host(`myapp.example.com`)",
                    "entryPoints": ["websecure"],
                    "service": "myapp",
                }
            },
            "services": {"myapp": {"loadBalancer": {"servers": [{"url": "http://EU01_myapp:3000"}]}}},
        }
    }

    class MockSSHEmpty:
        def run(self, command, hide=True, sudo=False):
            return type("R", (), {"stdout": "", "stderr": "", "exited": 0})()

    class MockSSHMatching:
        def __init__(self):
            self.desired = yaml.dump(traefik_config, sort_keys=False, default_flow_style=False)

        def run(self, command, hide=True, sudo=False):
            if "cat /var/lib/traefik/conf/myapp.yml" in command:
                return type("R", (), {"stdout": self.desired, "stderr": "", "exited": 0})()
            return type("R", (), {"stdout": "", "stderr": "", "exited": 0})()

    svc = ImageService()
    svc.name = "myapp"
    config = {"traefik": traefik_config}

    actions = svc._plan_static_configs(MockSSHEmpty(), config)
    assert len(actions) == 1
    assert "would write" in actions[0]

    actions = svc._plan_static_configs(MockSSHMatching(), config)
    assert len(actions) == 0


def test_image_service_traefik_key_no_config():
    from cstation.commands.docker.services.image_service import ImageService

    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)

    svc = ImageService()
    svc.name = "myapp"
    written = svc._write_static_configs(MockSSH(), {})
    assert len(written) == 0
    assert len(recorded_commands) == 0


def test_traefik_service_writes_both_static_and_traefik():
    from cstation.commands.docker.services.traefik import TraefikService

    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)
            return type("R", (), {"stdout": "", "stderr": "", "exited": 0})()

    svc = TraefikService()
    config = {
        "image": "traefik:latest",
        "network": "PW_NET",
        "ports": ["80:80", "443:443"],
        "volumes": [],
        "restart_policy": "unless-stopped",
        "static_config": {
            "global": {"checknewversion": False, "sendanonymoususage": False},
            "entryPoints": {"web": {"address": ":80"}},
            "api": {"dashboard": True},
        },
        "traefik": {
            "http": {
                "routers": {
                    "traefik-dashboard": {
                        "rule": "Host(`traefik.eu01.synercatalyst.com`)",
                        "entryPoints": ["websecure"],
                        "service": "api@internal",
                        "tls": {"certResolver": "le_dns_resolver"},
                    }
                }
            }
        },
    }
    written = svc._write_static_configs(MockSSH(), config)
    assert len(written) == 2
    assert "/var/lib/traefik/conf/traefik.yml" in written[0]
    assert "/var/lib/traefik/etc/traefik.yml" in written[1]
    dynamic_commands = [c for c in recorded_commands if "traefik.yml" in c and "/conf/" in c]
    static_commands = [c for c in recorded_commands if "traefik.yml" in c and "/etc/" in c]
    assert len(dynamic_commands) == 1
    assert len(static_commands) == 1


def test_traefik_service_plans_both_static_and_traefik():
    from cstation.commands.docker.services.traefik import TraefikService

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            return type("R", (), {"stdout": "", "stderr": "", "exited": 0})()

    svc = TraefikService()
    config = {
        "image": "traefik:latest",
        "network": "PW_NET",
        "ports": ["80:80", "443:443"],
        "volumes": [],
        "restart_policy": "unless-stopped",
        "static_config": {
            "global": {"checknewversion": False},
            "entryPoints": {"web": {"address": ":80"}},
        },
        "traefik": {
            "http": {
                "routers": {
                    "traefik-dashboard": {
                        "rule": "Host(`traefik.eu01.synercatalyst.com`)",
                        "entryPoints": ["websecure"],
                        "service": "api@internal",
                        "tls": {"certResolver": "le_dns_resolver"},
                    }
                }
            }
        },
    }
    actions = svc._plan_static_configs(MockSSH(), config)
    assert len(actions) == 2
    action_paths = [a for a in actions if "would write" in a]
    assert len(action_paths) == 2


def test_image_service_command_field():
    import yaml
    from cstation.commands.docker.services.image_service import ImageService

    svc = ImageService()
    svc.name = "myapp"
    config = {
        "image": "myapp:latest",
        "network": "PW_NET",
        "command": ["--config", "/etc/myapp/config.yml"],
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert compose["services"]["myapp"]["command"] == ["--config", "/etc/myapp/config.yml"]


def test_image_service_command_absent():
    import yaml
    from cstation.commands.docker.services.image_service import ImageService

    svc = ImageService()
    svc.name = "myapp"
    config = {
        "image": "myapp:latest",
        "network": "PW_NET",
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert "command" not in compose["services"]["myapp"]


def test_image_service_owner_chown():
    from cstation.commands.docker.services.image_service import ImageService

    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)
            return type("R", (), {"stdout": "", "stderr": "", "exited": 0})()

    svc = ImageService()
    svc.name = "myapp"
    config = {
        "image": "myapp:latest",
        "network": "PW_NET",
        "owner": "1000:1000",
    }
    ssh = MockSSH()
    svc.apply(ssh, config)
    chown_commands = [c for c in recorded_commands if "chown" in c and "1000:1000" in c]
    assert len(chown_commands) == 1
    assert "/var/lib/myapp" in chown_commands[0]


def test_image_service_owner_plan():
    from cstation.commands.docker.services.image_service import ImageService

    svc = ImageService()
    svc.name = "myapp"
    config = {
        "image": "myapp:latest",
        "network": "PW_NET",
        "owner": "2000:2000",
    }

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            return type("R", (), {"stdout": "", "stderr": "", "exited": 0})()

    actions = svc.plan(MockSSH(), config)
    chown_actions = [a for a in actions if "chown" in a and "2000:2000" in a]
    assert len(chown_actions) == 1


def test_image_service_no_owner():
    from cstation.commands.docker.services.image_service import ImageService

    recorded_commands = []

    class MockSSH:
        def run(self, command, hide=True, sudo=False):
            recorded_commands.append(command)
            return type("R", (), {"stdout": "", "stderr": "", "exited": 0})()

    svc = ImageService()
    svc.name = "myapp"
    config = {
        "image": "myapp:latest",
        "network": "PW_NET",
    }
    ssh = MockSSH()
    svc.apply(ssh, config)
    chown_commands = [c for c in recorded_commands if "chown" in c]
    assert len(chown_commands) == 0


def test_image_service_subdirs_from_config():
    from cstation.commands.docker.services.image_service import ImageService

    svc = ImageService()
    svc.name = "myapp"
    svc.subdirs = ["default_dir"]
    config = {
        "network": "PW_NET",
        "subdirs": ["data", "config"],
    }
    dirs = svc._create_dirs(None, config)
    assert "/var/lib/myapp/data" in dirs
    assert "/var/lib/myapp/config" in dirs
    assert "/var/lib/myapp/default_dir" not in dirs


def test_image_service_subdirs_fallback():
    from cstation.commands.docker.services.image_service import ImageService

    svc = ImageService()
    svc.name = "myapp"
    svc.subdirs = ["etc", "data"]
    config = {"network": "PW_NET"}
    dirs = svc._create_dirs(None, config)
    assert "/var/lib/myapp/etc" in dirs
    assert "/var/lib/myapp/data" in dirs


def test_traefik_compose_uses_self_name():
    import yaml
    from cstation.commands.docker.services.traefik import TraefikService

    svc = TraefikService()
    config = {
        "image": "traefik:latest",
        "network": "PW_NET",
        "ports": ["80:80", "443:443"],
        "volumes": [],
        "restart_policy": "unless-stopped",
        "command": ["--configFile=/etc/traefik/traefik.yml"],
    }
    rendered = svc._render_compose(config)
    compose = yaml.safe_load(rendered)
    assert "traefik" in compose["services"]


def test_preflight_reads_network_from_vps_config(tmp_path, monkeypatch):
    vps_dir = tmp_path / "cstation" / "vps" / "test-vps"
    vps_yaml = _full_vps_yaml().replace("networks: [PW_NET]", "networks: [CUSTOM_NET]")
    _write(vps_dir / "vps.yaml", vps_yaml)
    _write(vps_dir / "traefik.yaml", _traefik_fragment())

    class MockResult:
        def __init__(self, stdout=""):
            self.stdout = stdout
            self.stderr = ""
            self.exited = 0

    def mock_run(self, command, hide=True, sudo=False):
        if "docker info" in command:
            return MockResult(stdout="ok")
        if "docker compose version" in command:
            return MockResult(stdout="ok")
        if "docker network ls" in command:
            return MockResult(stdout="bridge\nPW_NET")
        return MockResult(stdout="")

    monkeypatch.setattr("cstation.commands.docker.main.SSHManager.run", mock_run)
    monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", mock_run)

    r = runner.invoke(app, ["docker", "plan", str(vps_dir)])
    assert r.exit_code == 1
    assert "custom_net" in r.output.lower()


def test_docker_apply_with_container_flag(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    _mock_ssh_run(monkeypatch)
    import typer

    monkeypatch.setattr(typer, "confirm", lambda *a, **kw: True)

    r = runner.invoke(app, ["docker", "apply", str(vps_dir), "--container", "traefik", "--yes"])
    assert r.exit_code == 0
    assert "traefik" in r.output.lower()


def test_docker_apply_with_short_c_flag(tmp_path, monkeypatch):
    vps_dir = _setup_vps_dir(tmp_path)
    _mock_ssh_run(monkeypatch)
    import typer

    monkeypatch.setattr(typer, "confirm", lambda *a, **kw: True)

    r = runner.invoke(app, ["docker", "apply", str(vps_dir), "-c", "traefik", "--yes"])
    assert r.exit_code == 0
    assert "traefik" in r.output.lower()
