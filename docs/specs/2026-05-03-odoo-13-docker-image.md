# Odoo 13 Docker Image — Build & Deployment Guide

## 1. Overview

The `synercatalyst/odoo.13.0:latest` image runs Odoo 13 (nightly deb `13.0.20230601`) on **Ubuntu 22.04** with Python 3.10, built as a multi-arch image (linux/amd64 + linux/arm64).

## 2. Key Files

| File | Purpose |
|------|---------|
| `config/images/synercatalyst-odoo.13.0/Dockerfile` | Multi-arch Dockerfile |
| `config/images/synercatalyst-odoo.13.0/requirements.txt` | pip dependencies (werkzeug<1.0, reportlab, etc.) |
| `config/images/synercatalyst-odoo.13.0/entrypoint.sh` | Container entry point |
| `config/images/synercatalyst-odoo.13.0/odoo.conf` | Default Odoo config template |
| `config/images/synercatalyst-odoo.13.0/wait-for-psql.py` | PostgreSQL readiness probe |
| `config/images/synercatalyst-odoo.13.0/image.yaml` | Image build metadata |

## 3. Python 3.10 Compatibility Fixes

The official Odoo 13 deb targets Python 3.6 (Debian Buster). Running on Python 3.10 (Ubuntu 22.04) requires three patches:

### 3.1 werkzeug `contrib` module removed

**Problem:** Odoo 13 imports `werkzeug.contrib.fixers`, which was removed in werkzeug 1.0. Ubuntu 22.04 ships `python3-werkzeug` 2.x.

**Fix:** Pin `werkzeug<1.0` (installs 0.16.1) via pip, then delete the system werkzeug to ensure only the pip version is found:

```dockerfile
RUN pip3 install --no-cache-dir --force-reinstall --ignore-installed 'werkzeug<1.0' \
    && rm -rf /usr/lib/python3/dist-packages/werkzeug* \
    && pip3 install --no-cache-dir --upgrade -r /requirements.txt
```

See `requirements.txt`:
```
werkzeug<1.0
```

### 3.2 `resource.setrlimit` requires int, not float

**Problem:** Python 3.10 requires `resource.setrlimit()` arguments to be `int`. Odoo 13 passes `config['limit_time_cpu']` (float from config parser) and `config['limit_memory_hard']` directly, causing `TypeError: 'float' object cannot be interpreted as an integer`.

**Fix:** Post-install patch via a Python one-liner in the Dockerfile:

```dockerfile
RUN python3 -c "p='/usr/lib/python3/dist-packages/odoo/service/server.py';c=open(p).read();c=c.replace(\"config['limit_memory_hard']\",\"int(config['limit_memory_hard'])\").replace(\"cpu_time + config['limit_time_cpu']\",\"int(cpu_time + config['limit_time_cpu'])\");open(p,'w').write(c)"
```

### 3.3 `inspect.formatargspec` removed in Python 3.11+

**Problem:** Not applicable on Python 3.10 (still has `formatargspec`), but would break on Python 3.11+. This is why we use **Ubuntu 22.04** (Python 3.10) rather than Ubuntu 24.04 (Python 3.12).

## 4. Dependency Fixes

### 4.1 `python3-vatnumber` dummy package

**Problem:** Odoo 13 deb depends on `python3-vatnumber`, but `pip install vatnumber` fails on Python 3.10+ because it uses the deprecated `use_2to3` setup mechanism.

**Fix:** Create a dummy deb package using `equivs`:

```dockerfile
RUN printf "Section: python\nPriority: optional\nPackage: python3-vatnumber\nVersion: 1.0\nDescription: dummy package for odoo\n" > vatnumber-dummy \
    && equivs-build vatnumber-dummy \
    && dpkg -i python3-vatnumber_1.0_all.deb \
    && rm vatnumber-dummy python3-vatnumber_1.0_all.deb
```

### 4.2 `reportlab` for barcode support

**Problem:** Odoo's `ir_actions_report.py` imports `reportlab.graphics.barcode`, which is not included in the minimal `reportlab` namespace package on Ubuntu.

