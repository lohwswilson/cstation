# VPS Init (Provider-Target) Implementation Plan
 
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
 
**Goal:** Add `cstation vps init <provider>/<account>:<id>` to fetch provider metadata + SSH facts and write `config/vps/<name>.yaml`, refusing overwrite unless `--force`.
 
**Architecture:** Extend the existing `vps` command module with an `init` subcommand that resolves provider/account, fetches VPS metadata via providers, uses `SSHManager` for read-only facts, and serializes a YAML skeleton via `pyyaml`. Keep parsing/helpers in the `vps` module for now to match existing patterns.
 
**Tech Stack:** Python 3.13, Typer, Rich, PyYAML, Fabric (`SSHManager`), pytest.
 
---
 
## File Map (Create/Modify)
 
**Modify:**
- `src/cstation/commands/vps/main.py` (add `init` command + helpers)
- `tests/commands/test_vps_cli.py` (add CLI tests for init)
 
---
 
### Task 1: Add CLI tests for `vps init`
 
**Files:**
- Modify: `tests/commands/test_vps_cli.py`
 
- [ ] **Step 1: Add test for help examples**
 
```python
def test_vps_init_help_examples():
    r = CliRunner().invoke(app, ["vps", "init", "--help"])
    assert r.exit_code == 0
    out = r.output
    assert "hetzner/ANSIS:123456" in out
```
 
- [ ] **Step 2: Add test for successful init writing YAML**
 
```python
def test_vps_init_writes_yaml(monkeypatch, tmp_path: Path):
    from cstation.providers.base import VPS, VPSStatus
 
    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    hetzner:",
                "      accounts:",
                "        ANSIS:",
                "          token: t1",
                "",
            ]
        ),
    )
 
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()
 
    def fake_get_vps(self, *, id=None, name=None):
        assert id == "123456"
        return VPS(
            provider="hetzner",
            id="123456",
            name="sg05",
            region="hel1",
            status=VPSStatus.RUNNING,
            ipv4="1.2.3.4",
            ipv6=None,
        )
 
    class FakeResult:
        def __init__(self, stdout: str):
            self.stdout = stdout
            self.stderr = ""
 
    def fake_run(self, command: str, hide: bool = True, sudo: bool = False):
        outputs = {
            "cat /etc/os-release": 'NAME="Ubuntu"\\nVERSION_ID="22.04"\\nID=ubuntu\\n',
            "uname -r": "6.8.0\\n",
            "lscpu": "CPU(s): 4\\nModel name: Intel Xeon\\n",
            "free -m": "Mem: 8192 0 0\\n",
            "lsblk -b -J": '{"blockdevices":[{"name":"sda","size":85899345920}] }',
            "ip -j a": "[]",
            "ip route": "default via 1.2.3.1 dev eth0\\n",
            "hostname": "sg05\\n",
            "command -v apt-get": "/usr/bin/apt-get\\n",
            "dpkg -s openssh-server >/dev/null 2>&1; echo $?": "0\\n",
            "dpkg -s docker.io >/dev/null 2>&1; echo $?": "1\\n",
        }
        return FakeResult(outputs.get(command, ""))
 
    monkeypatch.setattr("cstation.providers.hetzner.HetznerProvider.get_vps", fake_get_vps)
    monkeypatch.setattr("cstation.ssh.SSHManager.run", fake_run)
 
    out_path = tmp_path / "config" / "vps" / "sg05.yaml"
    r = CliRunner().invoke(
        app,
        ["vps", "init", "hetzner/ANSIS:123456", "--out", str(out_path)],
    )
    assert r.exit_code == 0
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "identity:" in content
    assert "name: sg05" in content
    assert "region: hel1" in content
    assert "openssh-server" in content
```
 
- [ ] **Step 3: Add test for overwrite refusal without --force**
 
```python
def test_vps_init_refuses_overwrite(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    _write(
        home / ".config" / "cstation" / "config.yml",
        "\n".join(
            [
                "vps:",
                "  providers:",
                "    hetzner:",
                "      accounts:",
                "        ANSIS:",
                "          token: t1",
                "",
            ]
        ),
    )
 
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    _reset_config()
    initialize_configuration()
 
    out_path = tmp_path / "config" / "vps" / "sg05.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("existing: true", encoding="utf-8")

    r = CliRunner().invoke(app, ["vps", "init", "hetzner/ANSIS:123456", "--out", str(out_path)])
    assert r.exit_code != 0
    assert "already exists" in r.output.lower()
```
 
