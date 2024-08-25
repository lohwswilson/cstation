#!/usr/bin/env python

import click
import os

@click.group('')
@click.pass_context
def github(ctx):
    """
    \b
    Control Station - Managing GITHUB Account
    """
    pass


@github.command('oca_rebuild', short_help='Rebuild OCA modules from github')
@click.argument("version", metavar="<version>", type=click.STRING)
# @click.option('oca_filename', metavar="<oca_filename>", type=click.Path(exists=True))
@click.pass_context
def oca_rebuild(ctx, version):
    """
        Rebuild OCA modules from github

        \b
        <version>: Odoo version => 7.0
        \b
            6.0   : Version 16.0
            7.0   : Version 17.0
        \b        
        \b
        oca_addons.yaml in /opt/PW/PW_ADDONS.{version}/OCA directory
        \b
        File containing list of OCA repositories to build
        \b   
    """
    # Open the file in read mode
    os.system(f'gitoo install-all --conf_file /opt/PW/PW_ADDONS.{version}/OCA/oca_addons.yaml --destination /opt/PW/PW_ADDONS.{version}/OCA')
    


@github.command('repo_sync', short_help='Syncing repositories with upstream')
@click.argument('repo_filename', metavar="<repo_filename>", default='/opt/cstation/etc/github_repo.yaml', type=click.Path(exists=True))
# @click.option('-s', '--sync', is_flag=True, show_default=False, help='Syncing repositories with upstream')
@click.pass_context
def repo_sync(ctx, repo_filename):
    """
        Syncing repositories with upstream
        
        \b
        <repo_filename> : File containing list of repositories to sync
        Default File : /opt/cstation/etc/github_repo.yaml
        \b   
    """
    # Open the file in read mode
    with open(repo_filename, 'r') as file:
        lines = file.readlines()

    # # Print the lines
    for line in lines:
        if line.strip() != "":
            print(f'gh repo sync {line.strip()}')
            os.system(f'gh repo sync {line.strip()}')

    # Need to prepare directory for sending the files to Remote Host
    # click.echo (f'Deploy Streamlit Core Modules to -> {host} using Port {ssh_port}')
    # os.system(f'rsync -avzhe "ssh -p{ssh_port}"  --delete --exclude  ".*" --exclude "node_modules"  /opt/LLM/streamlit/* root@{host}.synercatalyst.com:/var/lib/streamlit
    # Need to prepare directory for sending the files to Remote Host
    # click.echo (f'Deploy Streamlit Core Modules to -> {host} using Port {ssh_port}')
    # os.system(f'rsync -avzhe "ssh -p{ssh_port}"  --delete --exclude  ".*" --exclude "node_modules"  /opt/LLM/streamlit/* root@{host}.synercatalyst.com:/var/lib/streamlit')
