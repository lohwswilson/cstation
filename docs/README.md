# CStation - Infrastructure Management CLI

🚀 A powerful DevOps CLI tool for managing infrastructure using Ansible, built with Python 3.13, Typer, and uv.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Ownership Management](#ownership-management)
- [Usage](#usage)
  - [Basic Commands](#basic-commands)
  - [Server Management](#server-management)
  - [GitHub Management](#github-management)
  - [Docker Services](#docker-services)
- [Available Docker Services](#available-docker-services)
- [Documentation](#documentation)
- [Configuration](#configuration)
- [Development](#development)

## Features

- **Server Management**: SSH key setup, status monitoring, host listing, and remote server administration
- **GitHub Management**: Repository management and SSH key setup for GitHub access
- **Project Initialization**: Scaffold new infrastructure projects with best practices
- **Rich CLI Interface**: Beautiful, colored output with progress indicators
- **Modern Python**: Built with Python 3.13 and modern tooling

## Installation

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Ansible (for server management features)

## Quick Start

```bash
# Install CStation
pip install cstation

# Initialize system configuration (root ownership)
sudo cstation init

# Initialize with user ownership (allows editing without sudo)
sudo cstation init --developer

# Restore root ownership after developer mode
sudo cstation init

# View available commands
cstation --help

# List available server profiles
cstation server profile

# List available Docker service profiles
cstation service docker ls

# Deploy Docker service to a server
cstation service docker push <profile> <target_host>
```

## Ownership Management

CStation supports two ownership modes for configuration files:

### Production Mode (Default)
- Files owned by root with restrictive permissions
- Requires `sudo` for editing configuration files
- Recommended for production environments

```bash
sudo cstation init
```

### Developer Mode
- Files owned by current user with permissive permissions
- Allows editing configuration files without `sudo`
- Ideal for development and testing

```bash
sudo cstation init --developer
```

### Switching Modes

You can easily switch between modes by re-running the init command:

```bash
# Enable developer mode
sudo cstation init --developer

# Restore production mode
sudo cstation init
```

## Usage

### Basic Commands

```bash
# Show help (default when no command provided)
cstation
cstation --help

# Show version
cstation version

# Get help for specific commands
cstation server --help
cstation github --help
```



### Server Management

#### SSH Key Setup
```bash
# Setup SSH key for a specific server
cstation server ssh sg01

# Setup SSH key with custom inventory
cstation server ssh sg01 -i /path/to/inventory.yml

# Setup SSH key with custom key path
cstation server ssh sg01 -k ~/.ssh/my_key.pub

# Generate new SSH key and setup
cstation server ssh sg01 --generate
```

#### Server Inventory Management
```bash
# List all servers in inventory
cstation server list

# Show details for specific server
cstation server list sg01

# Use custom inventory file
cstation server list -i /path/to/inventory.yml
```

#### Server Inventory Management
```bash
# Remove server from inventory with confirmation (requires sudo)
sudo cstation server rm eu01

# Force remove without confirmation
sudo cstation server rm eu01 --force

# Preview what would be removed (dry run - no sudo needed)
cstation server rm eu01 --dry-run

# Remove without creating backup
sudo cstation server rm eu01 --no-backup
```

**Server Removal Features:**
- **Safe Removal**: Confirmation prompts and automatic backups by default
- **Cross-group Search**: Automatically finds servers across all inventory groups
- **Dry Run Support**: Preview changes before execution
- **Detailed Feedback**: Shows exactly what will be removed and lists available servers if not found

#### Server Status and Monitoring
```bash
# Check status and uptime of all servers (displays in unified table)
cstation server status

# Check status and uptime of specific server
cstation server status sg01

# Check status only without uptime information
cstation server status --no-uptime

# Check status of specific server without uptime
cstation server status sg01 --no-uptime
```

**Status Display Features:**
- **Unified Table Format**: Status and uptime information displayed in a single, organized table
- **YAML-based Parsing**: Uses YAML library for reliable inventory file parsing
- **Smart Filtering**: Automatically filters out 'vars' sections from Ansible inventory
- **Clean Output**: Professional table layout with proper column headers (Host, Status, Uptime)
- **Conditional Columns**: When using `--no-uptime`, only Host and Status columns are shown



### GitHub Management

#### Repository Management
```bash
# Initialize GitHub configuration
cstation github repo config

# List configured repositories
cstation github repo list

# Clone a specific repository
cstation github repo clone my-project

# Clone to specific directory
cstation github repo clone my-project --directory /path/to/repos

# Sync all repositories with auto_sync enabled
cstation github repo sync

# Sync specific repository
cstation github repo sync my-project
```

**Advanced Sync Features:**
- **Upstream Integration**: Automatically fetches and merges from upstream repositories
- **Shallow Fetching**: Uses `--depth=1` for efficient single-branch fetches from upstream
- **Unrelated Histories**: Handles repositories with unrelated histories by resetting to upstream
- **Force Push**: Automatically force-pushes when needed after upstream synchronization
- **Timeout Management**: 60-second timeout for origin fetch, 120-second for upstream fetch
- **Branch Cleanup**: Uses `--prune` flag to clean up stale remote-tracking branches

**Sync Workflow:**
1. **Upstream Sync**: Fetches from upstream repository (if configured) with shallow clone
2. **Merge/Reset**: Attempts to merge upstream changes, or resets for unrelated histories
3. **Origin Fetch**: Fetches latest changes from origin with pruning
4. **Push**: Pushes changes to GitHub origin, with force push if needed after upstream sync

This workflow ensures your repositories stay synchronized with both upstream sources and your GitHub forks, handling complex scenarios like large repositories (Odoo) and unrelated commit histories automatically.

**Troubleshooting:**
- **"refusing to merge unrelated histories"**: Automatically handled by resetting to upstream
- **"non-fast-forward" push errors**: Automatically resolved with force push after upstream sync
- **Large repository timeouts**: Extended timeouts (60s origin, 120s upstream) prevent hanging
- **Stale remote branches**: Automatic cleanup with `--prune` flag during fetch operations

#### SSH Key Setup for GitHub
```bash
# Setup SSH key for GitHub on remote server
cstation github ssh sg01

# Generate new SSH key and setup for GitHub
cstation github ssh sg01 --generate

# Setup with custom SSH key path
cstation github ssh sg01 --key-path ~/.ssh/github_rsa

# Setup with specific GitHub username
cstation github ssh sg01 --github-user myusername

# Display instructions to add key to GitHub
cstation github ssh sg01 --add-to-github
```

### Docker Services

#### List Available Docker Services
```bash
# List all available Docker service profiles
cstation service docker ls
```

#### Deploy Docker Services
```bash
# Deploy Portainer (full management UI)
cstation service docker push portainer <target_host>

# Deploy Portainer Agent (for remote management)
cstation service docker push portainer_agent <target_host>

# Deploy other services
cstation service docker push traefik <target_host>
```

**Docker Service Features:**
- **Ansible-based Deployment**: Uses Ansible playbooks for reliable container deployment
- **Inventory Integration**: Validates target hosts against your server inventory
- **Service Profiles**: Pre-configured service templates for common applications
- **Automated Setup**: Handles container creation, networking, and volume management

## Available Docker Services

| Service | Description | Ports | Use Case |
|---------|-------------|-------|----------|
| **portainer** | Full Docker management UI | 8000, 9000, 9443 | Standalone Docker management or primary hub |
| **portainer_agent** | Lightweight remote management agent | 9001 | Remote Docker host management |
| **traefik** | Reverse proxy and load balancer | 80, 443, 8080 | HTTP routing and SSL termination |

### Service Setup Guides

- [Portainer Setup Guide](setup/PORTAINER_SETUP_GUIDE.md) - Complete Docker management UI
- [Portainer Agent Setup Guide](setup/PORTAINER_AGENT_SETUP_GUIDE.md) - Remote Docker management
- [Docker Service Management](commands/docker.md) - General service deployment guide

## Configuration Structure

CStation uses the following configuration structure in the `/etc/cstation/` directory:

```
/etc/cstation/
├── README.md
├── ansible/
│   ├── ansible.cfg         # Ansible configuration for server management
│   ├── inventory/
│   │   └── hosts.yml       # Server inventory file
│   ├── group_vars/         # Group variables
│   ├── host_vars/          # Host variables
│   ├── playbooks/          # Ansible playbooks (for server management)
│   ├── roles/              # Ansible roles (for server management)
│   └── software/           # Software installation configurations (legacy)
│       ├── packages.yml    # Legacy software groups and packages
│       └── examples/       # Legacy example configurations
└── github/
    ├── 16.0.oca.yml        # GitHub repositories configuration
    ├── 17.0.oca.yml        # GitHub repositories configuration
    ├── 18.0.oca.yml        # GitHub repositories configuration
    └── repos.sync.yml      # Repository sync configuration
```

## Development

### Running from Source

```bash
# Run directly with Python
python main.py --help

# Or use uv run
uv run python main.py --help
```

### Adding New Commands

1. Add new commands to the appropriate Typer app in `main.py`
2. Follow the existing pattern for error handling and rich output
3. Update this README with usage examples

### Dependencies

- **Typer**: Modern CLI framework with automatic help generation
- **Rich**: Beautiful terminal output with colors and formatting
- **Ansible**: Used internally for server management and infrastructure automation
- **Python 3.13**: Latest Python with improved performance and features

## Examples

### Complete Workflow Example

```bash
# 1. List all servers in inventory
cstation server list

# 2. Setup SSH keys for servers
cstation server ssh sg01
cstation server ssh sg02

# 3. Check server status and uptime (unified table display)
cstation server status

# 4. Setup GitHub repositories
cstation github repo config
cstation github repo sync
```

## Documentation

Detailed documentation is available in the following sections:

### Commands
- [Commands Overview](commands/README.md) - Complete guide to all available commands
- [Docker Management](commands/docker.md) - Container and image management
- [Server Management](commands/server.md) - Server provisioning and management
- [Service Management](commands/service.md) - Docker service deployment and management
- [GitHub Integration](commands/github.md) - Repository management and automation
- [GitHub Clone](commands/github-clone.md) - Repository cloning utilities
- [Init Command](commands/init.md) - System initialization and setup

### Docker Services
- [Services Overview](services/README.md) - Complete guide to all available Docker services
- [Portainer Setup](setup/PORTAINER_SETUP_GUIDE.md) - Full Docker management UI setup
- [Portainer Agent Setup](setup/PORTAINER_AGENT_SETUP_GUIDE.md) - Remote Docker management agent

### Configuration
- [Configuration Guide](configuration.md) - System configuration and settings

### Ansible Infrastructure Management
- [Ansible Overview](ansible/README.md) - Complete Ansible setup and usage guide
- [Inventory Management](ansible/inventory-guide.md) - Advanced inventory configuration
- [Variables Guide](ansible/variables-guide.md) - Ansible automation variables
- [Ansible Vault Guide](ansible/ansible-vault-guide.md) - Secure secrets management
- [Host Variables Example](ansible/host_vars_example.yml) - Example host configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation
- Review existing issues for solutions