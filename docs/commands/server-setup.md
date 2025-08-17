# CStation Server Setup Command

The `cstation server setup` command provides automated server configuration and software installation using Ansible profiles.

## Architecture

The setup command follows a profile-based approach where each profile defines:
- Software packages to install
- Services to configure
- Configuration templates
- Firewall rules
- Environment variables
- Post-installation tasks

## Command Structure

```
cstation server setup
└── software          # Install software packages, services, and configurations
```

## Usage Examples

### Software Installation
```bash
# List available profiles
cstation server profile

# Setup database server software (dry run)
cstation server setup sg01 --profile database_server --dry-run

# Setup database server software (execute)
cstation server setup sg01 --profile database_server

# Setup web server software on all hosts
cstation server setup all --profile web_server
```

### Container Deployment
```bash
# Note: Docker container deployment has been moved to 'cstation docker deploy'
# See: cstation docker deploy --help
```

### Advanced Usage
```bash
# Use custom inventory for software
cstation server setup sg01 --profile web_server --inventory /path/to/custom-inventory.yml

# Enable verbose output for software installation
cstation server setup sg01 --profile database_server --verbose

# Setup Odoo application server software
cstation server setup sg02 --profile odoo_app

# Note: Docker container deployment has been moved to 'cstation docker deploy'
# Example: cstation docker deploy sg01 --profile web_server --inventory /path/to/custom-inventory.yml
```

## Available Profiles

### database_server
**Purpose**: Complete database server setup
**Includes**:
- PostgreSQL with optimized configuration
- Redis server
- Monitoring tools (htop, iotop)
- Automated service configuration
- Firewall rules for database ports

### web_server
**Purpose**: Secure web server setup
**Includes**:
- Nginx with security headers
- SSL certificate support (Certbot)
- Firewall configuration (UFW)
- Security tools (Fail2ban)
- Performance optimizations

### odoo_app
**Purpose**: Odoo application server
**Includes**:
- Python 3 with development tools
- All Odoo dependencies
- PostgreSQL client
- Nginx for reverse proxy
- System libraries for PDF generation

## Profile Structure

Each profile is a YAML file located in `/etc/cstation/service/server/` with the following structure:

```yaml
description: "Profile description"

packages:
  - name: package_name
    version: latest
  - name: another_package
    version: "1.2.3"

services:
  - name: service_name
    enabled: true
    state: started

configurations:
  - src: template_file.j2
    dest: /path/to/config/file

firewall_rules:
  - port: 80
    protocol: tcp
    rule: allow
    comment: "HTTP"

environment_variables:
  VAR_NAME: "value"

post_install_tasks:
  - name: "Custom task"
    module_name:
      parameter: value
```

## Configuration Templates

Templates are stored in `/etc/cstation/ansible/templates/` and use Jinja2 syntax:

### PostgreSQL Templates
- `postgresql/postgresql.conf.j2`: Main PostgreSQL configuration
- `postgresql/pg_hba.conf.j2`: Authentication configuration

### Nginx Templates
- `nginx/nginx.conf.j2`: Main Nginx configuration
- `nginx/default.conf.j2`: Default site configuration

## Host-Specific Variables

The setup command automatically loads and merges host-specific variables from `/etc/cstation/ansible/host_vars/{hostname}.yml` files. These variables override profile defaults and enable per-host customization.

### Variable Processing

1. **Automatic Loading**: Host variables are loaded based on the target hostname
2. **Smart Merging**: Host variables take precedence over profile variables for:
   - `containers`: Container deployment configurations
   - `packages`: Package installation lists
   - `services`: Service management settings
   - `configurations`: Configuration file templates
3. **Docker Daemon Config**: Special handling for Docker daemon configuration
4. **Template Access**: All host variables are available in Jinja2 templates

### Docker Daemon Configuration

Docker daemon settings can be customized per host using the `docker_daemon_config` section:

```yaml
# In host_vars/hostname.yml
docker_daemon_config:
  log_driver: "json-file"
  log_opts:
    docker_log_max_size: "50m"  # Override default 10m
    docker_log_max_file: "3"    # Override default 3
  storage_driver: "overlay2"
  experimental: false
```

These settings are automatically extracted and made available to the Docker daemon template (`templates/docker/daemon.json.j2`).

### Container Deployment

Containers can be defined in host variables for automatic deployment:

```yaml
# In host_vars/hostname.yml
containers:
  traefik:
    name: "HOSTNAME_TRAEFIK"
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
```

## How It Works

### Setup Command (`cstation server setup`)
1. **Profile Loading**: Reads the specified profile YAML file
2. **Host Variables**: Automatically loads host-specific variables from `host_vars/`
3. **Configuration Merging**: Merges profile and host variables (host takes precedence)
4. **Validation**: Validates inventory file and profile existence
5. **Playbook Generation**: Creates dynamic Ansible playbook for software installation
6. **Package Installation**: Installs packages defined in profile and host variables
7. **Service Management**: Configures and starts services
8. **Configuration Files**: Processes Jinja2 templates and deploys configuration files
9. **Execution**: Runs ansible-playbook with generated configuration
10. **Cleanup**: Removes temporary files

### Docker Container Deployment

**Note**: Docker container deployment functionality has been moved to a dedicated top-level command:

```bash
cstation docker deploy <target> --profile <profile>
```

This provides better command organization and dedicated Docker management capabilities. The `software` command now focuses exclusively on package installation, service configuration, and file management, while container deployment is handled by the dedicated docker module.

## Error Handling

- **Missing Profile**: Shows available profiles if specified profile doesn't exist
- **Invalid Inventory**: Validates inventory file existence before execution
- **Ansible Errors**: Captures and displays ansible-playbook output
- **Template Errors**: Handles Jinja2 template processing errors

## Security Features

- **Dry Run Mode**: Preview changes before execution
- **Firewall Configuration**: Automated UFW rule setup
- **Security Headers**: Nginx security headers in templates
- **Service Hardening**: Optimized service configurations
- **SSL Support**: Built-in SSL certificate management

## Extending Profiles

To create a new profile:

1. Create a new YAML file in `/etc/cstation/service/server/`
2. Follow the profile structure documented above
3. Add any required templates to `/etc/cstation/ansible/templates/`
4. Test with `--dry-run` before deployment

## Dependencies

- **Ansible**: Required for playbook execution
- **Python 3**: For YAML processing and template rendering
- **Target System**: Ubuntu/Debian-based systems (uses apt package manager)

## Troubleshooting

### Common Issues

1. **"Profile not found"**: Check profile name and file existence
2. **"Inventory file not found"**: Verify inventory path
3. **Ansible connection errors**: Check SSH connectivity and inventory configuration
4. **Package installation failures**: Verify package names and repository availability

### Debug Mode

Use `--verbose` flag to see detailed Ansible output:
```bash
cstation server setup sg01 --profile database_server --verbose
```

### Dry Run Testing

Always test with `--dry-run` first:
```bash
cstation server setup sg01 --profile database_server --dry-run
```