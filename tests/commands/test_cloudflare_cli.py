from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from cstation.main import app
from cstation.config import config_manager, initialize_configuration
from cstation.providers.cloudflare import DNSZone


def _reset_config():
    config_manager.config_data = {}
    config_manager.config_sources = []


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_cloudflare_help():
    r = CliRunner().invoke(app, ["cloudflare", "--help"])
    assert r.exit_code == 0
    assert "zones" in r.output
    assert "plan" in r.output
    assert "apply" in r.output


def test_cloudflare_plan_no_domain_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    _write(home / ".config" / "cstation" / "config.yaml", "cloudflare:\n  api_token: test\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    r = CliRunner().invoke(app, ["cloudflare", "plan", "nonexistent.example.com"])
    assert r.exit_code == 6
    assert "No DNS config found" in r.output


def test_cloudflare_apply_no_token(tmp_path, monkeypatch):
    dns_dir = tmp_path / "config" / "dns"
    dns_dir.mkdir(parents=True)
    _write(dns_dir / "example.com.yaml", "apiVersion: cstation/v1\nkind: DNS\ndomain: example.com\nrecords:\n  - name: mail\n    type: A\n    value: 1.2.3.4\n    ttl: 300\n")
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    _write(tmp_path / "home" / ".config" / "cstation" / "config.yaml", "")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    r = CliRunner().invoke(app, ["cloudflare", "apply", "example.com"])
    assert r.exit_code == 2
    assert "No Cloudflare API token" in r.output


def test_cloudflare_zones_with_token(tmp_path, monkeypatch):
    home = tmp_path / "home"
    _write(home / ".config" / "cstation" / "config.yaml", "cloudflare:\n  api_token: test-token\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    mock_provider = Mock()
    mock_provider.list_zones.return_value = [
        DNSZone(id="z1", name="example.com", status="active"),
        DNSZone(id="z2", name="ansis.com.sg", status="active"),
    ]
    with patch("cstation.commands.cloudflare.main.CloudflareProvider", return_value=mock_provider):
        r = CliRunner().invoke(app, ["cloudflare", "zones"])
    assert r.exit_code == 0
    assert "example.com" in r.output
    assert "ansis.com.sg" in r.output


def test_cloudflare_plan_with_records(tmp_path, monkeypatch):
    dns_dir = tmp_path / "config" / "dns"
    dns_dir.mkdir(parents=True)
    _write(dns_dir / "example.com.yaml", "apiVersion: cstation/v1\nkind: DNS\ndomain: example.com\nrecords:\n  - name: mail\n    type: A\n    value: 1.2.3.4\n    ttl: 300\n")
    home = tmp_path / "home"
    _write(home / ".config" / "cstation" / "config.yaml", "cloudflare:\n  api_token: test-token\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    from cstation.providers.cloudflare import DNSRecord

    mock_provider = Mock()
    mock_provider.get_zone_id.return_value = "zone123"
    mock_provider.list_records.return_value = []

    with patch("cstation.commands.cloudflare.main.CloudflareProvider", return_value=mock_provider):
        r = CliRunner().invoke(app, ["cloudflare", "plan", "example.com"])

    assert r.exit_code == 0
    assert "+" in r.output


def test_cloudflare_plan_all_domains(tmp_path, monkeypatch):
    dns_dir = tmp_path / "config" / "dns"
    dns_dir.mkdir(parents=True)
    _write(dns_dir / "example.com.yaml", "apiVersion: cstation/v1\nkind: DNS\ndomain: example.com\nrecords:\n  - name: ''\n    type: MX\n    value: mail.example.com\n    priority: 10\n    ttl: 300\n")
    _write(dns_dir / "test.org.yaml", "apiVersion: cstation/v1\nkind: DNS\ndomain: test.org\nrecords:\n  - name: ''\n    type: A\n    value: 5.6.7.8\n    ttl: 300\n")
    home = tmp_path / "home"
    _write(home / ".config" / "cstation" / "config.yaml", "cloudflare:\n  api_token: test-token\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()

    from cstation.providers.cloudflare import DNSRecord

    mock_provider = Mock()
    mock_provider.get_zone_id.return_value = "zone123"
    mock_provider.list_records.return_value = []

    with patch("cstation.commands.cloudflare.main.CloudflareProvider", return_value=mock_provider):
        r = CliRunner().invoke(app, ["cloudflare", "plan"])

    assert r.exit_code == 0
    assert "example.com" in r.output
    assert "test.org" in r.output