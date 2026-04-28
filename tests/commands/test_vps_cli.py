from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

import typer

from cstation.config import config_manager, initialize_configuration
from cstation.main import app


def test_vps_help():
    r = CliRunner().invoke(app, ["vps", "--help"])
    assert r.exit_code == 0
    out = r.output.lower()
    assert "ls" in out
    assert "status" in out
    assert "create" not in out
    assert "delete" not in out
    assert "init" in out


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _reset_config() -> None:
    config_manager.config_data = {}
    config_manager.config_sources = []


def _normalize_output(text: str) -> str:
    no_ansi = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return re.sub(r"[^A-Za-z0-9/:._-]+", "", no_ansi)


def test_vps_ls_requires_token(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    _write(home / ".config" / "cstation" / "config.yml", "")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HETZNER_TOKEN", raising=False)
    _reset_config()
    initialize_configuration()

    monkeypatch.delenv("HETZNER_TOKEN", raising=False)
    r = CliRunner().invoke(app, ["vps", "ls"])
    assert r.exit_code != 0
    assert "no vps providers configured" in r.output.lower()


def test_vps_ls_aggregates_multiple_accounts(monkeypatch, tmp_path: Path):
    from cstation.providers.base import VPS, VPSStatus

    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    hetzner:",
                "      accounts:",
                "        personal:",
                "          token: t1",
                "        work:",
                "          token: t2",
                "",
            ]
        ),
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HETZNER_TOKEN", raising=False)
    _reset_config()
    initialize_configuration()

    def fake_list_vps(self):
        return [
            VPS(
                provider="hetzner",
                id=self.token,
                name="box",
                region="hel1",
                status=VPSStatus.RUNNING,
                ipv4="1.2.3.4",
                ipv6=None,
            )
        ]

    monkeypatch.setattr("cstation.providers.hetzner.HetznerProvider.list_vps", fake_list_vps)

    r = CliRunner().invoke(app, ["vps", "ls"])
    assert r.exit_code == 0
    normalized = _normalize_output(r.output)
    assert "personal:t1" in normalized
    assert "work:t2" in normalized


def test_vps_status_requires_account_when_multiple(monkeypatch, tmp_path: Path):
    from cstation.providers.base import VPS, VPSStatus

    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    hetzner:",
                "      accounts:",
                "        personal:",
                "          token: t1",
                "        work:",
                "          token: t2",
                "",
            ]
        ),
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HETZNER_TOKEN", raising=False)
    _reset_config()
    initialize_configuration()

    def fake_get_vps(self, *, id=None, name=None):
        return VPS(
            provider="hetzner",
            id=str(id or "unknown"),
            name=name or "box",
            region="hel1",
            status=VPSStatus.RUNNING,
            ipv4="1.2.3.4",
            ipv6=None,
        )

    monkeypatch.setattr("cstation.providers.hetzner.HetznerProvider.get_vps", fake_get_vps)

    r = CliRunner().invoke(app, ["vps", "status", "123"])
    assert r.exit_code != 0
    assert "multiple hetzner accounts" in r.output.lower()

    r2 = CliRunner().invoke(app, ["vps", "status", "personal:123"])
    assert r2.exit_code == 0
    assert "123" in r2.output


def test_vps_status_includes_allocated_resources_when_available(monkeypatch, tmp_path: Path):
    from cstation.providers.base import VPS, VPSStatus

    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    hetzner:",
                "      accounts:",
                "        personal:",
                "          token: t1",
                "",
            ]
        ),
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HETZNER_TOKEN", raising=False)
    _reset_config()
    initialize_configuration()

    def fake_get_vps(self, *, id=None, name=None):
        return VPS(
            provider="hetzner",
            id=str(id or "unknown"),
            name=name or "box",
            region="hel1",
            status=VPSStatus.RUNNING,
            ipv4="1.2.3.4",
            ipv6=None,
            vcpu=2,
            memory_mb=4096,
            disk_gb=80,
            bandwidth_gb=20000,
        )

    monkeypatch.setattr("cstation.providers.hetzner.HetznerProvider.get_vps", fake_get_vps)

    r = CliRunner().invoke(app, ["vps", "status", "personal:123"])
    assert r.exit_code == 0
    normalized = _normalize_output(r.output)
    assert "vCPU" in r.output
    assert "Memory" in r.output
    assert "Disk" in r.output
    assert "Bandwidth" in r.output
    assert "┏" in r.output


