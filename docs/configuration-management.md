# Configuration Management Guide

CStation uses an intelligent configuration management system that automatically detects and loads configuration files from multiple locations with clear precedence rules. This guide explains how the configuration system works and how to troubleshoot common issues.

## Overview

The configuration system provides:
- **Automatic Detection**: Finds configuration files in standard locations
- **Cross-Platform Support**: Works on Windows, macOS, and Linux
- **Precedence Rules**: Local configurations override system configurations
- **Error Handling**: Graceful fallbacks when configuration files are missing
- **Configuration Merging**: Deep merging of nested configuration structures

## Configuration Search Paths

CStation searches for configuration files in the following locations, in order of precedence (highest to lowest):

### 1. Local Configuration (Highest Precedence)
- **Path**: `./etc/` (relative to current working directory)
- **Use Case**: Project-specific configurations, development environments
- **Example**: `/home/user/myproject/etc/`

### 2. System-Wide Configuration
- **Unix/Linux/macOS**: `/etc/cstation/`
- **Windows**: `%PROGRAMDATA%/cstation/` (typically `C:/ProgramData/cstation/`)
- **Use Case**: System-wide defaults, production environments
- **Requires**: Administrative privileges to modify

### 3. User Configuration (Lowest Precedence)
- **Unix/Linux/macOS**: `~/.config/cstation/`
- **Windows**: `%APPDATA%/cstation/` (typically `C:/Users/username/AppData/Roaming/cstation/`)
- **Use Case**: User-specific preferences, personal development settings

## Configuration Files

### Application Configuration
CStation looks for application configuration files in this order:
1. `app/config.yml`
2. `app/config.yaml`
3. `config.yml`
4. `config.yaml`

### Ansible Configuration
CStation automatically detects and sets the `ANSIBLE_CONFIG` environment variable to point to:
- `ansible/ansible.cfg` in any of the search paths

## Configuration Precedence and Merging

### Precedence Rules
When multiple configuration files are found, CStation merges them with the following precedence:
1. **Local** configurations override **System** configurations
2. **System** configurations override **User** configurations
3. **User** configurations provide base defaults

### Deep Merging
Configuration dictionaries are merged recursively:

```yaml
# User config (~/.config/cstation/config.yml)
database:
  host: user-default
  port: 5432
app:
  debug: false

# System config (/etc/cstation/config.yml)
database:
  host: system-db
  timeout: 30
cache:
  enabled: true

# Local config (./etc/config.yml)
database:
  host: localhost

# Final merged configuration:
database:
  host: localhost      # From local (highest precedence)
  port: 5432          # From user
  timeout: 30         # From system
app:
  debug: false        # From user
cache:
  enabled: true       # From system
```

## Installation and Setup

### Package Installation
Install CStation as a Python package to make the `cstation` command globally available:

```bash
# Install from source
pip install -e .

# Or install from PyPI (when available)
pip install cstation

# Install with test dependencies
pip install -e ".[test]"
```

### Verify Installation
```bash
# Check if cstation command is available
cstation --help

# View configuration information
cstation config info  # (if implemented)
```

## Configuration Examples

### Basic Application Configuration
```yaml
# config.yml
app:
  name: "My CStation Setup"
  debug: true
  log_level: "INFO"

database:
  host: "localhost"
  port: 5432
  name: "cstation_db"

ansible:
  host_key_checking: false
  timeout: 30
```

### Environment-Specific Configurations

#### Development (./etc/config.yml)
```yaml
app:
  debug: true
  log_level: "DEBUG"
database:
  host: "localhost"
```

#### Production (/etc/cstation/config.yml)
```yaml
app:
  debug: false
  log_level: "WARNING"
database:
  host: "prod-db.example.com"
  ssl_mode: "require"
```

## Troubleshooting

### Common Issues

#### 1. "No configuration files found"
**Cause**: No configuration files exist in any search path.

**Solution**:
```bash
# Create a basic configuration
mkdir -p ./etc/app
cat > ./etc/app/config.yml << EOF
app:
  name: "CStation"
EOF
```

#### 2. "Permission denied reading configuration file"
**Cause**: Insufficient permissions to read configuration files.

**Solutions**:
```bash
# Check file permissions
ls -la /etc/cstation/

# Fix permissions (as root)
sudo chmod 644 /etc/cstation/config.yml

# Or use user configuration instead
mkdir -p ~/.config/cstation
cp /etc/cstation/config.yml ~/.config/cstation/
```

