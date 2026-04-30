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

## VPS config structure

Each VPS has its own directory under `config/vps/`:
```
config/vps/
├── eu01.synercatalyst.com/
│   ├── vps.yaml              ← kind: VPS (identity, access, facts, os, docker)
│   ├── traefik.yaml          ← kind: Container
│   ├── portainer.yaml        ← kind: Container
│   └── mailcow.yaml          ← kind: Stack
├── sg07.ansis.com.sg/
│   ├── vps.yaml
│   └── ...
```

### `vps.yaml` — Main VPS file (read by `cstation vps` commands)
Contains identity, access, facts, OS config, Docker infrastructure. Does NOT contain container declarations.

### Fragment files (read by `cstation docker` commands)
- Each fragment file is a separate YAML in the VPS config directory
- `kind: Container` — cstation generates the compose file (Traefik, Portainer, PostgreSQL, n8n)
- `kind: Stack` — cstation clones a git repo and patches it (Mailcow, Odoo)
- Fragment discovery: all `*.yaml` files except `vps.yaml`

### CLI argument resolution
Both `cstation vps` and `cstation docker` commands accept:
- Directory path: `cstation vps apply config/vps/eu01.synercatalyst.com`
- VPS name: `cstation vps apply eu01.synercatalyst.com` (auto-discover in `config/vps/`)

Provider tokens live in `~/.config/cstation/config.yaml`:
```yaml
vps:
  providers:
    hetzner:
      accounts:
        myaccount:
          token: "xxx"
```

## Command separation

| Command | Scope | Reads |
|---------|-------|-------|
| `cstation vps apply` | OS + Docker infrastructure (phases 1-13) | `vps.yaml` only |
| `cstation docker apply` | Container deployment | `vps.yaml` (for SSH) + fragment files |

`cstation vps apply` does NOT deploy containers. `cstation docker apply` does NOT touch OS/Docker infrastructure.

## VPS workflow: init → plan → apply

1. **`cstation vps init <provider>/<account>:<id>`** — SSHes into VPS, collects facts, writes `config/vps/<name>/vps.yaml`
2. **Edit `vps.yaml`** — user amends `os.baseline`, `os`, and `docker` sections
3. **`cstation vps plan <vps>`** — dry-run: SSHes in, compares declared state vs actual, prints what would change
4. **`cstation vps apply <vps>`** — executes changes. Supports `--phase <name>` and `--yes`

### VPS YAML schema (what `init` generates + manual additions)
```yaml
apiVersion: cstation/v1
kind: VPS
identity: { name, stage, region }
access: { host, user, port }
facts: { os, cpu, memory, disks, network, hostname, packages: { detected, missing } }
os:
  hostname: eu01.example.com
  baseline:
    upgrade_all: true
    packages: [...]
    shell: zsh
    terminal: xterm-256color
    swap: { size_gb: 4 }
    tuning: { vm_swappiness, vm_overcommit_memory, ... }
    sshd: { disable_password_auth: true }
    fail2ban: { bantime: 1h, findtime: 10m, maxretry: 5 }
    firewall: { mode: ufw, allow: [22/tcp, ...] }
  journald: { system_max_use: 500M, forward_to_syslog: false }
docker:
  daemon: { log_driver, log_opts, storage_driver, live_restore, iptables, default_ulimits }
  networks: [PW_NET]
  directories: [/var/lib/perfectwork]
```

Default output: `config/vps/<name>/vps.yaml`

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

Run a single phase with `--phase`: `cstation vps apply eu01.synercatalyst.com --phase packages`

### KEY_PACKAGES hard-coded list
`src/cstation/commands/vps/main.py:32-45` defines `KEY_PACKAGES` — the list checked during `vps init` fact collection. Missing ones become `os.baseline.packages` defaults. If you add a new package to detect, add it here.

### What `vps apply` does NOT do
- Deploy containers (use `cstation docker apply` for that)
- Configure services (Traefik, Mailcow, Portainer)
- Deploy apps (Odoo instances)
- Code sync (rsync to `/var/lib/perfectwork/`)

## Docker workflow: plan → apply

Container deployment is a separate step after `vps apply`.

1. **Ensure `vps apply` has been run** (Docker running, `PW_NET` exists)
2. **Create fragment files** in `config/vps/<name>/` (e.g., `traefik.yaml`, `portainer.yaml`)
3. **`cstation docker plan <vps>`** — dry-run: verifies Docker + PW_NET, checks port collisions, shows drift
4. **`cstation docker apply <vps>`** — deploys all enabled containers. Supports `--service <name>`, `--yes`, `--prune`

### Fragment schema: `kind: Container`
```yaml
apiVersion: cstation/v1
kind: Container
name: traefik
enabled: true
image: traefik:latest
network: PW_NET
ports: ["80:80", "443:443", ...]
volumes: [...]
env: { TRAEFIK_DASHBOARD: "true" }
restart_policy: unless-stopped
static_config: { ... }  # optional, service-specific (e.g., Traefik's traefik.yml)
```

### Fragment schema: `kind: Stack`
```yaml
apiVersion: cstation/v1
kind: Stack
name: mailcow
enabled: false
git_repo: "https://github.com/mailcow/mailcow-dockerized"
git_branch: master
git_dir: /opt/mailcow
network: PW_NET
env: { SKIP_LETS_ENCRYPT: "y", ... }
```

### Directory convention on VPS
- Infrastructure services: `/var/lib/<service>/` (e.g., `/var/lib/traefik/`, `/var/lib/portainer/`)
- Odoo/PerfectWork: `/var/lib/perfectwork/` (reserved for Odoo instances)
- `docker apply` creates its own directories; no need to add them to `docker.directories` in VPS YAML

### Docker commands reference
```bash
cstation docker plan <vps>                                # Dry-run all enabled services
cstation docker plan <vps> --service traefik              # Dry-run single service
cstation docker apply <vps>                               # Deploy all enabled services
cstation docker apply <vps> --service traefik             # Deploy single service
cstation docker apply <vps> --yes                         # Skip confirmation
cstation docker apply <vps> --prune                       # Remove undeclared containers
cstation docker status <vps>                              # Show container state
```

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

### Testing Docker commands (future)
- Mock `SSHManager.run` with command → stdout responses for `docker compose`, `docker network ls`, etc.
- Test fragment discovery: create temp directory with `vps.yaml` + fragment files
- Test plan: verify drift detection, port collision detection, orphan detection
- Test apply: verify compose file generation, static config writing, directory creation

## README caveats
The README references `cstation service` and `requirements-dev.txt` — neither exist.
Trust `pyproject.toml` and the source code over the README.

## Key specs
- `docs/superpowers/specs/2026-04-28-vps-declarative-management-design.md` — VPS infrastructure design
- `docs/superpowers/specs/2026-04-29-docker-service-management-design.md` — Docker container service design