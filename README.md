# CStation - DevOps Infrastructure Management CLI

A powerful Python CLI tool for managing DevOps infrastructure using Typer, Ansible, and Docker.

## Quick Start

```bash
# Install CStation
pip install cstation

# Initialize system configuration
# Standard initialization (root ownership, requires sudo for editing)
sudo cstation init

# Developer initialization (user ownership, allows editing without sudo)
sudo cstation init --developer

# Restore root ownership after developer mode
sudo cstation init

# View available commands
cstation --help

# List server profiles
cstation server profile

# Remove server from inventory (requires sudo)
sudo cstation server rm <server_name>

# Deploy containers
cstation docker deploy <target> --profile <profile>
```

## Documentation

All documentation has been consolidated in the `docs/` directory:

### Main Documentation
- [📖 Complete Documentation](docs/README.md) - Full project documentation
- [⚙️ Configuration Guide](docs/configuration.md) - Configuration and setup

### Commands
- [📋 Commands Overview](docs/commands/README.md) - All available commands
- [🐳 Docker Commands](docs/commands/docker.md) - Container management
- [🖥️ Server Commands](docs/commands/server.md) - Server management
- [🔧 Server Setup](docs/commands/server-setup.md) - Server configuration
- [📦 GitHub Commands](docs/commands/github.md) - Repository management
- [🔄 GitHub Clone](docs/commands/github-clone.md) - Repository cloning

### Setup Guides
- [🚀 Portainer Setup](docs/setup/PORTAINER_SETUP_GUIDE.md) - Container management UI

### Ansible
- [📝 Variables Guide](docs/ansible/variables-guide.md) - Ansible configuration

## Features

- **Server Management**: SSH setup, status monitoring, software installation
- **Container Deployment**: Docker container management with Ansible
- **GitHub Integration**: Repository cloning and management
- **Profile-based Configuration**: Reusable server and container profiles
- **Ansible Integration**: Automated infrastructure provisioning

## Libraries Used

- **Typer**: Modern CLI framework
- **Ansible**: Infrastructure automation
- **Docker**: Container management
- **Rich**: Beautiful terminal output

## Project Structure

```
cstation/
├── commands/          # CLI command modules
├── docs/             # Consolidated documentation
├── etc/              # Configuration templates (copied to /etc/cstation during installation)
│   ├── ansible/      # Ansible playbooks and configs
│   └── profiles/     # Server and container profiles
├── /etc/cstation/    # System configuration directory (created during installation)
│   ├── ansible/      # Ansible playbooks and configs
│   └── profiles/     # Server and container profiles
└── cstation.py       # Main CLI entry point
```

## Contributing

See the [complete documentation](docs/README.md) for detailed information about development, configuration, and usage.