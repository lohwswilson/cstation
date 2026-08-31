"""
Tests for Odoo CLI commands (sync, backup, restore, update).
"""

from pathlib import Path
import pytest
from typer.testing import CliRunner
from cstation.main import app


class _FakeResult:
    def __init__(self, stdout="", exited=0, stderr=""):
        self.stdout = stdout
        self.stderr = stderr
        self.exited = exited


def _setup_vps(tmp_path: Path):
    vps_dir = tmp_path / "vps" / "sg01"
    vps_dir.mkdir(parents=True)
    (vps_dir / "vps.yaml").write_text("""
apiVersion: cstation/v1
kind: VPS
identity:
  name: sg01
access:
  host: 10.0.0.1
  user: root
  port: 22
""")
    (vps_dir / "SG01_DEV.yaml").write_text("""
apiVersion: cstation/v1
kind: Container
name: SG01_DEV
image: synercatalyst/perfectwork:latest
volumes:
  - /var/lib/perfectwork/SG01/CONTAINERS/SG01_DEV:/var/lib/odoo
env:
  HOST: SG01_DB
  USER: sg01_dev
""")
    return vps_dir


def test_odoo_update_executes_upgrade(monkeypatch, tmp_path: Path):
    vps_dir = _setup_vps(tmp_path)
    executed_cmds = []

    def mock_run(self, command: str, hide: bool = True, sudo: bool = False):
        executed_cmds.append(command)
        if "docker inspect" in command:
            return _FakeResult(stdout="true")
        return _FakeResult(stdout="", exited=0)

    monkeypatch.setattr("cstation.commands.odoo.main.SSHManager.run", mock_run)

    r = CliRunner().invoke(app, ["odoo", "update", str(vps_dir), "SG01_DEV", "-d", "testdb", "-m", "perfectwork_sg_be"])
    assert r.exit_code == 0
    assert "Module update completed successfully" in r.output
    assert any("odoo -d testdb -u perfectwork_sg_be --stop-after-init" in cmd for cmd in executed_cmds)
    assert any("restart" in cmd for cmd in executed_cmds)


def test_odoo_update_fails_if_container_not_running(monkeypatch, tmp_path: Path):
    vps_dir = _setup_vps(tmp_path)

    def mock_run(self, command: str, hide: bool = True, sudo: bool = False):
        if "docker inspect" in command:
            return _FakeResult(stdout="false")
        return _FakeResult(stdout="", exited=0)

    monkeypatch.setattr("cstation.commands.odoo.main.SSHManager.run", mock_run)

    r = CliRunner().invoke(app, ["odoo", "update", str(vps_dir), "SG01_DEV", "-d", "testdb"])
    assert r.exit_code != 0
    assert "not running" in r.output
