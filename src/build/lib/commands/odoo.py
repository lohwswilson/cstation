#!/usr/bin/env python

import click
import os


@click.group("odoo")
@click.pass_context
def odoo(ctx):
    """
    \b
    Control Station
    Setting Up Odoo 16 or above Repositories
    """
    pass


@odoo.command(
    "server", short_help="Configure Odoo version => 16.0 for Remote Server",  no_args_is_help=True
)
@click.argument("host", metavar="<host>", type=click.STRING)
@click.argument("version", metavar="<version>", type=click.STRING)
@click.option(
    "-p",
    "--ssh_port",
    metavar="<ssh_port>",
    default="8288",
    show_default=True,
    help="SSH Port",
)
@click.option(
    "-oa",
    "--only_addons",
    default=False,
    is_flag=True,
    show_default=True,
    help="Only Sync Addons Modules [PW_ADDONS_X.0]",
)
@click.pass_context
def server(ctx, host, version, ssh_port, only_addons):
    """
    Setting Odoo for Remote Server Operations

    \b
    <host>: Hostname in the Inventory List or local
    \b
    <version>: Odoo version => 16.0
    \b
        16.0   : Version 16.0
        17.0   : Version 17.0
    \b
    """

    click.echo(
        f"Preparing PerfectWORK Version {version} - Deploy To -> {host} using Port {ssh_port}"
    )
    # Sync the addon directory
    if only_addons:
        click.echo(
            f"Deploy PerfectWORK Addons Modules {version} To -> {host} using Port {ssh_port}"
        )
        os.system(
            f'rsync -avzhe "ssh -p{ssh_port}" --copy-links --delete --exclude  ".*" --exclude "__pycache__"  /opt/PW/Addons.{version}/ root@{host}.synercatalyst.com:/var/lib/odoo/Addons.{version}'
        )
    else:
        # No Need to prepare directory for sending the files to Remote Host
        click.echo(
            f"Preparing PerfectWORK Core Modules {version} To -> {host} using Port {ssh_port}"
        )
        os.system(
            f"rm -rf ./Odoo.{version}"
        )
        os.system(
            f"rsync -avzhe --delete --exclude  '.*' /opt/PW/Odoo.{version}/  ./Odoo.{version}"
        )
        os.system(
            f"mv ./Odoo.{version}/odoo/addons/* ./Odoo.{version}/addons/"
        )
        os.system(
            f"rm -rf ./Odoo.{version}/odoo/addons"
        )
        os.system(
            f"mv ./Odoo.{version}/addons ./Odoo.{version}/odoo/"
        )
        os.system(
            "find ./ -name __pycache__ -type d -exec rm -rf {} + "
        )
        click.echo(
            f"Deploy PerfectWORK Version {version} To -> {host} using Port {ssh_port}"
        )
        os.system(
            f"rsync -avzhe 'ssh -p{ssh_port}'  --delete --exclude  '.*'  ./Odoo.{version}/odoo/ root@{host}.synercatalyst.com:/var/lib/odoo/Odoo.{version}"
        )
        os.system(
            f"rm -rf ./Odoo.{version}"
        )
        click.echo(
            f"Deploy PerfectWORK Addons Modules {version} To -> {host} using Port {ssh_port}"
        )
        os.system(
            f'rsync -avzhe "ssh -p{ssh_port}" --copy-links --delete --exclude  ".*" --exclude "__pycache__"  /opt/PW/PW_ADDONS.{version}/ root@{host}.synercatalyst.com:/var/lib/perfectwork/PW_ADDONS.{version}'
        )

@odoo.command(
    "local", short_help="Configure Odoo for Local Host Development Operations", no_args_is_help=True
)
@click.argument("version", metavar="<version>", type=click.STRING)
@click.option(
    "-oa",
    "--only_addons",
    default=False,
    is_flag=True,
    show_default=True,
    help="Prepare Addons Modules Only for [ADDONS.X.0]",
)
@click.pass_context
def local(ctx, version, only_addons):
    """
    Setting Odoo for Localhost Operations

    \b
    <version>: Odoo version => 16.0
    \b
        16.0   : Odoo 16.0
        17.0   : Odoo 17.0

    """
    if not only_addons:
        click.echo(f"Preparing Odoo Version {version} for Local Development")
        os.chdir("/opt/PW/odoo")
        os.system(f"git switch {version}")
        os.system(
            f"rsync -avzhe --delete --exclude '.*' --exclude '__pycache__' --exclude 'odoo.conf' /opt/PW/odoo/* /opt/PW/Odoo.{version}"
        )

    # Open the file in read mode
    with open(f'/opt/PW/Addons.{version}/odoo_addons_github.yaml', 'r') as file:
        lines = file.readlines()

    # # Print the lines
    for line in lines:
        parts = line.split("/",1)
        app_name = parts[1].split(".")[0]
        os.system(f'rm -rf /opt/PW/Addons.{version}/{app_name}')
        print(f'git clone {line.strip()} --single-branch --branch {version} - {app_name}')
        os.system(f'git clone {line.strip()} --single-branch --branch {version} /opt/PW/Addons.{version}/{app_name} ')
    
    # Download modules from OCA Repositories
    os.system(
        f"gitoo install-all --conf_file /opt/PW/Addons.{version}/odoo_addons_oca.yaml --destination /opt/PW/Addons.{version}"
    )