def test_vps_status_accepts_vultr_uuid_id(monkeypatch, tmp_path: Path):
    from cstation.providers.base import VPS, VPSStatus

    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    vultr:",
                "      accounts:",
                "        main:",
                "          token: v1",
                "",
            ]
        ),
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    instance_id = "3431427c-9755-4064-903e-7a3e8bc82791"

    def fake_get_vps(self, *, id=None, name=None):
        assert id == instance_id
        assert name is None
        return VPS(
            provider="vultr",
            id=instance_id,
            name="sg05",
            region="sgp",
            status=VPSStatus.RUNNING,
            ipv4="207.148.126.238",
            ipv6=None,
        )

    monkeypatch.setattr("cstation.providers.vultr.VultrProvider.get_vps", fake_get_vps)

    r = CliRunner().invoke(app, ["vps", "status", f"vultr/main:{instance_id}"])
    assert r.exit_code == 0
    assert instance_id in r.output
    assert "┏" in r.output


def test_vps_status_outputs_table(monkeypatch, tmp_path: Path):
    from cstation.providers.base import VPS, VPSStatus

    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    vultr:",
                "      accounts:",
                "        main:",
                "          token: v1",
                "",
            ]
        ),
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    instance_id = "3431427c-9755-4064-903e-7a3e8bc82791"

    def fake_get_vps(self, *, id=None, name=None):
        return VPS(
            provider="vultr",
            id=instance_id,
            name="sg05",
            region="sgp",
            status=VPSStatus.RUNNING,
            ipv4="207.148.126.238",
            ipv6=None,
            vcpu=2,
            memory_mb=4096,
            disk_gb=80,
            bandwidth_gb=2000,
            plan="vc2-1c-2gb",
        )

    monkeypatch.setattr("cstation.providers.vultr.VultrProvider.get_vps", fake_get_vps)

    r = CliRunner().invoke(app, ["vps", "status", f"vultr/main:{instance_id}"])
    assert r.exit_code == 0
    assert "┏" in r.output


def test_vps_init_help_examples():
    r = CliRunner().invoke(app, ["vps", "init", "--help"])
    assert r.exit_code == 0
    out = r.output
    assert "hetzner/ANSIS:123456" in out


def test_vps_init_writes_yaml(monkeypatch, tmp_path: Path):
    from cstation.providers.base import VPS, VPSStatus

    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    hetzner:",
                "      accounts:",
                "        ANSIS:",
                "          token: t1",
                "",
            ]
        ),
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    def fake_get_vps(self, *, id=None, name=None):
        assert id == "123456"
        return VPS(
            provider="hetzner",
            id="123456",
            name="sg05",
            region="hel1",
            status=VPSStatus.RUNNING,
            ipv4="1.2.3.4",
            ipv6=None,
        )

    class FakeResult:
        def __init__(self, stdout: str):
            self.stdout = stdout
            self.stderr = ""

    def fake_run(self, command: str, hide: bool = True, sudo: bool = False):
        outputs = {
            "cat /etc/os-release": 'NAME="Ubuntu"\nVERSION_ID="22.04"\nID=ubuntu\n',
            "uname -r": "6.8.0\n",
            "lscpu": "CPU(s): 4\nModel name: Intel Xeon\n",
            "free -m": "Mem: 8192 0 0\n",
            "lsblk -b -J": '{"blockdevices":[{"name":"sda","size":85899345920}]}',
            "ip -j a": "[]",
            "ip route": "default via 1.2.3.1 dev eth0\n",
            "hostname": "sg05\n",
            "command -v apt-get": "/usr/bin/apt-get\n",
            "dpkg -s openssh-server >/dev/null 2>&1; echo $?": "0\n",
            "dpkg -s docker.io >/dev/null 2>&1; echo $?": "1\n",
        }
        return FakeResult(outputs.get(command, ""))

    monkeypatch.setattr("cstation.providers.hetzner.HetznerProvider.get_vps", fake_get_vps)
    monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", fake_run)

    out_path = tmp_path / "config" / "vps" / "prod_hel1_sg05.yaml"
    r = CliRunner().invoke(
        app,
        ["vps", "init", "hetzner/ANSIS:123456", "--stage", "prod", "--out", str(out_path)],
    )
    assert r.exit_code == 0
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "identity:" in content
    assert "name: sg05" in content
    assert "region: hel1" in content
    assert "openssh-server" in content


