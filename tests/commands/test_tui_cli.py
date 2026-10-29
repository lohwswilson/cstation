"""
Unit tests for CStation TUI dashboard command.
"""
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cstation.main import app
from cstation.commands.tui.app import CStationApp, resolve_command_execution


def test_tui_help():
    r = CliRunner().invoke(app, ["tui", "--help"])
    assert r.exit_code == 0
    assert "Interactive TUI dashboard" in r.output


def test_ui_alias_help():
    r = CliRunner().invoke(app, ["ui", "--help"])
    assert r.exit_code == 0
    assert "Interactive TUI dashboard" in r.output


def test_dashboard_alias_help():
    r = CliRunner().invoke(app, ["dashboard", "--help"])
    assert r.exit_code == 0
    assert "Interactive TUI dashboard" in r.output


def test_cstation_app_instantiation():
    tui_app = CStationApp()
    assert tui_app.TITLE == "CStation Infrastructure Dashboard"
    palette_cmds = tui_app.get_palette_commands()
    assert any("Fleet: Refresh" in cmd[0] for cmd in palette_cmds)
    assert any("Fleet: Lint" in cmd[0] for cmd in palette_cmds)
    assert any("Config: Export" in cmd[0] for cmd in palette_cmds)
    assert any("State: View Audit Log" in cmd[0] for cmd in palette_cmds)
    assert any("DNS: List Cloudflare Zones" in cmd[0] for cmd in palette_cmds)
    assert any("Image: List Image Recipes" in cmd[0] for cmd in palette_cmds)


def test_cstation_app_bindings():
    tui_app = CStationApp()
    binding_keys = [b[0] for b in tui_app.BINDINGS]
    assert "colon" in binding_keys
    assert "u" in binding_keys
    assert "s" in binding_keys
    assert "p" in binding_keys
    assert "r" in binding_keys


def test_cstation_app_per_vps_palette_items():
    tui_app = CStationApp()
    tui_app.vps_list = [{"name": "demo-server", "host": "1.2.3.4", "dir": Path("/tmp"), "metrics": ""}]
    palette_cmds = tui_app.get_palette_commands()
    cmd_titles = [cmd[0] for cmd in palette_cmds]
    assert any("VPS: Check Uptime & Health (demo-server)" in t for t in cmd_titles)
    assert any("VPS: Open SSH Shell (demo-server)" in t for t in cmd_titles)
    assert any("VPS: Apply 12-Phase OS Setup (demo-server)" in t for t in cmd_titles)
    assert any("Docker: Plan Containers (demo-server)" in t for t in cmd_titles)
    assert any("Docker: Apply Container Stacks (demo-server)" in t for t in cmd_titles)
    assert any("Odoo: Backup Database (demo-server)" in t for t in cmd_titles)
    assert any("Hindsight: Status Check (demo-server)" in t for t in cmd_titles)
    assert any("VPS: Remove Server Config (demo-server)" in t for t in cmd_titles)


def test_cstation_app_context_aware_execution():
    # 1. Shell commands like 'uptime' should execute via SSH on the selected VPS
    mode, cmd = resolve_command_execution("uptime", "sg05.ansis.com.sg")
    assert mode == "ssh"
    assert cmd == "uptime"

    mode, cmd = resolve_command_execution("docker ps -a", "sg05.ansis.com.sg")
    assert mode == "ssh"
    assert cmd == "docker ps -a"

    # 2. CStation commands like 'docker apply' should auto-inject selected server
    mode, cmd = resolve_command_execution("docker apply", "sg05.ansis.com.sg")
    assert mode == "local"
    assert cmd == "docker apply sg05.ansis.com.sg"

    # 3. VPS apply auto-injects server and --yes
    mode, cmd = resolve_command_execution("vps apply", "sg05.ansis.com.sg")
    assert mode == "local"
    assert cmd == "vps apply sg05.ansis.com.sg --yes"

    # 4. Global commands like 'lint' or 'config export' should run locally
    mode, cmd = resolve_command_execution("lint", "sg05.ansis.com.sg")
    assert mode == "local"
    assert cmd == "lint"

    mode, cmd = resolve_command_execution("config export", "sg05.ansis.com.sg")
    assert mode == "local"
    assert cmd == "config export"

    # 5. Explicit 'local' prefix should run locally
    mode, cmd = resolve_command_execution("local ping 127.0.0.1", "sg05.ansis.com.sg")
    assert mode == "local"
    assert cmd == "ping 127.0.0.1"

    # 6. If no VPS is selected, default to local CLI
    mode, cmd = resolve_command_execution("uptime", None)
    assert mode == "local"
    assert cmd == "uptime"


def test_tui_run_invocation():
    with patch("cstation.commands.tui.app.CStationApp.run") as mock_run:
        r = CliRunner().invoke(app, ["tui"])
        assert r.exit_code == 0
        mock_run.assert_called_once()