**Fix:** Install `reportlab` via pip in `requirements.txt`:

```
reportlab
```

## 5. Build & Deploy

### 5.1 Build the image

```bash
uv run cstation image build synercatalyst-odoo.13.0
```

This builds for linux/amd64 and linux/arm64 and pushes to Docker Hub as `synercatalyst/odoo.13.0:latest`.

### 5.2 Deploy on US02

```bash
# Pull latest image on the target VPS
ssh root@152.53.169.95 "docker pull synercatalyst/odoo.13.0:latest"

# Stop and remove existing container
ssh root@152.53.169.95 "docker stop US02_DEV3_US02DB && docker rm US02_DEV3_US02DB"

# Fix ownership on data directories
ssh root@152.53.169.95 "chown -R 101:101 /var/lib/US02_DEV3_US02DB/ /var/lib/perfectwork/US02/CONTAINERS/US02_dev3_US02DB/"

# Deploy via cstation
uv run cstation docker apply us02.synercatalyst.com --service US02_DEV3_US02DB --yes

# Create the DB user if not already created
ssh root@152.53.169.95 "docker exec US02_DB psql -U postgres -c \"CREATE USER us02_dev3_us02db WITH PASSWORD 'Wengseng1@' CREATEDB;\""
```

### 5.3 Verify

```bash
# Container should be "Up" (not restarting)
ssh root@152.53.169.95 "docker ps --filter name=US02_DEV3_US02DB"

# Logs should show workers alive, no traceback
ssh root@152.53.169.95 "docker logs US02_DEV3_US02DB --tail 10"

# HTTP should respond (303 redirect to database selector)
ssh root@152.53.169.95 "docker exec US02_DEV3_US02DB curl -sI http://localhost:8069/web/login"

# Access Odoo via wildcard subdomain
# https://<database>.dev3.perfectwork.app
```

## 6. Architecture Notes

- **Base image:** `ubuntu:22.04` (Python 3.10.12)
- **Odoo uid/gid:** 101:101 (Ubuntu 22.04's `adduser odoo` creates uid 101)
- **Fragment `owner`:** `"101:101"` (must match Odoo uid)
- **DB credentials:** Passed via `PASSWORD` env var, not in `odoo.conf`
- **DB user creation:** Done by `cstation docker apply` via `_create_db_user()`
- **Traefik routing:** Wildcard `*.dev3.perfectwork.app` via file-provider dynamic config
- **Addons path:** `/mnt`, `/mnt/SYC`, `/mnt/ENTERPRISE`, `/mnt/OCA`, `/mnt/CUSTOMERS`, `/mnt/ADVANCE`, `/mnt/THEMES`, `/mnt/TEST`, `/mnt/extra-addons`
- **PW3.0 addon/source data:** Must be rsync'd from SG01 to `/var/lib/perfectwork/PW_ADDONS.3.0/` and `/var/lib/perfectwork/PW.3.0/` on the target VPS

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: No module named 'werkzeug.contrib'` | System werkzeug 2.x overrides pip werkzeug 0.16.1 | Delete system werkzeug: `rm -rf /usr/lib/python3/dist-packages/werkzeug*` in Dockerfile |
| `TypeError: 'float' object cannot be interpreted as an integer` in `setrlimit` | Python 3.10 requires int args for `resource.setrlimit` | Patch `server.py` to wrap args with `int()` |
| `ImportError: cannot import name 'formatargspec'` | Python 3.12 removed `inspect.formatargspec` | Use Ubuntu 22.04 (Python 3.10) instead of 24.04 |
| Workers spawn and immediately exit | `setrlimit` float error (see above) | Apply the int-cast patch |
| Container exits with code 127 (`odoo: not found`) | `apt-get install -f` removes the odoo deb | Use `dpkg --force-depends` instead |
| DB authentication failed | DB user not created or password mismatch | Create user: `docker exec US02_DB psql -U postgres -c "CREATE USER us02_dev3_us02db WITH PASSWORD '...' CREATEDB;"` |
| 500 Internal Server Error on `/web/login` | DB user not yet created (first deploy) | Create the DB user, then refresh |