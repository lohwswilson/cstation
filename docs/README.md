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

# Deploy containers to a server
cstation docker deploy <target> --profile <profile>
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

#### Server Setup and Configuration Management
```bash
# List available software profiles
cstation server profile

# Setup database server with dry run
cstation server setup sg01 --profile database_server --dry-run

# Setup database server on specific host
cstation server setup sg01 --profile database_server

# Setup web server on all hosts
cstation server setup all --profile web_server

# Setup Odoo application server
cstation server setup sg02 --profile odoo_app

# Use custom inventory file
cstation server setup sg01 --profile web_server --inventory /path/to/inventory.yml

# Enable verbose output
cstation server setup sg01 --profile database_server --verbose
```

**Server Setup Features:**
- **Profile-based Configuration**: Use predefined software profiles for different server types
- **Ansible Integration**: Leverages existing Ansible inventory and generates dynamic playbooks
- **Automatic Configuration**: CLI commands automatically use `/etc/cstation/ansible/ansible.cfg` for consistent Ansible settings
- **Dry Run Mode**: Preview changes before execution for safe deployments
- **Template Management**: Jinja2 templates for service configurations (PostgreSQL, Nginx)
- **Service Management**: Automatically configure and start services after installation
- **Firewall Configuration**: Automated firewall rule setup based on profile requirements
- **Multi-Server Support**: Deploy software across multiple servers simultaneously
- **Custom Inventory**: Support for custom Ansible inventory files

**Available Software Profiles:**
- **database_server**: PostgreSQL, Redis, monitoring tools with optimized configurations
- **web_server**: Nginx, SSL certificates, security tools, and firewall setup
- **odoo_app**: Complete Odoo application server with Python dependencies and web stack

**Profile Structure:**
Profiles are YAML files located in `/etc/cstation/service/server/` that define complete server configurations including:
- **Packages**: List of software packages to install with version specifications
- **Services**: Service configuration with enable/disable and start/stop settings
- **Configurations**: Template files for service configuration (PostgreSQL, Nginx, etc.)
- **Docker Containers**: Container definitions with images, ports, volumes, and networks
- **Docker Networks**: Network creation and configuration for container communication
- **Firewall Rules**: Port and protocol specifications for security
- **Environment Variables**: Service-specific environment configuration
- **Post-install Tasks**: Additional Ansible tasks for custom setup requirements

**Profile Types:**

**Unified Profiles** (Recommended): Contain both software and container definitions in a single file
- `basic_server.yml` - Basic server setup with essential packages and Docker
- `web_server.yml` - Complete web server with Nginx, Traefik, WordPress, MySQL, Redis
- `database_server.yml` - Database server with PostgreSQL, Redis, and monitoring tools

**Creating a New Profile:**

```bash
# Create a new profile based on existing one
sudo cp /etc/cstation/service/server/web_server.yml /etc/cstation/service/server/my_profile.yml
# Edit the profile
sudo vim /etc/cstation/service/server/my_profile.yml
```

### Host-Specific Variables

Host-specific variables can be defined in `/etc/cstation/ansible/host_vars/<hostname>.yml` to override profile defaults and customize configurations for individual servers:

#### Basic Host Override Example
```yaml
# /etc/cstation/ansible/host_vars/server01.yml
server_info:
  hostname: server01
  environment: production

docker_daemon_config:
  log_driver: "json-file"
  log_opts:
    docker_log_max_size: "50m"
    docker_log_max_file: "3"

containers:
  traefik:
    environment:
      TRAEFIK_LOG_LEVEL: "INFO"
```

#### Production Host Override Example
The `web01.yml` example demonstrates a comprehensive production server configuration:

```yaml
# /etc/cstation/ansible/host_vars/web01.yml
server_info:
  hostname: web01
  environment: production
  location: usa_east

# Production domain settings
domain_name: "mycompany.com"
ssl_email: "devops@mycompany.com"

# Enhanced Docker daemon for production
docker_daemon_config:
  log_driver: "json-file"
  log_opts:
    docker_log_max_size: "100m"  # Larger logs
    docker_log_max_file: "5"     # More retention
  live_restore: true

# Override containers with production settings
containers:
  traefik:
    name: "traefik_prod"
    environment:
      TRAEFIK_API_INSECURE: "false"  # Secure dashboard
      TRAEFIK_LOG_LEVEL: "INFO"
    resource_limits:
      memory: "1g"
      cpu: "1.0"
    labels:
      traefik.http.routers.traefik.rule: "Host(`traefik.mycompany.com`)"
      traefik.http.routers.traefik.tls.certresolver: "letsencrypt"

  wordpress:
    name: "wordpress_prod"
    environment:
      WORDPRESS_DB_NAME: "wordpress_prod"
      FORCE_SSL_ADMIN: "true"
    labels:
      traefik.http.routers.wordpress.rule: "Host(`www.mycompany.com`) || Host(`mycompany.com`)"

# Additional production containers
  prometheus:
    name: "prometheus_prod"
    image: "prom/prometheus:latest"
    volumes:
      - "./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro"
    command:
      - "--storage.tsdb.retention.time=30d"

# Production-specific networks
docker_networks:
  - name: "monitoring_network"
    driver: "bridge"

# Production backup configuration
backup_config:
  enabled: true
  s3_bucket: "mycompany-backups"
  retention_policy:
    daily: 7
    weekly: 4
    monthly: 12
```

#### Host Override Capabilities

