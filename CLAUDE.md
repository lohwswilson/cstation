# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Run all tests: `uv run pytest -q`
- Run a single test: `uv run pytest -q tests/path/to/test_file.py::test_name`
- Run CLI: `uv run cstation <command>`
- Install with all deps: `uv pip install -e ".[test]"`

## Architecture

**Entry point**: `src/cstation/main.py` — Typer app that registers all command groups. Each group lives in `src/cstation/commands/<group>/main.py` and exports a `typer.Typer` instance (e.g., `vps_app`, `docker_app`, `image_app`). To add a new group, create the module and call `app.add_typer(...)` in `main.py`.

**SSH layer**: `src/cstation/ssh.py` (`SSHManager`) wraps Fabric/Paramiko. The critical method is `run_batch()` — it bundles multiple shell commands into a single SSH round-trip using `==CS_SEP==` as a separator. All fact collection is built on top of this to minimize latency.

**Config flow**: `src/cstation/config.py` — `ConfigManager` merges YAML configs from `./etc/`, `/etc/cstation/`, and `~/.config/cstation/` (lowest to highest precedence). `initialize_configuration()` is called once at startup in `main()`.

**Models**: `src/cstation/models.py` — Pydantic models for `VPSConfig`, `ContainerConfig`, `DockerImageConfig`, `DNSConfig`, `GitHubConfig`. Container config uses `extra = "allow"` to support service-specific fields (`odoo_conf`, `traefik`, `static_config`).

**Providers**: `src/cstation/providers/` — Cloud provider adapters (Hetzner, Vultr, Netcup, Static). All follow the same interface defined in `base.py`. The `static` provider handles any server with SSH access (no cloud API needed).

**Fact caching**: `src/cstation/facts.py` — `load_cached_facts()` / `save_cached_facts()` read/write `.facts.json` in each VPS config directory with a `_cached_at` timestamp. `format_facts_summary()` produces the one-line display used in `vps list`.

**VPS management** (`src/cstation/commands/vps/main.py`): The largest module. Key flow: `init` creates config from provider metadata + SSH facts; `plan`/`apply` follows a 13-phase pipeline (upgrade → packages → shell → terminal → sshd → firewall → swap → tuning → fail2ban → hostname → docker_daemon → docker_networks → docker_directories); `status` uses cached facts by default, `--refresh` forces live collection.

**Docker image builds** (`src/cstation/commands/image/main.py`): Reads `config/images/<name>/image.yaml` + Dockerfile. Auto-detects podman vs docker runtime. For multi-arch podman builds, creates a manifest and adds per-platform images.

## Key patterns
- All config paths resolve under `~/.config/cstation/` — VPS configs at `vps/<hostname>/vps.yaml`, container fragments as sibling YAML files, images at `images/<name>/image.yaml`.
- SSH commands should use `run_batch()` when multiple facts need collecting in one call. Single commands use `ssh.run()`.
- Dry-run is implemented via a `dry_run=True` parameter passed through to each `_apply_*` function, not by a separate code path.
- Pydantic `ValidationError` is caught at config load boundaries and rendered to the user with location + message per error.
