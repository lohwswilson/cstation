# AGENTS.md

Guidance for AI coding agents (Claude Code, Hermes, Aider, …) working in this repo. This is the single source of project conventions — do not also maintain `CLAUDE.md` or similar variants.

## Environment
- Python **3.13** (pinned via `.python-version`)
- Package manager: `uv`
- Build backend: `hatchling`
- Entry point: `cstation = "cstation.main:main"` (declared in `pyproject.toml`)

## Commands
- Run all tests: `uv run pytest -q`
- Run a single test: `uv run pytest -q tests/path/to/test_file.py::test_name`
- Run CLI: `uv run cstation <command>`
- Install (editable, with test extras): `uv pip install -e ".[test]"`

## Architecture

**Entry point** — `src/cstation/main.py` is a Typer app that registers all command groups. Each group lives in `src/cstation/commands/<group>/main.py` and exports a `typer.Typer` instance (e.g. `vps_app`, `docker_app`, `image_app`).

Current groups (registered in `main.py`):

| Group | Module | Purpose |
|-------|--------|---------|
| `vps` | `commands/vps/main.py` | VPS lifecycle (init / plan / apply / status / list) |
| `docker` | `commands/docker/main.py` | Declarative container deployment |
| `image` | `commands/image/main.py` | Multi-arch Docker image build & push |
| `github` | `commands/github/main.py` | GitHub SSH-key & repo helpers (list / sync / clone) |
| `dns` | `commands/dns/main.py` | DNS zone and record management |
| `cloudflare` | `commands/cloudflare/main.py` | Cloudflare DNS adapter (legacy alias for `dns`) |
| `auth` | `commands/auth/main.py` | Provider authentication management (`netcup`) |
| `netcup` | `commands/netcup/main.py` | Netcup provider adapter (legacy alias for `auth netcup`) |
| `odoo` | `commands/odoo/main.py` | Odoo workflows (backup / restore / sync) |
| `server` | `commands/server/main.py` | Server subcommands (`playbook`, `ssh`, `status`, `ls`, `rm`) |

**Adding a new command group**

1. Create `src/cstation/commands/<group>/main.py` exporting a `typer.Typer` instance.
2. Register it in `src/cstation/main.py`:
   ```python
   from .commands.<group>.main import <group_app>
   app.add_typer(<group_app>)
   ```

**SSH layer** — `src/cstation/ssh.py` (`SSHManager`) wraps Fabric/Paramiko. The critical method is `run_batch()`: it bundles multiple shell commands into a single SSH round-trip using `==CS_SEP==` as a separator. All fact collection is built on top of this to minimise latency.

**Config flow** — `src/cstation/config.py`. `ConfigManager` merges YAML configs from `./etc/`, `/etc/cstation/`, and `~/.config/cstation/` (lowest → highest precedence). `initialize_configuration()` is called once at startup in `main()`. Per the recent flatten (2026-07-07), live state lives under `~/.config/cstation/` — do not reintroduce legacy config paths.

**Models** — `src/cstation/models.py`. Pydantic models for `VPSConfig`, `ContainerConfig`, `DockerImageConfig`, `DNSConfig`, `GitHubConfig`. `ContainerConfig` uses `extra = "allow"` to support service-specific fields (`odoo_conf`, `traefik`, `static_config`). Every load boundary must catch `ValidationError` and render location + message per error to the user.

**Providers** — `src/cstation/providers/`. Cloud adapters (`hetzner`, `vultr`, `netcup`) plus a `static` SSH-only provider. All implement the interface in `base.py`. The `static` provider handles any server with SSH access (no cloud API needed) and is the default for `vps init` when no provider prefix is supplied.

**Fact caching** — `src/cstation/facts.py`. `load_cached_facts()` / `save_cached_facts()` read/write `.facts.json` in each VPS config directory with a `_cached_at` timestamp. `format_facts_summary()` produces the one-line display used by `vps list`. This is what makes `vps list` and `vps status` respond in under 100 ms.

