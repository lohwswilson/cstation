# Odoo Container Service — Design Specification

## 1. Overview

CStation currently deploys PostgreSQL containers with tuned parameters via declarative fragment YAMLs. This spec adds **Odoo/PerfectWork container support** with:

- `odoo.conf` rendering from declarative fragment config
- Traefik routing via Docker labels AND/OR file-provider dynamic config
- PostgreSQL DB user creation at deploy time
- Data directory ownership (`chown 101:102`) and permissions (`chmod`)
- Auto-detection of Odoo containers by `odoo_conf` key in fragment

---

## 2. Current State Analysis

### 2.1 What Ansible Does (That We Need to Replace)

| Step | Ansible Action | CStation Gap |
|------|---------------|--------------|
| 1 | Create Docker container (image, ports, volumes, env, network) | Done — `ImageService._render_compose()` |
| 2 | Add Traefik labels (routing, TLS, services, middlewares) | **Missing** — no `labels` support in compose |
| 3 | Write Traefik dynamic config (websocket/longpolling YAML) | **Partially done** — `traefik` key writes to file provider |
| 4 | Render `pw.conf`/`odoo.conf` with 20+ Odoo tuning params | **Missing** — no config file rendering |
| 5 | `chown -R 101:102` + `chmod -R 766` on data volume | **Missing** — `owner` exists, `chmod` does not |
| 6 | Create PostgreSQL user via `postgresql_user` module | **Missing** — no DB user creation |
| 7 | Open UFW port for polling | Out of scope for docker apply (belongs in `vps apply`) |

### 2.2 Production Traefik Patterns

Three routing patterns observed in production:

| Pattern | Example | Mechanism | Cert Resolver | Use Case |
|---------|---------|-----------|---------------|-----------|
| **Multi-domain** | SG07_SEQ8, SG01_FOCUS | Docker labels with `Host()` | `le_resolver` | Specific domains (1-5) |
| **Wildcard** | SG01_DEV7 | Docker labels with `HostRegexp()` | `le_dns_resolver` | Multi-tenant (`*.domain`) |
| **File provider** | SG07 SEQ8 websocket, SG01 all websocket | Dynamic YAML in Traefik conf dir | Either | Websocket/longpolling |

Both cert resolvers exist on all VPS:
- `le_resolver` — ACME TLS challenge (HTTP-01) for specific domains
- `le_dns_resolver` — ACME DNS challenge (Cloudflare DNS-01) for wildcards

### 2.3 Existing Fragment (SG07_SEQ8) — What's Missing

```yaml
apiVersion: cstation/v1
kind: Container
name: SG07_SEQ8_SG07DB
enabled: true
image: synercatalyst/odoo.18.0:latest
container_name: SG07_SEQ8_SG07DB
network: PW_NET
ports:
  - 3338:8069
  - 3337:8072
volumes:
  - /var/lib/perfectwork/PW_ADDONS.18.0:/mnt
  - /var/lib/perfectwork/SG07/SG07_SEQ8_SG07DB:/var/lib/odoo
  - /var/lib/perfectwork/PW.18.0:/usr/lib/python3/dist-packages/odoo
env:
  HOST: SG07_DB
  PORT: '5432'
  USER: sg07_seq8_sg07db
  PASSWORD: wai39kua
  ODOO_RC: /var/lib/odoo/odoo.conf
  LANG: en_US.UTF-8
  ODOO_VERSION: '18.0'
restart_policy: always
```

**Missing**: `odoo_conf`, `labels`, `owner`, `chmod`, `secrets` (PASSWORD is plaintext)

---

## 3. Design Decisions

### 3.1 OdooService Auto-Detection

**Decision**: When a fragment YAML contains an `odoo_conf` key, `_get_service_instance()` returns an `OdooService` instead of generic `ImageService`.

Rationale: Odoo container names don't follow a predictable pattern (e.g., `SG07_SEQ8_SG07DB`), so name-based detection won't work. The `odoo_conf` key is the natural indicator.

