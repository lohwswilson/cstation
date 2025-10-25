# CStation - Infrastructure Management CLI

🚀 A powerful DevOps CLI tool for managing infrastructure using Ansible, built with Python 3.13, Typer, and uv.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Development Installation](#development-installation)
  - [Production Installation](#production-installation)
  - [Verification](#verification)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Basic Commands](#basic-commands)
  - [Server Management](#server-management)
  - [GitHub Management](#github-management)
  - [Docker Services](#docker-services)
- [Available Docker Services](#available-docker-services)
- [Configuration](#configuration)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## Features

- **Server Management**: SSH key setup, status monitoring, host listing, and remote server administration
- **GitHub Management**: Repository management and SSH key setup for GitHub access
- **Project Initialization**: Scaffold new infrastructure projects with best practices
- **Rich CLI Interface**: Beautiful, colored output with progress indicators
- **Modern Python**: Built with Python 3.13 and modern tooling
- **Modular Architecture**: Clean, maintainable code structure with proper packaging

## Installation

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip
- Ansible (for server management features)

### Development Installation

For development work, install CStation in editable mode:

```bash
# Clone the repository
git clone <repository-url>
cd cstation

# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
uv pip install -e .

# Verify installation
cstation --help
```

### Production Installation

For production use, install directly from the package:

```bash
# Using uv (recommended)
uv pip install cstation

# Or using pip
pip install cstation
```

### Verification

After installation, verify that CStation is working correctly:

```bash
# Check version
cstation version

# View available commands
cstation --help

# Test from any directory
cd /tmp
cstation version
```

## Quick Start

```bash
# Initialize system configuration (root ownership)
sudo cstation init

# Initialize with user ownership (allows editing without sudo)
sudo cstation init --developer

# Restore root ownership after developer mode
sudo cstation init
```

## Usage

### Basic Commands

```bash
# Show version information
cstation version

# Initialize configuration
cstation init

# Get help for any command
cstation <command> --help
```

### Server Management

```bash
# List available servers
cstation server ls

# Check server status
cstation server status <hostname>

# Setup SSH key authentication
cstation server ssh <hostname>

# List available playbooks
cstation server code

# Execute playbook on target
cstation server push <playbook> <target>

# Remove server from inventory
cstation server rm <hostname>
```

### GitHub Management

```bash
# GitHub repository operations
cstation github --help

# Setup GitHub SSH keys
cstation github ssh
```

### Docker Services

```bash
# Service management
cstation service --help

# Docker service operations
cstation service docker --help
```

## Available Docker Services

CStation supports management of various Docker services for infrastructure needs. Use `cstation service --help` for detailed information.

## Configuration

CStation stores its configuration in `/etc/cstation/` by default. The configuration includes:

- Ansible configuration files
- Inventory files
- Playbooks and roles
- SSH keys and certificates

## Development

### Project Structure

```
cstation/
├── src/                     # Source code directory
│   └── cstation/            # Main package
│       ├── __init__.py      # Package initialization
│       ├── main.py          # CLI entry point
│       ├── config.py        # Configuration management
│       └── commands/        # Command modules
│           ├── version/     # Version command
│           ├── init/        # Initialization command
│           ├── server/      # Server management
│           ├── github/      # GitHub operations
│           └── service/     # Service management
├── tests/                   # Test suite
├── docs/                    # Documentation
├── pyproject.toml          # Package configuration
├── requirements-dev.txt    # Development dependencies
└── README.md               # This file
```

**Directory Structure Conventions:**

- **`src/`**: Contains all source code following Python packaging best practices
- **`src/cstation/`**: Main package with clear separation from project root
- **`tests/`**: Test suite with same structure as source code
- **`docs/`**: Comprehensive documentation and guides
- **`pyproject.toml`**: Modern Python packaging configuration
- **`requirements-dev.txt`**: Development-specific dependencies

This structure follows the **src-layout** pattern, which:
- Prevents accidental imports from the project directory
- Ensures proper package installation testing
- Provides clear separation between source code and project files
- Follows modern Python packaging standards

### Setting up Development Environment

```bash
# Clone and setup
git clone <repository-url>
cd cstation

# Create virtual environment
uv venv

# Activate environment
source .venv/bin/activate

# Install in editable mode with dev dependencies
uv pip install -e ".[test]"

# Run tests
pytest

# Run specific test
pytest tests/test_config.py
```

### Making Changes

1. Make your changes to the code
2. Test locally: `cstation --help`
3. Run tests: `pytest`
4. The editable installation will reflect changes immediately

## Troubleshooting

### Common Installation Issues

#### Command Not Found After Installation

**Problem**: `cstation: command not found` after installation

**Solutions**:

1. **Virtual Environment**: Ensure your virtual environment is activated:
   ```bash
   source .venv/bin/activate
   which cstation  # Should show path in .venv/bin/
   ```

2. **Global Installation**: For global access, install in your system Python:
   ```bash
   # Using uv globally
   uv pip install --system cstation
   
   # Or using pip
   pip install --user cstation
   ```

3. **PATH Issues**: Add the installation directory to your PATH:
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   export PATH="$HOME/.local/bin:$PATH"
   ```

#### Import Errors

**Problem**: `ModuleNotFoundError` when running commands

**Solutions**:

1. **Reinstall in editable mode**:
   ```bash
   uv pip uninstall cstation
   uv pip install -e .
   ```

2. **Check Python path**:
   ```bash
   python -c "import cstation; print(cstation.__file__)"
   ```

#### Permission Errors

**Problem**: Permission denied when running `cstation init`

**Solution**: Use sudo for system-wide configuration:
```bash
sudo cstation init
```

#### Ansible Not Found

**Problem**: Ansible commands fail

**Solution**: Install Ansible:
```bash
uv pip install ansible
# or
pip install ansible
```

### Getting Help

1. **Check command help**: `cstation <command> --help`
2. **Verify installation**: `cstation version`
3. **Check logs**: Look in `/etc/cstation/logs/` (if configured)
4. **Test in clean environment**: Create a new virtual environment and test

### Development Troubleshooting

#### Editable Installation Not Working

```bash
# Uninstall and reinstall
uv pip uninstall cstation
uv pip install -e .

# Verify
python -c "import cstation; print(cstation.__file__)"
```

#### Tests Failing

```bash
# Install test dependencies
uv pip install -e ".[test]"

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_config.py -v
```

---

**Note**: This CLI tool is designed for DevOps professionals and requires proper understanding of Ansible, Docker, and infrastructure management concepts.