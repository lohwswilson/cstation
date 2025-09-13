#!/usr/bin/env python3
"""
List profiles command for server management
"""

import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
import yaml
import subprocess
import tempfile
import os

console = Console()



def generate_playbook_from_profile(profile_config: dict, hostname: str) -> str:
    """
    Generate Ansible playbook content from server profile configuration.
    """
    playbook = {
        'name': f'Deploy server configuration to {hostname}',
        'hosts': hostname,
        'become': True,
        'gather_facts': True,
        'tasks': []
    }
    
    # Add package installation tasks
    packages = profile_config.get('packages', [])
    if packages:
        package_names = []
        for pkg in packages:
            if isinstance(pkg, dict):
                package_names.append(pkg.get('name'))
            else:
                package_names.append(str(pkg))
        
        playbook['tasks'].append({
            'name': 'Install required packages',
            'apt': {
                'name': package_names,
                'state': 'present',
                'update_cache': True
            }
        })
    
    # Add service management tasks
    services = profile_config.get('services', [])
    for service in services:
        if isinstance(service, dict):
            service_name = service.get('name')
            enabled = service.get('enabled', True)
            state = service.get('state', 'started')
            
            playbook['tasks'].append({
                'name': f'Manage {service_name} service',
                'systemd': {
                    'name': service_name,
                    'enabled': enabled,
                    'state': state
                }
            })
    
    # Add configuration file tasks
    configurations = profile_config.get('configurations', [])
    for config in configurations:
        if isinstance(config, dict):
            src = config.get('src')
            dest = config.get('dest')
            
            if src and dest:
                playbook['tasks'].append({
                    'name': f'Deploy configuration file {dest}',
                    'template': {
                        'src': f'/etc/cstation/ansible/templates/{src}',
                        'dest': dest,
                        'backup': True
                    },
                    'notify': ['restart docker'] if 'docker' in dest else []
                })
    
    # Add environment variables
    env_vars = profile_config.get('environment_variables', {})
    if env_vars:
        env_content = '\n'.join([f'{key}={value}' for key, value in env_vars.items()])
        playbook['tasks'].append({
            'name': 'Set environment variables',
            'blockinfile': {
                'path': '/etc/environment',
                'block': env_content,
                'marker': '# {mark} CSTATION MANAGED BLOCK'
            }
        })
    
    # Add post-install tasks
    post_tasks = profile_config.get('post_install_tasks', [])
    for task in post_tasks:
        if isinstance(task, dict):
            playbook['tasks'].append(task)
    
    # Add handlers
    handlers = profile_config.get('handlers', [])
    if handlers:
        playbook['handlers'] = handlers
    
    # Convert to YAML
    import yaml
    return yaml.dump([playbook], default_flow_style=False, sort_keys=False)