def test_vps_init_refuses_overwrite(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    hetzner:",
                "      accounts:",
                "        ANSIS:",
                "          token: t1",
                "",
            ]
        ),
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    def fake_get_vps(self, *, id=None, name=None):
        from cstation.providers.base import VPS, VPSStatus
        return VPS(
            provider="hetzner",
            id="123456",
            name="sg05",
            region="hel1",
            status=VPSStatus.RUNNING,
            ipv4="1.2.3.4",
            ipv6=None,
        )

    monkeypatch.setattr("cstation.providers.hetzner.HetznerProvider.get_vps", fake_get_vps)

    out_path = tmp_path / "config" / "vps" / "prod_hel1_sg05.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("existing: true", encoding="utf-8")

    r = CliRunner().invoke(app, ["vps", "init", "hetzner/ANSIS:123456", "--out", str(out_path)])
    assert r.exit_code != 0
    assert "already exists" in r.output.lower()


def test_vps_ls_aggregates_multiple_providers(monkeypatch, tmp_path: Path):
    from cstation.providers.base import VPS, VPSStatus

    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  default_provider: hetzner",
                "  providers:",
                "    hetzner:",
                "      accounts:",
                "        personal:",
                "          token: t1",
                "    vultr:",
                "      accounts:",
                "        main:",
                "          token: v1",
                "",
            ]
        ),
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HETZNER_TOKEN", raising=False)
    _reset_config()
    initialize_configuration()

    def fake_h_list(self):
        return [
            VPS(
                provider="hetzner",
                id="111",
                name="hbox",
                region="hel1",
                status=VPSStatus.RUNNING,
                ipv4="1.2.3.4",
                ipv6=None,
            )
        ]

    def fake_v_list(self):
        return [
            VPS(
                provider="vultr",
                id="222",
                name="vbox",
                region="ewr",
                status=VPSStatus.RUNNING,
                ipv4="5.6.7.8",
                ipv6=None,
            )
        ]

    monkeypatch.setattr("cstation.providers.hetzner.HetznerProvider.list_vps", fake_h_list)
    monkeypatch.setattr("cstation.providers.vultr.VultrProvider.list_vps", fake_v_list)

    r = CliRunner().invoke(app, ["vps", "ls"])
    assert r.exit_code == 0
    normalized = _normalize_output(r.output)
    assert "hetzner" in normalized
    assert "vultr" in normalized
    assert "111" in normalized
    assert "222" in normalized


def test_vps_ls_provider_filter_vultr(monkeypatch, tmp_path: Path):
    from cstation.providers.base import VPS, VPSStatus

    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    vultr:",
                "      accounts:",
                "        main:",
                "          token: v1",
                "",
            ]
        ),
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    def fake_v_list(self):
        return [
            VPS(
                provider="vultr",
                id="222",
                name="vbox",
                region="ewr",
                status=VPSStatus.RUNNING,
                ipv4="5.6.7.8",
                ipv6=None,
            )
        ]

    monkeypatch.setattr("cstation.providers.vultr.VultrProvider.list_vps", fake_v_list)

    r = CliRunner().invoke(app, ["vps", "ls", "--provider", "vultr"])
    assert r.exit_code == 0
    normalized = _normalize_output(r.output)
    assert "main:222" in normalized