### 3.2 `odoo.conf` Rendering (Replacing Ansible Jinja2 Template)

**Legacy approach**: Ansible used Jinja2 templates (`pw.conf.j2` / `pw.conf_full.j2`) where each `PW_*` variable in the template was substituted from the per-container YAML file (e.g., `SG07_SEQ8_SG07DB.yaml`). The template contained 20+ `{{ PW_* }}` variables, default values, and comments.

**New approach**: The fragment YAML's `odoo_conf` dict replaces the Jinja2 template entirely. Instead of a template + variables, the fragment contains all the values directly. The `OdooService._render_odoo_conf()` method merges user-specified values with sensible defaults and renders the final INI file — this is the equivalent of the Jinja2 template rendering.

**Mapping from legacy to new**:

| Legacy PW Variable | New `odoo_conf` Key | Default |
|---------------------|---------------------|---------|
| `PW_addons_path` | `addons_path` | — (required) |
| `PW_db_host` | `db_host` | — (required, should match `env.HOST`) |
| `PW_db_user` | `db_user` | — (required, should match `env.USER`) |
| `PW_db_password` | _(excluded — use `env.PASSWORD` or `secrets`)_ | — |
| `PW_db_port` | `db_port` | `5432` |
| `PW_admin_passwd` | `admin_passwd` | — (required) |
| `PW_db_maxconn` | `db_maxconn` | `32` |
| `PW_dbfilter` | `dbfilter` | — (required, per-app pattern like `SEQ*`) |
| `PW_log_level` | `log_level` | `info` |
| `PW_server_wide_modules` | `server_wide_modules` | `web` |
| `PW_workers` | `workers` | `3` |
| `PW_max_cron_threads` | `max_cron_threads` | `2` |
| `PW_limit_time_cpu` | `limit_time_cpu` | `1800` |
| `PW_limit_time_real` | `limit_time_real` | `3600` |
| `PW_limit_memory_soft` | `limit_memory_soft` | `1677721600` |
| `PW_limit_memory_hard` | `limit_memory_hard` | `1073741824` |
| `PW_limit_request` | `limit_request` | `8192` |

**Rendering rules**:
- `ODOO_RC=/var/lib/odoo/odoo.conf` env var points Odoo to this config file
- Keys preserve casing (critical for Odoo: `addons_path`, `db_host`, `server_wide_modules`, etc.)
- Values are written as-is (strings remain strings, numbers remain numbers)
- User-specified keys override defaults; user keys appear in their original order
- `db_password` is **excluded** from `odoo.conf` — it's provided via env var `PASSWORD` instead (matches current production behavior where it's commented out: `# db_password = wai39kua`)
- `db_name = False` is always included (Odoo default — shows all databases matching `dbfilter`)

### 3.3 Traefik Routing: Labels vs File Provider

**Decision**: Support **both** mechanisms:

| Fragment Key | Mechanism | Use Case |
|-------------|-----------|----------|
| `labels` | Docker labels in compose service def | Simple domain routing, non-wildcard |
| `traefik` | File provider YAML in `/var/lib/traefik/conf/{name}.yml` | Wildcard routing, websocket, custom middlewares |

Both can coexist. For most Odoo containers:
- **Multi-domain containers** (specific domains) → `labels` key
- **Wildcard containers** (`*.domain.app`) → `traefik` key

### 3.4 db_password Handling

**Decision**: DB password is provided via:
1. `env.PASSWORD` (or `secrets` key resolved from `~/.config/cstation/config.yaml`)
2. `odoo_conf.db_password` can optionally be set but is NOT rendered to `odoo.conf`
3. The container connects to PG via `HOST`/`PORT`/`USER`/`PASSWORD` env vars (Odoo default behavior)
4. `odoo_conf` only contains `db_host`, `db_user`, `db_port` — not `db_password`

This matches production where `odoo.conf` has `# db_password = wai39kua` commented out.

### 3.5 Database User and Database Creation

