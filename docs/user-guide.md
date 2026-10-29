# CStation User Guide 📘

Welcome to the **CStation User Guide**. This document provides an end-to-end walkthrough of managing multi-cloud infrastructure, declarative Docker container stacks, DNS zones, Odoo business applications, AI memory services, and runtime state using CStation.

---

## 📑 Table of Contents

1. [Introduction & Core Concepts](#1-introduction--core-concepts)
2. [Installation & Setup](#2-installation--setup)
3. [Interactive TUI Dashboard & Command Palette](#3-interactive-tui-dashboard--command-palette)
4. [VPS Fleet Lifecycle & OS Hardening](#4-vps-fleet-lifecycle--os-hardening)
5. [Declarative Docker Container Stacks](#5-declarative-docker-container-stacks)
6. [Enterprise Odoo Operations](#6-enterprise-odoo-operations)
7. [AI Memory Service (Hindsight)](#7-ai-memory-service-hindsight)
8. [Configuration Portability (Export & Import)](#8-configuration-portability-export--import)
9. [SQLite Runtime State & Operational Audit](#9-sqlite-runtime-state--operational-audit)
10. [Cloudflare DNS Automation](#10-cloudflare-dns-automation)
11. [Multi-Arch Docker Image Builds](#11-multi-arch-docker-image-builds)
12. [AI Agent Tooling & JSON Automation Contract](#12-ai-agent-tooling--json-automation-contract)

---

## 1. Introduction & Core Concepts

CStation is built around four fundamental principles:

1. **Local-First GitOps**: All infrastructure state is declared as human-readable YAML files in `~/.config/cstation/`. There is no central master server or heavy control plane that can fail or get compromised.
2. **Sub-100ms Telemetry**: Multi-command SSH fact collection is bundled into single round trips using `SSHManager.run_batch()` and cached in local `.facts.json` files.
3. **Dual-Surface Architecture**:
   * **For Humans**: An interactive full-screen **TUI Dashboard** (`cstation tui`) with a fuzzy **Command Palette (`Ctrl+P`)** that eliminates the need to memorize CLI subcommands and options.
   * **For AI Agents**: Machine-readable JSON output (`--output json`) across all inspection commands, with deterministic exit codes and non-interactive flags.
4. **Declarative Idempotence**: Every mutating action includes a dry-run `plan` mode before executing `apply`.

---

## 2. Installation & Setup

### Prerequisites
* **Python 3.13+** (managed via `.python-version`)
* [**uv**](https://docs.astral.sh/uv/) (high-performance Python package installer)

### Quick Install (Editable Global Tool)
Install CStation into your global environment so it is available from any directory:

```bash
# Clone the repository
git clone https://github.com/lohwswilson/cstation.git ~/Projects/cstation
cd ~/Projects/cstation

# Install globally in editable mode
uv tool install --editable . --force
```

### Shell Auto-Completion
CStation supports instant tab completion for commands, server hostnames, and flags:

```bash
# Install completion for your active shell (zsh, bash, or fish)
cstation --install-completion

# Reload your shell
exec zsh  # or exec bash
```

---

## 3. Interactive TUI Dashboard & Command Palette

If you ever find it difficult to remember subcommands or syntax, launch the terminal dashboard:

```bash
cstation tui
# Aliases: cstation dashboard  OR  cstation ui
```

```
┌─ CStation Infrastructure Dashboard ────────────────────────────── [Ctrl+P: Commands] ─┐
│                                                                                       │
│  🌐 SERVERS (Fleet)          │ 🐳 CONTAINERS: sg05.ansis.com.sg                       │
│ ──────────────────────────── │ ────────────────────────────────────────────────────── │
│  ● sg01.synercatalyst.com    │ Service              Kind       Enabled    Image       │
│    107.155.65.47             │ SG05_TRAEFIK         Container  enabled    traefik:... │
│    L: 1.10 | M: 7% | D: 3%   │ SG05_DB              Container  enabled    postgres:16 │
│                              │ SG05_DANLI_SG05DB    Container  enabled    pw7.0:...   │
│ ▶● sg05.ansis.com.sg         │ SG05_DANLI_02_SG05DB Container  enabled    pw7.0:...   │
│    207.148.126.238           │ SG05_CAMBRIAN_SG05DB Container  enabled    pw7.0:...   │
│    L: 0.00 | M: 54% | D: 24% │ portainer            Container  enabled    portainer.. │
│                              ├───────────────────────────────────────────────────────┤
│  ● sg06.ansis.com.sg         │ 📋 EXECUTION LOGS                                     │
│  ● sg07.ansis.com.sg         │ [21:55:00] ✓ Discovered 7 managed VPS instances.      │
│  ● us01.synercatalyst.com    │ [21:55:01] ▶ Running: cstation docker plan sg05...    │
│  ● us02.synercatalyst.com    │            Connected via SSH (207.148.126.238)        │
│  ● local.dev                 │            ✓ All containers match desired state.      │
└──────────────────────────────┴───────────────────────────────────────────────────────┘
  [Ctrl+P] Commands   [:] Run   [u] Uptime   [s] SSH   [p] Plan   [r] Refresh   [l] Lint   [q] Quit
```

### Key Capabilities:
* **Interactive Command Runner Bar (`:` Mode)**:
  Press `:` anywhere in the dashboard to open the bottom runner bar:
  * **Server-Aware Shell Commands**: If you type `uptime`, `free`, `df -h`, or `docker ps`, it automatically runs them over SSH on the **currently highlighted server** and displays the output in the log pane.
  * **CStation CLI Commands**: Type any CLI command (e.g. `vps apply sg05 --yes`, `docker apply sg01`, `state audit`, `config export`, `hindsight backup sg07`) and it executes asynchronously with live streaming output.
  * Press `Enter` to run, or `Escape` to close.
* **Fuzzy Command Palette (`Ctrl + P`)**:
  Press `Ctrl + P` to open the search bar. Start typing any keyword:
  * **VPS Lifecycle**: `VPS: Plan OS Hardening (<vps>)`, `VPS: Apply 12-Phase OS Setup (<vps>)`, `VPS: Check Uptime & Health (<vps>)`, `VPS: Open SSH Shell (<vps>)`, `VPS: Add Server`, `VPS: Remove Server (<vps>)`.
  * **Docker Containers**: `Docker: Plan (<vps>)`, `Docker: Apply Container Stacks (<vps>)`, `Docker: Status (<vps>)`.
  * **Odoo & Hindsight**: `Odoo: Backup Database (<vps>)`, `Hindsight: Status Check (<vps>)`.
  * **DNS & Images**: `DNS: List Cloudflare Zones`, `Image: List Image Recipes`.
  * **Config & State**: `Config: Export Configuration Archive`, `State: View Audit Log`.
* **Context-Aware Container Actions**:
  Select or press `Enter` on any container service in the table to immediately fetch and stream its live Docker logs (`docker logs --tail 40`).
* **Hotkeys**:
  * `[:]`: Open the interactive command runner bar.
  * `[u]`: Instantly query live `uptime`, memory, and disk usage for the selected server.
  * `[s]`: Drop into an interactive SSH shell (using terminal suspension, returns cleanly upon exit).
  * `[p]`: Run dry-run `docker plan` on the highlighted server.
  * `[r]`: Refresh server list and cached hardware metrics.
  * `[l]`: Run pre-flight configuration linter.
  * `[c]`: Clear the execution log pane.
  * `[q]`: Quit dashboard.

---

## 4. VPS Fleet Lifecycle & OS Hardening

CStation manages bare-metal and cloud VPS instances across Hetzner, Vultr, Netcup, and static hosts.

### Adding a VPS or Remote Server
You can add a server interactively, non-interactively via CLI flags, or offline before the machine is booted:

```bash
# 1. Interactive configuration wizard (prompts for Name, Host, User, Port, Key, Stage)
cstation vps add

# 2. Non-interactive CLI flags (ideal for scripts and AI agents)
cstation vps add prod-web-01 --host 107.155.65.47 --user root --port 22 --key ~/.ssh/id_ed25519 --stage prod

# 3. Offline / Pre-boot declaration (generates starter vps.yaml without live SSH probe)
cstation vps add staging-app --host 198.51.100.5 --skip-facts

# 4. Cloud provider import (Hetzner, Vultr, Netcup)
cstation vps add hetzner/ANSIS:123456

# 5. Machine-readable JSON output for automated pipelines
cstation vps add prod-web-01 --host 107.155.65.47 --skip-facts --output json
```

### Removing a VPS / Remote Server
Safely delete a server's local configuration directory (`~/.config/cstation/vps/<name>/`) and purge its secrets from `config.yaml`:

```bash
# Interactive prompt (checks for running Docker containers first)
cstation vps remove prod-web-01

# Non-interactive / Force removal (ideal for AI agents and scripts)
cstation vps remove prod-web-01 --yes

# Offline removal (skip SSH container check if server is already destroyed or unreachable)
cstation vps remove prod-web-01 --yes --skip-check

# Machine-readable JSON output
cstation vps remove prod-web-01 --force --output json
```

### Inspecting Fleet Status
```bash
# List all VPS instances with parallel hardware telemetry (<100ms cached)
cstation vps list

# Force live SSH telemetry refresh across all servers
cstation vps list --refresh

# View live hardware metrics for a specific node
cstation vps status sg05.ansis.com.sg
```

### The 12-Phase OS Setup Pipeline
When provisioning a new VPS or updating system baselines, CStation executes an idempotent 12-phase pipeline over SSH:
1. `packages`: Baseline system packages (`ufw`, `fail2ban`, `rsync`, `curl`, `git`, `python3`).
2. `shell`: Bash/Zsh configuration, PATH defaults, customized MOTD banner.
3. `terminal`: UTF-8 locale and TTY settings.
4. `sshd`: SSH daemon hardening (disables password authentication, enforces key auth, disables root password logins).
5. `firewall`: UFW firewall rules (allows SSH, HTTP 80, HTTPS 443; drops unauthorized traffic).
6. `swap`: Configures swap file with optimal vm.swappiness.
7. `tuning`: Kernel sysctl tuning (TCP BBR congestion control, file descriptors, journald storage limits).
8. `fail2ban`: SSH jail configurations to mitigate brute-force attacks.
9. `hostname`: Sets system hostname matching configuration.
10. `docker_daemon`: Configures `/etc/docker/daemon.json` (log-driver rotation limits).
11. `docker_networks`: Pre-creates declared Docker networks (e.g. `PW_NET`).
12. `docker_directories`: Pre-creates declared bind-mount directories (e.g. `/srv/data/`).

```bash
# Dry-run: inspect what would change without modifying the server
cstation vps plan sg05.ansis.com.sg

# Apply: execute the setup pipeline
cstation vps apply sg05.ansis.com.sg --yes
```

### Remote Shell Access
Connect to any server over SSH without looking up IP addresses or keys:
```bash
# Interactive TTY shell
cstation vps ssh sg05.ansis.com.sg

# Run remote one-liner
cstation vps ssh sg05.ansis.com.sg "docker ps"
```

---

## 5. Declarative Docker Container Stacks

Container services are declared as individual YAML fragments under each server's directory in `~/.config/cstation/vps/<host>/`.

### Example Fragment: `SG05_TRAEFIK.yaml`
```yaml
apiVersion: cstation/v1
kind: Container
name: SG05_TRAEFIK
enabled: true
image: traefik:latest
restart: unless-stopped
networks:
  - PW_NET
ports:
  - "80:80"
  - "443:443"
volumes:
  - "/var/run/docker.sock:/var/run/docker.sock:ro"
  - "/srv/traefik/acme.json:/acme.json"
```

### Container Lifecycle Commands
```bash
# Check status of managed container services
cstation docker status sg05.ansis.com.sg

# Preview container drift and configuration changes
cstation docker plan sg05.ansis.com.sg

# Deploy/reconcile container stacks on the remote VPS
cstation docker apply sg05.ansis.com.sg

# Reverse import: scan a running container on a VPS and generate a local YAML fragment
cstation docker import sg05.ansis.com.sg my-container
```

---

## 6. Enterprise Odoo Operations

CStation includes specialized pipelines for multi-version Odoo deployments (Odoo 13, 15, 16, 18).

### High-Speed Code Sync (`odoo sync`)
Syncs Odoo core code and customer addons to remote containers via delta `rsync`:
```bash
# Sync entire Odoo 18 stack to a VPS
cstation odoo sync sg01.synercatalyst.com 18.0

# Targeted single-module sync (<0.2s):
# Auto-discovers module location across customer, enterprise, and OCA subdirectories
cstation odoo sync sg01.synercatalyst.com 15.0 -m perfectwork_sg_be
```

### Database Module Updates (`odoo update`)
Runs Odoo database upgrades directly inside the remote container over SSH:
```bash
cstation odoo update sg01.synercatalyst.com SG01_DEV5_SG01DB -d be5 -m perfectwork_sg_be
```

### Backups & Retention Pruning (`odoo backup`)
Downloads auto-backup ZIP archives to your local machine and automatically prunes old remote backups:
```bash
cstation odoo backup us01.synercatalyst.com US01_BESOLUTION_US01DB PW5-BESOLUTION --keep 7
```

### Database Restore (`odoo restore`)
Restores an Odoo database archive to a target container with automatic PostgreSQL collation repair:
```bash
cstation odoo restore sg01.synercatalyst.com SG01_DEV5_SG01DB --dest-db be5_staging --yes
```

---

## 7. AI Memory Service (Hindsight)

For self-hosted Hindsight vector memory services running on your VPS fleet:

### Check Status
```bash
cstation hindsight status sg07.ansis.com.sg
```
* Shows running container name, port bindings, and latest remote database dump timestamp/size.

### Remote Backup & Pruning
```bash
cstation hindsight backup sg07.ansis.com.sg --dest ~/.hermes/backups/hindsight --keep 5
```
* Safely downloads compressed PostgreSQL database dumps (`hindsight_YYYYMMDD_HHMMSS.dump.gz`) and prunes older local copies.

---

## 8. Configuration Portability (Export & Import)

To migrate or synchronize your fleet configuration across machines (e.g. from your MacBook to your Mac mini):

### Export Configuration
```bash
# Export full configuration to a timestamped .tar.gz bundle
cstation config export

# Export to a custom path
cstation config export --out ~/Downloads/cstation-fleet.tar.gz

# Export a clean template without secrets (.env and OAuth tokens excluded)
cstation config export --no-secrets --out ~/Downloads/cstation-template.tar.gz
```
* Safely filters out ephemeral files (`.DS_Store`, `state.db*`, `__pycache__`).
* Logs the export event to the operational audit database.

### Import Configuration
```bash
# Preview files before importing (dry-run)
cstation config import ~/Downloads/cstation-fleet.tar.gz --dry-run

# Import and overwrite
cstation config import ~/Downloads/cstation-fleet.tar.gz
```
* **Automatic Rollback Snapshot**: Automatically copies your existing `~/.config/cstation/` to `~/.config/cstation.bak.<timestamp>` before extraction.
* **ZipSlip Guard**: Rejects archives containing illegal relative path traversals.
* **Automatic Validation**: Automatically triggers `cstation lint` after import to verify configuration health.

---

## 9. SQLite Runtime State & Operational Audit

Runtime operational state, audit logs, and hardware telemetry are stored in **`~/.config/cstation/state.db`** (SQLite in WAL mode).

### Viewing Operational Audit Trail
Tracks every mutation executed by humans or AI agents:
```bash
# View recent 30 audit logs
cstation state audit

# Filter by command name
cstation state audit --command "docker"
```

### Viewing Historical VPS Resource Snapshots
Every time `vps status` or `cstation tui` runs, hardware metrics are captured into SQLite:
```bash
cstation state history sg05.ansis.com.sg --limit 10
```

---

## 10. Cloudflare DNS Automation

Declarative DNS configurations reside in `~/.config/cstation/dns/<domain>.yaml`.

### Commands
```bash
# List all Cloudflare DNS zones
cstation dns zones

# Dry-run compare declared records against Cloudflare
cstation dns plan synercatalyst.com

# Apply declared DNS records to Cloudflare
cstation dns apply synercatalyst.com --yes
```

---

## 11. Multi-Arch Docker Image Builds

Multi-architecture image recipes live in `~/.config/cstation/images/<name>/image.yaml`.

```bash
# List available image recipes and supported architectures
cstation image list

# Build multi-arch image (linux/amd64 + linux/arm64) and push to registry
cstation image build synercatalyst-odoo.13.0
```

---

## 12. AI Agent Tooling & JSON Automation Contract

CStation is engineered as a first-class tool for autonomous AI coding agents (Hermes, Antigravity, Claude Code).

### Universal `--output json` Support
All read and inspection commands support `--output json` with pure JSON output (zero ANSI escape codes, zero banner prefixes):

| Command | Output Structure | Typical Agent Use Case |
| :--- | :--- | :--- |
| `cstation vps list --output json` | Array of VPS dicts | Fleet discovery and IP resolution |
| `cstation vps status <vps> --output json` | Full hardware & facts dict | CPU, RAM, Disk, Docker telemetry checks |
| `cstation docker status <vps> --output json` | Array of container service states | Verification that containers are running |
| `cstation dns zones --output json` | Array of zone dicts (`id`, `name`, `status`) | Resolving Cloudflare Zone IDs |
| `cstation hindsight status <vps> --output json` | Hindsight container & backup dict | Automated backup verification |
| `cstation state audit --output json` | Array of audit log dicts | Post-execution verification |
| `cstation state history <vps> --output json` | Array of resource metric snapshots | Historical resource utilization checks |
| `cstation lint --output json` | Object (`passed`, `issues`, `counts`) | Automated pre-flight validation |
| `cstation image list --output json` | Array of image recipe dicts | Build target enumeration |

### Example Agent Invocation (Python)
```python
import subprocess
import json

# Agent runs command with --output json
res = subprocess.run(
    ["cstation", "vps", "status", "sg05.ansis.com.sg", "--output", "json"],
    capture_output=True,
    text=True,
    check=True,
)

data = json.loads(res.stdout)
print(f"Server {data['name']} is {data['status']}. RAM: {data['memory']['used_mb']}MB")
```

### Exit Codes Contract
* `0`: Success / Target in desired state.
* `1`: Operational error (SSH connectivity failure, execution aborted).
* `2`: Authentication failure (invalid Cloudflare token, SSH auth error).
* `3`: Target not found.
* `6`: Configuration schema validation error.
