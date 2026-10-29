"""
SQLite runtime state, telemetry, and audit logging for CStation.
Stored in ~/.config/cstation/state.db with WAL mode enabled.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from cstation.config import CSTATION_CONFIG_DIR

def get_db_path() -> Path:
    """Return path to SQLite state database."""
    env_path = os.getenv("CSTATION_STATE_DB")
    if env_path:
        db_path = Path(env_path)
    else:
        db_path = CSTATION_CONFIG_DIR / "state.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_connection() -> sqlite3.Connection:
    """Open or create a connection to the state database with WAL mode."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Ensure tables and indices exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            command TEXT NOT NULL,
            target TEXT,
            status TEXT NOT NULL,
            duration_ms INTEGER DEFAULT 0,
            message TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_log_command ON audit_log(command);

        CREATE TABLE IF NOT EXISTS vps_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vps_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            load_avg TEXT,
            memory_used_mb INTEGER,
            memory_total_mb INTEGER,
            memory_pct REAL,
            disk_used_gb REAL,
            disk_total_gb REAL,
            disk_pct REAL,
            docker_running INTEGER,
            docker_total INTEGER,
            facts_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_vps_metrics_name_time ON vps_metrics(vps_name, timestamp DESC);
        """
    )
    conn.commit()


def record_audit(
    command: str,
    target: Optional[str] = None,
    status: str = "success",
    duration_ms: int = 0,
    message: str = "",
) -> int:
    """Record a CLI or TUI action to the audit log."""
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO audit_log (timestamp, command, target, status, duration_ms, message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now_iso, command, target, status, duration_ms, message),
            )
            return cur.lastrowid or 0
    except Exception:
        return 0


def record_vps_metrics(vps_name: str, facts: dict[str, Any]) -> int:
    """Record a snapshot of VPS resource facts to SQLite."""
    now_iso = datetime.now(timezone.utc).isoformat()

    mem = facts.get("memory", {})
    mem_total = mem.get("total_mb", 0)
    mem_used = mem.get("used_mb", 0)
    mem_pct = round((mem_used / mem_total * 100), 1) if mem_total > 0 else None

    du = facts.get("disk_usage", {})
    # Parse total and used from e.g. "169G", "39G"
    disk_total_gb = None
    disk_used_gb = None
    disk_pct = None
    try:
        tot_str = str(du.get("total", ""))
        used_str = str(du.get("used", ""))
        if tot_str.endswith("G"):
            disk_total_gb = float(tot_str[:-1])
        if used_str.endswith("G"):
            disk_used_gb = float(used_str[:-1])
        pct_str = str(du.get("percent", ""))
        if pct_str.endswith("%"):
            disk_pct = float(pct_str[:-1])
    except Exception:
        pass

    ds = facts.get("docker_summary", {})
    docker_running = ds.get("running")
    docker_total = ds.get("total")

    facts_json = json.dumps(facts, default=str)

    try:
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO vps_metrics (
                    vps_name, timestamp, load_avg,
                    memory_used_mb, memory_total_mb, memory_pct,
                    disk_used_gb, disk_total_gb, disk_pct,
                    docker_running, docker_total, facts_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vps_name,
                    now_iso,
                    str(facts.get("load_avg") or ""),
                    mem_used,
                    mem_total,
                    mem_pct,
                    disk_used_gb,
                    disk_total_gb,
                    disk_pct,
                    docker_running,
                    docker_total,
                    facts_json,
                ),
            )
            return cur.lastrowid or 0
    except Exception:
        return 0


def get_audit_logs(limit: int = 50, command_filter: Optional[str] = None) -> list[dict[str, Any]]:
    """Retrieve recent audit log entries."""
    query = "SELECT id, timestamp, command, target, status, duration_ms, message FROM audit_log"
    params: list[Any] = []
    if command_filter:
        query += " WHERE command LIKE ?"
        params.append(f"%{command_filter}%")
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_vps_metrics_history(vps_name: str, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve metrics snapshots for a specific VPS."""
    query = """
        SELECT id, vps_name, timestamp, load_avg,
               memory_used_mb, memory_total_mb, memory_pct,
               disk_used_gb, disk_total_gb, disk_pct,
               docker_running, docker_total
        FROM vps_metrics
        WHERE vps_name = ?
        ORDER BY id DESC LIMIT ?
    """
    with get_connection() as conn:
        rows = conn.execute(query, (vps_name, limit)).fetchall()
        return [dict(r) for r in rows]