**Context**: A single PostgreSQL container (e.g., `SG07_DB`) serves multiple Odoo instances. Each Odoo instance has its own PostgreSQL user and database, isolated via the `dbfilter` in `odoo.conf`. For example:

| Odoo Container | PG User | PG Database | dbfilter |
|---------------|---------|-------------|----------|
| SG07_SEQ8_SG07DB | `sg07_seq8_sg07db` | `SEQ8` | `SEQ*` |
| SG07_ANSIS8_SG07DB | `sg07_ansis8_sg07db` | `ANSIS8` | `ANSIS*` |
| SG07_BYQ6_SG07DB | `sg07_byq6_sg07db` | `BYQ6` | `BYQ*` |

**Decision**: `OdooService.apply()` creates the PostgreSQL user AND database **before** `docker compose up -d`:

**Step 1 — Create user** (idempotent, skips if exists):

```bash
docker exec <db_container> psql -U postgres -c \
  "DO \$\$ BEGIN CREATE USER \"<user>\" WITH PASSWORD '<password>' SUPERUSER; \
   EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;"
```

**Step 2 — Create database owned by that user** (idempotent, uses `CREATE DATABASE` with `IF NOT EXISTS` equivalent):

```bash
docker exec <db_container> psql -U postgres -c \
  "SELECT 'CREATE DATABASE \"<dbname>\" OWNER \"<user>\"' WHERE NOT EXISTS \
   (SELECT 1 FROM pg_database WHERE datname='<dbname>')\gexec"
```

Or more simply with a conditional:
```bash
docker exec <db_container> psql -U postgres -c \
  "CREATE DATABASE \"<dbname>\" OWNER \"<user>\";" 2>&1 || true
```

**New fragment key: `odoo_db`** — declares the database name to create:

```yaml
odoo_db:
  name: SEQ8        # database name to create
  owner: sg07_seq8_sg07db  # must match odoo_conf.db_user
```

If `odoo_db` is omitted, no database is created (assumes database already exists or Odoo will create it on first run via `dbfilter`).

**Where values come from**:
- `db_container` → `env.HOST` (the PG container name on `PW_NET`, e.g., `SG07_DB`)
- `db_user` → `odoo_conf.db_user` or `env.USER` (e.g., `sg07_seq8_sg07db`)
- `db_password` → resolved secrets or `env.PASSWORD`
- `dbname` → `odoo_db.name` (e.g., `SEQ8`)
- `owner` → `odoo_db.owner` (defaults to `db_user`)

**Idempotency**: Both user creation and database creation are idempotent — they skip if the resource already exists.

### 3.6 File Ownership

**Decision**: After writing `odoo.conf` and before container start:
1. `chown 101:102` on the data volume directory (host path of volume mounted to `/var/lib/odoo`)
2. `chown 101:102` on `odoo.conf` specifically
3. `chmod` on the data volume directory (configurable via `chmod` key, default `766`)

The data volume host path is auto-detected from `volumes` list (the entry mounting to `/var/lib/odoo`).

### 3.7 `privileged` Flag

**Decision**: Add `privileged` support to `_render_compose()`. The current production containers do NOT use privileged mode (verified: `SG07_SEQ8_SG07DB` has `Privileged: false`). Available as opt-in but not default.

---

## 4. Schema: Odoo Fragment YAML

### 4.1 Full Schema (SG07_SEQ8 Example — Multi-Domain Labels)

