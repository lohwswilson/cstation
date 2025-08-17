# Docker Command Module

This module provides Docker container management functionality for the cstation CLI tool.

## Overview

The docker command has been moved from `cstation server setup docker` to `cstation docker` to provide a more intuitive and organized command structure.

## Commands

### Deploy Containers

```bash
cstation docker deploy <target> --profile <profile_name> [options]
```

Deploy Docker containers on servers using Ansible profiles.

**Arguments:**
- `target`: Target server hostname or 'all' for all servers

**Options:**
- `--profile, -p`: Software profile containing container definitions (required)
- `--inventory, -i`: Path to Ansible inventory file (default: /etc/cstation/ansible/inventory/hosts.yml)
- `--dry-run`: Show what containers would be deployed without executing
- `--verbose, -v`: Enable verbose output

**Examples:**
```bash
# Deploy Portainer on eu01 server
cstation docker deploy eu01 --profile portainer

# Deploy database containers on all servers with dry run
cstation docker deploy all --profile database_server --dry-run

# Deploy with custom inventory and verbose output
cstation docker deploy sg01 --profile web_app --inventory ./custom-inventory.yml --verbose
```

### List Containers

```bash
cstation docker list <target> [options]
```

List running Docker containers on target server.

**Arguments:**
- `target`: Target server hostname

**Options:**
- `--inventory, -i`: Path to Ansible inventory file
- `--verbose, -v`: Enable verbose output

## Migration from Server Setup

The docker functionality has been moved from `cstation server setup docker` to `cstation docker deploy`. The old command is still available but shows a deprecation warning.

### Old Command (Deprecated)
```bash
cstation server setup docker eu01 --profile portainer
```

### New Command
```bash
cstation docker deploy eu01 --profile portainer
```

## Architecture

The docker module follows the same architecture as the original implementation:

1. **Profile Loading**: Reads container profiles from `/etc/cstation/service/containers/` and server profiles from `/etc/cstation/service/server/`
2. **Host Variables**: Loads host-specific variables from `/etc/cstation/ansible/host_vars/`
3. **Configuration Merging**: Merges profile and host variables
4. **Ansible Execution**: Creates and executes Ansible playbooks for container deployment

## Dependencies

- **Typer**: CLI framework
- **Rich**: Terminal formatting and tables
- **PyYAML**: YAML configuration parsing
- **Ansible**: Container deployment automation

## Files

- `main.py`: Main docker command implementation
- `__init__.py`: Module initialization
- `README.md`: This documentation file