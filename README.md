# CStation - Infrastructure Management CLI

🚀 A powerful DevOps CLI tool for managing infrastructure using Ansible, built with Python 3.13, Typer, and uv.

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

### Install Dependencies

```bash
# Install dependencies with uv
uv sync

# Install the CLI tool in development mode
uv pip install -e .
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

#### Server Status and Monitoring
```bash
# Check status of all servers
cstation server status

# Check status of specific server
cstation server status sg01

# Check status with service information
cstation server status sg01 --services

# Check uptime of all servers
cstation server uptime

# Check uptime of specific server
cstation server uptime sg01
```

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

## Configuration Structure

CStation uses the following configuration structure in the `./etc/` directory:

```
./etc/
├── README.md
├── ansible/
│   ├── ansible.cfg         # Ansible configuration for server management
│   ├── inventory/
│   │   └── hosts.yml       # Server inventory file
│   ├── group_vars/         # Group variables
│   ├── host_vars/          # Host variables
│   ├── playbooks/          # Ansible playbooks (for server management)
│   └── roles/              # Ansible roles (for server management)
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

# 3. Check server status
cstation server status

# 4. Check specific server status with services
cstation server status sg01 --services

# 5. Check server uptime
cstation server uptime sg01

# 6. Setup GitHub repositories
cstation github repo config
cstation github repo sync
```

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