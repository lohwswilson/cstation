"""
Completion command module for CStation CLI.
Generates and installs shell auto-completions for bash, zsh, fish, and powershell.
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console

console = Console()

completion_app = typer.Typer(
    name="completion",
    help="Shell auto-completion utilities (bash, zsh, fish)",
)

ZSH_SNIPPET = """# CStation zsh completion
autoload -Uz compinit
compinit
eval "$(_CSTATION_COMPLETE=zsh_source cstation)"
"""

BASH_SNIPPET = """# CStation bash completion
eval "$(_CSTATION_COMPLETE=bash_source cstation)"
"""

FISH_SNIPPET = """# CStation fish completion
eval (env _CSTATION_COMPLETE=fish_source cstation)
"""


@completion_app.command(name="show")
def show_completion(
    shell: str = typer.Argument("zsh", help="Shell type: zsh, bash, or fish"),
) -> None:
    """
    Print the shell auto-completion hook script to stdout.
    """
    shell = shell.lower()
    if shell == "zsh":
        print(ZSH_SNIPPET.strip())
    elif shell == "bash":
        print(BASH_SNIPPET.strip())
    elif shell == "fish":
        print(FISH_SNIPPET.strip())
    else:
        console.print(f"[red]Unsupported shell '{shell}'. Supported shells: zsh, bash, fish[/red]")
        raise typer.Exit(code=1)


@completion_app.command(name="install")
def install_completion(
    shell: Optional[str] = typer.Option(None, "--shell", "-s", help="Target shell: zsh, bash, or fish (auto-detected if omitted)"),
) -> None:
    """
    Install auto-completion script into your user shell configuration.
    """
    detected_shell = shell
    if not detected_shell:
        shell_env = os.environ.get("SHELL", "")
        if "zsh" in shell_env:
            detected_shell = "zsh"
        elif "bash" in shell_env:
            detected_shell = "bash"
        elif "fish" in shell_env:
            detected_shell = "fish"
        else:
            detected_shell = "zsh"

    home = Path.home()
    if detected_shell == "zsh":
        rc_file = home / ".zshrc"
        snippet = f"\n{ZSH_SNIPPET}"
    elif detected_shell == "bash":
        rc_file = home / ".bashrc" if (home / ".bashrc").exists() else home / ".bash_profile"
        snippet = f"\n{BASH_SNIPPET}"
    elif detected_shell == "fish":
        rc_file = home / ".config" / "fish" / "completions" / "cstation.fish"
        rc_file.parent.mkdir(parents=True, exist_ok=True)
        snippet = FISH_SNIPPET
    else:
        console.print(f"[red]Unsupported shell: {detected_shell}[/red]")
        raise typer.Exit(code=1)

    if rc_file.exists() and "_CSTATION_COMPLETE=" in rc_file.read_text(encoding="utf-8"):
        console.print(f"[yellow]Auto-completion is already configured in {rc_file}[/yellow]")
        return

    try:
        with open(rc_file, "a", encoding="utf-8") as f:
            f.write(snippet)
        console.print(f"[bold green]✓ Shell auto-completion installed for {detected_shell} in {rc_file}![/bold green]")
        console.print("[dim]Restart your terminal or run `source " + str(rc_file) + "` to activate.[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to write completion snippet to {rc_file}: {e}[/red]")
        raise typer.Exit(code=1)
