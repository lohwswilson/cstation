# CStation GitHub Repository Clone Command

The `cstation github repo clone` command provides fast, selective cloning of GitHub repositories, allowing you to download only specific directories or files from large repositories.

## Features

- **Fast Selective Cloning**: Clone only specific directories/files from repositories using Git sparse-checkout
- **Performance Optimized**: Uses sparse-checkout and shallow cloning (depth=1) for maximum speed
- **Configuration-driven**: Uses YAML configuration files to define repositories and their selective includes
- **Batch Operations**: Clone multiple repositories or specific ones
- **Rich UI**: Beautiful terminal interface with progress indicators
- **Automatic Fallback**: Falls back to regular shallow clone if sparse-checkout fails
- **Error Handling**: Comprehensive error handling and user feedback

## Command Structure

```bash
cstation github repo clone [OPTIONS] [REPO_NAME]
```

### Arguments
- `REPO_NAME` (optional): Name of specific repository to clone. If omitted, clones all repositories in config.

### Options
- `--config PATH`: Path to configuration file (default: `etc/github/repos.yml`)
- `--directory PATH`: Override default clone directory
- `--user TEXT`: Override GitHub username

## Configuration Format

The configuration file should follow this YAML structure:

```yaml
github:
  username: "your-github-username"
  clone_method: "ssh"  # or "https"
  default_directory: "/path/to/default/clone/location"
  organization: "your-org"

repositories:
  - name: "repo-name"
    description: "Repository description"
    url: "https://github.com/user/repo.git"
    branch: "main"  # Can be string or number (e.g., 18.0)
    local_path: "/path/to/local/clone/location"
    includes:
      - "directory1"
      - "directory2/subdirectory"
      - "specific-file.txt"
```

## Usage Examples

### Clone a specific repository
```bash
cstation github repo clone --config etc/github/18.0.oca.yml Muk
```

### Clone all repositories from configuration
```bash
cstation github repo clone --config etc/github/18.0.oca.yml
```

### Use custom configuration file
```bash
cstation github repo clone --config /path/to/custom-config.yml
```

### Override clone directory
```bash
cstation github repo clone --directory /custom/path MyRepo
```

## How It Works

### Optimized Sparse-Checkout Method (Primary)
1. **Configuration Loading**: Reads the specified YAML configuration file
2. **Repository Selection**: Processes either a specific repository or all configured repositories
3. **Sparse-Checkout Setup**: 
   - Initializes an empty Git repository
   - Configures sparse-checkout patterns for only the required directories
   - Fetches only the specified files/directories with `--depth 1`
4. **Selective Copying**: Copies the sparse-checked content to the target location
5. **Cleanup**: Automatically removes temporary files after copying

### Multi-Level Fallback System (If sparse-checkout fails)
1. **Optimized Fallback**: Uses partial clone with blob filtering (`--filter=blob:none`)
2. **Treeless Fallback**: Even more aggressive filtering (`--filter=tree:0`)
3. **Basic Fallback**: Simple shallow clone with `--depth 1` as last resort
4. **Selective Copying**: Copies only the specified directories/files from the `includes` list
5. **Cleanup**: Automatically removes temporary files after copying

### Performance Benefits
- **Primary Method**: Sparse-checkout downloads only required files, dramatically reducing network transfer
- **Optimized Fallbacks**: Partial clone with blob filtering avoids downloading file contents initially
- **Progressive Degradation**: Multiple fallback levels ensure compatibility while maintaining performance
- **Shallow operations**: All methods use `--depth 1` to avoid downloading Git history
- **Smart filtering**: Git 2.19+ features like `--filter=blob:none` and `--filter=tree:0` for minimal downloads
- **10-50x faster**: For large repos with selective includes, can be dramatically faster than full clones

## Error Handling

- **Missing Git**: Checks for Git installation and provides clear error messages
- **Invalid URLs**: Validates repository URLs and provides feedback
- **Missing Directories**: Reports which included items were not found in the repository
- **Permission Issues**: Handles file system permission problems gracefully
- **Network Issues**: Provides clear feedback on connection problems
- **Automatic Fallback**: If sparse-checkout fails, automatically tries regular shallow clone

## Requirements

- Git installed and accessible from command line (version 2.25+ recommended for best sparse-checkout support)
- Python with Typer, Rich, and PyYAML libraries
- Appropriate permissions for the target directories

## Performance Tips

- **For very large repositories**: The optimized methods can be 10-50x faster than regular cloning
- **Network optimization**: Multiple filtering strategies reduce bandwidth usage by 80-95%
- **Storage optimization**: Only downloads required files, saving significant disk space
- **Git version recommendations**:
  - Git 2.25+ for optimal sparse-checkout performance
  - Git 2.19+ for partial clone features (`--filter=blob:none`)
  - Git 2.20+ for treeless clone features (`--filter=tree:0`)
- **Include patterns**: Be specific with your `includes` list to minimize unnecessary downloads
- **Batch operations**: Clone multiple repos in one command for efficiency
- **Fallback system**: Automatically adapts to your Git version and repository capabilities

## Related Commands

- `cstation github repo list`: List all configured repositories
- `cstation github repo sync`: Sync existing repositories with upstream
- `cstation github ssh`: Setup GitHub SSH authentication

## Example Output

```
╭─ Optimized Repository Clone ─╮
│ Fast Selective Clone: MyRepo  │
│ URL: https://github.com/...   │
│ Branch: main                  │
│ Target: /opt/project/addons   │
│ Includes: module1, module2    │
│ Using sparse-checkout for     │
│ faster cloning                │
╰───────────────────────────────╯

Initializing sparse checkout for MyRepo...
Fetching only required directories from MyRepo...
  ✓ Copied directory: module1
  ✓ Copied directory: module2
✓ Successfully copied 2 items from MyRepo
  Target location: /opt/project/addons
  Used sparse-checkout for faster cloning
```

This optimized approach makes it practical to work with large repositories where you only need specific components, dramatically reducing clone times and storage requirements.