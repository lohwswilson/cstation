from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

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
            "cat /etc/os-release": 'NAME="Ubuntu"\\nVERSION_ID="22.04"\\nID=ubuntu\\n',
            "uname -r": "6.8.0\\n",
            "lscpu": "CPU(s): 4\\nModel name: Intel Xeon\\n",
            "free -m": "Mem: 8192 0 0\\n",
            "lsblk -b -J": '{"blockdevices":[{"name":"sda","size":85899345920}]}',
            "ip -j a": "[]",
            "ip route": "default via 1.2.3.1 dev eth0\\n",
            "hostname": "sg05\\n",
            "command -v apt-get": "/usr/bin/apt-get\\n",
            "dpkg -s openssh-server >/dev/null 2>&1; echo $?": "0\\n",
            "dpkg -s docker.io >/dev/null 2>&1; echo $?": "1\\n",
        }
        return FakeResult(outputs.get(command, ""))

    monkeypatch.setattr("cstation.providers.hetzner.HetznerProvider.get_vps", fake_get_vps)
    monkeypatch.setattr("cstation.ssh.SSHManager.run", fake_run)

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

    out_path = tmp_path / "config" / "vps" / "prod_hel1_sg05.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("existing: true", encoding="utf-8")

    r = CliRunner().invoke(app, ["vps", "init", "hetzner/ANSIS:123456", "--out", str(out_path)])
    assert r.exit_code != 0
    assert "already exists" in r.output.lower()
    assert "vcpu" in r.output.lower()


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