- [ ] **Step 4: Run tests to verify failure**
 
Run: `uv run pytest -q tests/commands/test_vps_cli.py::test_vps_init_help_examples tests/commands/test_vps_cli.py::test_vps_init_writes_yaml tests/commands/test_vps_cli.py::test_vps_init_refuses_overwrite`  
Expected: FAIL (command not implemented).
 
- [ ] **Step 5: Commit tests**
 
```bash
git add tests/commands/test_vps_cli.py
git commit -m "test: add vps init CLI coverage"
```
 
---
 
### Task 2: Implement `vps init` command + helpers
 
**Files:**
- Modify: `src/cstation/commands/vps/main.py`
 
- [ ] **Step 1: Add helper parsers and YAML writer**
 
Add helpers near the top of `vps/main.py`:
 
```python
import yaml
from pathlib import Path
from cstation.ssh import SSHManager
 
KEY_PACKAGES = [
    "openssh-server",
    "ufw",
    "nftables",
    "fail2ban",
    "docker",
    "docker.io",
    "containerd",
    "python3",
    "rsync",
    "curl",
    "git",
    "sudo",
]
 
def _parse_os_release(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"')
    return out
 
def _first_line(result: Any) -> str:
    if not result or not getattr(result, "stdout", ""):
        return ""
    return result.stdout.strip().splitlines()[0].strip()
```
 
- [ ] **Step 2: Add fact collection function**
 
```python
def _detect_package_manager(ssh: SSHManager, os_id: str) -> str:
    if os_id in ("ubuntu", "debian"):
        return "apt"
    if os_id in ("centos", "rhel", "fedora", "rocky", "almalinux"):
        return "dnf"
    if os_id in ("alpine",):
        return "apk"
    # fallback: check for apt-get/dnf/yum/apk
    if _first_line(ssh.run("command -v apt-get")):
        return "apt"
    if _first_line(ssh.run("command -v dnf")):
        return "dnf"
    if _first_line(ssh.run("command -v yum")):
        return "yum"
    if _first_line(ssh.run("command -v apk")):
        return "apk"
    return "unknown"
 
def _package_installed(ssh: SSHManager, mgr: str, name: str) -> bool:
    if mgr == "apt":
        return _first_line(ssh.run(f"dpkg -s {name} >/dev/null 2>&1; echo $?")) == "0"
    if mgr in ("dnf", "yum"):
        return _first_line(ssh.run(f"rpm -q {name} >/dev/null 2>&1; echo $?")) == "0"
    if mgr == "apk":
        return _first_line(ssh.run(f"apk info -e {name} >/dev/null 2>&1; echo $?")) == "0"
    return False
 
def _collect_facts(ssh: SSHManager) -> dict[str, Any]:
    os_release_raw = _first_line(ssh.run("cat /etc/os-release")) or ""
    os_release_raw_full = ssh.run("cat /etc/os-release").stdout if ssh.run("cat /etc/os-release") else ""
    os_release = _parse_os_release(os_release_raw_full)
    kernel = _first_line(ssh.run("uname -r"))
    hostname = _first_line(ssh.run("hostname"))
    lscpu = ssh.run("lscpu").stdout if ssh.run("lscpu") else ""
    mem = ssh.run("free -m").stdout if ssh.run("free -m") else ""
    lsblk = ssh.run("lsblk -b -J").stdout if ssh.run("lsblk -b -J") else ""
    ip_addr = ssh.run("ip -j a").stdout if ssh.run("ip -j a") else ""
    ip_route = ssh.run("ip route").stdout if ssh.run("ip route") else ""
 
    os_id = os_release.get("ID", "")
    pkg_mgr = _detect_package_manager(ssh, os_id)
    detected = [p for p in KEY_PACKAGES if _package_installed(ssh, pkg_mgr, p)]
 
    return {
        "os": {
            "id": os_release.get("ID"),
            "version": os_release.get("VERSION_ID"),
            "pretty": os_release.get("PRETTY_NAME"),
            "kernel": kernel,
            "package_manager": pkg_mgr,
        },
        "cpu": {
            "raw": lscpu,
        },
        "memory": {
            "raw": mem,
        },
        "disks": {
            "raw": lsblk,
        },
        "network": {
            "interfaces": ip_addr,
            "routes": ip_route,
        },
        "hostname": hostname,
        "packages": {
            "detected": detected,
        },
    }
```
 