def test_vps_ls_continues_when_one_provider_account_auth_fails(monkeypatch, tmp_path: Path):
    from cstation.providers.base import VPS, VPSStatus
    from cstation.providers.errors import ProviderAuthError

    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    hetzner:",
                "      accounts:",
                "        personal:",
                "          token: t1",
                "    vultr:",
                "      accounts:",
                "        main:",
                "          token: v1",
                "",
            ]
        ),
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HETZNER_TOKEN", raising=False)
    _reset_config()
    initialize_configuration()

    def fake_h_list(self):
        return [
            VPS(
                provider="hetzner",
                id="111",
                name="hbox",
                region="hel1",
                status=VPSStatus.RUNNING,
                ipv4="1.2.3.4",
                ipv6=None,
            )
        ]

    def fake_v_list(self):
        raise ProviderAuthError("Vultr authentication failed")

    monkeypatch.setattr("cstation.providers.hetzner.HetznerProvider.list_vps", fake_h_list)
    monkeypatch.setattr("cstation.providers.vultr.VultrProvider.list_vps", fake_v_list)

    r = CliRunner().invoke(app, ["vps", "ls"])
    assert r.exit_code == 0
    assert "hbox" in r.output
    assert "Vultr authentication failed" in r.output


def test_vps_ls_fails_when_all_provider_accounts_auth_fail(monkeypatch, tmp_path: Path):
    from cstation.providers.errors import ProviderAuthError

    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    vultr:",
                "      accounts:",
                "        main:",
                "          token: v1",
                "",
            ]
        ),
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    def fake_v_list(self):
        raise ProviderAuthError("Vultr authentication failed")

    monkeypatch.setattr("cstation.providers.vultr.VultrProvider.list_vps", fake_v_list)

    r = CliRunner().invoke(app, ["vps", "ls"])
    assert r.exit_code == 2
    assert "Vultr authentication failed" in r.output


# ── plan / apply tests ──────────────────────────────────────────────


