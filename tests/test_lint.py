"""
Tests for Lint Command in CStation CLI.
"""

import pytest
from cstation.commands.lint.main import _parse_port_binding, run_lint_checks


def test_parse_port_binding():
    assert _parse_port_binding("80") == ("0.0.0.0", 80, "tcp")
    assert _parse_port_binding("8069:8069") == ("0.0.0.0", 8069, "tcp")
    assert _parse_port_binding("127.0.0.1:5432:5432") == ("127.0.0.1", 5432, "tcp")
    assert _parse_port_binding("443:443/udp") == ("0.0.0.0", 443, "udp")


def test_run_lint_checks_passes():
    results = run_lint_checks()
    assert isinstance(results, dict)
    assert "total_checks" in results
    assert "issues" in results
    assert results["total_checks"] > 0
    assert results["passed"] is True


def test_run_lint_checks_flags_missing_secrets(tmp_path, monkeypatch):
    from cstation.commands.lint import main as lint_mod
    vps_dir = tmp_path / "vps" / "test.vps"
    vps_dir.mkdir(parents=True)
    (vps_dir / "vps.yaml").write_text("apiVersion: cstation/v1\nkind: VPS\nidentity:\n  name: test.vps\naccess:\n  host: 1.2.3.4\n")
    (vps_dir / "app.yaml").write_text("apiVersion: cstation/v1\nkind: Container\nname: app\nimage: nginx\nsecrets:\n  - MISSING_SECRET_KEY\n")
    monkeypatch.setattr(lint_mod, "CSTATION_VPS_DIR", tmp_path / "vps")
    monkeypatch.setattr(lint_mod, "CSTATION_IMAGES_DIR", tmp_path / "images")
    monkeypatch.setattr(lint_mod, "CSTATION_DNS_DIR", tmp_path / "dns")
    monkeypatch.setattr(lint_mod, "get_vps_secrets", lambda vps, c: {})

    results = lint_mod.run_lint_checks()
    secret_issues = [i for i in results["issues"] if i["rule"] == "secret:missing"]
    assert len(secret_issues) == 1
    assert "MISSING_SECRET_KEY" in secret_issues[0]["message"]
