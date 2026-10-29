"""
State command module for CStation CLI
"""
from __future__ import annotations

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from cstation.output import OutputFormat, print_formatted
from cstation.state import get_audit_logs, get_vps_metrics_history

console = Console()

state_app = typer.Typer(
    name="state",
    help="Inspect runtime state, audit logs, and metrics history (SQLite)",
    invoke_without_command=True,
)


@state_app.command("audit")
def state_audit(
    limit: int = typer.Option(30, "--limit", "-n", help="Number of recent audit entries to retrieve"),
    command_filter: Optional[str] = typer.Option(None, "--command", "-c", help="Filter by command name"),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format: table, json, or yaml",
    ),
) -> None:
    """View recent operational audit logs recorded by CStation."""
    logs = get_audit_logs(limit=limit, command_filter=command_filter)

    def render_table():
        if not logs:
            console.print("[dim]No audit log entries found.[/dim]")
            return

        table = Table(title="CStation Operational Audit Log", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="dim", width=6)
        table.add_column("Timestamp", width=22)
        table.add_column("Command", style="bold white")
        table.add_column("Target", style="cyan")
        table.add_column("Status")
        table.add_column("Duration", justify="right")
        table.add_column("Message", style="dim")

        for r in logs:
            status_style = "[green]success[/green]" if r["status"] == "success" else f"[red]{r['status']}[/red]"
            dur_str = f"{r['duration_ms']}ms" if r["duration_ms"] else "-"
            table.add_row(
                str(r["id"]),
                r["timestamp"][:19].replace("T", " "),
                r["command"],
                r["target"] or "-",
                status_style,
                dur_str,
                r["message"] or "",
            )
        console.print(table)

    print_formatted(logs, format_type=output, table_renderer=render_table)


@state_app.command("history")
def state_history(
    vps: str = typer.Argument(..., help="VPS name to query metrics history for"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of recent records to retrieve"),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format: table, json, or yaml",
    ),
) -> None:
    """View historical resource metrics snapshots for a specific VPS."""
    records = get_vps_metrics_history(vps, limit=limit)

    def render_table():
        if not records:
            console.print(f"[dim]No metrics history recorded for {vps}.[/dim]")
            return

        table = Table(title=f"Resource Metrics History: {vps}", show_header=True, header_style="bold cyan")
        table.add_column("Timestamp", width=20)
        table.add_column("Load Avg", width=18)
        table.add_column("Memory", justify="right")
        table.add_column("Disk", justify="right")
        table.add_column("Containers", justify="center")

        for r in records:
            mem_pct = f"{r['memory_pct']}%" if r["memory_pct"] is not None else "-"
            mem_str = f"{r['memory_used_mb']}/{r['memory_total_mb']}MB ({mem_pct})" if r["memory_used_mb"] else "-"
            disk_str = f"{r['disk_pct']}%" if r["disk_pct"] is not None else "-"
            docker_str = f"{r['docker_running']}/{r['docker_total']}" if r["docker_running"] is not None else "-"

            table.add_row(
                r["timestamp"][:19].replace("T", " "),
                r["load_avg"] or "-",
                mem_str,
                disk_str,
                docker_str,
            )
        console.print(table)

    print_formatted(records, format_type=output, table_renderer=render_table)


@state_app.callback()
def state_callback(ctx: typer.Context) -> None:
    """Inspect runtime state, audit logs, and metrics history (SQLite)."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
