import typer
from .commands.vps.main import app as vps_app
from .commands.stack.main import app as stack_app
from .commands.code.main import app as code_app
from .commands.config.main import app as config_app

app = typer.Typer(
    name="cstation-cli",
    help="Modern Infrastructure Management CLI (No-Ansible)",
    add_completion=False,
)

# Add subcommands
app.add_typer(vps_app, name="vps")
app.add_typer(stack_app, name="stack")
app.add_typer(code_app, name="code")
app.add_typer(config_app, name="config")

@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Modern Infrastructure Management CLI (No-Ansible)"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

def main():
    app()

if __name__ == "__main__":
    main()
