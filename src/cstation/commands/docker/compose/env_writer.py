from __future__ import annotations

from typing import Any


def render_env(env: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in sorted(env.items()):
        v = str(value)
        if any(c in v for c in (" ", "'", '"', "\n", "#")):
            v = f"'{v.replace(chr(39), chr(39)+chr(39))}'"
        lines.append(f"{key}={v}")
    return "\n".join(lines) + "\n"


def render_secrets_env(secrets: dict[str, str]) -> str:
    return render_env(secrets)