"""
Unit tests for CStation configuration export and import commands.
"""
from pathlib import Path
from typer.testing import CliRunner

from cstation.main import app


def test_config_path():
    r = CliRunner().invoke(app, ["config", "path"])
    assert r.exit_code == 0
    assert "CStation User Config:" in r.output


def test_config_export_and_import_dry_run(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("vps:\n  providers: {}\n")
    vps_dir = config_dir / "vps" / "node1"
    vps_dir.mkdir(parents=True)
    (vps_dir / "vps.yaml").write_text("apiVersion: cstation/v1\nkind: VPS\nidentity:\n  name: node1\n")

    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(config_dir))

    export_tar = tmp_path / "exported.tar.gz"
    r_exp = CliRunner().invoke(app, ["config", "export", "--out", str(export_tar)])
    assert r_exp.exit_code == 0
    assert "Successfully exported" in r_exp.output
    assert export_tar.exists()

    # Dry-run import
    r_imp = CliRunner().invoke(app, ["config", "import", str(export_tar), "--dry-run"])
    assert r_imp.exit_code == 0
    assert "Dry-run: Previewing import" in r_imp.output
    assert "vps/node1/vps.yaml" in r_imp.output
