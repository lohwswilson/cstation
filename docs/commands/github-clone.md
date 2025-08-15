# GitHub Repository Clone Command

The `cstation github repo clone` command provides selective cloning functionality that allows you to clone only specific directories or files from repositories based on configuration files.

## Command Structure

```bash
cstation github repo clone [REPO_NAME] [OPTIONS]
```

## Features

- **Selective Cloning**: Clone only specific directories/files from repositories
- **Configuration-based**: Uses YAML configuration files to define repositories and includes
- **Batch Processing**: Clone multiple repositories at once
- **Branch Support**: Supports specific branch cloning (including numeric branches like 18.0)
- **Temporary Cloning**: Uses temporary directories to avoid full repository downloads

## Configuration Format

The configuration file should follow this YAML structure:

```yaml
github:
  username: "your-github-username"
  default_clone_method: "ssh"  # or "https"
  default_directory: "/etc/cstation/github"
  organization: "your-org"  # Default organization for repositories

repositories:
  - name: "repo-name"
    description: "Repository description"
    url: https://github.com/owner/repo.git
    branch: 18.0  # Can be string or number
    local_path: "/path/to/local/destination"
    includes:
      - directory1
      - directory2
      - file.txt
      - path/to/nested/directory
```

## Usage Examples

### Clone a specific repository
```bash
cstation github repo clone Muk --config /etc/cstation/github/18.0.oca.yml
```

### Clone all repositories from configuration
```bash
cstation github repo clone --config /etc/cstation/github/18.0.oca.yml
```

### Clone with custom target directory
```bash
cstation github repo clone Muk --config /etc/cstation/github/18.0.oca.yml --directory /custom/path
```

## Command Options

- `--config, -c`: GitHub repositories configuration file (default: /etc/cstation/github/repos.sync.yml)
- `--directory, -d`: Target directory for cloning (default: current directory)
- `--user, -u`: GitHub username (will use config if not provided)
- `--help`: Show help message

## How It Works

1. **Configuration Loading**: Reads the YAML configuration file
2. **Repository Selection**: Filters repositories based on the provided name (or all if none specified)
3. **Temporary Cloning**: Clones the full repository to a temporary directory
4. **Selective Copying**: Copies only the specified directories/files from the `includes` list
5. **Cleanup**: Automatically removes the temporary clone

## Example Configuration File

```yaml
github:
  username: "lohwswilson"
  default_clone_method: "ssh"
  default_directory: "/etc/cstation/github"
  organization: "ansis-ai"

repositories:
  - name: "Muk"
    description: "Muk-it Odoo Modules"
    url: https://github.com/muk-it/odoo-modules.git
    branch: 18.0
    local_path: "/opt/PW/PW_ADDONS.18.0/OCA"
    includes:
      - muk_contacts
      - muk_product
      - muk_web_appsbar
      - muk_web_colors
      - muk_web_chatter
      - muk_web_dialog
      - muk_mail_route
      - muk_web_utils
      - muk_web_theme

  - name: "queue"
    description: "OCA Queue"
    url: https://github.com/OCA/queue.git
    branch: 18.0
    local_path: "/opt/PW/PW_ADDONS.18.0/OCA"
    includes:
      - queue_job
      - queue_job_cron_jobrunner
```

## Output Example

```
Cloning 1 repositories with selective directories...
╭─── Selective Repository Clone ────╮
│ Selective Clone: Muk              │
│ URL: https://github.com/muk-it/odoo-modules.git │
│ Branch: 18.0                      │
│ Target: /opt/PW/PW_ADDONS.18.0/OCA │
│ Includes: muk_contacts, muk_product, ... │
╰───────────────────────────────────╯
Cloning Muk to temporary location...
  ✓ Copied directory: muk_contacts
  ✓ Copied directory: muk_product
  ✓ Copied directory: muk_web_appsbar
  ...
✓ Successfully copied 9 items from Muk
  Target location: /opt/PW/PW_ADDONS.18.0/OCA
```

## Error Handling

- **Missing Configuration**: Shows error if config file doesn't exist
- **Repository Not Found**: Lists available repositories if specified repo doesn't exist
- **Missing Fields**: Validates required fields (url, local_path, includes)
- **Git Errors**: Displays git command errors with helpful messages
- **Missing Items**: Reports which included items were not found in the repository

## Requirements

- Git must be installed and available in PATH
- Network access to clone repositories
- Write permissions to target directories
- Python packages: typer, yaml, rich

## Related Commands

- `cstation github repo list`: List configured repositories
- `cstation github repo sync`: Sync repositories with upstream
- `cstation github ssh`: Setup SSH keys for GitHub access