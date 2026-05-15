#!/usr/bin/env python3
"""
Configuration Management Module for CStation CLI

This module handles configuration file detection, loading, and merging
with proper precedence rules and cross-platform path resolution.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import yaml
from rich.console import Console

console = Console()

def _parse_dotenv_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
        return value[1:-1]
    return value


def _parse_dotenv_lines(content: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        out[key] = _parse_dotenv_value(value)
    return out


def _find_project_root(start: Path) -> Optional[Path]:
    p = start.resolve()
    for candidate in [p, *p.parents]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return None


def _system_dotenv_path() -> Optional[Path]:
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        return Path(appdata) / "cstation" / ".env"
    return Path.home() / ".config" / "cstation" / ".env"


def load_dotenv() -> None:
    initial_keys = set(os.environ.keys())

    dotenv_paths: list[Path] = []
    system_env = _system_dotenv_path()
    if system_env is not None:
        dotenv_paths.append(system_env)

    project_root = _find_project_root(Path.cwd())
    if project_root is not None:
        dotenv_paths.append(project_root / ".env")

    for path in dotenv_paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for key, value in _parse_dotenv_lines(content).items():
            if key in initial_keys:
                continue
            os.environ[key] = value


class ConfigurationError(Exception):
    """Custom exception for configuration-related errors"""
    pass


CSTATION_VPS_DIR = Path.home() / ".config" / "cstation" / "vps"
CSTATION_DNS_DIR = Path.home() / ".config" / "cstation" / "dns"
CSTATION_IMAGES_DIR = Path.home() / ".config" / "cstation" / "images"


def get_vps_secrets(vps_name: str, service_name: str) -> dict[str, str]:
    try:
        return config_manager.config_data["vps"]["secrets"][vps_name][service_name]
    except (KeyError, TypeError):
        return {}


class ConfigManager:
    """
    Configuration manager that handles multiple configuration sources
    with proper precedence and error handling.
    """
    
    def __init__(self):
        self.config_data: Dict[str, Any] = {}
        self.config_sources: List[str] = []
        
    def get_config_search_paths(self) -> List[Path]:
        """
        Get configuration search paths in order of precedence (highest to lowest):
        1. Current working directory ./etc/
        2. System-wide /etc/cstation/ (Unix) or %PROGRAMDATA%/cstation/ (Windows)
        3. User home directory ~/.config/cstation/ (Unix) or %APPDATA%/cstation/ (Windows)
        """
        paths = []
        
        # 1. Local configuration (highest precedence)
        local_config = Path.cwd() / "etc"
        paths.append(local_config)
        
        # 2. System-wide configuration
        if sys.platform.startswith('win'):
            # Windows system configuration
            system_config = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / "cstation"
        else:
            # Unix-like system configuration
            system_config = Path("/etc/cstation")
        paths.append(system_config)
        
        # 3. User configuration (lowest precedence)
        if sys.platform.startswith('win'):
            # Windows user configuration
            user_config = Path(os.environ.get('APPDATA', '')) / "cstation"
        else:
            # Unix-like user configuration
            user_config = Path.home() / ".config" / "cstation"
        paths.append(user_config)
        
        return paths
    
    def find_ansible_config(self) -> Optional[Path]:
        """
        Find the Ansible configuration file in the search paths.
        Returns the first valid ansible.cfg found.
        """
        # Prioritize system-wide ansible configuration first
        system_ansible_cfg = Path("/etc/cstation/ansible/ansible.cfg")
        if system_ansible_cfg.exists() and system_ansible_cfg.is_file():
            return system_ansible_cfg
            
        # Then check other search paths
        for base_path in self.get_config_search_paths():
            ansible_cfg = base_path / "ansible" / "ansible.cfg"
            if ansible_cfg.exists() and ansible_cfg.is_file():
                return ansible_cfg
        return None
    
    def find_app_config(self) -> Optional[Path]:
        """
        Find the application configuration file in the search paths.
        Returns the first valid config.yml found.
        """
        for base_path in self.get_config_search_paths():
            config_files = [
                base_path / "app" / "config.yml",
                base_path / "app" / "config.yaml",
                base_path / "config.yml",
                base_path / "config.yaml"
            ]
            for config_file in config_files:
                if config_file.exists() and config_file.is_file():
                    return config_file
        return None
    
    def load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Load and parse a YAML configuration file with error handling.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            Dictionary containing the parsed configuration
            
        Raises:
            ConfigurationError: If file cannot be read or parsed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                self.config_sources.append(str(file_path))
                return data
        except FileNotFoundError:
            raise ConfigurationError(f"Configuration file not found: {file_path}")
        except PermissionError:
            raise ConfigurationError(f"Permission denied reading configuration file: {file_path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file {file_path}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Unexpected error reading configuration file {file_path}: {e}")
    
    def merge_configs(self, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two configuration dictionaries with deep merging.
        
        Args:
            base_config: Base configuration (lower precedence)
            override_config: Override configuration (higher precedence)
            
        Returns:
            Merged configuration dictionary
        """
        result = base_config.copy()
        
        for key, value in override_config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Deep merge for nested dictionaries
                result[key] = self.merge_configs(result[key], value)
            else:
                # Override for non-dict values or new keys
                result[key] = value
        
        return result
    
    def load_configuration(self) -> Dict[str, Any]:
        """
        Load and merge configuration from all available sources.
        
        Returns:
            Merged configuration dictionary
        """
        merged_config = {}
        
        # Load configurations in reverse precedence order (lowest to highest)
        search_paths = list(reversed(self.get_config_search_paths()))
        
        for base_path in search_paths:
            config_files = [
                base_path / "app" / "config.yml",
                base_path / "app" / "config.yaml",
                base_path / "config.yml",
                base_path / "config.yaml"
            ]
            
            for config_file in config_files:
                if config_file.exists() and config_file.is_file():
                    try:
                        file_config = self.load_yaml_file(config_file)
                        merged_config = self.merge_configs(merged_config, file_config)
                        console.print(f"[green]✓[/green] Loaded configuration from: {config_file}")
                        break  # Use first found config file in this directory
                    except ConfigurationError as e:
                        console.print(f"[yellow]⚠[/yellow] Warning: {e}")
                        continue
        
        self.config_data = merged_config
        return merged_config
    
    def get_ansible_config_path(self) -> str:
        """
        Get the path to the Ansible configuration file.
        
        Returns:
            Path to ansible.cfg as string
            
        Raises:
            ConfigurationError: If no ansible.cfg is found
        """
        ansible_cfg = self.find_ansible_config()
        if ansible_cfg:
            return str(ansible_cfg)

        raise ConfigurationError("No ansible.cfg found")
    
    def setup_ansible_environment(self) -> None:
        """
        Set up the ANSIBLE_CONFIG environment variable.
        """
        ansible_cfg = self.find_ansible_config()
        if not ansible_cfg:
            return

        os.environ["ANSIBLE_CONFIG"] = str(ansible_cfg)
        console.print(f"[green]✓[/green] Set ANSIBLE_CONFIG to: {ansible_cfg}")
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key with dot notation support.
        
        Args:
            key: Configuration key (supports dot notation like 'database.host')
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config_data
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def validate_configuration(self) -> List[str]:
        """
        Validate the loaded configuration and return any issues found.
        
        Returns:
            List of validation error messages
        """
        issues = []
        
        # Check if any configuration was loaded
        if not self.config_data and not self.config_sources:
            issues.append("No configuration files found in any search path")
        
        return issues
    
    def print_configuration_info(self) -> None:
        """
        Print information about the loaded configuration for debugging.
        """
        console.print("\n[bold]Configuration Information:[/bold]")
        console.print(f"Search paths (in precedence order):")
        for i, path in enumerate(self.get_config_search_paths(), 1):
            exists = "✓" if path.exists() else "✗"
            console.print(f"  {i}. [{exists}] {path}")
        
        console.print(f"\nLoaded configuration sources:")
        if self.config_sources:
            for source in self.config_sources:
                console.print(f"  • {source}")
        else:
            console.print("  [yellow]No configuration files loaded[/yellow]")
        
        # Validate and show any issues
        issues = self.validate_configuration()
        if issues:
            console.print(f"\n[red]Configuration Issues:[/red]")
            for issue in issues:
                console.print(f"  • {issue}")
        else:
            console.print(f"\n[green]✓ Configuration validation passed[/green]")


# Global configuration manager instance
config_manager = ConfigManager()


def initialize_configuration() -> ConfigManager:
    """
    Initialize the global configuration manager.
    
    Returns:
        Configured ConfigManager instance
    """
    try:
        load_dotenv()
        config_manager.load_configuration()
        config_manager.setup_ansible_environment()
        return config_manager
    except Exception as e:
        console.print(f"[red]✗[/red] Configuration initialization failed: {e}")
        return config_manager


def get_config() -> ConfigManager:
    """
    Get the global configuration manager instance.
    
    Returns:
        ConfigManager instance
    """
    return config_manager
