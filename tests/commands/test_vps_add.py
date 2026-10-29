from __future__ import annotations

import json
from pathlib import Path
import re

from typer.testing import CliRunner
import yaml

from cstation.config import config_manager, initialize_configuration
from cstation.main import app
from cstation.state import get_connection


def _reset_config() -> None:
    config_manager.config_data = {}
    config_manager.config_sources = []


def test_vps_add_help():
    r = CliRunner().invoke(app, ["vps", "add", "--help"])
    assert r.exit_code == 0
    clean_output = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", r.output)
    assert "--host" in clean_output
    assert "--skip-facts" in clean_output
    assert "--output" in clean_output


def test_vps_add_offline_creates_yaml(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    config_dir = home / ".config" / "cstation"
    config_dir.mkdir(parents=True, exist_ok=True)
    db_file = config_dir / "state.db"

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("CSTATION_STATE_DB", str(db_file))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    r = CliRunner().invoke(
        app,
        [
            "vps",
            "add",
            "offline-server",
            "--host",
            "192.0.2.1",
            "--user",
            "admin",
            "--port",
            "2222",
            "--stage",
            "staging",
            "--skip-facts",
        ],
    )
    assert r.exit_code == 0
    assert "Wrote" in r.output

    vps_file = config_dir / "vps" / "offline-server" / "vps.yaml"
    assert vps_file.exists()
    with vps_file.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["identity"]["name"] == "offline-server"
    assert data["identity"]["stage"] == "staging"
    assert data["access"]["host"] == "192.0.2.1"
    assert data["access"]["user"] == "admin"
    assert data["access"]["port"] == 2222
    assert "2222/tcp" in data["os"]["baseline"]["firewall"]["allow"]

    # Verify audit log entry in SQLite
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM audit_log WHERE command = 'vps add'").fetchone()
        assert row is not None
        assert row["target"] == "offline-server"
        assert row["status"] == "success"


def test_vps_add_json_output(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    config_dir = home / ".config" / "cstation"
    config_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("CSTATION_STATE_DB", str(config_dir / "state.db"))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    r = CliRunner().invoke(
        app,
        [
            "vps",
            "add",
            "json-box",
            "--host",
            "198.51.100.25",
            "--skip-facts",
            "--output",
            "json",
        ],
    )
    assert r.exit_code == 0
    res = json.loads(r.output)
    assert res["status"] == "created"
    assert res["name"] == "json-box"
    assert res["host"] == "198.51.100.25"
    assert res["probed"] is False


def test_vps_add_refuses_overwrite_without_force(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    config_dir = home / ".config" / "cstation"
    vps_file = config_dir / "vps" / "dup-box" / "vps.yaml"
    vps_file.parent.mkdir(parents=True, exist_ok=True)
    vps_file.write_text("existing: true\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("CSTATION_STATE_DB", str(config_dir / "state.db"))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    r1 = CliRunner().invoke(
        app,
        ["vps", "add", "dup-box", "--host", "10.0.0.1", "--skip-facts"],
    )
    assert r1.exit_code == 5
    assert "already exists" in r1.output

    r2 = CliRunner().invoke(
        app,
        ["vps", "add", "dup-box", "--host", "10.0.0.1", "--skip-facts", "--force"],
    )
    assert r2.exit_code == 0
    assert "Wrote" in r2.output


def test_vps_remove_with_json_and_audit(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    config_dir = home / ".config" / "cstation"
    vps_dir = config_dir / "vps" / "to-delete"
    vps_dir.mkdir(parents=True, exist_ok=True)
    (vps_dir / "vps.yaml").write_text(
        "apiVersion: cstation/v1\nkind: VPS\nidentity:\n  name: to-delete\naccess:\n  host: 1.2.3.4\n"
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("CSTATION_STATE_DB", str(config_dir / "state.db"))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    r = CliRunner().invoke(
        app,
        ["vps", "remove", "to-delete", "--force", "--output", "json"],
    )
    assert r.exit_code == 0
    res = json.loads(r.output)
    assert res["status"] == "removed"
    assert res["vps"] == "to-delete"
    assert not vps_dir.exists()

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM audit_log WHERE command = 'vps remove'").fetchone()
        assert row is not None
        assert row["target"] == "to-delete"