## Key patterns
- All config paths resolve under `~/.config/cstation/` — VPS configs at `vps/<hostname>/vps.yaml`, container fragments as sibling YAML files, images at `images/<name>/image.yaml`.
- SSH commands should use `run_batch()` when multiple facts need collecting in one call. Single commands use `ssh.run()`.
- Dry-run is implemented via a `dry_run=True` parameter threaded into each `_apply_*` function — there is no separate code path.
- Pydantic `ValidationError` is caught at config-load boundaries and rendered to the user with location + message per error.

## VPS Management (Local-First)
Source of truth: `~/.config/cstation/vps/`.

| Command | Behaviour |
|---------|-----------|
| `vps list` | Scans the config dir and runs parallel SSH uptime checks (cached facts). |
| `vps status <host>` | Shows live Load Avg, Memory, Disk, Docker stats. `--refresh` forces live collection. |
| `vps init <host>` | Defaults to `static` provider; discovery via live SSH scan. |
| `vps plan <host>` | Dry-run of `apply` — shows what would change. |
| `vps apply <host>` | Executes the 12-phase setup pipeline over SSH. |

### `vps apply` phase order
Phases run in this order (matches `vps/main.py:_apply_*` calls in `plan`/`apply`):

1. `packages` — install baseline apt/dnf/apk packages
2. `shell` — shell config (`.bashrc`, PATH, motd)
3. `terminal` — TTY / locale settings
4. `sshd` — `sshd_config` hardening
5. `firewall` — UFW / nftables rules
6. `swap` — swap file creation
7. `tuning` — sysctl + `journald` tuning
8. `fail2ban` — jail config
9. `hostname` — set system hostname
10. `docker_daemon` — `daemon.json` (log driver, etc.)
11. `docker_networks` — create declared networks
12. `docker_directories` — create declared bind-mount dirs

Each phase accepts a `dry_run: bool` and reports what it *would* do without executing when `dry_run=True`.

## Docker Management (Declarative)
- `docker import <vps> <container>` — scans a running container on the VPS and emits a local YAML fragment.
- `docker apply <vps>` — deploys all enabled fragments under `vps/<vps>/`.
- `docker status <vps>` — shows the state of managed containers on the VPS.

## Image Management
- `image list` — enumerates available image configs in `config/images/`.
- `image build <name>` — builds a multi-arch image from `config/images/<name>/` (Dockerfile + `image.yaml`) and pushes to the configured registry.
- Auto-detects **podman** vs **docker** at runtime; for multi-arch podman builds, creates a manifest and adds per-platform images.

Images are defined by `config/images/<name>/image.yaml`. See `config/images/synercatalyst-odoo.13.0/` for a full example (Python compatibility patches, dummy deb packages, pip pinning).

## VPS YAML Schema
```yaml
apiVersion: cstation/v1
kind: VPS
identity: { name, stage, region, provider }
access:   { host, user, port, key }
facts:    { os, cpu, memory, disks, disk_usage, load_avg, docker_summary }
os:
  baseline: { packages, sshd, firewall, swap, tuning, fail2ban, hostname, journald }
docker:
  daemon:      { log_driver, log_opts, … }
  networks:    [PW_NET]
  directories: [/srv/data/…]
```

## Command Separation
- `cstation vps apply` — OS + Docker infrastructure setup.
- `cstation docker apply` — Container deployment (depends on `vps apply` having run first).
- `cstation image build` — Build and push Docker images (depends on Docker buildx / podman + registry credentials).

## Docker Image Build — Known Compatibility Issues (Odoo 13 on Python 3.10)
Full context: `docs/specs/2026-05-03-odoo-13-docker-image.md`.

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| `werkzeug.contrib` not found | Removed in werkzeug 1.0+ | Pin `werkzeug<1.0` via pip, delete system werkzeug |
| `setrlimit` TypeError (float) | Python 3.10 requires `int` | Patch `server.py`: cast args with `int()` |
| `inspect.formatargspec` removed | Python 3.12+ | Use Ubuntu 22.04 (Python 3.10) |
| `python3-vatnumber` missing | pip `vatnumber` uses `use_2to3` | Dummy deb via `equivs` |
| `reportlab.graphics.barcode` missing | Minimal system package | Install `reportlab` via pip |
