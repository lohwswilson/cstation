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
7. [`cstation github` - GitHub Repositories & SSH Keys](#6-cstation-github)
8. [`cstation check` / `cstation lint` - Pre-Flight Schema Validator](#7-cstation-check--lint)
9. [`cstation completion` - Shell Auto-Completion](#8-cstation-completion)
10. [`cstation server` - Ansible & Server Playbooks](#9-cstation-server)
11. [`cstation tui` / `dashboard` - Interactive TUI & Command Palette](#11-cstation-tui--dashboard)
12. [`cstation config` - Configuration Portability & Migration](#12-cstation-config)
13. [`cstation state` - SQLite Runtime State, Audit & Metrics](#13-cstation-state)
14. [`cstation hindsight` - Hindsight AI Memory Service](#14-cstation-hindsight)

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
- `--output, -o [table|json|yaml]`: Output format (default: `table`). Use `json` for AI agents.

### `cstation vps status`
Show detailed live or cached status for a specific VPS instance.

```bash
cstation vps status <vps-name-or-path> [OPTIONS]
```
- `--refresh, -r`: Fetch live metrics instead of using cached facts.
- `--output, -o [table|json|yaml]`: Output format (default: `table`). Use `json` for AI agents.

### `cstation vps add`
Add a new VPS / remote server to CStation configuration. Supports interactive configuration wizards, declarative CLI flags, offline generation, and cloud provider discovery.

```bash
# Interactive configuration wizard
cstation vps add

# Declarative non-interactive declaration
cstation vps add prod-web-01 --host 107.155.65.47 --user root --port 22 --key ~/.ssh/id_ed25519 --stage prod

# Offline generation (no live SSH connection required)
cstation vps add staging-app --host 198.51.100.5 --skip-facts

# Cloud provider discovery (Hetzner, Vultr, Netcup)
cstation vps add hetzner/ANSIS:123456

# Machine-readable JSON output
cstation vps add prod-web-01 --host 107.155.65.47 --skip-facts --output json
```
- `[name]`: VPS identifier or cloud target (`<provider>/<account>:<id>`).
- `--host, -H TEXT`: Target hostname or IP address (defaults to name for static hosts).
- `--stage, -s [prod|staging|dev]`: Environment stage (default: `prod`).
- `--provider, -p [static|hetzner|vultr|netcup]`: Provider type (default: `static`).
- `--region, -r TEXT`: Server region code (e.g. `sin`, `fsn1`, `us-east`).
- `--user, -u TEXT`: SSH user (default: `root`).
- `--port, -P INT`: SSH port (default: `22`).
- `--key, -k PATH`: Path to private SSH key.
- `--skip-facts, --no-ssh, --offline`: Generate configuration without connecting to the remote host via SSH.
- `--force, -f`: Overwrite existing configuration if it already exists.
- `--out PATH`: Custom output YAML file path.
- `--interactive, -i`: Force interactive wizard.
- `--output, -o [text|json|yaml]`: Output format (default: `text`). Use `json` for AI agents.

### `cstation vps init`
Initialize a new local VPS configuration by scanning a remote server via SSH (or cloud API). Legacy alias for `cstation vps add`.

```bash
cstation vps init <target> [OPTIONS]
```
- `<target>`: Server identifier (e.g. `sg01.synercatalyst.com` for static SSH, or `hetzner/ANSIS:123456`).
- `--port INT`: SSH port (default: 22).
- `--user TEXT`: SSH user (default: root).
- `--key PATH`: Path to private SSH key.
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

### `cstation vps remove` / `cstation vps rm`
Delete a local VPS configuration directory (`~/.config/cstation/vps/<name>/`) and purge associated credentials from `config.yaml`.

```bash
# Interactive prompt (checks for running Docker containers first)
cstation vps remove <vps-name-or-path>

# Non-interactive / Scripted deletion
cstation vps remove <vps-name-or-path> --yes

# Offline deletion (bypass SSH container verification)
cstation vps remove <vps-name-or-path> --yes --skip-check

# Machine-readable JSON output
cstation vps remove <vps-name-or-path> --force --output json
```
- `--yes, -y` / `--force, -f`: Remove without interactive confirmation.
- `--skip-check`: Skip checking remote Docker containers before removal.
- `--output, -o [text|json|yaml]`: Output format (default: `text`). Use `json` for AI agents.

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
cstation docker status <vps> [OPTIONS]
```
- `--output, -o [table|json|yaml]`: Output format (default: `table`). Use `json` for AI agents.

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

#### `cstation odoo backup`
Download the latest automated backup zip from a remote Odoo container to your local machine, with optional server-side retention pruning.

```bash
cstation odoo backup <vps> <container> <dbname> [OPTIONS]
```
- `--keep, -k INT`: Number of recent backup archives to retain in the remote container (automatically deletes older archives).
- Automatically verifies internal `manifest.json` database metadata across timestamped archives.

### `cstation odoo restore`
Restore an Odoo backup zip (PostgreSQL SQL dump + filestore) to a target remote VPS. If `<backup_file.zip>` is omitted, CStation automatically scans the local directory and presents an interactive backup picker.

```bash
cstation odoo restore <vps> <container> [backup_file.zip] [OPTIONS]
```
- `[backup_file.zip]`: Local backup zip file path (optional; auto-prompts with available `.dump.zip` archives if omitted).
- `--dest-db, -d TEXT`: Target database name (defaults to database name from manifest).
- `--yes, -y`: Skip confirmation prompt.
- Includes automatic PostgreSQL `template1` collation self-healing and strict error assertions.

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
cstation dns zones [OPTIONS]
```
- `--output, -o [table|json|yaml]`: Output format (default: `table`). Use `json` for AI agents.

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

## 6. `cstation github`

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

### `cstation github ssh`
Generate and install dedicated Ed25519 SSH deploy keys to target GitHub repositories.

```bash
cstation github ssh <repo-name>
```

---

## 7. `cstation check` / `cstation lint`

Offline pre-flight configuration linter, secret validator, and schema checker.

```bash
# Table format (default)
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

Ansible playbook execution and server inventory management.

```bash
# Add a server to Ansible inventory
cstation server add prod-db --host 10.0.0.5 --group databases

# Remove a server from Ansible inventory
cstation server remove prod-db --force

# SSH key authentication setup
cstation server ssh-setup <host>

# Check server status via Ansible
cstation server status <host>

# Run Ansible playbooks
cstation server playbook <playbook.yml> <host>
```

---

## 11. `cstation tui` / `dashboard`

Interactive Terminal User Interface (TUI) dashboard with live VPS fleet health metrics, container stacks table, real-time execution logs, and a fuzzy Command Palette.

### Command Aliases
```bash
cstation tui
cstation dashboard
cstation ui
```

### Controls & Keybindings
* **`Ctrl + P`**: Open fuzzy Command Palette. Search across all VPS, Docker, Odoo, Hindsight, DNS, Config, State, and Image actions.
* **`:` (Colon)**: Open the interactive command runner bar at the bottom. Run server-aware commands (`uptime`, `free`, `df -h`, `docker ps`) or full CStation CLI commands (`vps apply`, `docker apply`, `state audit`).
* **`u`**: Instantly query live `uptime`, memory, and root disk usage on the selected VPS over SSH.
* **`s`**: Open a direct full interactive TTY SSH session on the selected VPS (temporarily suspends TUI and resumes automatically upon exit).
* **`Up` / `Down` / `j` / `k`**: Navigate between VPS nodes in the left panel.
* **`p`**: Run dry-run `docker plan` for the selected server.
* **`r`**: Refresh server fleet list and hardware telemetry.
* **`l`**: Run pre-flight configuration linter.
* **`c`**: Clear the execution logs pane.
* **`q`**: Quit the dashboard.
* **Container Row Selection**: Select or press `Enter` on any container service in the table to stream its live Docker logs (`docker logs --tail 40`).

---

## 12. `cstation config`

Export, import, inspect, and migrate CStation configuration bundles across machines.

### `cstation config path`
Display the active configuration directory and its status.

```bash
cstation config path
```

### `cstation config export`
Package `~/.config/cstation/` (VPS configs, container fragments, DNS zones, GitHub specs) into a portable `.tar.gz` archive.

```bash
# Default timestamped archive in current directory
cstation config export

# Custom output destination
cstation config export --out ~/Downloads/cstation-fleet.tar.gz

# Exclude sensitive secrets (.env, tokens) for sharing templates
cstation config export --no-secrets --out ~/Downloads/cstation-template.tar.gz
```

### `cstation config import`
Restore and validate CStation configuration from a `.tar.gz` bundle.

```bash
# Dry-run preview of files in archive
cstation config import archive.tar.gz --dry-run

# Import with confirmation
cstation config import archive.tar.gz

# Overwrite existing configuration without prompt
cstation config import archive.tar.gz --force
```
* **Rollback Safety**: Automatically creates a timestamped safety backup of existing `~/.config/cstation/` prior to extraction.
* **Validation**: Automatically runs `cstation lint` after import to verify configuration health.

---

## 13. `cstation state`

Inspect operational audit logs and historical VPS resource metrics stored in SQLite (`~/.config/cstation/state.db` in WAL mode).

### `cstation state audit`
View the operational audit trail of commands executed by users or AI agents.

```bash
# Human-readable table
cstation state audit

# Filter by command name
cstation state audit --command "docker"

# Retrieve specific limit
cstation state audit -n 50

# Machine-readable JSON output for AI agents
cstation state audit --output json
```

### `cstation state history`
View historical hardware resource snapshots (load avg, RAM, disk, container count) recorded during inspections.

```bash
# Table format
cstation state history sg05.ansis.com.sg

# Agent JSON format
cstation state history sg05.ansis.com.sg --output json
```

---

## 14. `cstation hindsight`

Operational workflows for self-hosted Hindsight vector memory services running on VPS targets.

### `cstation hindsight status`
Inspect running Hindsight container status, ports, and latest remote backup archive metadata.

```bash
# Table format
cstation hindsight status sg07.ansis.com.sg

# Agent JSON format
cstation hindsight status sg07.ansis.com.sg --output json
```

### `cstation hindsight backup`
Download remote PostgreSQL backup dump from VPS to local storage and prune older local archives.

```bash
# Download latest dump and keep 5 most recent local copies
cstation hindsight backup sg07.ansis.com.sg --dest ~/.hermes/backups/hindsight --keep 5
```
