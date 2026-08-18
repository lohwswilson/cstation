## Pre-flight Linting & Validation (`cstation lint`)

### `cstation lint`
Run offline pre-flight validation and schema checking across all VPS configurations, container fragments, port allocations, and secret bindings.

```bash
# Human-readable table
cstation lint

# Machine-readable JSON output
cstation lint -o json

# Machine-readable YAML output
cstation lint -o yaml
```

---

## Shell Auto-Completion (`cstation completion`)

### `cstation completion install`
Detects current shell (`zsh`, `bash`, `fish`) and automatically installs completion hooks into user rc files.

```bash
cstation completion install
```

### `cstation completion show [shell]`
Prints raw completion script to standard output (e.g. for `eval "$(cstation completion show zsh)"`).

```bash
cstation completion show zsh
cstation completion show bash
cstation completion show fish
```

---
# CStation CLI Reference Manual

`cstation` is a local-first DevOps command-line interface for managing VPS infrastructure, declarative Docker container stacks, DNS records, Odoo applications, Docker images, and GitHub repositories.

---

## Table of Contents

1. [Global Options](#global-options)
2. [`cstation vps` - VPS Lifecycle & Infrastructure](#cstation-vps)
3. [`cstation docker` - Declarative Container Stacks](#cstation-docker)
4. [`cstation odoo` - Odoo Application Workflows](#cstation-odoo)
5. [`cstation image` - Docker Image Build & Push](#cstation-image)
6. [`cstation dns` - DNS Zone & Record Management](#cstation-dns)
7. [`cstation auth` - Provider Authentication](#cstation-auth)
8. [`cstation github` - GitHub Repositories & SSH Keys](#cstation-github)
9. [`cstation server` - Ansible & Server Management](#cstation-server)

---

## Global Options

```bash
cstation [OPTIONS] COMMAND [ARGS]...
```

- `--version`: Print CLI version and exit.
- `--verbose, -v`: Show configuration loading details (also surfaces full tracebacks on errors).
- `--help`: Show top-level help and list available command groups.
- `--install-completion` / `--show-completion`: Install or display shell completion scripts.

---

## `cstation vps`

Manage the lifecycle, security baseline, and OS-level configuration of remote servers.

### Commands

#### `cstation vps list`
List all managed VPS instances with live or cached health metrics (load average, memory, disk, Docker status).

```bash
cstation vps list [OPTIONS]
```
- `--refresh, -r`: Force live SSH connection and bypass `.facts.json` cache.
- `--filter, -f TEXT`: Filter VPS instances by name, provider, or stage.

#### `cstation vps status`
Show an interactive rich status dashboard for a specific VPS instance.

```bash
cstation vps status <vps-name-or-path> [OPTIONS]
```
- `--refresh, -r`: Fetch live metrics instead of using cached facts.

#### `cstation vps init`
Initialize a new local VPS configuration by scanning a remote server via SSH (or cloud API).

```bash
cstation vps init <target> [OPTIONS]
```
- `<target>`: Server identifier (e.g. `sg01.synercatalyst.com` for static SSH, or `hetzner/ANSIS:123456`).
- `--port, -p INT`: SSH port (default: `22`).
- `--user, -u TEXT`: SSH user (default: `root`).
- `--key, -k PATH`: Private SSH key path (default: `~/.ssh/id_rsa`).
- `--force`: Overwrite existing local configuration if it already exists.

#### `cstation vps plan`
Dry-run the 12-phase OS setup pipeline to preview what changes would be made on the server.

```bash
cstation vps plan <vps-name-or-path>
```

#### `cstation vps apply`
Execute the 12-phase OS setup pipeline over SSH to bring the VPS into the declared state.

```bash
cstation vps apply <vps-name-or-path> [OPTIONS]
```
- `--yes, -y`: Skip confirmation prompt.
- `--phase TEXT`: Execute only a specific phase (`packages`, `upgrade_all`, `shell`, `terminal`, `sshd`, `firewall`, `swap`, `tuning`, `fail2ban`, `hostname`, `docker_daemon`, `docker_networks`, `docker_directories`).

##### Declarative Tuning & BBR Network Acceleration (`vps.yaml`)
```yaml
os:
  baseline:
    swap:
      size_gb: 8
    tuning:
      vm_swappiness: 10
      bbr: true                     # Auto-loads tcp_bbr module & sets FQ + BBR
      vm_overcommit_memory: 1
      net_ipv4_tcp_max_syn_backlog: 4096
      fs_inotify_max_user_watches: 524288
```

#### `cstation vps rm`
Remove a VPS configuration from the local configuration directory.

```bash
cstation vps rm <vps-name-or-path> [OPTIONS]
```
- `--skip-check`: Skip checking if containers are still running on the remote host before removal.
- `--force, -f`: Confirm deletion without interactive prompt.

---

## `cstation docker`

Declarative multi-container management using YAML fragments and SSH Compose orchestration.

### Commands

#### `cstation docker import`
Scrape running containers on a VPS and generate local YAML fragments.

```bash
cstation docker import <vps-name> [CONTAINER_NAME] [OPTIONS]
```
- `--all`: Import all running containers found on the host.

#### `cstation docker rm` / `cstation docker remove`
Stop and remove a container stack on the remote VPS, and clean up local configurations and secrets.

```bash
# Interactive confirmation
cstation docker rm sg07.ansis.com.sg SG07_OLD_CONTAINER

# Also purge named volumes/data (-v) and bypass prompt (-y)
cstation docker rm sg07.ansis.com.sg SG07_OLD_CONTAINER -v -y

# Archive local YAML to .disabled instead of deleting
cstation docker rm sg07.ansis.com.sg SG07_OLD_CONTAINER --archive

# Dry-run inspection
cstation docker rm sg07.ansis.com.sg SG07_OLD_CONTAINER --dry-run
```

### `cstation docker status`
Display running vs declared container status on the target VPS.

```bash
cstation docker status <vps-name>
```

#### `cstation docker plan`
Compare declared container fragments against the remote host and preview deployment actions (create dirs, write `.env`, compose generation).

```bash
cstation docker plan <vps-name> [OPTIONS]
```
- `--service, -s TEXT`: Plan a single container service.

#### `cstation docker apply`
Deploy, update, or restart declared container services on the VPS.

```bash
cstation docker apply <vps-name> [OPTIONS]
```
- `--yes, -y`: Skip confirmation prompt.
- `--service, -s TEXT`: Apply only a single container service.

#### `cstation docker down`
Stop and remove container services on the VPS.

```bash
cstation docker down <vps-name> [SERVICE_NAME]
```

#### `cstation docker restart`
Restart container services on the VPS.

```bash
cstation docker restart <vps-name> [SERVICE_NAME]
```

---

## `cstation odoo`

Unified workflows for Odoo source code synchronization, database backups, and full restores.

### Commands

#### `cstation odoo sync`
Sync Odoo core code (`PW.<version>`) and custom addons (`PW_ADDONS.<version>`) to a remote VPS using high-speed incremental `rsync`.

```bash
cstation odoo sync <host> <version> [OPTIONS]
```
- `<host>`: Target VPS hostname (e.g. `sg06` or `sg06.ansis.com.sg`).
- `<version>`: Odoo/PW version (e.g. `14.0`, `16.0`, `18.0`).
- `--port, -p INT`: SSH port (default: `22`).
- `--dry-run, -n`: Show what files would be transferred without modifying the server.
- `--verbose, -v`: Enable verbose file-by-file `rsync` progress output.

#### `cstation odoo backup`
Locate and download the latest automated database backup zip from a remote Odoo container.

```bash
cstation odoo backup <vps> <container> <dbname>
```
- `<vps>`: VPS hostname or config path.
- `<container>`: Running Odoo container name (e.g. `US02_DEV8_US02DB`).
- `<dbname>`: PostgreSQL database name.

#### `cstation odoo restore`
Restore an Odoo backup zip archive (database SQL dump + filestore + checklist directories) into a remote container.

```bash
cstation odoo restore <vps> <container> <backup-file> [OPTIONS]
```
- `--dest-db, -d TEXT`: Target database name (defaults to source DB name from archive manifest).
- `--yes, -y`: Skip confirmation prompt.

---

## `cstation image`

Build multi-architecture Docker images with custom patches and push to registries.

### Commands

#### `cstation image list`
List all image definitions configured in `~/.config/cstation/images/`.

```bash
cstation image list
```

#### `cstation image build`
Build a multi-architecture Docker image (supports Docker Buildx and Podman) and push to the container registry.

```bash
cstation image build <image-name> [OPTIONS]
```
- `--push / --no-push`: Push image to registry after building (default: `--push`).
- `--tag, -t TEXT`: Additional custom tag to apply.

---

## `cstation dns`

Declarative DNS record and zone management via Cloudflare.

### Commands

#### `cstation dns zones`
List all DNS zones accessible by the configured API token.

```bash
cstation dns zones
```

#### `cstation dns plan`
Dry-run comparison between local `~/.config/cstation/dns/<domain>.yaml` files and remote Cloudflare records.

```bash
cstation dns plan [DOMAINS]...
```

#### `cstation dns apply`
Synchronize local DNS declarations to Cloudflare.

```bash
cstation dns apply [DOMAINS]... [OPTIONS]
```
- `--yes, -y`: Skip confirmation prompt.
- `--delete`: Delete remote records that are not defined in the local configuration file.

*(Note: `cstation cloudflare` is available as a backward-compatible alias)*

---

## `cstation auth`

Provider authentication management for interactive services.

### Commands

#### `cstation auth netcup login`
Authenticate with Netcup SCP via OAuth2 Device Code flow.

```bash
cstation auth netcup login
```

#### `cstation auth netcup logout`
Revoke active refresh tokens and clear stored credentials.

```bash
cstation auth netcup logout
```

#### `cstation auth netcup status`
Show authentication status and verify token retrieval.

```bash
cstation auth netcup status
```

---

## `cstation github`

Declarative Git repository management and remote SSH key deployment.

### Commands

#### `cstation github repo list`
List all repositories configured in `~/.config/cstation/github/odoo_repos.sync.yml`.

```bash
cstation github repo list [OPTIONS]
```
- `--config, -c PATH`: Custom configuration file path.

#### `cstation github repo sync`
Sync repositories with upstream (e.g. `odoo/odoo`, `OCA/OpenUpgrade`), merge updates, pull origin, and push back to your GitHub fork.

```bash
cstation github repo sync [REPO_NAME] [OPTIONS]
```
- `[REPO_NAME]`: Specific repository name (syncs all `auto_sync: true` repos by default).
- `--directory, -d PATH`: Target local clone path.
- `--user, -u TEXT`: GitHub username override.

#### `cstation github repo clone`
Clone configured repositories to local disk using **ultra-fast blobless sparse-checkout** (`--filter=blob:none --sparse`) and **multi-threaded parallel execution**. Downloads only the specific addon folders declared in `includes`, speeding up OCA repo syncs by 10x–20x.

```bash
cstation github repo clone [REPO_NAME] [OPTIONS]
```
- `[REPO_NAME]`: Specific repository name (optional, clones all configured repos in parallel by default).
- `--directory, -d PATH`: Target directory for cloning.
- `--user, -u TEXT`: GitHub username override.

#### `cstation github ssh`
Deploy or generate SSH keys on a remote VPS for GitHub access.

```bash
cstation github ssh <vps-hostname> [OPTIONS]
```
- `--key-path, -k PATH`: Local private SSH key to copy (default: `~/.ssh/id_rsa`).
- `--generate`: Generate a new SSH key pair directly on the remote VPS.
- `--add-to-github`: Print instructions and public key for GitHub Deploy Keys.

---

## `cstation server`

Ansible playbook execution and legacy inventory management.

### Commands

- `cstation server ls`: List servers in Ansible inventory.
- `cstation server status`: Ping and check server health using Ansible.
- `cstation server ssh-setup <target>`: Configure SSH key authentication via Ansible (`ssh` is a legacy alias).
- `cstation server playbook list`: List available playbooks.
- `cstation server playbook run <playbook>`: Execute an Ansible playbook against an inventory.
- `cstation server pw sync <host> <version>`: Sync PerfectWork files to a remote host.
