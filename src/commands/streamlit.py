#!/usr/bin/env python

import sys
import click
import os

@click.group('')
@click.pass_context
def streamlit(ctx):
    """
    \b
    Control Station
    Setting Up Streamlit Repositories
    """
    pass


@streamlit.command('server', short_help='Configure Streamlit for Remote Server')
@click.argument('host', metavar="<host>", type=click.STRING)
@click.option('-p', '--ssh_port', metavar="<ssh_port>", default="8288", show_default=True, help='SSH Port')
@click.pass_context
def server(ctx, host, ssh_port):
    """
        Setting Up Streamlit for Remote Server Operations
        
        \b
        <host>: Hostname in the Inventory List or local
        \b
    """
    
    click.echo(f'Preparing Streamlit - Deploy To -> {host} using Port {ssh_port}')
    # Sync the addon directory

    # Need to prepare directory for sending the files to Remote Host
    click.echo(f'Deploy Streamlit Core Modules to -> {host} using Port {ssh_port}')
    os.system(f'rsync -avzhe "ssh -p{ssh_port}"  --delete --exclude  ".*" --exclude "node_modules"  /opt/LLM/streamlit/* root@{host}.synercatalyst.com:/var/lib/streamlit')
