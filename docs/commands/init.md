# CStation Init Command

The `cstation init` command initializes the CStation configuration system by copying configuration files from the project directory to `/etc/cstation` and setting up proper permissions.

## Usage

```bash
# Standard initialization (root ownership)
sudo cstation init

# Developer mode (user ownership)
sudo cstation init --developer

# Force initialization (overwrite existing)
sudo cstation init --force

# Dry run (preview changes)
sudo cstation init --dry-run
```

## Options

- `--force, -f`: Force initialization even if `/etc/cstation` exists
- `--backup/--no-backup`: Create backup of existing `/etc/cstation` directory (default: enabled)
- `--dry-run`: Show what would be done without executing
- `--developer`: Set user ownership and permissions to allow editing configuration files without sudo

## Ownership Management

### Standard Mode (Default)

```bash
sudo cstation init
```

- Files are owned by `root:wheel`
- Restrictive permissions (644 for files, 755 for directories)
- Requires `sudo` for editing configuration files
- Recommended for production environments

### Developer Mode

```bash
sudo cstation init --developer
```

- Files are owned by the current user (detected from `SUDO_USER`)
- Permissive permissions (666 for config files, 755 for executables)
- Allows editing configuration files without `sudo`
- Ideal for development and testing

### Switching Between Modes

You can easily switch between ownership modes:

```bash
# Enable developer mode
sudo cstation init --developer

# Restore root ownership
sudo cstation init
```

## What Gets Initialized

1. **Directory Structure**: Creates `/etc/cstation` with subdirectories
2. **Ansible Configuration**: Copies playbooks, roles, inventory, and templates
3. **Container Profiles**: Copies Docker container configurations
4. **Service Profiles**: Copies service deployment configurations
5. **GitHub Integration**: Copies repository synchronization configs
6. **Path Updates**: Updates `ansible.cfg` with absolute paths

## Examples

### First-time Setup

```bash
# Initialize for production use
sudo cstation init

# Initialize for development
sudo cstation init --developer
```

### Updating Configuration

```bash
# Update with latest configs (creates backup)
sudo cstation init --force

# Preview what would change
sudo cstation init --dry-run
```

### Development Workflow

```bash
# Enable developer mode for easy editing
sudo cstation init --developer

# Edit configs without sudo
vim /etc/cstation/ansible/inventory/hosts.yml

# Test changes
cstation server list

# Restore production permissions when done
sudo cstation init
```

## Security Considerations

- **Production**: Always use standard mode (`sudo cstation init`) for production servers
- **Development**: Developer mode is safe for local development but should not be used on production systems
- **Backups**: Automatic backups are created before overwriting existing configurations
- **Permissions**: The system automatically sets appropriate permissions based on the mode

## Troubleshooting

### Permission Denied Errors

If you encounter permission errors:

1. Ensure you're running with `sudo`
2. Check if you need to switch to developer mode: `sudo cstation init --developer`
3. Verify file ownership: `ls -la /etc/cstation/`

### Backup Recovery

If you need to restore from a backup:

```bash
# List available backups
ls -la /tmp/cstation.backup.*

# Restore from backup (replace timestamp)
sudo rm -rf /etc/cstation
sudo mv /tmp/cstation.backup.TIMESTAMP /etc/cstation
```

## Related Commands

- [`cstation server list`](server.md#list): List configured servers
- [`cstation server rm`](server.md#remove): Remove servers (requires appropriate permissions)
- [`cstation service docker ls`](../README.md): List Docker service profiles