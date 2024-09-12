#!/usr/bin/env python

import click
import os

@click.group('')
@click.pass_context
def server(ctx):
    """
    \b
    Setting Up Remote Virtual Server
    """
    pass


@server.command('copy_ssh_key', short_help='Setup SSH Key for Remote Login ')
@click.argument("ssh_login", metavar="<ssh login>", type=click.STRING)
@click.option(
    "-p",
    "--ssh_port",
    metavar="<ssh_port>",
    default="22",
    show_default=True,
    help="SSH Port",
)
@click.pass_context
def copy_ssh_key(ctx, ssh_login, ssh_port):
    """
        Setup SSH Key for Remote Login

        \b
        <ssh login>: SSH Login for the remote host (root@sg08.synercatalyst.com)
        \b
        \b   
    """
    # Open the file in read mode
    os.system(f'ssh-copy-id -p {ssh_port} {ssh_login}')
    #

@server.command('server_setup', short_help='Setup Remote Server for Production ')
@click.argument('host', metavar="<host>", type=click.STRING)
@click.pass_context
def server_setup(ctx, host):
    """
       Setup Remote Server for Production

        \b
        <host>: sg01 --> sg01.synercatalyst.com
        \b
        \b   
    """
    # Open the file in read mode
    os.system(f"ansible-playbook -l {host} /opt/cstation/ansible_playbook/server/server_setup.yaml")
    #
