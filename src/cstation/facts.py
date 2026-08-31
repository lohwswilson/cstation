import json
import time
from pathlib import Path
from typing import Any, Optional


def load_cached_facts(vps_dir: Path) -> Optional[dict[str, Any]]:
    """Load facts from the local .facts.json cache."""
    cache_file = vps_dir / ".facts.json"
    if not cache_file.exists():
        return None
    try:
        with cache_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_cached_facts(vps_dir: Path, facts: dict[str, Any]) -> None:
    """Save facts to the local .facts.json cache with a timestamp."""
    cache_file = vps_dir / ".facts.json"
    facts["_cached_at"] = time.time()
    try:
        with cache_file.open("w", encoding="utf-8") as f:
            json.dump(facts, f, indent=2)
    except Exception:
        pass


def format_facts_summary(facts: dict[str, Any]) -> str:
    """Format a one-line summary of facts for listing."""
    load = facts.get("load_avg", "").split(",")[0] if facts.get("load_avg") else "?"

    mem = facts.get("memory", {})
    mem_pct = "?"
    if mem.get("total_mb") and mem.get("used_mb"):
        mem_pct = f"{int(mem['used_mb'] / mem['total_mb'] * 100)}%"

    disk = facts.get("disk_usage", {})
    disk_pct = disk.get("percent", "?")

    docker = facts.get("docker_summary", {})
    docker_str = ""
    if docker.get("total", 0) > 0:
        docker_str = f" | 🐳 {docker.get('running')}/{docker.get('total')}"

    return f"L: {load} | M: {mem_pct} | D: {disk_pct}{docker_str}"
