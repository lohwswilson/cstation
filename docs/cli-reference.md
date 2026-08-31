# CStation CLI Command Reference Manual 📖

`cstation` is a local-first DevOps CLI for managing VPS infrastructure, declarative Docker container stacks, DNS records, Odoo applications, Docker images, and GitHub repositories.

---

## 📑 Table of Contents

1. [Global Options](#global-options)
2. [`cstation vps` - VPS Lifecycle & Infrastructure](#1-cstation-vps)
3. [`cstation docker` - Declarative Container Stacks](#2-cstation-docker)
4. [`cstation odoo` - Odoo Application Workflows](#3-cstation-odoo)
5. [`cstation image` - Docker Image Build & Push](#4-cstation-image)
6. [`cstation dns` - DNS Zone & Record Management](#5-cstation-dns)
7. [`cstation auth` - Provider Authentication](#6-cstation-auth)
8. [`cstation github` - GitHub Repositories & SSH Keys](#7-cstation-github)
9. [`cstation check` / `cstation lint` - Pre-Flight Schema Validator](#8-cstation-check--lint)
10. [`cstation completion` - Shell Auto-Completion](#9-cstation-completion)
11. [`cstation server` - Ansible & Server Playbooks](#10-cstation-server)

---

## Global Options

```bash
cstation [OPTIONS] COMMAND [ARGS]...
```

- `--version`: Print CLI version and exit.
- `--verbose, -v`: Show detailed configuration loading steps and full tracebacks on errors.
- `--help`: Show top-level help and list all registered command groups.
- `--install-completion` / `--show-completion`: Install or display shell completion scripts.

---

## 1. `cstation vps`

Manage the lifecycle, security baseline, and OS-level configuration of remote servers.

### `cstation vps list`
List all managed VPS instances with live or cached health metrics (load average, memory, disk, Docker status).

```bash
cstation vps list [OPTIONS]
```
- `--refresh, -r`: Force live SSH connection and bypass `.facts.json` cache.
- `--filter, -f TEXT`: Filter VPS instances by name, provider, or stage.

### `cstation vps status`
Show an interactive rich status dashboard for a specific VPS instance.

```bash
cstation vps status <vps-name-or-path> [OPTIONS]
```
- `--refresh, -r`: Fetch live metrics instead of using cached facts.

### `cstation vps init`
Initialize a new local VPS configuration by scanning a remote server via SSH (or cloud API).

```bash
cstation vps init <target> [OPTIONS]
```
- `<target>`: Server identifier (e.g. `sg01.synercatalyst.com` for static SSH, or `hetzner/ANSIS:123456`).
- `--port, -p INT`: SSH port (default: 22).
- `--user, -u TEXT`: SSH user (default: root).
- `--key, -k PATH`: Path to private SSH key.
- `--force`: Overwrite existing local configuration directory.

### `cstation vps plan`
Dry-run the 13-phase OS setup pipeline to inspect what changes will be applied.

```bash
cstation vps plan <vps-name-or-path>
```

### `cstation vps apply`
Execute the 13-phase setup pipeline over SSH to configure the remote VPS.

```bash
cstation vps apply <vps-name-or-path> [OPTIONS]
```
- `--yes, -y`: Skip confirmation prompt.

### `cstation vps ssh`
Open an interactive SSH shell or run a command directly on the remote VPS without manually specifying IP, port, or key.

```bash
# Open interactive TTY shell
cstation vps ssh <vps-name-or-path>

# Run a remote command
cstation vps ssh <vps-name-or-path> htop
```

### `cstation vps rm`
Delete a local VPS configuration directory.

```bash
cstation vps rm <vps-name-or-path> [OPTIONS]
```
- `--force, -f`: Remove without confirmation.

---

## 2. `cstation docker`

Declarative container management with automatic compose, `.env`, and reverse-proxy generation.

### `cstation docker import`
Scrape running containers from a VPS into local declarative YAML fragments.

```bash
cstation docker import <vps> [CONTAINER] [OPTIONS]
```
- `--all`: Import all running containers on the target VPS.
- `--name, -n TEXT`: Custom name for the generated fragment file.
- `--force`: Overwrite existing fragment file.

### `cstation docker status`
Display running state vs declared state of all managed containers on the VPS.

```bash
cstation docker status <vps>
```

### `cstation docker plan`
Dry-run container configurations and preview compose changes.

```bash
cstation docker plan <vps> [OPTIONS]
```
- `--service, -s TEXT` / `--container, -c TEXT`: Target a specific container only.

### `cstation docker apply`
Deploy, update, or restart declared container stacks on the remote VPS.

```bash
cstation docker apply <vps> [OPTIONS]
```
- `--service, -s TEXT` / `--container, -c TEXT`: Target a specific container only.
- `--yes, -y`: Skip interactive confirmation.

---

## 3. `cstation odoo`

Enterprise Odoo codebase synchronization, auto-backup extraction, and database restoration.

### `cstation odoo update`
Run an Odoo database module upgrade or installation directly inside a remote container over SSH.

```bash
# Upgrade specific module on a database
cstation odoo update <vps> <container> -d <dbname> -m perfectwork_sg_be

# Upgrade all modules and restart container
cstation odoo update <vps> <container> -d <dbname> -m all

# Install new module without restarting
cstation odoo update <vps> <container> -d <dbname> -i my_new_module --no-restart
```

### `cstation odoo sync`
Synchronize local PerfectWork/Odoo source code and addons to a remote VPS using optimized delta rsync.

```bash
cstation odoo sync <host> <version> [OPTIONS]
```
- `<host>`: Target VPS hostname (e.g. `sg01`).
- `<version>`: Odoo/PW version (e.g. `3.0`, `5.0`, `7.0`, `18.0`).
- `--port, -p INT`: SSH port (default: 22).
- `--dry-run, -n`: Show what would be transferred without modifying remote files.
- `--verbose, -v`: Enable verbose transfer output.

### `cstation odoo backup`
Download the latest automated backup zip from a remote Odoo container to your local machine.

```bash
cstation odoo backup <vps> <container> <dbname>
```
- Automatically verifies internal `manifest.json` database metadata across timestamped archives.

### `cstation odoo restore`
Restore an Odoo backup zip (PostgreSQL SQL dump + filestore) to a target remote VPS.

```bash
cstation odoo restore <vps> <container> <backup_file.zip> [OPTIONS]
```
- `--dest-db, -d TEXT`: Target database name (defaults to database name from manifest).
- `--yes, -y`: Skip confirmation prompt.

---

## 4. `cstation image`

Multi-architecture Docker and Podman image build and push automation.

### `cstation image list`
List all declared image build recipes in `~/.config/cstation/images/`.

```bash
cstation image list
```

### `cstation image build`
Build a multi-architecture Docker image and push it to the configured container registry.

```bash
cstation image build <image-name> [OPTIONS]
```
- `--push / --no-push`: Push to registry after successful build (default: push).
- `--platform TEXT`: Target platforms (e.g. `linux/amd64,linux/arm64`).

---

## 5. `cstation dns`

Declarative DNS zone and record management via Cloudflare API.

### `cstation dns zones`
List all active DNS zones accessible via configured Cloudflare credentials.

```bash
cstation dns zones
```

### `cstation dns plan`
Dry-run DNS record differences between local YAML definitions and Cloudflare live records.

```bash
cstation dns plan <zone-name>
```

### `cstation dns apply`
Synchronize declared DNS records to Cloudflare.

```bash
cstation dns apply <zone-name> [OPTIONS]
```
- `--yes, -y`: Skip confirmation prompt.

---

## 6. `cstation auth`

Authentication management for external cloud providers.

### `cstation auth netcup login`
Initiate interactive OAuth2 device-flow authentication for Netcup Server Control Panel (SCP).

```bash
cstation auth netcup login
```

### `cstation auth netcup status`
Check active Netcup SCP authentication credentials and token validity.

```bash
cstation auth netcup status
```

### `cstation auth netcup logout`
Revoke and remove local Netcup SCP credentials.

```bash
cstation auth netcup logout
```

---

## 7. `cstation github`

GitHub repository management, fork synchronization, and fast selective cloning.

### `cstation github repo list`
Display the configured mapping of GitHub repositories and local target directories.

```bash
cstation github repo list
```

### `cstation github repo clone`
Perform fast, blobless (`--filter=blob:none`) clones of configured repositories in parallel.

```bash
cstation github repo clone [REPO_NAME] [OPTIONS]
```
- `[REPO_NAME]`: Optional single repository to clone.
- `--jobs, -j INT`: Number of parallel worker threads (default: 4).

### `cstation github repo sync`
Fetch upstream updates (e.g. `odoo/odoo`), merge changes, pull origin, and push to GitHub forks.

```bash
cstation github repo sync [REPO_NAME]
```

---

## 8. `cstation check` / `lint`

Offline pre-flight linter and schema validator.

### `cstation check` (alias: `cstation lint`)
Validates all local VPS YAML configurations, container fragments, port allocations, and secret bindings.

```bash
# Human-readable table
cstation check

# JSON output
cstation check -o json

# YAML output
cstation check -o yaml
```

---

## 9. `cstation completion`

Shell auto-completion configuration.

### `cstation completion install`
Auto-detects shell (`zsh`, `bash`, `fish`) and installs completion hooks into user rc files.

```bash
cstation completion install
```

### `cstation completion show [shell]`
Print raw completion script for shell evaluation.

```bash
cstation completion show zsh
```

---

## 10. `cstation server`

Ansible playbook execution and server management tools.

```bash
cstation server ssh-setup <host>
cstation server status <host>
cstation server playbook <playbook.yml> <host>
```