#### 3. "Invalid YAML in configuration file"
**Cause**: Syntax errors in YAML configuration files.

**Solution**:
```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yml'))"

# Or use online YAML validator
# Fix indentation and syntax errors
```

#### 4. "Ansible configuration not found"
**Cause**: No `ansible.cfg` file found in search paths.

**Solutions**:
```bash
# Create basic ansible.cfg
mkdir -p ./etc/ansible
cat > ./etc/ansible/ansible.cfg << EOF
[defaults]
host_key_checking = False
inventory = inventory/hosts.yml
EOF
```

#### 5. Configuration not taking effect
**Cause**: Configuration precedence or caching issues.

**Debug Steps**:
```bash
# Check which configuration files are being loaded
cstation --debug  # (if debug mode implemented)

# Verify search paths
python -c "
from cstation.config import ConfigManager
cm = ConfigManager()
cm.print_configuration_info()
"

# Clear any cached configurations
rm -rf ~/.cache/cstation/  # (if caching implemented)
```

### Debug Configuration Loading

You can debug configuration loading programmatically:

```python
from cstation.config import ConfigManager

# Create config manager
config_manager = ConfigManager()

# Print search paths and found files
config_manager.print_configuration_info()

# Load and validate configuration
config_manager.load_configuration()
issues = config_manager.validate_configuration()

if issues:
    print("Configuration issues found:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("Configuration loaded successfully!")
```

## Best Practices

### 1. Configuration Organization
```
/etc/cstation/
├── config.yml              # Main application config
├── ansible/
│   ├── ansible.cfg         # Ansible configuration
│   └── inventory/
│       └── hosts.yml       # Inventory file
├── profiles/
│   ├── servers/            # Server profiles
│   └── containers/         # Container profiles
└── secrets/
    └── vault.yml           # Encrypted secrets (use ansible-vault)
```

### 2. Environment Management
- Use **local** configurations (`./etc/`) for development
- Use **system** configurations (`/etc/cstation/`) for production
- Use **user** configurations (`~/.config/cstation/`) for personal preferences

### 3. Security Considerations
- Never store plain-text passwords in configuration files
- Use Ansible Vault for sensitive data
- Set appropriate file permissions (644 for config files)
- Use environment variables for secrets when possible

### 4. Version Control
```bash
# Include in version control
git add etc/config.yml
git add etc/ansible/ansible.cfg

# Exclude sensitive files
echo "etc/secrets/" >> .gitignore
echo "etc/**/*.vault" >> .gitignore
```

## Configuration Schema

While CStation doesn't enforce a strict schema, here's a recommended structure:

```yaml
# Application settings
app:
  name: string
  debug: boolean
  log_level: string  # DEBUG, INFO, WARNING, ERROR
  
# Database configuration
database:
  host: string
  port: integer
  name: string
  user: string
  # password: use vault or environment variable
  
# Ansible settings
ansible:
  host_key_checking: boolean
  timeout: integer
  inventory: string
  
# Custom application settings
custom:
  # Your application-specific settings
```

## Migration from Previous Versions

If you're upgrading from a version that used hardcoded paths:

### 1. Backup Existing Configuration
```bash
cp -r etc/ etc.backup/
```

### 2. Update Import Statements
```python
# Old way
import os
os.environ['ANSIBLE_CONFIG'] = './etc/ansible/ansible.cfg'

# New way
from cstation.config import initialize_configuration
initialize_configuration()
```

### 3. Test Configuration Loading
```bash
# Verify configuration is loaded correctly
cstation --help
```

### 4. Update Scripts and Automation
Update any scripts that relied on hardcoded paths to use the new configuration system.

## API Reference

### ConfigManager Class

```python
from cstation.config import ConfigManager, get_config

# Get global config manager
config = get_config()

# Load configuration
config.load_configuration()

# Get configuration values
value = config.get_config_value('database.host', 'localhost')

# Get Ansible config path
ansible_cfg = config.get_ansible_config_path()

# Validate configuration
issues = config.validate_configuration()
```

### Functions

```python
from cstation.config import initialize_configuration, get_config

# Initialize configuration (call once at startup)
initialize_configuration()

# Get config manager instance
config_manager = get_config()
```

This configuration management system provides a robust, flexible foundation for CStation's infrastructure management capabilities while maintaining backward compatibility and ease of use.