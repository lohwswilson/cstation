"""
Unit tests for CStation SQLite state and audit telemetry.
"""
from pathlib import Path
from typer.testing import CliRunner

from cstation.main import app
from cstation.state import (
    record_audit,
    record_vps_metrics,
    get_audit_logs,
    get_vps_metrics_history,
)


def test_state_audit_and_metrics(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "test_state.db"
    monkeypatch.setenv("CSTATION_STATE_DB", str(db_file))

    # Test audit logging
    log_id = record_audit(command="docker apply", target="test-vps", status="success", duration_ms=120, message="Applied 3 containers")
    assert log_id > 0

    logs = get_audit_logs(limit=10)
    assert len(logs) == 1
    assert logs[0]["command"] == "docker apply"
    assert logs[0]["target"] == "test-vps"

    # Test CLI state audit command
    r = CliRunner().invoke(app, ["state", "audit"])
    assert r.exit_code == 0
    assert "docker" in r.output

    # Test CLI state audit JSON
    r_json = CliRunner().invoke(app, ["state", "audit", "--output", "json"])
    assert r_json.exit_code == 0
    import json
    data = json.loads(r_json.output)
    assert len(data) == 1
    assert data[0]["command"] == "docker apply"

    # Test VPS metrics recording
    facts = {
        "load_avg": "0.15, 0.20, 0.18",
        "memory": {"total_mb": 8000, "used_mb": 4000},
        "disk_usage": {"total": "100G", "used": "20G", "percent": "20%"},
        "docker_summary": {"running": 5, "total": 5},
    }
    metric_id = record_vps_metrics("test-vps", facts)
    assert metric_id > 0

    history = get_vps_metrics_history("test-vps", limit=10)
    assert len(history) == 1
    assert history[0]["vps_name"] == "test-vps"
    assert history[0]["memory_pct"] == 50.0

    # Test CLI state history command
    r_hist = CliRunner().invoke(app, ["state", "history", "test-vps"])
    assert r_hist.exit_code == 0
    assert "50.0%" in r_hist.output
