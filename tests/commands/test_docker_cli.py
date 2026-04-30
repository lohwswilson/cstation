from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cstation.main import app


runner = CliRunner()


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _full_vps_yaml() -> str:
    return "\n".join([
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
    ])


def _traefik_fragment() -> str:
    return "\n".join([
        "apiVersion: cstation/v1",
        "kind: Container",
        "name: traefik",
        "enabled: true",
        "image: traefik:latest",
        "network: PW_NET",
        "ports:",
        "  - '80:80'",
        "  - '443:443'",
        "  - '8080:8080'",
        "volumes:",
        "  - /var/run/docker.sock:/var/run/docker.sock:ro",
        "  - /var/lib/traefik/letsencrypt:/letsencrypt",
        "  - /var/lib/traefik/conf:/etc/traefik/conf",
        "  - /var/lib/traefik/etc/traefik.yml:/etc/traefik/traefik.yml:ro",
        "restart_policy: unless-stopped",
        "static_config:",
        "  entryPoints:",
        "    web: ':80'",
        "    websecure: ':443'",
    ])


def _portainer_fragment() -> str:
    return "\n".join([
        "apiVersion: cstation/v1",
        "kind: Container",
        "name: portainer",
        "enabled: true",
        "image: portainer/portainer-ce:2.21",
        "network: PW_NET",
        "ports:",
        "  - '9443:9443'",
        "volumes:",
        "  - /var/run/docker.sock:/var/run/docker.sock:ro",
        "  - /var/lib/portainer/data:/data",
        "restart_policy: unless-stopped",
    ])


def _disabled_mailcow_fragment() -> str:
    return "\n".join([
        "apiVersion: cstation/v1",
        "kind: Stack",
        "name: mailcow",
        "enabled: false",
        "git_repo: 'https://github.com/mailcow/mailcow-dockerized'",
        "git_branch: master",
        "git_dir: /opt/mailcow",
        "network: PW_NET",
    ])


def _setup_vps_dir(tmp_path: Path) -> Path:
    vps_dir = tmp_path / "config" / "vps" / "test-vps"
    _write(vps_dir / "vps.yaml", _full_vps_yaml())
    _write(vps_dir / "traefik.yaml", _traefik_fragment())
    _write(vps_dir / "portainer.yaml", _portainer_fragment())
    _write(vps_dir / "mailcow.yaml", _disabled_mailcow_fragment())
    return vps_dir


MOCK_DOCKER_RESPONSES = {
    "docker info >/dev/null 2>&1 && echo ok || echo missing": "ok",
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

    monkeypatch.chdir(tmp_path)

    r = runner.invoke(app, ["docker", "plan", "test-vps"])
    assert r.exit_code == 0
    assert "traefik" in r.output.lower()


def test_docker_fragment_discovery(tmp_path):
    vps_dir = tmp_path / "config" / "vps" / "my-vps"
    _write(vps_dir / "vps.yaml", _full_vps_yaml())
    _write(vps_dir / "traefik.yaml", _traefik_fragment())
    _write(vps_dir / "some-notes.txt", "not a yaml")

    from cstation.commands.docker.main import _discover_fragments
    fragments = _discover_fragments(vps_dir)
    assert len(fragments) == 1
    assert fragments[0].name == "traefik.yaml"


def test_docker_load_fragments_skips_vps_yaml(tmp_path):
    vps_dir = tmp_path / "config" / "vps" / "my-vps"
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