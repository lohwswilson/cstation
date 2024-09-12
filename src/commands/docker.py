#!/usr/bin/env python
import click
import os

from auto_click_auto import enable_click_shell_completion
from auto_click_auto.constants import ShellType

@click.group()
@click.pass_context
def docker(ctx):
    """
    \b
    Docker Container Operations and Deployments
    """
    pass


@docker.command('server', short_help='Deploy Docker Container to Server')
@click.argument('host', metavar="<host>", type=click.STRING)
@click.argument('application', metavar="<application>", type=click.STRING)
@click.option('-f', '--docker_config', metavar="<file>", help='docker Configuration File [US01_SYNER_US01DB]')
@click.pass_context
def deploy(ctx, host, application, docker_config):
    """
        Deploy Docker Container to Server
        
        \b
        <host>: sg01 --> sg01.synercatalyst.com
        \b
        <application>: Application for docker
        \b
            portainer    : Portainer Application
            traefik      : Traefik Reversed Proxy
            postgresql   : PostgreSQL Database 
            odoo         : Odoo >= 16.0
            perfectwork  : PerfectWORK 3.0 - 5.0
            perfectwork_dns : Multiple domains/databases PerfectWORK
            perfectwork6_dns : Multiple domains/databases PerfectWORK
    """

    if docker_config is None:
        os.system(f"ansible-playbook -l {host} /opt/cstation/ansible_playbook/docker/{application}.yaml")
    else:
        os.system(f"ansible-playbook -l {host} /opt/cstation/ansible_playbook/docker/{application}.yaml --extra-vars @/opt/cstation/config_file/{host}/{docker_config}.yaml")