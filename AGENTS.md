# AGENTS.md

## Environment
- Python **3.13** (exact — see `.python-version`)
- Package manager: `uv`
- Build backend: `hatchling`
- Entry point: `cstation = "cstation.main:main"` in `pyproject.toml`

## Commands
- Run all tests: `uv run pytest -q`
- Run CLI: `uv run cstation <command>`
- Install in editable mode: `uv pip install -e .`

## Architecture
- `src/cstation/main.py` — Typer app, registers all command groups
- `src/cstation/commands/vps/main.py` — Core VPS orchestration (Local-First, SSH-Centric)
- `src/cstation/commands/docker/main.py` — Docker service management & import logic
- `src/cstation/providers/` — Cloud provider adapters (Hetzner, Vultr)
- `src/cstation/providers/static.py` — Default SSH-based provider
- `src/cstation/ssh.py` — `SSHManager` wrapping Fabric, supporting optimized `run_batch` for performance.
- `src/cstation/models.py` — Pydantic models for configuration validation and type safety.
- `src/cstation/facts.py` — Logic for local fact caching and summary formatting.

### Adding a new command group
1. Create `src/cstation/commands/<group>/main.py` with a Typer app
2. Register in `src/cstation/main.py`:
   ```python
   from .commands.<group>.main import <group_app>
   app.add_typer(<group_app>)
   ```
### Performance & Cache
- **Fact Caching**: Live metrics are cached in `config/vps/<host>/.facts.json` to enable sub-100ms response times for `vps list` and `vps status`.
- **SSH Batching**: Facts are collected in a single SSH round-trip using subshell grouping and a custom separator (`==CS_SEP==`) to minimize latency.

### Safety & Orchestration
- **Validation**: Every configuration (VPS, Container, DNS, GitHub) is validated against Pydantic models in `src/cstation/models.py`.
- **Native SSH**: Remote setup tasks (OS baseline, Docker, GitHub SSH, Odoo Restore) are performed directly via `SSHManager` (Fabric/Paramiko), eliminating Ansible dependencies for orchestration.

### VPS Management (Local-First)
...

The source of truth is the `config/vps/` directory.

- **`list`**: Scans `config/vps/` and performs parallel SSH uptime checks.
- **`status <hostname>`**: Connects via SSH to show live Load Avg, Memory, Disk, and Docker stats.
- **`init <hostname>`**: Defaults to `static` provider, discovery via live SSH scan.
- **`apply <hostname>`**: Executes OS hardening and Docker setup via SSH.

### Docker Management (Declarative)
- **`import <vps> <container>`**: Scans a running container on the VPS and generates a local YAML fragment.
- **`apply <vps>`**: Deploys all enabled fragments in `config/vps/<vps>/`.
- **`status <vps>`**: Shows the state of managed containers on the VPS.

### Static Provider
The `static` provider handles any server with SSH access. It bypasses Cloud APIs and relies on `access.host` in the YAML. It is the default for `vps init` when no provider prefix is provided.

## VPS YAML Schema
```yaml
apiVersion: cstation/v1
kind: VPS
identity: { name, stage, region, provider }
access: { host, user, port, key }
facts: { os, cpu, memory, disks, disk_usage, load_avg, docker_summary }
os:
  baseline: { packages, sshd, firewall }
docker:
  daemon: { log_driver, log_opts, ... }
  networks: [PW_NET]
```

## Command Separation
- `cstation vps apply`: OS + Docker infrastructure setup.
- `cstation docker apply`: Container deployment (depends on `vps apply` having run first).
