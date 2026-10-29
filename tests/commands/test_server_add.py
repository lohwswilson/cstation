from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner
import yaml

from cstation.main import app


def test_server_add_creates_inventory(tmp_path: Path):
    inv_dir = tmp_path / "inventory"
    inv_dir.mkdir(parents=True, exist_ok=True)

    r = CliRunner().invoke(
        app,
        [
            "server",
            "add",
            "db-primary",
            "--host",
            "10.0.0.100",
            "--group",
            "databases",
            "--user",
            "postgres",
            "--port",
            "5432",
            "-i",
            str(inv_dir),
        ],
    )
    assert r.exit_code == 0
    assert "Added server db-primary" in r.output

    inv_file = inv_dir / "databases.yml"
    assert inv_file.exists()
    with inv_file.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "databases" in data
    assert "db-primary" in data["databases"]["hosts"]
    assert data["databases"]["hosts"]["db-primary"]["ansible_host"] == "10.0.0.100"
    assert data["databases"]["hosts"]["db-primary"]["ansible_user"] == "postgres"
    assert data["databases"]["hosts"]["db-primary"]["ansible_port"] == 5432


def test_server_add_duplicate_requires_force(tmp_path: Path):
    inv_dir = tmp_path / "inventory"
    inv_file = inv_dir / "web.yml"
    inv_dir.mkdir(parents=True, exist_ok=True)
    inv_file.write_text("web:\n  hosts:\n    web-01:\n      ansible_host: 1.1.1.1\n")

    r1 = CliRunner().invoke(
        app,
        [
            "server",
            "add",
            "web-01",
            "--host",
            "2.2.2.2",
            "--group",
            "web",
            "-i",
            str(inv_dir),
        ],
    )
    assert r1.exit_code == 1
    assert "already exists" in r1.output

    r2 = CliRunner().invoke(
        app,
        [
            "server",
            "add",
            "web-01",
            "--host",
            "2.2.2.2",
            "--group",
            "web",
            "-i",
            str(inv_dir),
            "--force",
        ],
    )
    assert r2.exit_code == 0
    assert "Added server web-01" in r2.output
