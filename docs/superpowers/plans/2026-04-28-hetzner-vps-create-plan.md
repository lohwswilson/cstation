# Hetzner VPS Create (CLI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal Hetzner Cloud VPS provisioning workflow under `cstation vps` (create/list/status/delete) with safe authentication handling and tests.

**Update (Declarative Direction):**
- Per-VPS config entry file naming: `config/vps/<vps_name>.yaml`
- Proposed command: `cstation vps init <provider>/<account>:<id>` (provider metadata + SSH read-only facts → write per-VPS YAML; refuses overwrite unless `--force`)
- `stage` is user-provided (default `prod`); `name`/`region` inferred from provider metadata
- Example: `cstation vps init hetzner/ANSIS:123456`

**Architecture:** Implement a provider interface with a Hetzner adapter that wraps the Hetzner Cloud API. Add a small set of `cstation vps` commands that call the provider adapter and render results. Keep the surface area small and expand later.

**Tech Stack:** Python, Typer, Rich, urllib.request (built-in HTTP), pytest (run via uv).

---

## File Map (Create/Modify)

**Likely existing files (verify before editing):**
- Modify: `src/cstation/main.py` (register `vps` group)
- Modify: `src/cstation/config.py` (load provider token and local config)
- Modify: `src/cstation/commands/server/*` (pattern reference)
- Modify: `src/cstation/commands/github/*` (pattern reference)

**New files (minimal set):**
- Create: `src/cstation/commands/vps/main.py` (Typer group for vps)
- Create: `src/cstation/providers/base.py` (provider protocol + models)
- Create: `src/cstation/providers/hetzner.py` (Hetzner adapter)
- Create: `src/cstation/providers/errors.py` (provider exceptions)
- Create: `tests/providers/test_hetzner.py` (unit tests, mocked HTTP)
- Create: `tests/commands/test_vps_cli.py` (CLI smoke tests using Typer runner)

> If `providers/` already exists, reuse it. If requests is not used in repo, prefer whatever HTTP client is already present.

---

### Task 1: Explore current CLI structure and dependencies

**Files:**
- Inspect: `pyproject.toml`
- Inspect: `src/cstation/main.py`
- Inspect: existing command modules under `src/cstation/commands/`

- [ ] **Step 1: Identify dependency for HTTP**

Run:
```bash
python -c "import tomllib, pathlib; p=pathlib.Path('pyproject.toml'); print('pyproject.toml exists:', p.exists())"
```

Then inspect `pyproject.toml` for an HTTP client dependency (e.g., `requests`, `httpx`).

- [ ] **Step 2: Identify how config is loaded**

Find how secrets/config are loaded (likely from `~/.config/cstation` / `/etc/cstation`) and how commands access config.

- [ ] **Step 3: Identify test runner**

Search for `pytest` usage and existing tests.

Expected outcome:
- A chosen HTTP client and a known test command (e.g., `uv run pytest -q`).

---

### Task 2: Define provider models and interface

**Files:**
- Create: `src/cstation/providers/base.py`
- Create: `src/cstation/providers/errors.py`
- Test: `tests/providers/test_models.py`

- [ ] **Step 1: Write failing tests for models**

Create `tests/providers/test_models.py`:
```python
from cstation.providers.base import VPS, VPSStatus


def test_vps_has_expected_fields():
    vps = VPS(
        provider="hetzner",
        id="123",
        name="sg07",
        region="hel1",
        status=VPSStatus.RUNNING,
        ipv4="1.2.3.4",
    )
    assert vps.name == "sg07"
    assert vps.status.value == "running"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest -q tests/providers/test_models.py
```
Expected: FAIL (module/import missing)

- [ ] **Step 3: Implement minimal models + errors**

Create `src/cstation/providers/errors.py`:
```python
class ProviderError(Exception):
    pass


class ProviderAuthError(ProviderError):
    pass


class ProviderNotFoundError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass
```

Create `src/cstation/providers/base.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol


class VPSStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VPS:
    provider: str
    id: str
    name: str
    region: Optional[str]
    status: VPSStatus
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None


class VPSProvider(Protocol):
    provider_name: str

    def list_vps(self) -> list[VPS]: ...
    def get_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> VPS: ...
    def create_vps(
        self,
        *,
        name: str,
        region: str,
        server_type: str,
        image: str,
        ssh_keys: list[str],
    ) -> VPS: ...
    def delete_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> None: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest -q tests/providers/test_models.py
```
Expected: PASS

---

### Task 3: Implement Hetzner provider adapter (mocked HTTP)

**Files:**
- Create: `src/cstation/providers/hetzner.py`
- Test: `tests/providers/test_hetzner.py`

