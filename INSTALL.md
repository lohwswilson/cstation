# CStation Installation Guide

This guide provides comprehensive installation instructions for CStation, a Python CLI tool for DevOps infrastructure management.

## Prerequisites

- **Python 3.8+** (recommended: Python 3.9 or later)
- **pip** (Python package installer)
- **Ansible** (will be installed automatically as a dependency)
- **Docker** (optional, for containerized deployments)

## Installation Methods

### Method 1: Package Installation (Recommended)

#### Install from Source (Development)
```bash
# Clone the repository
git clone <repository-url>
cd cstation

# Install in development mode
pip install -e .

# Verify installation
cstation --help
```

#### Install with Test Dependencies
```bash
# Install with testing capabilities
pip install -e ".[test]"

# Run tests to verify installation
pytest tests/
```

### Method 2: Direct Installation (Future PyPI Release)
```bash
# When available on PyPI
pip install cstation

# Verify installation
cstation --help
```

## Post-Installation Configuration

### Automatic Configuration Detection

CStation automatically detects and loads configuration files from multiple locations with the following precedence:

1. **Local Configuration** (highest precedence): `./etc/`
2. **System Configuration**: 
   - Unix/Linux/macOS: `/etc/cstation/`
   - Windows: `%PROGRAMDATA%/cstation/`
3. **User Configuration** (lowest precedence):
   - Unix/Linux/macOS: `~/.config/cstation/`
   - Windows: `%APPDATA%/cstation/`

### Initial Setup Options

#### Option 1: Local Development Setup
```bash
# Create local configuration directory
mkdir -p ./etc/ansible

# Create basic Ansible configuration
cat > ./etc/ansible/ansible.cfg << EOF
[defaults]
host_key_checking = False
inventory = inventory/hosts.yml
timeout = 30

[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s
pipelining = True
EOF

# Create inventory directory
mkdir -p ./etc/ansible/inventory

# Create basic inventory file
cat > ./etc/ansible/inventory/hosts.yml << EOF
all:
  children:
    servers:
      hosts:
        # Add your servers here
        # example-server:
        #   ansible_host: 192.168.1.100
        #   ansible_user: ubuntu
EOF
```

#### Option 2: System-Wide Setup (Production)
```bash
# Create system configuration directory (requires sudo)
sudo mkdir -p /etc/cstation/ansible/inventory

# Copy configuration from local setup
sudo cp -r ./etc/* /etc/cstation/

# Set appropriate permissions
sudo chmod -R 644 /etc/cstation/
sudo chmod 755 /etc/cstation/ansible
```

#### Option 3: User-Specific Setup
```bash
# Create user configuration directory
mkdir -p ~/.config/cstation/ansible/inventory

# Copy configuration
cp -r ./etc/* ~/.config/cstation/
```

## Installation Steps

## Verification and Testing

### Verify Installation
```bash
# Check if cstation command is available globally
cstation --help

# Check version
cstation version

# Test configuration loading (if implemented)
cstation config info
```

### Test Configuration Precedence
```bash
# Create test configurations in different locations
mkdir -p ./etc/app
echo "app: {name: 'local-config'}" > ./etc/app/config.yml

mkdir -p ~/.config/cstation/app
echo "app: {name: 'user-config'}" > ~/.config/cstation/app/config.yml

# Local config should take precedence
cstation config show  # Should show 'local-config'
```

### Run Tests (Development Installation)
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=cstation

# Run specific test categories
pytest tests/test_config.py -v
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
│   └── odoo_repos.sync.yml       # GitHub repository sync config
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

### Ownership Management

CStation provides flexible ownership management to support both production and development workflows:

#### Production Mode (Default)
```bash
sudo cstation init
```
- **Ownership**: Files owned by `root:wheel`
- **Permissions**: Restrictive (644 for files, 755 for directories)
- **Editing**: Requires `sudo` for all configuration changes
- **Use Case**: Production servers, shared systems, security-sensitive environments
- **Security**: Maximum security with root-only write access

#### Developer Mode
```bash
sudo cstation init --developer
```
- **Ownership**: Files owned by current user (detected from `SUDO_USER`)
- **Permissions**: Permissive (666 for config files, 755 for executables)
- **Editing**: No `sudo` required for configuration changes
- **Use Case**: Local development, testing, rapid iteration
- **Convenience**: Easy editing with any text editor

#### Switching Between Modes

You can seamlessly switch between ownership modes:

```bash
# Enable developer mode for easy editing
sudo cstation init --developer

# Work on configurations
vim /etc/cstation/ansible/inventory/hosts.yml
cstation server list

# Restore production security when done
sudo cstation init
```

#### When to Use Each Mode

**Use Production Mode When**:
- Deploying to production servers
- Multiple users access the system
- Security compliance is required
- System is shared or managed by multiple administrators

**Use Developer Mode When**:
- Local development and testing
- Rapid configuration iteration
- Single-user development environment
- Frequent configuration file editing

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