```yaml
apiVersion: cstation/v1
kind: Container
name: SG07_SEQ8_SG07DB
enabled: true
image: synercatalyst/odoo.18.0:latest
container_name: SG07_SEQ8_SG07DB
network: PW_NET
ports:
  - 3338:8069
  - 3337:8072
volumes:
  - /var/lib/perfectwork/PW_ADDONS.18.0:/mnt
  - /var/lib/perfectwork/SG07/SG07_SEQ8_SG07DB:/var/lib/odoo
  - /var/lib/perfectwork/PW.18.0:/usr/lib/python3/dist-packages/odoo
env:
  HOST: SG07_DB
  PORT: '5432'
  USER: sg07_seq8_sg07db
  ODOO_RC: /var/lib/odoo/odoo.conf
  LANG: en_US.UTF-8
  ODOO_VERSION: '18.0'
secrets:
  - DB_PASSWORD
restart_policy: always
labels:
  traefik.enable: "true"
  traefik.http.routers.SG07_SEQ8_SG07DB.entrypoints: websecure
  traefik.http.routers.SG07_SEQ8_SG07DB.rule: Host(`skinequality.com`)
  traefik.http.routers.SG07_SEQ8_SG07DB.service: SG07_SEQ8_SG07DB
  traefik.http.routers.SG07_SEQ8_SG07DB.tls: "true"
  traefik.http.routers.SG07_SEQ8_SG07DB.tls.certresolver: le_resolver
  traefik.http.routers.SG07_SEQ8_SG07DB.middlewares: compress,security-headers,sslheader
  traefik.http.routers.SG07_SEQ8_SG07DB_2.entrypoints: websecure
  traefik.http.routers.SG07_SEQ8_SG07DB_2.middlewares: compress,security-headers,sslheader
  traefik.http.routers.SG07_SEQ8_SG07DB_2.rule: Host(`www.skinequality.com`)
  traefik.http.routers.SG07_SEQ8_SG07DB_2.service: SG07_SEQ8_SG07DB
  traefik.http.routers.SG07_SEQ8_SG07DB_2.tls: "true"
  traefik.http.routers.SG07_SEQ8_SG07DB_2.tls.certresolver: le_resolver
  # ... additional domain routers (beautywithpro.com, www.beautywithpro.com)
  traefik.http.routers.SG07_SEQ8_SG07DB_ws.entrypoints: websecure
  traefik.http.routers.SG07_SEQ8_SG07DB_ws.middlewares: compress,security-headers,sslheader
  traefik.http.routers.SG07_SEQ8_SG07DB_ws.rule: "Host(`skinequality.com`) && (PathPrefix(`/longpolling`) || PathPrefix(`/websocket`) || Path(`/websocket`))"
  traefik.http.routers.SG07_SEQ8_SG07DB_ws.service: SG07_SEQ8_SG07DB_ws
  traefik.http.routers.SG07_SEQ8_SG07DB_ws.tls: "true"
  traefik.http.routers.SG07_SEQ8_SG07DB_ws.tls.certresolver: le_resolver
  # ... additional websocket routers per domain
  traefik.http.services.SG07_SEQ8_SG07DB.loadbalancer.server.port: "8069"
  traefik.http.services.SG07_SEQ8_SG07DB_ws.loadbalancer.server.port: "8072"
odoo_conf:
  db_host: SG07_DB
  db_port: 5432
  db_user: sg07_seq8_sg07db
  dbfilter: SEQ*
  admin_passwd: Wengseng1@
  db_maxconn: 32
  addons_path: /mnt/ansis, /mnt/ENTERPRISE, /mnt/OCA, /mnt/customers
  server_wide_modules: web
  log_level: info
  workers: 5
  max_cron_threads: 2
  limit_memory_soft: 1677721600
  limit_memory_hard: 1073741824
  limit_request: 8192
  limit_time_cpu: 1800
  limit_time_real: 3600
odoo_db:
  name: SEQ8
  owner: sg07_seq8_sg07db
owner: "101:102"
chmod: "766"
```

### 4.2 Wildcard Variant (File Provider Traefik)