def _minimal_vps_yaml(tmp_path: Path) -> Path:
    """Write a minimal VPS config YAML and return its path."""
    cfg = tmp_path / "vps.yaml"
    cfg.write_text(
        "\n".join(
            [
                "apiVersion: cstation/v1",
                "kind: VPS",
                "identity:",
                "  name: testbox",
                "  stage: prod",
                "  region: hel1",
                "access:",
                "  host: 1.2.3.4",
                "  user: root",
                "  port: 22",
                "facts:",
                "  os:",
                "    id: ubuntu",
                "    package_manager: apt",
                "  packages:",
                "    detected: [openssh-server, curl]",
                "    missing: [fail2ban, docker.io]",
                "os:",
                "  baseline:",
                "    packages: [fail2ban, docker.io]",
                "    sshd:",
                "      disable_password_auth: true",
                "    firewall:",
                "      mode: ufw",
                "      allow:",
                "        - 22/tcp",
                "        - 80/tcp",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


class _FakeSSHResult:
    def __init__(self, stdout: str = "", exited: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.exited = exited
        self.stderr = stderr


def _make_fake_ssh(monkeypatch, responses: dict[str, str] | None = None):
    """Patch SSHManager.run to return canned responses."""
    if responses is None:
        responses = {}

    def fake_run(self, command: str, hide: bool = True, sudo: bool = False):
        output = responses.get(command, "")
        return _FakeSSHResult(stdout=output)

    monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", fake_run)
    # Also patch _ssh_from_config to skip real connections
    # (plan/apply construct their own SSHManager from the YAML)


def _skip_confirm(monkeypatch):
    """Auto-confirm the apply prompt."""
    monkeypatch.setattr(typer, "confirm", lambda *a, **kw: True)


def test_vps_plan_help():
    r = CliRunner().invoke(app, ["vps", "plan", "--help"])
    assert r.exit_code == 0
    assert "dry-run" in r.output.lower() or "plan" in r.output.lower()


def test_vps_apply_help():
    r = CliRunner().invoke(app, ["vps", "apply", "--help"])
    assert r.exit_code == 0
    assert "phase" in r.output.lower()


def test_vps_plan_shows_missing_packages(monkeypatch, tmp_path: Path):
    cfg = _minimal_vps_yaml(tmp_path)

    responses = {
        "dpkg -s openssh-server >/dev/null 2>&1; echo $?": "0",
        "dpkg -s fail2ban >/dev/null 2>&1; echo $?": "1",
        "dpkg -s docker.io >/dev/null 2>&1; echo $?": "1",
        "ufw status": "Status: inactive\n",
    }
    _make_fake_ssh(monkeypatch, responses)

    r = CliRunner().invoke(app, ["vps", "plan", str(cfg)])
    assert r.exit_code == 0
    assert "fail2ban" in r.output
    assert "docker.io" in r.output


def test_vps_apply_installs_packages(monkeypatch, tmp_path: Path):
    cfg = _minimal_vps_yaml(tmp_path)

    install_cmds_seen: list[str] = []

    def fake_run(self, command: str, hide: bool = True, sudo: bool = False):
        if "apt-get" in command and "install" in command:
            install_cmds_seen.append(command)
            return _FakeSSHResult(stdout="", exited=0)
        if command == "ufw status":
            return _FakeSSHResult(stdout="Status: active\n")
        if command.startswith("ufw status | grep"):
            return _FakeSSHResult(stdout="0")
        if command == "ufw status verbose | grep 'Default:'":
            return _FakeSSHResult(stdout="Default: deny (incoming)\n")
        if "PasswordAuthentication" in command and "grep" in command:
            return _FakeSSHResult(stdout="1")  # exit 1 = not found
        if command.startswith("sed -i") or "sshd_config.d" in command or "reload" in command:
            return _FakeSSHResult(stdout="", exited=0)
        if command.startswith("dpkg -s"):
            return _FakeSSHResult(stdout="1")
        if command == "ufw allow 22/tcp" or command == "ufw allow 80/tcp":
            return _FakeSSHResult(stdout="Rule added\n")
        if command == "ufw --force enable":
            return _FakeSSHResult(stdout="Firewall is active\n")
        return _FakeSSHResult(stdout="")

    monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", fake_run)
    _skip_confirm(monkeypatch)

    r = CliRunner().invoke(app, ["vps", "apply", str(cfg), "--yes"])
    assert r.exit_code == 0
    assert "packages" in r.output.lower()


def test_vps_apply_single_phase(monkeypatch, tmp_path: Path):
    cfg = _minimal_vps_yaml(tmp_path)

    ssh_calls: list[str] = []

    def fake_run(self, command: str, hide: bool = True, sudo: bool = False):
        ssh_calls.append(command)
        if "grep" in command and "PasswordAuthentication" in command:
            return _FakeSSHResult(stdout="", exited=1)
        if command.startswith("sed") or "sshd_config.d" in command or "reload" in command:
            return _FakeSSHResult(stdout="", exited=0)
        return _FakeSSHResult(stdout="")

    monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", fake_run)
    _skip_confirm(monkeypatch)

    r = CliRunner().invoke(app, ["vps", "apply", str(cfg), "--yes", "--phase", "sshd"])
    assert r.exit_code == 0
    assert "sshd" in r.output.lower()
    # Should NOT contain package-related commands
    assert "apt-get" not in " ".join(ssh_calls)


def test_vps_plan_invalid_config(tmp_path: Path):
    bad_cfg = tmp_path / "bad.yaml"
    bad_cfg.write_text("invalid: true\n", encoding="utf-8")
    r = CliRunner().invoke(app, ["vps", "plan", str(bad_cfg)])
    assert r.exit_code != 0


def test_vps_plan_nonexistent_config(tmp_path: Path):
    r = CliRunner().invoke(app, ["vps", "plan", str(tmp_path / "nope.yaml")])
    assert r.exit_code != 0
