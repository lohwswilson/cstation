"""
Tests for cstation docker rm command.
"""

from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
from typer.testing import CliRunner
from cstation.main import app

runner = CliRunner()


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _vps_yaml() -> str:
    return """apiVersion: cstation/v1
kind: VPS
identity:
  name: test-vps
  provider: static
access:
  host: 127.0.0.1
  user: root
  port: 22
"""


def _container_yaml() -> str:
    return """apiVersion: cstation/v1
kind: Container
name: test_container
image: nginx:alpine
enabled: true
ports:
  - "80:80"
"""


def test_docker_rm_dry_run():
    home = Path.home()
    vps_dir = home / ".config" / "cstation" / "vps" / "test-vps"
    _write(vps_dir / "vps.yaml", _vps_yaml())
    _write(vps_dir / "test_container.yaml", _container_yaml())

    result = runner.invoke(app, ["docker", "rm", "test-vps", "test_container", "--dry-run"])
    assert result.exit_code == 0
    assert "Docker Remove: test_container on test-vps" in result.output
    assert "Dry-run mode" in result.output
    assert (vps_dir / "test_container.yaml").exists()


@patch("cstation.commands.docker.main._ssh_from_config")
@patch("cstation.commands.docker.main._get_service_instance")
def test_docker_rm_yes(mock_get_svc, mock_ssh):
    home = Path.home()
    vps_dir = home / ".config" / "cstation" / "vps" / "test-vps"
    _write(vps_dir / "vps.yaml", _vps_yaml())
    c_yaml = vps_dir / "test_container.yaml"
    _write(c_yaml, _container_yaml())

    mock_service = MagicMock()
    mock_get_svc.return_value = mock_service

    result = runner.invoke(app, ["docker", "rm", "test-vps", "test_container", "--yes", "--purge-local", "--keep-secrets"])
    assert result.exit_code == 0
    mock_service.remove.assert_called_once()
    assert not c_yaml.exists()


@patch("cstation.commands.docker.main._ssh_from_config")
@patch("cstation.commands.docker.main._get_service_instance")
def test_docker_rm_archive_local(mock_get_svc, mock_ssh):
    home = Path.home()
    vps_dir = home / ".config" / "cstation" / "vps" / "test-vps"
    _write(vps_dir / "vps.yaml", _vps_yaml())
    c_yaml = vps_dir / "test_container.yaml"
    _write(c_yaml, _container_yaml())

    mock_service = MagicMock()
    mock_get_svc.return_value = mock_service

    result = runner.invoke(app, ["docker", "rm", "test-vps", "test_container", "--yes", "--archive", "--keep-secrets"])
    assert result.exit_code == 0
    assert not c_yaml.exists()
    assert (vps_dir / "test_container.yaml.disabled").exists()
