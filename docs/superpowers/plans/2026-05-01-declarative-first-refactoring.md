# Implementation Plan: Declarative-First Docker Service Refactoring

**Date**: 2026-05-01
**Objective**: Make all container configuration declarative via YAML fragments. Remove hard-coded service-specific logic from Python classes. Any container's routing, command, directory ownership, and structure should be configurable from its fragment YAML — no Python changes needed.

## Design Principle

**YAML is the single source of truth.** Python is the engine that reads YAML and executes it. Service-specific Python classes should be minimal — only for truly unique behavior that can't be expressed declaratively. The goal: adding a new container (PostgreSQL, n8n, Odoo) requires only a new YAML file, no new Python code.

## Changes

### 1. Add `command` field to fragment YAML ✅ COMPLETE

**Problem**: TraefikService hard-codes `"command": ["--configFile=/etc/traefik/traefik.yml"]` in `_render_compose()`. Any container needing CLI args requires a Python subclass.

**Solution**: Add `command` field support to `ImageService._render_compose()`. Move Traefik's command to `traefik.yaml`.

**Files changed**:
- `src/cstation/commands/docker/services/image_service.py` — Added `if config.get("command"): service_def["command"] = config["command"]`
- `src/cstation/commands/docker/services/traefik.py` — Removed `_render_compose()` override, now uses base class
- `config/vps/eu01.synercatalyst.com/traefik.yaml` — Added `command: ["--configFile=/etc/traefik/traefik.yml"]`
- `tests/commands/test_docker_cli.py` — Updated Traefik compose tests to verify command from config
- `AGENTS.md` — Documented `command` field in Container schema

### 2. Add `owner` field to fragment YAML ✅ COMPLETE

**Problem**: StalwartService hard-codes `chown -R 2000:2000 /var/lib/stalwart`. Any container needing special directory ownership requires a Python subclass override.

**Solution**: Add `owner` field to `ImageService.apply()`. After creating dirs and writing configs, if `owner` is set, `chown -R <owner> <service_dir>`. Also added to `plan()` for drift detection.

**Files changed**:
- `src/cstation/commands/docker/services/image_service.py` — Added owner handling in `apply()` and `plan()`
- `src/cstation/commands/docker/services/stalwart.py` — Removed `apply()` override entirely; StalwartService is now just `name` + registration
- `config/vps/eu01.synercatalyst.com/stalwart.yaml` — Added `owner: "2000:2000"`
- `tests/commands/test_docker_cli.py` — Updated Stalwart chown test, added ImageService owner tests
- `AGENTS.md` — Documented `owner` field in Container schema

### 3. Make `subdirs` declarable from fragment YAML ✅ COMPLETE

**Problem**: `subdirs = ["etc", "conf", ...]` is hard-coded in Python service classes. Changing directory structure requires editing Python.

**Solution**: `_create_dirs()` checks `config.get("subdirs")` first, falls back to `self.subdirs` class attribute. Fragment YAML can override subdirs.

**Files changed**:
- `src/cstation/commands/docker/services/image_service.py` — Modified `_create_dirs()` to check config first
- `config/vps/eu01.synercatalyst.com/traefik.yaml` — Added `subdirs: [etc, conf, letsencrypt, logs]`
- `config/vps/eu01.synercatalyst.com/stalwart.yaml` — Added `subdirs: [etc, data]`
- `config/vps/eu01.synercatalyst.com/portainer.yaml` — Added `subdirs: [data]`
- `tests/commands/test_docker_cli.py` — Added submodule override tests
- `AGENTS.md` — Documented `subdirs` field in Container schema

### 4. Fix TraefikService compose key to use `self.name` ✅ COMPLETE

**Problem**: TraefikService hard-codes `{"traefik": service_def}` instead of `{self.name: service_def}`.

**Solution**: Use `self.name` in compose output for consistency.

**Files changed**:
- `src/cstation/commands/docker/services/traefik.py` — Changed `"traefik"` to `self.name` in compose dict

### 5. Read network name from VPS config in preflight check ✅ COMPLETE

**Problem**: `_preflight_check()` hard-codes `"PW_NET"`. Should read from VPS config's `docker.networks`.

**Solution**: `_preflight_check()` accepts `vps_data: dict`, reads `docker.networks[0]` with `"PW_NET"` fallback.

**Files changed**:
- `src/cstation/commands/docker/main.py` — `_preflight_check()` now accepts `vps_data`, reads network from config
- All callers (`docker_plan`, `docker_apply`, `docker_status`) pass `vps_data`
- `tests/commands/test_docker_cli.py` — Updated preflight tests to pass vps_data

## Files Changed (Complete List)

### Source code
- `src/cstation/commands/docker/services/image_service.py` — command, owner, subdirs support
- `src/cstation/commands/docker/services/traefik.py` — Removed `_render_compose()` override, fixed compose key
- `src/cstation/commands/docker/services/stalwart.py` — Removed `apply()` override (just name + registration)
- `src/cstation/commands/docker/services/portainer.py` — Unchanged (already just name + subdirs)
- `src/cstation/commands/docker/main.py` — preflight reads network from VPS config

### Config fragments
- `config/vps/eu01.synercatalyst.com/traefik.yaml` — Added `command`, `subdirs`, `traefik` (dashboard routing)
- `config/vps/eu01.synercatalyst.com/stalwart.yaml` — Added `owner`, `subdirs`, `traefik` (admin routing)
- `config/vps/eu01.synercatalyst.com/portainer.yaml` — Added `subdirs`, `traefik` (UI routing)

### Tests
- `tests/commands/test_docker_cli.py` — Updated all affected tests

### Documentation
- `AGENTS.md` — Documented `command`, `owner`, `subdirs`, `traefik` fields
- `docs/superpowers/plans/2026-05-01-declarative-first-refactoring.md` — This plan

## Remaining Work

None for this phase. All 5 items are complete.

## Updated Fragment Schema

```yaml
apiVersion: cstation/v1
kind: Container
name: my-service
enabled: true
image: my-service:latest
container_name: EU01_my-service
network: PW_NET
ports: ["80:80"]
volumes: [...]
env: {...}
env_file: .env
secrets: [...]
restart_policy: unless-stopped
command: ["--flag", "value"]       # NEW: Docker compose command override
owner: "1000:1000"                  # NEW: chown -R after apply (uid:gid)
subdirs: [data, etc]               # NEW: Override service subdirectories
traefik:                            # Traefik dynamic routing config
  http:
    routers:
      my-service:
        rule: "Host(`my-service.example.com`)"
        entryPoints: [websecure]
        service: my-service
        tls:
          certResolver: le_dns_resolver
    services:
      my-service:
        loadBalancer:
          serverPort: 3000
```

## Service Class Status After Refactoring

| Service Class | Has Override | Purpose |
|---------------|-------------|---------|
| `ImageService` | N/A (base) | Handles command, owner, subdirs, traefik, static_config generically |
| `TraefikService` | `_write_static_configs`, `_plan_static_configs` | Writes `static_config` to `etc/traefik.yml` + calls super for `traefik` key |
| `StalwartService` | None | Just `name = "stalwart"` + auto-registration |
| `PortainerService` | None | Just `name = "portainer"` + auto-registration |