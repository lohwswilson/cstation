# CStation Installation Guide

This guide explains how to install CStation CLI with system-wide configuration support.

## Overview

CStation now uses `/etc/cstation` as the system-wide configuration directory. This ensures that:
- Configuration files are accessible from anywhere on the system
- Multiple users can share the same configuration
- The CLI works consistently regardless of the current working directory

## Installation Steps

### 1. Install CStation CLI

```bash
# Install from PyPI
pip install cstation

# Or install in development mode
git clone <repository-url>
cd cstation
pip install -e .
```

### 2. Initialize System Configuration

```bash
# Initialize /etc/cstation directory (requires sudo)
sudo cstation init

# For user-friendly permissions (allows regular users to edit config files)
sudo cstation init --developer

# Or with other options
sudo cstation init --force --backup
```

The `cstation init` command will:
- Create `/etc/cstation` directory structure
- Copy all configuration files from the package to `/etc/cstation/`
- Set proper permissions (root ownership by default, or user-editable with --developer)
- Create a timestamped backup of any existing `/etc/cstation` directory
- Update Ansible configuration with absolute paths

### 3. Verify Installation

```bash
# Check if cstation command is available
cstation --help

# Test configuration access
cstation server list

# Verify Ansible configuration
ANSIBLE_CONFIG=/etc/cstation/ansible/ansible.cfg ansible-inventory --list
```

## Configuration Structure

After installation, your configuration will be organized as follows:

```
/etc/cstation/
├── ansible/
│   ├── ansible.cfg          # Main Ansible configuration
│   ├── inventory/
│   │   └── hosts.yml        # Server inventory
│   ├── host_vars/           # Host-specific variables
│   ├── roles/               # Ansible roles
│   ├── collections/         # Ansible collections
│   └── templates/           # Configuration templates
├── profiles/
│   ├── servers/             # Server software profiles
│   └── containers/          # Container profiles
├── github/
│   └── repos.sync.yml       # GitHub repository sync config
└── app/
    └── config.yml           # Application configuration
```

## Key Changes

### Absolute Paths
All CLI commands now use absolute paths to `/etc/cstation/` instead of relative paths to `etc/`.

### Ansible Configuration
The `ansible.cfg` file has been updated to use absolute paths:
- `inventory = /etc/cstation/ansible/inventory/hosts.yml`
- `roles_path = /etc/cstation/ansible/roles`
- `collections_path = /etc/cstation/ansible/collections`

### Environment Variables
All CLI commands automatically set `ANSIBLE_CONFIG=/etc/cstation/ansible/ansible.cfg` to ensure consistent Ansible behavior.

## Troubleshooting

### Permission Issues
If you encounter permission errors:

```bash
# Ensure you're running as root
sudo cstation init

# Check directory permissions
ls -la /etc/cstation/

# Fix permissions if needed
sudo chown -R root:root /etc/cstation/
sudo chmod -R 755 /etc/cstation/
sudo find /etc/cstation -name "*.yml" -exec chmod 644 {} \;
sudo find /etc/cstation -name "*.yaml" -exec chmod 644 {} \;
sudo find /etc/cstation -name "*.cfg" -exec chmod 644 {} \;
```

### Configuration File Editing

**Standard Mode (Default)**:
- Files are owned by root with restrictive permissions (644/755)
- Only root can edit configuration files
- More secure for production environments
- Use: `sudo cstation init`

**User-Friendly Mode**:
- Files are owned by root but with permissive permissions (666/755)
- Regular users can edit configuration files
- Better for development and testing
- Use: `sudo cstation init --developer`

To switch between modes, re-run the init command with your preferred option.

### Initialization Options

```bash
# Force initialization (overwrite existing)
sudo cstation init --force

# Set user-friendly permissions (allows regular users to edit config files)
sudo cstation init --user-friendly

# Skip backup creation
sudo cstation init --no-backup

# Dry run (see what would be done)
sudo cstation init --dry-run

# Get help
cstation init --help
```

### Configuration Not Found
If the CLI cannot find configuration files:

1. Verify `/etc/cstation` exists and contains the expected files:
   ```bash
   ls -la /etc/cstation/
   ```

2. Re-run the installation script:
   ```bash
   sudo ./install.sh
   ```

### Ansible Issues
If Ansible commands fail:

1. Test Ansible configuration directly:
   ```bash
   ANSIBLE_CONFIG=/etc/cstation/ansible/ansible.cfg ansible-inventory --list
   ```

2. Check inventory file:
   ```bash
   cat /etc/cstation/ansible/inventory/hosts.yml
   ```

## Uninstallation

To remove CStation:

```bash
# Remove the CLI package
pip uninstall cstation

# Remove system configuration (optional)
sudo rm -rf /etc/cstation
```

## Development Setup

For development work:

```bash
# Clone and install in development mode
git clone <repository-url>
cd cstation
pip install -e .

# Initialize configuration
sudo cstation init

# Make changes to code
# Test changes
cstation --help
```

For development, you can still use the local `etc/` directory by temporarily setting environment variables:

```bash
# Use local configuration for development
export ANSIBLE_CONFIG="$(pwd)/etc/ansible/ansible.cfg"

# Or modify the CLI commands to use relative paths during development
```

## Migration from Previous Versions

If you're upgrading from a version that used relative paths:

1. Back up your existing configuration:
   ```bash
   cp -r etc/ etc.backup
   ```

2. Run the installation script:
   ```bash
   sudo ./install.sh
   ```

3. Update any custom scripts or automation that relied on relative paths.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the logs for specific error messages
3. Ensure all dependencies are installed
4. Verify file permissions and ownership