- [ ] **Step 3: Add the `vps init` command**
 
```python
@vps_app.command("init")
def vps_init(
    target: str = typer.Argument(..., help="Target in the form <provider>/<account>:<id>"),
    stage: str = typer.Option("prod", "--stage"),
    out: Optional[Path] = typer.Option(None, "--out", help="Output YAML path"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing output"),
    user: str = typer.Option("root", "--user"),
    port: int = typer.Option(22, "--port"),
    key: Optional[Path] = typer.Option(None, "--key", help="SSH private key"),
) -> None:
    """
    Initialize a per-VPS config from provider metadata + SSH facts.
 
    Examples:
      cstation vps init hetzner/ANSIS:123456
      cstation vps init vultr/MAIN:9b2f... --stage prod
      cstation vps init hetzner/ANSIS:123456 --out config/vps/sg05.yaml
    """
    if "/" not in target:
        raise typer.BadParameter("Target must be <provider>/<account>:<id>")
    provider_name, rest = target.split("/", 1)
    account_name, raw_target = _split_account_target(rest)
    if account_name is None:
        raise typer.BadParameter("Target must include account: <provider>/<account>:<id>")
    id_, name = _parse_target(raw_target)
    if not id_:
        raise typer.BadParameter("Target must include VPS id after <account>:")
 
    _, provider = _provider(provider_name, account_name)
    vps = provider.get_vps(id=id_, name=name)
 
    resolved_name = vps.name
    resolved_region = vps.region or "unknown"
    output_path = out or Path("config") / "vps" / f"{resolved_name}.yaml"
 
    if output_path.exists() and not force:
        console.print(f"[red]✗[/red] Output file already exists: {output_path}")
        raise typer.Exit(5)
 
    host = vps.ipv4 or vps.ipv6
    if not host:
        console.print("[red]✗[/red] VPS has no reachable IP address")
        raise typer.Exit(4)
 
    ssh = SSHManager(host=host, user=user, key_filename=str(key) if key else None)
    facts = _collect_facts(ssh)
 
    payload = {
        "apiVersion": "cstation/v1",
        "kind": "VPS",
        "identity": {
            "name": resolved_name,
            "stage": stage,
            "region": resolved_region,
        },
        "access": {
            "host": host,
            "user": user,
            "port": port,
            "key": str(key) if key else None,
        },
        "facts": facts,
        "os": {
            "baseline": {
                "packages": [],
                "sshd": {"disable_password_auth": True},
                "firewall": {"mode": "ufw", "allow": ["22/tcp"]},
            }
        },
    }
 
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)
 
    console.print(f"[green]✓[/green] Wrote {output_path}")
```
 
- [ ] **Step 4: Run tests**
 
Run: `uv run pytest -q tests/commands/test_vps_cli.py::test_vps_init_help_examples tests/commands/test_vps_cli.py::test_vps_init_writes_yaml tests/commands/test_vps_cli.py::test_vps_init_refuses_overwrite`  
Expected: PASS
 
- [ ] **Step 5: Commit**
 
```bash
git add src/cstation/commands/vps/main.py tests/commands/test_vps_cli.py
git commit -m "feat: add vps init command"
```
 
---
 
## Self-Review Checklist
 
- Spec coverage: `vps init` provider-target, stage default `prod`, region/name inferred, overwrite refusal, CLI examples, key package facts, YAML output path `config/vps/...`.
- Placeholder scan: no TODO/TBD placeholders left in the plan.
- Type consistency: `Path` usage, Typer options, and provider parsing match existing `vps` utilities.
 
---
 
Plan complete and saved to `docs/superpowers/plans/2026-04-28-vps-init-plan.md`. Two execution options:
 
1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration  
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints
 
Which approach?
