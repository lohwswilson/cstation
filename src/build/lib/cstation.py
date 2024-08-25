import click

from commands import odoo
from commands import container
from commands import github
from commands import perfectwork
from commands import perfectwork6

@click.group()
@click.pass_context
@click.version_option("0.1.4", prog_name="cstation Control Station")

# @click.pass_context
def cli(ctx):
    """
    \b
    Control Station
    A wrapper around ansible for Deployment
    """
    pass

cli.add_command(odoo.odoo)
cli.add_command(container.container)
cli.add_command(perfectwork.perfectwork)
cli.add_command(perfectwork6.perfectwork6)
cli.add_command(github.github)

if __name__ == "__main__":
    cli()
