#!/usr/bin/env python
import click
import os

from auto_click_auto import enable_click_shell_completion
from auto_click_auto.constants import ShellType

@click.group()
@click.pass_context
def container(ctx):
    """
    \b
    Control Station
    Docker Container Operations and Deployments
    """
    pass


@container.command('deploy', short_help='Deploy Docker Container to Server')
@click.argument('host', metavar="<host>", type=click.STRING)
@click.argument('application', metavar="<application>", type=click.STRING)
@click.option('-f', '--container_config', metavar="<file>", help='Container Configuration File [US01_SYNER_US01DB]')
@click.pass_context
def deploy(ctx, host, application, container_config):
    """
        Deploy Docker Container to Server
        
        \b
        <host>: Hostname in the Inventory List
        \b
        <application>: Application for Container
        \b
            portainer    : Portainer Application
            traefik      : Traefik Reversed Proxy
            perfectwork  : PerfectWORK 3.0 - 5.0
            perfectwork_dns : Multiple domains/databases PerfectWORK
            perfectwork6 : PerfectWORK >= 6.0
            perfectwork6_dns : Multiple domains/databases PerfectWORK
    """

    if container_config is None:
        os.system(f"ansible-playbook -l {host} /opt/SysOps/ansible/container/{application}.yaml")
    else:
        os.system(f"ansible-playbook -l {host} /opt/SysOps/ansible/container/{application}.yaml --extra-vars @/opt/SysOps/config_file/{host}/{container_config}.yaml")