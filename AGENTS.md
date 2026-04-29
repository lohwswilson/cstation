# AGENTS.md

## Environment
- Python **3.13** (exact — see `.python-version`)
- Package manager: `uv`
- Build backend: `hatchling`
- Entry point: `cstation = "cstation.main:main"` in `pyproject.toml`

## Commands
- Run all tests: `uv run pytest -q`
- Run single test: `uv run pytest -q tests/path/to/test.py::test_name`
- Run CLI: `uv run cstation <command>`
- Install in editable mode: `uv pip install -e .`
- Install with test deps: `uv pip install -e ".[test]"`

## No lint/typecheck
There is no `[tool.ruff]`, `[tool.mypy]`, or `[tool.pyright]` in `pyproject.toml`.
Do not attempt to run lint or typecheck commands.

## Architecture
- `src/cstation/main.py` — Typer app, registers all command groups
- `src/cstation/commands/<group>/main.py` — each command group is a Typer app
- `src/cstation/providers/` — cloud provider adapters (`base.py` has the `VPSProvider` protocol)
- `src/cstation/config.py` — `ConfigManager` loads YAML from `~/.config/cstation/`
- `src/cstation/ssh.py` — `SSHManager` wrapping Fabric

### Adding a new command group
1. Create `src/cstation/commands/<group>/__init__.py` (empty)
2. Create `src/cstation/commands/<group>/main.py` with a Typer app
3. Import and register in `src/cstation/main.py`:
   ```python
   from cstation.commands.<group>.main import <group>_app
   app.add_typer(<group>_app)
   ```

### Adding a new provider
1. Create `src/cstation/providers/<name>.py` implementing `VPSProvider` protocol from `base.py`
2. Add to `_provider_from_token()` in `src/cstation/commands/vps/main.py`

## VPS config
Provider tokens live in `~/.config/cstation/config.yaml`:
```yaml
vps:
  providers:
    hetzner:
      accounts:
        myaccount:
          token: "xxx"
```

VPS command targets use the format `<provider>/<account>:<id>`.
Example: `cstation vps init hetzner/myaccount:123456`

## VPS workflow: init → plan → apply

This is the primary user workflow. Understand it thoroughly.

1. **`cstation vps init <provider>/<account>:<id>`** — SSHes into VPS, collects facts, writes a YAML config to `config/vps/<name>.yaml`
2. **Edit the YAML** — user amends `os.baseline`, `os`, and `docker` sections
3. **`cstation vps plan <config.yaml>`** — dry-run: SSHes in, compares declared state vs actual, prints what would change
4. **`cstation vps apply <config.yaml>`** — executes changes. Supports `--phase <name>` to run a single phase, and `--yes` to skip confirmation

### Current YAML schema (what `init` generates + manual additions)
```yaml
apiVersion: cstation/v1
kind: VPS
identity: { name, stage, region }
access: { host, user, port }
facts: { os, cpu, memory, disks, network, hostname, packages: { detected, missing } }
os:
  hostname: eu01.example.com       # set hostname via hostnamectl
  baseline:
    upgrade_all: true              # apt-get upgrade before installing packages
    packages: [...]                # missing key packages from KEY_PACKAGES list
    shell: zsh                     # set default shell (zsh, bash, fish)
    terminal: xterm-256color       # set TERM in /etc/environment
    swap:
      size_gb: 4                   # create swap file
    tuning:
      vm_swappiness: 10            # sysctl params written to /etc/sysctl.d/99-cstation.conf
      vm_overcommit_memory: 1
      net_ipv4_tcp_max_syn_backlog: 1024
      fs_inotify_max_user_watches: 524288
      net_ipv4_tcp_keepalive_time: 600
    sshd: { disable_password_auth: true }
    fail2ban:
      bantime: 1h                  # write /etc/fail2ban/jail.local
      findtime: 10m
      maxretry: 5
    firewall: { mode: ufw, allow: [22/tcp] }
  journald:
    system_max_use: 500M           # write /etc/systemd/journald.conf.d/99-cstation.conf
    forward_to_syslog: false
docker:
  daemon:
    log_driver: json-file           # write /etc/docker/daemon.json
    log_opts: { max_size: 10m, max_file: "3" }
    storage_driver: overlay2
    live_restore: true
    iptables: true
    default_ulimits: { nofile: 65536 }
  networks: [PW_NET]               # docker network create
  directories: [/var/lib/perfectwork]  # mkdir -p
```

Default output path is `config/vps/<name>.yaml` (just the VPS name, no stage/region prefix).

### Apply phases (in order)
1. `upgrade_all` — upgrade all installed packages
2. `packages` — install missing packages
3. `shell` — set default shell
4. `terminal` — set TERM in /etc/environment
5. `sshd` — configure SSH daemon
6. `firewall` — configure UFW
7. `swap` — create swap file, set swappiness, add to fstab
8. `tuning` — write sysctl params + journald config
9. `fail2ban` — write jail.local, restart fail2ban
10. `hostname` — set hostname via hostnamectl
11. `docker_daemon` — write /etc/docker/daemon.json, restart docker
12. `docker_networks` — create Docker networks
13. `docker_directories` — create directories

Run a single phase with `--phase`: `cstation vps apply config.yaml --phase packages`

### KEY_PACKAGES hard-coded list
`src/cstation/commands/vps/main.py:32-45` defines `KEY_PACKAGES` — the list checked during `vps init` fact collection. Missing ones become `os.baseline.packages` defaults. If you add a new package to detect, add it here.

### What `init` does NOT configure (not yet built)
- Service deployment (Traefik, Postgres, Portainer)
- App deployment (Odoo instances, Mailcow)
- Code sync (rsync to `/var/lib/perfectwork/`)
- Non-root sudo user bootstrap

These are planned phases 4-7 per `docs/superpowers/specs/2026-04-28-vps-declarative-management-design.md`.

## Testing
- Tests live in `tests/` mirroring `src/` structure
- VPS CLI tests: `tests/commands/test_vps_cli.py`
- Provider tests: `tests/providers/test_hetzner.py`, `tests/providers/test_vultr.py`
- Tests use `monkeypatch` to mock `SSHManager.run` and provider methods via `monkeypatch.setattr("cstation.commands.vps.main.SSHManager.run", ...)`
- Provider tests use `unittest.mock.Mock` for the HTTP client
- VPS commands that need provider tokens require `~/.config/cstation/config.yaml` — tests write temp config to `tmp_path`
- Config loading must be reset between tests: call `_reset_config()` then `initialize_configuration()`

### Testing VPS init/plan/apply
- Mock `SSHManager.run` with a dict of command → stdout responses
- Mock provider methods via `monkeypatch.setattr("cstation.providers.hetzner.HetznerProvider.get_vps", ...)`
- For `apply` tests that require confirmation, patch `typer.confirm`: `monkeypatch.setattr(typer, "confirm", lambda *a, **kw: True)`

## README caveats
The README references `cstation service` and `requirements-dev.txt` — neither exist.
Trust `pyproject.toml` and the source code over the README.