```yaml
apiVersion: cstation/v1
kind: Container
name: US02_DEV7_Wildcard
enabled: true
image: synercatalyst/perfectwork7.0:latest
container_name: US02_DEV7_Wildcard
network: PW_NET
volumes:
  - /var/lib/perfectwork/PW_ADDONS.17.0:/mnt
  - /var/lib/perfectwork/US02/DEV7:/var/lib/odoo
  - /var/lib/perfectwork/PW.17.0:/usr/lib/python3/dist-packages/odoo
secrets:
  - DB_PASSWORD
env:
  HOST: US02_DB
  USER: us02_dev7
  ODOO_RC: /var/lib/odoo/odoo.conf
odoo_conf:
  db_host: US02_DB
  db_port: 5432
  db_user: us02_dev7
  dbfilter: DEV7*
  admin_passwd: Wengseng1@
  db_maxconn: 32
  addons_path: /mnt, /mnt/ENTERPRISE, /mnt/OCA, /mnt/customers, /mnt/themes
  server_wide_modules: web
  log_level: info
  workers: 5
  max_cron_threads: 2
  limit_memory_soft: 1677721600
  limit_memory_hard: 1073741824
  limit_request: 8192
  limit_time_cpu: 1800
  limit_time_real: 3600
odoo_db:
  name: DEV7
  owner: us02_dev7
owner: "101:102"
chmod: "750"
traefik:
  http:
    routers:
      us02-dev7:
        rule: "HostRegexp(`{subdomain:[a-z0-9]+}.dev7.perfectwork.app`)"
        entryPoints:
          - websecure
        middlewares:
          - compress
          - sslheader
        tls:
          certResolver: le_dns_resolver
          domains:
            - main: "dev7.perfectwork.app"
              sans:
                - "*.dev7.perfectwork.app"
        service: us02-dev7-main
      us02-dev7-ws:
        rule: "Path(`/websocket`) && HostRegexp(`{subdomain:[a-z0-9]+}.dev7.perfectwork.app`)"
        entryPoints:
          - websecure
        middlewares:
          - upgradeheader
          - sslheader
        tls:
          certResolver: le_dns_resolver
        service: us02-dev7-ws
    services:
      us02-dev7-main:
        loadBalancer:
          servers:
            - url: "http://US02_DEV7_Wildcard:8069"
      us02-dev7-ws:
        loadBalancer:
          servers:
            - url: "http://US02_DEV7_Wildcard:8072"
    middlewares:
      upgradeheader:
        headers:
          customRequestHeaders:
            Connection: "Upgrade"
            Upgrade: "websocket"
      sslheader:
        headers:
          customRequestHeaders:
            X-Forwarded-Proto: "https"
restart_policy: always
```

---

## 5. `odoo_conf` INI Rendering Specification

### 5.1 Input (fragment YAML)

```yaml
odoo_conf:
  db_host: SG07_DB
  db_port: 5432
  db_user: sg07_seq8_sg07db
  dbfilter: SEQ*
  admin_passwd: Wengseng1@
  db_maxconn: 32
  addons_path: /mnt/ansis, /mnt/ENTERPRISE, /mnt/OCA, /mnt/customers
  server_wide_modules: web
  log_level: info
  workers: 5
  max_cron_threads: 2
  limit_memory_soft: 1677721600
  limit_memory_hard: 1073741824
  limit_request: 8192
  limit_time_cpu: 1800
  limit_time_real: 3600
```

### 5.2 Output (written to `{data_volume}/odoo.conf`)

```ini
[options]
addons_path = /mnt/ansis, /mnt/ENTERPRISE, /mnt/OCA, /mnt/customers
app_store = install
csv_internal_sep = ,
data_dir = /var/lib/odoo
db_host = SG07_DB
db_port = 5432
db_user = sg07_seq8_sg07db
dbfilter = SEQ*
admin_passwd = Wengseng1@
db_maxconn = 32
db_sslmode = prefer
db_template = template1
http_enable = True
http_interface = 
http_port = 8069
longpolling_port = 8072
list_db = True
log_db = False
log_db_level = warning
log_handler = :INFO
log_level = info
logrotate = True
max_cron_threads = 2
proxy_mode = True
server_wide_modules = web
unaccent = False
without_demo = False
workers = 5
limit_memory_soft = 1677721600
limit_memory_hard = 1073741824
limit_request = 8192
limit_time_cpu = 1800
limit_time_real = 3600
transient_age_limit = 1.0
```

### 5.3 Default Values

These are injected if not specified in the fragment (matching current production `odoo.conf`):

