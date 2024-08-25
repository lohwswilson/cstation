#!/usr/bin/env python

import click
import os


@click.group("perfectwork6")
@click.pass_context
def perfectwork6(ctx):
    """
    \b
    Control Station
    Setting Up PerfectWORK => 6.0 Repositories
    """
    pass


@perfectwork6.command(
    "server", short_help="Configure PerfectWORK => 6.0 for Remote Server"
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
    Setting PerfectWORK for Remote Server Operations

    \b
    <host>: Full host name of the server
    \b
    sg01.synercatalyst.com
    sg01.ansis.com.sg
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
            f'rsync -avzhe "ssh -p{ssh_port}" --copy-links --delete --exclude  ".*" --exclude "__pycache__"  /opt/PW/PW_ADDONS.{version}/ root@{host}:/var/lib/perfectwork/PW_ADDONS.{version}'
        )
    else:
        # No Need to prepare directory for sending the files to Remote Host
        click.echo(
            f"Preparing PerfectWORK Core Modules {version} To -> {host} using Port {ssh_port}"
        )
        os.system(
            f"rm -rf ./PW.{version}"
        )
        os.system(
            f"rsync -avzhe --delete --exclude  '.*' /opt/PW/PW.{version}/  ./PW.{version}"
        )
        os.system(
            f"mv ./PW.{version}/odoo/addons/* ./PW.{version}/addons/"
        )
        os.system(
            f"rm -rf ./PW.{version}/odoo/addons"
        )
        os.system(
            f"mv ./PW.{version}/addons ./PW.{version}/odoo/"
        )
        os.system(
            "find ./ -name __pycache__ -type d -exec rm -rf {} + "
        )
        click.echo(
            f"Deploy PerfectWORK Version {version} To -> {host} using Port {ssh_port}"
        )
        os.system(
            f"rsync -avzhe 'ssh -p{ssh_port}'  --delete --exclude  '.*'  ./PW.{version}/odoo/ root@{host}.synercatalyst.com:/var/lib/perfectwork/PW.{version}"
        )
        os.system(
            f"rm -rf ./PW.{version}"
        )
        click.echo(
            f"Deploy PerfectWORK Addons Modules {version} To -> {host} using Port {ssh_port}"
        )
        os.system(
            f'rsync -avzhe "ssh -p{ssh_port}" --copy-links --delete --exclude  ".*" --exclude "__pycache__"  /opt/PW/PW_ADDONS.{version}/ root@{host}.synercatalyst.com:/var/lib/perfectwork/PW_ADDONS.{version}'
        )

@perfectwork6.command(
    "local", short_help="Configure PerfectWORK for Local Development Operations"
)
@click.argument("version", metavar="<version>", type=click.STRING)
@click.option(
    "-a",
    "--with_addons",
    default=False,
    is_flag=True,
    show_default=True,
    help="Inclusive Addons Modules [PW_ADDONS]",
)
@click.pass_context
def local(ctx, version, with_addons):
    """
    Setting Odoo for Localhost Operations

    \b
    <version>: Odoo version => 6.0
    \b
        16.0   : Version 16.0
        17.0   : Version 17.0

    """

    click.echo(f"Preparing PerfectWORK Version {version} for Local Development")
    os.chdir("/opt/PW/odoo")
    os.system(f"git switch {version}")
    os.system(
        f"rsync -avzhe --delete --exclude '.*' --exclude '__pycache__' /opt/PW/odoo/* /opt/PW/Odoo.{version}"
    )
