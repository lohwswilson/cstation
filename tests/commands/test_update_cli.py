"""
Unit tests for cstation update command.
"""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cstation.main import app
from cstation.commands.update.main import is_version_newer, detect_install_method

runner = CliRunner()


def test_is_version_newer():
    assert is_version_newer("1.0.1", "1.0.0") is True
    assert is_version_newer("2.0.0", "1.9.9") is True
    assert is_version_newer("1.0.0", "1.0.0") is False
    assert is_version_newer("0.1.21", "1.0.0") is False


def test_detect_install_method():
    method, path = detect_install_method()
    assert method in ("uv_tool_editable", "uv_tool_pypi", "uv_tool", "git_checkout", "unknown")


def test_update_check_only_table():
    with patch("cstation.commands.update.main.get_latest_pypi_version", return_value="1.0.0"):
        res = runner.invoke(app, ["update", "--check-only"])
        assert res.exit_code == 0
        assert "CStation current version:" in res.stdout
        assert "Latest PyPI version: v1.0.0" in res.stdout
        assert "CStation is up to date" in res.stdout


def test_update_check_only_json():
    with patch("cstation.commands.update.main.get_latest_pypi_version", return_value="1.0.0"):
        res = runner.invoke(app, ["update", "--check-only", "--output", "json"])
        assert res.exit_code == 0
        data = json.loads(res.stdout)
        assert data["installed_version"] == "1.0.0"
        assert data["latest_pypi_version"] == "1.0.0"
        assert data["update_available"] is False
        assert data["status"] == "up_to_date"


def test_update_check_only_update_available_json():
    with patch("cstation.commands.update.main.get_latest_pypi_version", return_value="2.0.0"):
        res = runner.invoke(app, ["update", "--check-only", "--output", "json"])
        assert res.exit_code == 0
        data = json.loads(res.stdout)
        assert data["latest_pypi_version"] == "2.0.0"
        assert data["update_available"] is True
        assert data["status"] == "update_available"


def test_update_execute_uv_tool_pypi():
    with patch("cstation.commands.update.main.detect_install_method", return_value=("uv_tool_pypi", None)), \
         patch("cstation.commands.update.main.shutil.which", return_value="/usr/local/bin/uv"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")
        res = runner.invoke(app, ["update", "--output", "json"])
        assert res.exit_code == 0
        data = json.loads(res.stdout)
        assert data["success"] is True
        assert data["install_method"] == "uv_tool_pypi"
