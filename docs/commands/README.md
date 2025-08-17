# CStation Commands Documentation

This directory contains detailed documentation for all CStation commands.

## Available Commands

- [Init](init.md) - Initialize CStation configuration system
- [Server Management](server.md) - Manage server inventory and operations
- [Docker Management](docker.md) - Deploy and manage containers
- [GitHub Integration](github.md) - Repository management and synchronization


## Benefits of This Structure

1. **Modularity**: Each command group has its own directory
2. **Easier Debugging**: Issues can be isolated to specific modules
3. **Better Organization**: Related functionality is grouped together
4. **Scalability**: New commands can be easily added as separate modules
5. **Maintainability**: Code is easier to navigate and modify

## Adding New Commands

### Adding a New Top-Level Command

1. Create a new directory under `commands/` (e.g., `commands/deploy/`)
2. Add `__init__.py` to make it a Python package
3. Create `main.py` with your command implementation
4. Import and register the command in the main `cstation.py`

### Adding a New Subcommand to Ansible

1. Create a new `.py` file in `commands/ansible/` (e.g., `vault.py`)
2. Implement your command function
3. Import and register it in `commands/ansible/main.py`

## Example: Adding a New Command

```python
# commands/deploy/main.py
import typer
from rich import print as rprint

def deploy(
    environment: str = typer.Argument(..., help="Target environment")
):
    """Deploy application to specified environment"""
    rprint(f"[blue]Deploying to:[/blue] {environment}")
    # Implementation here

# In cstation.py, add:
# from commands.deploy.main import deploy
# app.command()(deploy)
```

This modular structure makes the codebase more maintainable and easier to debug while preserving all existing functionality.