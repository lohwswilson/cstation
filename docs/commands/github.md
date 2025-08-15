# GitHub Command Module

The GitHub command module provides comprehensive GitHub repository management and SSH key setup for remote servers.

## Features

- **SSH Key Management**: Set up SSH keys for GitHub access on remote servers
- **Repository Management**: List and sync GitHub repositories
- **Configuration Management**: Store all GitHub configurations in `./etc/github`
- **Ansible Integration**: Use Ansible for remote SSH key setup
- **Batch Operations**: Sync multiple repositories at once

## Commands

### SSH Key Setup

```bash
# Set up SSH key for GitHub on a remote server
cstation github ssh <hostname>

# Generate new SSH key and set up on remote server
cstation github ssh <hostname> --generate

# Use custom SSH key path
cstation github ssh <hostname> --key-path ~/.ssh/github_rsa

# Specify GitHub username
cstation github ssh <hostname> --github-user myusername
```

### Repository Management

```bash
# List configured repositories
cstation github repo list

# Sync all repositories with auto_sync enabled
# (fetches from upstream, merges changes, and pushes to GitHub)
cstation github repo sync

# Sync specific repository
cstation github repo sync my-project
```

## Configuration

All GitHub configurations are stored in `./etc/github/`:

- `repos.sync.yml` - Repository configuration file
- `repos.yml.example` - Example configuration template

### Repository Configuration Format

```yaml
github:
  username: "your-github-username"
  default_clone_method: "ssh"  # or "https"
  default_directory: "./repositories"

repositories:
  - name: "my-project"
    description: "Main project repository"
    clone_method: "ssh"
    auto_sync: true
    local_path: "./repositories/my-project"
  
  - name: "dotfiles"
    description: "Personal dotfiles configuration"
    clone_method: "ssh"
    auto_sync: true
    local_path: "./repositories/dotfiles"
```

## SSH Key Setup Arguments

- `hostname` (required): Target server hostname or IP address

## SSH Key Setup Options

- `--inventory, -i`: Ansible inventory file (default: inventory.ini)
- `--key-path, -k`: SSH key path (default: ~/.ssh/id_rsa)
- `--github-user, -u`: GitHub username for SSH key setup
- `--generate, -g`: Generate new SSH key pair if it doesn't exist

## Repository Management Arguments

- `action`: Action to perform (list, sync)
- `repo_name`: Repository name (for sync action)

## Repository Management Options

- `--config, -c`: Configuration file path (default: etc/github/repos.sync.yml)
- `--directory, -d`: Target directory for cloning
- `--user, -u`: GitHub username (overrides config)

## How It Works

### SSH Key Setup

1. **Key Generation**: Optionally generates new SSH key pair
2. **Ansible Playbook**: Creates temporary playbook for remote setup
3. **Key Deployment**: Copies public key to remote server
4. **SSH Configuration**: Configures SSH client for GitHub
5. **Connection Test**: Tests SSH connection to GitHub
6. **Instructions**: Displays instructions to add key to GitHub

### Repository Management

1. **Configuration Loading**: Loads repository settings from YAML
2. **Repository Operations**: Performs sync or list operations
3. **Upstream Synchronization**: Fetches and merges from upstream repositories
4. **GitHub Updates**: Pushes changes to GitHub for production deployment
5. **Batch Processing**: Handles multiple repositories efficiently
6. **Error Handling**: Provides detailed error messages and recovery

## Prerequisites

- **Ansible**: Required for remote SSH key setup
- **Git**: Required for repository operations
- **SSH Access**: Target servers must be accessible via SSH
- **Python Dependencies**: PyYAML, typer, rich

## Examples

### Complete SSH Setup Workflow

```bash
# Generate and set up new SSH key for GitHub
cstation github ssh server01 --generate --github-user myusername

# The command will:
# 1. Generate new SSH key pair
# 2. Deploy to remote server
# 3. Configure SSH for GitHub
# 4. Test connection
# 5. Show instructions to add key to GitHub
```

### Repository Management Workflow

```bash
# List configured repositories
cstation github repo list

# Sync all auto-sync repositories
# This will:
# 1. Fetch from upstream (if configured)
# 2. Merge upstream changes
# 3. Fetch from origin
# 4. Push updates to GitHub
cstation github repo sync

# Sync specific repository
cstation github repo sync my-project
```

## Security Notes

- SSH keys are generated with secure defaults (RSA 4096-bit)
- Private keys remain on the target server
- Public keys are safely deployed via Ansible
- SSH configuration follows security best practices
- Repository configurations support both SSH and HTTPS methods

## Troubleshooting

### SSH Key Issues

- **Permission denied**: Ensure SSH key is added to GitHub account
- **Connection timeout**: Check network connectivity to GitHub
- **Key not found**: Verify key path and permissions

### Repository Issues

- **Sync failed**: Verify local repository state and remote access
- **Config not found**: Ensure configuration file exists at etc/github/repos.sync.yml

### Ansible Issues

- **Host unreachable**: Verify inventory file and SSH access
- **Permission denied**: Check SSH key authentication
- **Module not found**: Ensure Ansible is properly installed