**Complete Override**: Replace entire sections
```yaml
containers:
  nginx:  # Completely replaces nginx container definition
    image: "nginx:alpine"
    ports: ["8080:80"]
```

**Partial Override**: Merge with profile defaults
```yaml
containers:
  nginx:
    environment:  # Adds to existing environment variables
      CUSTOM_VAR: "value"
```

**Resource Scaling**: Adjust for different environments
```yaml
containers:
  mysql:
    resource_limits:
      memory: "4g"    # Production: more memory
      cpu: "2.0"      # Production: more CPU
```

**Environment-Specific Settings**:
```yaml
# Development
containers:
  app:
    environment:
      DEBUG: "true"
      LOG_LEVEL: "debug"

# Production  
containers:
  app:
    environment:
      DEBUG: "false"
      LOG_LEVEL: "info"
```

**Profile Configuration Sections:**

*Software Configuration:*
```yaml
packages:
  - name: nginx
    version: latest
  - name: docker.io
    version: latest

services:
  - name: nginx
    state: started
    enabled: true
  - name: docker
    state: started
    enabled: true

configurations:
  - src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    owner: root
    group: root
    mode: '0644'
```

*Container Configuration:*
```yaml
containers:
  traefik:
    name: "traefik"
    image: "traefik:v3.0"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
    environment:
      TRAEFIK_API_DASHBOARD: "true"
    networks:
      - "web_network"
    restart_policy: "unless-stopped"
    labels:
      traefik.enable: "true"

docker_networks:
  - name: "web_network"
    driver: "bridge"
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

### Complete Server Setup with Profiles

#### Basic Server Setup
```bash
# Setup a basic server with essential packages and Docker
cstation server setup sg01 --profile basic_server

# Deploy containers defined in the profile
cstation server setup docker sg01
```

#### Web Server with Custom Configuration
```bash
# Setup web server with Nginx, Traefik, WordPress, MySQL, Redis
cstation server setup web01 --profile web_server

# Deploy all containers (Traefik, WordPress, MySQL, Redis, monitoring)
cstation server setup docker web01
```

#### Database Server Setup
```bash
# Setup database server with PostgreSQL, Redis, and monitoring
cstation server setup db01 --profile database_server

# Deploy database containers (PostgreSQL, Redis, pgAdmin, monitoring)
cstation server setup docker db01
```

### Production Deployment with Host Overrides

#### Production Web Server (using web01.yml host vars)
```bash
# Deploy production web server with custom domain and SSL
cstation server setup software web01 --profile web_server

# Deploy production containers with enhanced security and monitoring
cstation server setup docker web01
```

#### Container-Only Deployments
```bash
# Deploy only specific containers (assumes software is installed)
cstation server setup docker web01

# Update container configurations without reinstalling software
cstation server setup docker web01 --force
```

### Development vs Production

#### Development Environment
```bash
# Create development host vars with debug settings
# /etc/cstation/ansible/host_vars/dev01.yml
server_info:
  environment: development
containers:
  wordpress:
    environment:
      WORDPRESS_DEBUG: "true"
      WP_DEBUG_LOG: "true"

# Deploy development server
cstation server setup dev01 --profile web_server
cstation server setup docker dev01
```

#### Production Environment
```bash
# Use production host vars (web01.yml) with optimized settings
# Enhanced security, monitoring, backups, SSL certificates

# Deploy production server
cstation server setup software web01 --profile web_server
cstation server setup docker web01
```

### Scaling and Customization

#### Custom Profile Creation
```bash
# Create custom profile based on web_server
sudo cp /etc/cstation/service/server/web_server.yml /etc/cstation/service/server/ecommerce_server.yml

# Edit to add ecommerce-specific containers
sudo vim /etc/cstation/service/server/ecommerce_server.yml

# Deploy custom profile
cstation server setup shop01 --profile ecommerce_server
cstation server setup docker shop01
```

#### Multi-Server Deployment
```bash
# Deploy multiple servers with same profile but different host configs
cstation server setup web01 --profile web_server  # Production
cstation server setup web02 --profile web_server  # Staging
cstation server setup dev01 --profile web_server  # Development

# Deploy containers to all servers
cstation server setup docker web01
cstation server setup docker web02
cstation server setup docker dev01
```

### Complete Workflow Example

```bash
# 1. List all servers in inventory
cstation server list

# 2. Setup SSH keys for servers
cstation server ssh sg01
cstation server ssh sg02

# 3. Check server status and uptime (unified table display)
cstation server status

# 4. Check server status after setup
cstation server status

# 5. Setup GitHub repositories
cstation github repo config
cstation github repo sync
```

## Documentation

Detailed documentation is available in the following sections:

### Commands
- [Commands Overview](commands/README.md) - Complete guide to all available commands
- [Docker Management](commands/docker.md) - Container and image management
- [Server Management](commands/server.md) - Server provisioning and management
- [Server Setup](commands/server-setup.md) - Detailed server setup procedures
- [GitHub Integration](commands/github.md) - Repository management and automation
- [GitHub Clone](commands/github-clone.md) - Repository cloning utilities

### Configuration
- [Configuration Guide](configuration.md) - System configuration and settings
- [Portainer Setup](setup/PORTAINER_SETUP_GUIDE.md) - Container management UI setup

### Ansible Infrastructure Management
- [Ansible Overview](ansible/README.md) - Complete Ansible setup and usage guide
- [Inventory Management](ansible/inventory-guide.md) - Advanced inventory configuration
- [Variables Guide](ansible/variables-guide.md) - Ansible automation variables

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