- [ ] **Step 1: Write failing test for auth header + list parsing**

Create `tests/providers/test_hetzner.py`:
```python
import json
from unittest.mock import Mock

from cstation.providers.hetzner import HetznerProvider
from cstation.providers.base import VPSStatus


def test_list_vps_parses_servers():
    http = Mock()
    http.get.return_value.status_code = 200
    http.get.return_value.json.return_value = {
        "servers": [
            {
                "id": 123,
                "name": "sg07",
                "status": "running",
                "datacenter": {"location": {"name": "hel1"}},
                "public_net": {"ipv4": {"ip": "1.2.3.4"}, "ipv6": {"ip": "2001:db8::1"}},
            }
        ]
    }

    p = HetznerProvider(token="secret", http=http)
    vps_list = p.list_vps()
    assert len(vps_list) == 1
    assert vps_list[0].name == "sg07"
    assert vps_list[0].status == VPSStatus.RUNNING
    http.get.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest -q tests/providers/test_hetzner.py
```
Expected: FAIL (module missing)

- [ ] **Step 3: Implement minimal HetznerProvider**

Create `src/cstation/providers/hetzner.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from cstation.providers.base import VPS, VPSProvider, VPSStatus
from cstation.providers.errors import ProviderAuthError, ProviderError, ProviderNotFoundError


def _status_from_hetzner(value: str) -> VPSStatus:
    try:
        return VPSStatus(value)
    except Exception:
        return VPSStatus.UNKNOWN


@dataclass
class HetznerProvider(VPSProvider):
    token: str
    http: Any
    base_url: str = "https://api.hetzner.cloud/v1"
    provider_name: str = "hetzner"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _handle_error(self, status_code: int, payload: Any) -> None:
        if status_code in (401, 403):
            raise ProviderAuthError("Hetzner authentication failed")
        raise ProviderError(f"Hetzner API error: {status_code}")

    def list_vps(self) -> list[VPS]:
        resp = self.http.get(f"{self.base_url}/servers", headers=self._headers())
        if resp.status_code != 200:
            self._handle_error(resp.status_code, getattr(resp, "text", None))
        data = resp.json()
        out: list[VPS] = []
        for s in data.get("servers", []):
            ipv4 = (((s.get("public_net") or {}).get("ipv4") or {}).get("ip"))
            ipv6 = (((s.get("public_net") or {}).get("ipv6") or {}).get("ip"))
            region = (((s.get("datacenter") or {}).get("location") or {}).get("name"))
            out.append(
                VPS(
                    provider=self.provider_name,
                    id=str(s.get("id")),
                    name=str(s.get("name")),
                    region=region,
                    status=_status_from_hetzner(str(s.get("status", ""))),
                    ipv4=ipv4,
                    ipv6=ipv6,
                )
            )
        return out

    def get_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> VPS:
        vps_list = self.list_vps()
        for v in vps_list:
            if id and v.id == id:
                return v
            if name and v.name == name:
                return v
        raise ProviderNotFoundError("VPS not found")

    def create_vps(
        self,
        *,
        name: str,
        region: str,
        server_type: str,
        image: str,
        ssh_keys: list[str],
    ) -> VPS:
        payload = {"name": name, "location": region, "server_type": server_type, "image": image, "ssh_keys": ssh_keys}
        resp = self.http.post(f"{self.base_url}/servers", headers=self._headers(), json=payload)
        if resp.status_code not in (200, 201):
            self._handle_error(resp.status_code, getattr(resp, "text", None))
        server = resp.json().get("server") or {}
        return VPS(
            provider=self.provider_name,
            id=str(server.get("id")),
            name=str(server.get("name")),
            region=region,
            status=_status_from_hetzner(str(server.get("status", ""))),
        )

    def delete_vps(self, *, id: Optional[str] = None, name: Optional[str] = None) -> None:
        v = self.get_vps(id=id, name=name)
        resp = self.http.delete(f"{self.base_url}/servers/{v.id}", headers=self._headers())
        if resp.status_code not in (200, 204):
            self._handle_error(resp.status_code, getattr(resp, "text", None))
```

- [ ] **Step 4: Run tests**

Run:
```bash
uv run pytest -q tests/providers/test_hetzner.py
```
Expected: PASS

---

### Task 4: Add `cstation vps` command group and subcommands

**Files:**
- Create: `src/cstation/commands/vps/main.py`
- Modify: `src/cstation/main.py`
- Test: `tests/commands/test_vps_cli.py`

- [ ] **Step 1: Write CLI tests (Typer runner)**

Create `tests/commands/test_vps_cli.py` with a simple help smoke test:
```python
from typer.testing import CliRunner

from cstation.main import app


def test_vps_help():
    r = CliRunner().invoke(app, ["vps", "--help"])
    assert r.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest -q tests/commands/test_vps_cli.py
```
Expected: FAIL (no vps command)