```python
ODOO_CONF_DEFAULTS = {
    "app_store": "install",
    "csv_internal_sep": ",",
    "data_dir": "/var/lib/odoo",
    "db_sslmode": "prefer",
    "db_template": "template1",
    "http_enable": "True",
    "http_interface": "",
    "http_port": "8069",
    "longpolling_port": "8072",
    "list_db": "True",
    "log_db": "False",
    "log_db_level": "warning",
    "log_handler": ":INFO",
    "logrotate": "True",
    "proxy_mode": "True",
    "transient_age_limit": "1.0",
    "unaccent": "False",
    "without_demo": "False",
}
```

### 5.4 Excluded Keys

- `db_password` — provided via `env.PASSWORD` or secrets, NOT in conf file
- Keys starting with `_` — internal metadata

### 5.5 Key Ordering

Output follows the order from the live production `odoo.conf` on SG07:

1. `addons_path` (first — it's the longest and most important)
2. Database settings (`app_store`, `csv_internal_sep`, `data_dir`, `db_*`, `admin_passwd`, `dbfilter`)
3. HTTP/service settings (`http_*`, `longpolling_port`, `list_db`, `log_*`, `logrotate`)
4. Worker/tuning settings (`max_cron_threads`, `proxy_mode`, `server_wide_modules`, `unaccent`, `without_demo`, `workers`, `limit_*`)

User-specified keys override defaults. User keys appear in their original order; defaults fill in the gaps.

---

## 6. Odoo Tuning Guidelines

Tuning values per server profile, derived from the Ansible templates and production configs:

| Parameter | Dev (per container) | Prod Standard | Notes |
|-----------|--------------------:|--------------:|-------|
| `workers` | 3-5 | 5-8 | ~1 per CPU core, max 2*CPU+1 |
| `max_cron_threads` | 2 | 2 | Rarely needs more |
| `limit_memory_soft` | 1,677,721,600 (1.6 GB) | 2,684,354,560 (2.5 GB) | Per-worker soft limit |
| `limit_memory_hard` | 1,073,741,824 (1 GB) | 2,684,354,560 (2.5 GB) | Per-worker hard limit |
| `limit_request` | 8192 | 8192 | Requests before worker recycle |
| `limit_time_cpu` | 1800 | 1800 | CPU seconds per request |
| `limit_time_real` | 3600 | 3600 | Wall-clock seconds per request |
| `db_maxconn` | 32 | 64 | PG connections per container |
| `dbfilter` | `^%d$` or per-app | Per-app pattern | `^%d$` for multi-tenant with `db_name` |
| `server_wide_modules` | `web` | `web` or `web,queue_job` | `queue_job` for PW5+ |

---

## 7. Implementation Plan

### Step 1: Add `labels` and `privileged` to `ImageService._render_compose()`

**File**: `src/cstation/commands/docker/services/image_service.py`

Add after the `command` block in `_render_compose()`:

```python
if config.get("labels"):
    service_def["labels"] = config["labels"]
if config.get("privileged"):
    service_def["privileged"] = config["privileged"]
```

**Test**: Verify `labels` dict and `privileged: true` appear in rendered compose YAML.

### Step 2: Add `chmod` to `ImageService.apply()`

**File**: `src/cstation/commands/docker/services/image_service.py`

After the existing `owner` chown block:

```python
chmod = config.get("chmod")
if chmod:
    ssh.run(f"chmod -R {chmod} {self.service_dir}", sudo=True)
    console.print(f"  [green]✓[/green] chmod {chmod} {self.service_dir}")
```

**Test**: Verify chmod command is generated when `chmod` key is present.

### Step 3: Create `OdooService` class

**File**: `src/cstation/commands/docker/services/odoo.py` (new)

Extends `ImageService` with Odoo-specific logic:

**Methods:**

| Method | Purpose |
|--------|---------|
| `_render_odoo_conf(config)` | Render `odoo_conf` dict as INI `[options]` file, merging defaults |
| `_odoo_data_volume(config)` | Find host path of volume mounting to `/var/lib/odoo` |
| `_create_db_user(ssh, config)` | Create PG user via `docker exec <db_container> psql` |
| `_create_db_database(ssh, config)` | Create PG database owned by that user |
| `plan(ssh, config)` | Extend base plan with odoo.conf, DB user, and DB database checks |
| `apply(ssh, config)` | Extend base apply with odoo.conf write, chown/chmod, DB user + DB creation |

**Apply sequence:**

```
1. Create directories           (ImageService)
2. Write compose file           (ImageService)
3. Write .env file              (ImageService)
4. Write odoo.conf              (OdooService)
5. Create DB user               (OdooService — needs running DB container)
6. Create DB database           (OdooService — needs running DB container, only if odoo_db present)
7. Chown data volume            (OdooService)
8. Chmod data volume            (OdooService)
9. Owner chown on service_dir   (ImageService)
10. Chmod on service_dir        (ImageService)
11. Write static configs        (ImageService — traefik file provider)
12. docker compose up -d        (ImageService)
```

**DB creation details**: The `odoo_db` key in the fragment specifies the database name and owner. If `odoo_db` is present, `OdooService` creates both the user and the database. If `odoo_db` is absent, only the user is created (for cases where the database already exists or will be created by Odoo on first run).

**Multi-tenant architecture**: One PostgreSQL container serves multiple Odoo instances. Each instance has its own user (e.g., `sg07_seq8_sg07db`) with SUPERUSER privileges and its own database (e.g., `SEQ8`). The `dbfilter` in `odoo.conf` controls which databases each instance can see (e.g., `SEQ*` matches `SEQ8`).

**DB container must be running**: The DB container must be running before steps 5-6. Since fragments are processed alphabetically and `SG07_DB.yaml` comes before `SG07_SEQ8_SG07DB.yaml`, the DB container is already up when the Odoo container is deployed.

### Step 4: Auto-Detect `odoo_conf` + Register Service

**File**: `src/cstation/commands/docker/main.py`

Modify `_get_service_instance()` to accept optional `config` parameter:

```python
def _get_service_instance(name: str, kind: str, config: dict = None):
    if config and config.get("odoo_conf"):
        from .services.odoo import OdooService
        svc = OdooService()
        svc.name = name
        svc.kind = kind
        return svc
    try:
        svc_cls = get_service(name)
        return svc_cls()
    except ValueError:
        # ... existing fallback to generic ImageService
```

Update all call sites in `docker_plan()`, `docker_apply()`, `docker_status()` to pass `data` dict.

**File**: `src/cstation/commands/docker/services/__init__.py`

Add: `from .odoo import OdooService  # noqa: F401`

### Step 5: Write Tests

**File**: `tests/test_odoo_service.py` (new)

| Test | Validates |
|------|-----------|
| `test_render_odoo_conf` | INI output format with defaults merged |
| `test_render_odoo_conf_excludes_password` | `db_password` not in INI output |
| `test_render_odoo_conf_includes_db_name_false` | `db_name = False` always present |
| `test_odoo_data_volume_detection` | Finds `/var/lib/odoo` mount path from volumes list |
| `test_odoo_data_volume_missing` | Returns None when no `/var/lib/odoo` mount |
| `test_labels_in_compose` | `labels` dict appears in rendered compose YAML |
| `test_privileged_in_compose` | `privileged: true` appears in compose |
| `test_no_privileged_by_default` | `privileged` key absent when not set |
| `test_auto_detection_with_odoo_conf` | Returns `OdooService` when `odoo_conf` present |
| `test_auto_detection_without_odoo_conf` | Returns generic `ImageService` when no `odoo_conf` |
| `test_chmod_in_apply` | chmod command generated from config |
| `test_db_user_creation_sql` | Correct SQL for `CREATE USER ... SUPERUSER` |
| `test_db_database_creation_sql` | Correct SQL for `CREATE DATABASE ... OWNER` |
| `test_odoo_db_key_present` | Creates both user and database when `odoo_db` present |
| `test_odoo_db_key_absent` | Creates only user when `odoo_db` absent |

### Step 6: Update Fragment YAMLs (SG07 Cluster)

**Files to update:**

| File | Changes |
|------|---------|
| `config/vps/sg07.ansis.com.sg/SG07_SEQ8_SG07DB.yaml` | Add `odoo_conf`, `odoo_db`, `labels`, `owner`, `chmod`, move PASSWORD to `secrets` |
| `config/vps/sg07.ansis.com.sg/SG07_ANSIS8_SG07DB.yaml` | Same |
| `config/vps/sg07.ansis.com.sg/SG07_BYQ6_SG07DB.yaml` | Same |

**Labels source**: Extracted from live `docker inspect SG07_SEQ8_SG07DB` on `5.223.74.96`.

**`odoo_db` values** (from live PG `\l` on SG07_DB):

| Container | `odoo_db.name` | `odoo_db.owner` |
|-----------|----------------|-----------------|
| SG07_SEQ8_SG07DB | SEQ8 | sg07_seq8_sg07db |
| SG07_ANSIS8_SG07DB | ANSIS8 | sg07_ansis8_sg07db |
| SG07_BYQ6_SG07DB | BYQ6 | sg07_byq6_sg07db |

### Step 7: Run Tests & Verify

```bash
uv run pytest -q
uv run cstation docker plan sg07.ansis.com.sg
```

---

## 8. Dependency Graph

```
Step 1 (labels/privileged in ImageService) ──┐
Step 2 (chmod in ImageService)             ──┤
                                              ├──> Step 3 (OdooService)
                                              │         │
                                              │         ├──> Step 4 (auto-detect + __init__)
                                              │         └──> Step 5 (tests)
                                              │
                                              └──────> Step 6 (update fragments)
                                                          │
                                                          └──> Step 7 (run tests + verify)
```

Steps 1 and 2 are independent prerequisites. Steps 3, 4, 5 depend on 1+2. Step 6 depends on 3+4. Step 7 validates everything.

---

## 9. Open Items & Decisions Needed

| # | Item | Options | Recommendation | Status |
|---|------|---------|----------------|--------|
| 1 | Migrate SG01 fragments to secrets | Do all SG01 Odoo fragments now, or just SG07? | SG07 first, SG01 in follow-up | **Pending** |
| 2 | Create US02 wildcard Odoo fragment | Create `US02_DEV7_Wildcard.yaml` now? | After OdooService is implemented and tested on SG07 | **Pending** |
| 3 | `privileged` mode for Odoo | Current production doesn't use it. Needed? | Default `false`, available if needed | **Decided: no** |
| 4 | `db_password` in `odoo_conf` | Include or skip? | Skip — use env var `PASSWORD` via `.env` | **Decided: skip** |
| 5 | Container start order | DB must be up before Odoo | Alphabetical fragment processing guarantees this (`SG07_DB` < `SG07_SEQ8`) | **Decided: rely on sort order** |
| 6 | Websocket routing labels vs file provider | Current SG07 uses Docker labels for websocket. SG01 uses file provider. | Support both — let fragment author choose | **Decided: both** |
| 7 | Traefik middlewares ownership | `compress`, `security-headers`, `sslheader`, `upgradeheader` are defined on Traefik container labels, not on Odoo container labels. But SG07 Odoo containers reference them in label `middlewares` key. | Verify middleware names match across VPS | **Pending: need to verify per-VPS** |
| 8 | Database creation vs Odoo auto-create | Should we create the PG database, or let Odoo create it on first run? | Create database at deploy time via `odoo_db` key. If `odoo_db` is absent, assume database already exists or will be created by Odoo. | **Decided: create at deploy time when `odoo_db` present** |
| 9 | PG user SUPERUSER vs restricted permissions | Ansible creates users with SUPERUSER. Should we restrict? | Match Ansible: SUPERUSER for now (can restrict later) | **Decided: SUPERUSER** |