- [ ] **Step 3: Implement `vps` group with `ls/status/create/delete`**

Create `src/cstation/commands/vps/main.py`:
```python
from __future__ import annotations

import os
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from cstation.providers.hetzner import HetznerProvider
from cstation.providers.errors import ProviderAuthError, ProviderError, ProviderNotFoundError


app = typer.Typer(help="Manage VPS lifecycle (provider-backed).")
console = Console()


def _hetzner_provider() -> HetznerProvider:
    token = os.getenv("HETZNER_TOKEN")
    if not token:
        raise typer.BadParameter("Missing HETZNER_TOKEN environment variable")
    import requests  # noqa: WPS433

    return HetznerProvider(token=token, http=requests)


@app.command("ls")
def ls(provider: str = typer.Option("hetzner")) -> None:
    if provider != "hetzner":
        raise typer.BadParameter("Only hetzner is supported in MVP")
    p = _hetzner_provider()
    vps_list = p.list_vps()

    table = Table(title="VPS")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Region")
    table.add_column("Status")
    table.add_column("IPv4")
    for v in vps_list:
        table.add_row(v.id, v.name, v.region or "-", v.status.value, v.ipv4 or "-")
    console.print(table)


@app.command("status")
def status(target: str, provider: str = typer.Option("hetzner")) -> None:
    if provider != "hetzner":
        raise typer.BadParameter("Only hetzner is supported in MVP")
    p = _hetzner_provider()
    v = p.get_vps(id=target if target.isdigit() else None, name=None if target.isdigit() else target)
    console.print({"id": v.id, "name": v.name, "region": v.region, "status": v.status.value, "ipv4": v.ipv4})


@app.command("create")
def create(
    name: str = typer.Option(...),
    region: str = typer.Option(..., help="Hetzner location, e.g. hel1"),
    server_type: str = typer.Option(..., help="Hetzner server type, e.g. cx21"),
    image: str = typer.Option(..., help="Image name, e.g. ubuntu-24.04"),
    ssh_key: list[str] = typer.Option([], help="SSH key name(s) uploaded to Hetzner"),
    provider: str = typer.Option("hetzner"),
) -> None:
    if provider != "hetzner":
        raise typer.BadParameter("Only hetzner is supported in MVP")
    p = _hetzner_provider()
    v = p.create_vps(name=name, region=region, server_type=server_type, image=image, ssh_keys=ssh_key)
    console.print({"id": v.id, "name": v.name, "status": v.status.value})


@app.command("delete")
def delete(target: str, yes: bool = typer.Option(False, "--yes"), provider: str = typer.Option("hetzner")) -> None:
    if provider != "hetzner":
        raise typer.BadParameter("Only hetzner is supported in MVP")
    if not yes:
        raise typer.BadParameter("Refusing to delete without --yes")
    p = _hetzner_provider()
    p.delete_vps(id=target if target.isdigit() else None, name=None if target.isdigit() else target)
    console.print("deleted")
```

Modify `src/cstation/main.py` to register the group:
```python
from cstation.commands.vps.main import app as vps_app
app.add_typer(vps_app, name="vps")
```

- [ ] **Step 4: Run CLI tests**

Run:
```bash
uv run pytest -q tests/commands/test_vps_cli.py
```
Expected: PASS

---

### Task 5: Add error handling tests for missing token

**Files:**
- Modify: `tests/commands/test_vps_cli.py`

- [ ] **Step 1: Add failing test**

Append:
```python
def test_vps_ls_requires_token(monkeypatch):
    monkeypatch.delenv("HETZNER_TOKEN", raising=False)
    r = CliRunner().invoke(app, ["vps", "ls"])
    assert r.exit_code != 0
    assert "HETZNER_TOKEN" in r.stdout
```

- [ ] **Step 2: Run and verify**

Run:
```bash
uv run pytest -q tests/commands/test_vps_cli.py::test_vps_ls_requires_token
```
Expected: PASS

---

### Task 6: Lint/typecheck/test commands

**Files:**
- None

- [ ] **Step 1: Run unit tests**

Run:
```bash
uv run pytest -q
```

- [ ] **Step 2: Run lint/typecheck if configured**

If repo has `ruff`, `mypy`, or `pyright`, run the configured commands (from docs or `pyproject.toml`).

---

## Self-Review Checklist

- Plan uses only moving branch refs (strings) and records resolved SHAs (to be implemented later).
- CLI stays shallow (`cstation vps ...`), Hetzner-only guarded in MVP.
- Deletes require explicit `--yes`.
- No secrets are printed; token pulled from env var.
