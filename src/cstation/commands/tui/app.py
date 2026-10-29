"""
CStation TUI Dashboard App powered by Textual.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Callable

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    ListItem,
    ListView,
    RichLog,
    Static,
)

from cstation.config import CSTATION_VPS_DIR
from cstation.commands.vps.main import (
    _load_vps_config,
    _remove_vps_secrets,
    _resolve_vps_dir,
    _ssh_from_config,
)
from cstation.commands.docker.main import _get_service_instance, _load_fragments
from cstation.facts import format_facts_summary, load_cached_facts
from cstation.state import record_audit


def resolve_command_execution(cmd_text: str, vps_name: str | None) -> tuple[str, str]:
    """
    Determine whether to execute via SSH on the active server or locally via CStation CLI.
    Returns (mode, resolved_cmd) where mode is "ssh" or "local".
    """
    cmd_text = cmd_text.strip()
    if not cmd_text:
        return ("none", "")

    # 1. Explicit local escape hatch
    if cmd_text.startswith("local "):
        return ("local", cmd_text[6:].strip())

    # 2. Global CStation commands (run locally on workstation)
    global_cstation_cmds = (
        "lint",
        "cstation lint",
        "config",
        "cstation config",
        "dns",
        "cstation dns",
        "state audit",
        "cstation state audit",
        "completion",
        "cstation completion",
        "version",
        "cstation version",
    )
    if any(cmd_text == c or cmd_text.startswith(c + " ") for c in global_cstation_cmds):
        clean_cmd = cmd_text[9:].strip() if cmd_text.startswith("cstation ") else cmd_text
        return ("local", clean_cmd)

    # 3. Server-targeted CStation commands (auto-target active VPS if server name not specified)
    server_cstation_verbs = (
        "docker apply", "docker plan", "docker status", "docker import",
        "vps apply", "vps plan", "vps status",
        "odoo backup", "odoo restore", "odoo sanitize", "odoo sync",
        "hindsight backup", "hindsight status",
    )
    matched_verb = None
    for verb in server_cstation_verbs:
        if (
            cmd_text == verb
            or cmd_text.startswith(verb + " ")
            or cmd_text == f"cstation {verb}"
            or cmd_text.startswith(f"cstation {verb} ")
        ):
            matched_verb = verb
            break

    if matched_verb and vps_name:
        tokens = cmd_text.split()
        verb_tokens = matched_verb.split()
        after_tokens = []
        for i in range(len(tokens)):
            if tokens[i : i + len(verb_tokens)] == verb_tokens:
                after_tokens = tokens[i + len(verb_tokens) :]
                break

        has_server_target = any(not t.startswith("-") for t in after_tokens)
        if not has_server_target:
            if matched_verb == "vps apply" and "--yes" not in after_tokens and "-y" not in after_tokens:
                after_tokens.append("--yes")
            injected_cmd = f"{matched_verb} {vps_name} {' '.join(after_tokens)}".strip()
        else:
            injected_cmd = cmd_text[9:].strip() if cmd_text.startswith("cstation ") else cmd_text

        return ("local", injected_cmd)

    # 4. Default: All other shell commands execute directly on the active VPS via SSH!
    if vps_name:
        return ("ssh", cmd_text)

    # 5. If no VPS selected, fall back to local CStation CLI execution
    return ("local", cmd_text)


class CStationCommandProvider(Provider):
    """Command palette provider for CStation TUI."""

    async def discover(self) -> Hits:
        app = self.app
        if not isinstance(app, CStationApp):
            return
        for title, help_text, handler in app.get_palette_commands():
            yield DiscoveryHit(display=title, command=handler, help=help_text)

    async def search(self, query: str) -> Hits:
        app = self.app
        if not isinstance(app, CStationApp):
            return
        matcher = self.matcher(query)
        for title, help_text, handler in app.get_palette_commands():
            score = matcher.match(title)
            if score > 0:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(title),
                    command=handler,
                    help=help_text,
                )


class ServerItem(ListItem):
    """A list item representing a managed VPS server."""

    def __init__(self, vps_name: str, host: str, metrics: str, is_active: bool = True) -> None:
        super().__init__()
        self.vps_name = vps_name
        self.host = host
        self.metrics = metrics
        self.is_active = is_active

    def compose(self) -> ComposeResult:
        status_dot = "[bold green]●[/bold green]" if self.is_active else "[bold red]○[/bold red]"
        yield Static(f"{status_dot} [bold white]{self.vps_name}[/bold white]")
        yield Static(f"  [dim cyan]{self.host}[/dim cyan]")
        if self.metrics:
            yield Static(f"  [dim]{self.metrics}[/dim]")
        else:
            yield Static("  [dim]-[/dim]")


class CStationApp(App):
    """Interactive TUI Dashboard for CStation."""

    TITLE = "CStation Infrastructure Dashboard"
    SUB_TITLE = "Press Ctrl+P for Commands, ':' to run CLI"

    COMMANDS = App.COMMANDS | {CStationCommandProvider}

    CSS = """
    Screen {
        background: #0d1117;
        color: #c9d1d9;
    }

    Header {
        background: #161b22;
        color: #58a6ff;
    }

    Footer {
        background: #161b22;
        color: #8b949e;
    }

    #left-pane {
        width: 38;
        border-right: solid #30363d;
        background: #161b22;
        padding: 0 1;
    }

    #right-pane {
        width: 1fr;
        padding: 0 1;
    }

    .panel-title {
        background: #21262d;
        color: #79c0ff;
        text-style: bold;
        padding: 0 1;
        margin: 1 0 0 0;
        height: 1;
    }

    #vps-list {
        background: transparent;
        border: none;
        height: 1fr;
    }

    ServerItem {
        padding: 1 1;
        border-bottom: solid #21262d;
        background: transparent;
    }

    ServerItem:hover {
        background: #21262d;
    }

    ServerItem.-selected {
        background: #1f6feb;
        color: #ffffff;
    }

    #container-table {
        height: 12;
        background: #0d1117;
        border: solid #30363d;
        margin-bottom: 1;
    }

    #log-pane {
        height: 1fr;
        background: #090d13;
        border: solid #30363d;
        color: #8b949e;
        padding: 0 1;
    }

    #cmd-bar {
        background: #161b22;
        border: solid #1f6feb;
        color: #58a6ff;
        margin-top: 1;
        display: none;
    }
    """

    BINDINGS = [
        ("ctrl+p", "command_palette", "Commands"),
        ("colon", "open_cmd_bar", "Run (:)"),
        ("u", "server_uptime", "Uptime"),
        ("s", "server_ssh", "SSH"),
        ("p", "plan_docker", "Plan"),
        ("r", "refresh_fleet", "Refresh"),
        ("l", "lint_fleet", "Lint"),
        ("c", "clear_logs", "Clear"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected_vps: str | None = None
        self.vps_list: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="left-pane"):
                yield Static(" 🌐 SERVERS (Fleet)", classes="panel-title")
                yield ListView(id="vps-list")
            with Vertical(id="right-pane"):
                yield Static(" 🐳 CONTAINERS", id="container-title", classes="panel-title")
                yield DataTable(id="container-table")
                yield Static(" 📋 EXECUTION LOGS", classes="panel-title")
                yield RichLog(id="log-pane", highlight=True, markup=True, wrap=True)
                yield Input(
                    id="cmd-bar",
                    placeholder="cstation > Type CLI or server command (e.g. 'uptime', 'docker apply', 'vps apply', 'state audit') [Enter: run, Esc: close]",
                )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Service", "Kind", "Enabled", "Image")
        self.log_message("[bold green]✓ CStation TUI initialized.[/bold green]")
        self.log_message(
            "Press [bold cyan]Ctrl+P[/bold cyan] for Command Palette, [bold cyan]:[/bold cyan] to run CLI/remote commands, [bold cyan]s[/bold cyan] for SSH."
        )
        self.action_refresh_fleet()

    def action_open_cmd_bar(self) -> None:
        """Open inline command runner bar."""
        cmd_bar = self.query_one("#cmd-bar", Input)
        cmd_bar.display = True
        cmd_bar.focus()

    def on_key(self, event: events.Key) -> None:
        """Handle Escape to close command bar."""
        cmd_bar = self.query_one("#cmd-bar", Input)
        if cmd_bar.display and event.key == "escape":
            cmd_bar.value = ""
            cmd_bar.display = False
            self.query_one(ListView).focus()
            event.stop()

    @on(Input.Submitted, "#cmd-bar")
    def on_cmd_submitted(self, event: Input.Submitted) -> None:
        cmd_text = event.value.strip()
        cmd_bar = self.query_one("#cmd-bar", Input)
        cmd_bar.value = ""
        cmd_bar.display = False
        self.query_one(ListView).focus()

        if not cmd_text:
            return

        self.execute_cli_or_remote_command(cmd_text)

    def log_message(self, message: str) -> None:
        """Append a message to the execution log pane."""
        try:
            log_pane = self.query_one(RichLog)
            log_pane.write(message)
        except Exception:
            pass

    def action_clear_logs(self) -> None:
        """Clear execution log pane."""
        log_pane = self.query_one(RichLog)
        log_pane.clear()
        self.log_message("[dim]Logs cleared.[/dim]")

    def action_refresh_fleet(self) -> None:
        """Reload fleet data from local configs and cached facts."""
        self.load_servers_data()

    @work(thread=True)
    def load_servers_data(self) -> None:
        """Scan and populate VPS server list in background."""
        self.call_from_thread(self._populate_servers)

    def _populate_servers(self) -> None:
        vps_list_view = self.query_one(ListView)
        vps_list_view.clear()
        self.vps_list = []

        if not CSTATION_VPS_DIR.exists():
            self.log_message(f"[yellow]⚠ Config directory not found: {CSTATION_VPS_DIR}[/yellow]")
            return

        for p in sorted(CSTATION_VPS_DIR.iterdir()):
            if not p.is_dir() or p.name.startswith("."):
                continue
            if not (p / "vps.yaml").exists():
                continue

            try:
                vps_cfg = _load_vps_config(p)
                vps_name = vps_cfg.identity.name
                host = vps_cfg.access.host
                facts = load_cached_facts(p) or {}
                metrics = format_facts_summary(facts) or ""

                self.vps_list.append({
                    "name": vps_name,
                    "host": host,
                    "dir": p,
                    "metrics": metrics,
                    "facts": facts,
                })
                vps_list_view.append(ServerItem(vps_name, host, metrics))
            except Exception as e:
                self.log_message(f"[red]✗ Failed to load VPS {p.name}: {e}[/red]")

        if self.vps_list:
            self.log_message(f"[dim]Discovered {len(self.vps_list)} managed VPS instances in fleet.[/dim]")
            self._update_active_server_context(self.vps_list[0]["name"])

    def _update_active_server_context(self, vps_name: str) -> None:
        self.selected_vps = vps_name
        vps_dir = CSTATION_VPS_DIR / vps_name
        self._load_containers_for_vps(vps_name, vps_dir)
        try:
            cmd_bar = self.query_one("#cmd-bar", Input)
            cmd_bar.placeholder = f"[{vps_name}] SSH > Type command to run on this server (or 'cstation <cmd>', Esc to close)"
        except Exception:
            pass

    @on(ListView.Selected, "#vps-list")
    def on_server_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, ServerItem):
            self._update_active_server_context(event.item.vps_name)

    @on(ListView.Highlighted, "#vps-list")
    def on_server_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, ServerItem):
            self._update_active_server_context(event.item.vps_name)

    def _load_containers_for_vps(self, vps_name: str, vps_dir: Path) -> None:
        container_title = self.query_one("#container-title", Static)
        container_title.update(f" 🐳 CONTAINERS: [bold white]{vps_name}[/bold white]")

        table = self.query_one(DataTable)
        table.clear()

        try:
            fragments = _load_fragments(vps_dir)
            if not fragments:
                table.add_row("[dim]No containers declared[/dim]", "-", "-", "-")
                return

            for name, config, status in fragments:
                enabled_styled = "[green]enabled[/green]" if status == "enabled" else "[dim red]disabled[/dim red]"
                table.add_row(
                    f"[bold cyan]{name}[/bold cyan]",
                    config.kind,
                    enabled_styled,
                    config.image or "[dim]-[/dim]",
                )
        except Exception as e:
            self.log_message(f"[red]✗ Error loading containers for {vps_name}: {e}[/red]")

    @on(DataTable.RowSelected, "#container-table")
    def on_container_selected(self, event: DataTable.RowSelected) -> None:
        if not self.selected_vps:
            return
        row_key = event.row_key
        table = self.query_one(DataTable)
        row = table.get_row(row_key)
        if row and row[0]:
            service_name = str(row[0])
            clean_name = re.sub(r"\[.*?\]", "", service_name).strip()
            if clean_name and clean_name != "No containers declared":
                self.log_message(f"\n[cyan]▶ Selected container: {clean_name} on {self.selected_vps}[/cyan]")
                self.execute_docker_logs(self.selected_vps, clean_name)

    def action_server_uptime(self) -> None:
        """Run quick uptime & resource snapshot on currently highlighted server."""
        if not self.selected_vps:
            self.log_message("[yellow]⚠ No server selected.[/yellow]")
            return
        self.execute_server_uptime(self.selected_vps)

    @work(thread=True)
    def execute_server_uptime(self, vps_name: str) -> None:
        self.call_from_thread(self.log_message, f"\n[bold cyan]▶ Probing live uptime and health for {vps_name}...[/bold cyan]")
        try:
            vps_dir = _resolve_vps_dir(Path(vps_name))
            vps_data = _load_vps_config(vps_dir)
            ssh = _ssh_from_config(vps_data)

            res = ssh.run("uptime && echo '---' && free -h | grep -E 'Mem|Swap' && echo '---' && df -h / | tail -1", hide=True)
            if res and res.stdout:
                for line in res.stdout.strip().splitlines():
                    self.call_from_thread(self.log_message, f"  {line}")
            self.call_from_thread(self.log_message, f"[bold green]✓ Health check complete for {vps_name}[/bold green]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Failed to query health: {e}[/red]\n")

    def action_server_ssh(self) -> None:
        """Open direct interactive SSH shell using app.suspend()."""
        if not self.selected_vps:
            self.log_message("[yellow]⚠ No server selected for SSH.[/yellow]")
            return
        self.action_server_ssh_target(self.selected_vps)

    def action_server_ssh_target(self, vps_name: str) -> None:
        self.log_message(f"\n[bold cyan]Connecting to {vps_name} via SSH...[/bold cyan]")
        try:
            vps_dir = _resolve_vps_dir(Path(vps_name))
            vps_data = _load_vps_config(vps_dir)
            host = vps_data.access.host
            user = vps_data.access.user or "root"
            port = vps_data.access.port or 22
            key = vps_data.access.key

            ssh_cmd = ["ssh", "-p", str(port)]
            if key:
                expanded_key = os.path.expanduser(key)
                if os.path.exists(expanded_key):
                    ssh_cmd.extend(["-i", expanded_key])
            ssh_cmd.append(f"{user}@{host}")

            with self.suspend():
                subprocess.call(ssh_cmd)

            self.log_message(f"[bold green]✓ Returned from SSH session ({vps_name})[/bold green]\n")
        except Exception as e:
            self.log_message(f"[red]✗ SSH session failed: {e}[/red]\n")

    def action_plan_docker(self) -> None:
        """Run dry-run docker plan for currently selected VPS."""
        if not self.selected_vps:
            self.log_message("[yellow]⚠ No VPS selected to plan.[/yellow]")
            return
        self.execute_plan_for_vps(self.selected_vps)

    @work(thread=True)
    def execute_plan_for_vps(self, vps_name: str) -> None:
        self.call_from_thread(self.log_message, f"\n[bold cyan]▶ Running: cstation docker plan {vps_name}[/bold cyan]")
        try:
            vps_dir = _resolve_vps_dir(Path(vps_name))
            vps_data = _load_vps_config(vps_dir)
            ssh = _ssh_from_config(vps_data)
            fragments = _load_fragments(vps_dir)

            self.call_from_thread(self.log_message, f"  Connected via SSH ({vps_data.access.host})")
            for name, data, status in fragments:
                if status == "disabled":
                    self.call_from_thread(self.log_message, f"  [dim]- {name} ({data.kind}): disabled (skip)[/dim]")
                    continue
                svc = _get_service_instance(name, data.kind, data)
                res = svc.status(ssh, data)
                state = res.get("state", "unknown") if isinstance(res, dict) else str(res)
                self.call_from_thread(self.log_message, f"  [green]✓[/green] {name}: current state is [bold]{state}[/bold]")

            self.call_from_thread(self.log_message, f"[bold green]✓ Docker plan complete for {vps_name}[/bold green]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Plan failed: {e}[/red]\n")

    @work(thread=True)
    def execute_docker_apply(self, vps_name: str) -> None:
        self.call_from_thread(self.log_message, f"\n[bold cyan]▶ Running: cstation docker apply {vps_name}[/bold cyan]")
        try:
            proc = subprocess.Popen(
                ["cstation", "docker", "apply", vps_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if proc.stdout:
                for line in iter(proc.stdout.readline, ""):
                    cleaned = line.rstrip()
                    if cleaned:
                        self.call_from_thread(self.log_message, f"  {cleaned}")
                proc.stdout.close()
            code = proc.wait()
            if code == 0:
                self.call_from_thread(self.log_message, f"[bold green]✓ Docker apply succeeded for {vps_name}[/bold green]\n")
            else:
                self.call_from_thread(self.log_message, f"[bold red]✗ Docker apply exited with code {code}[/bold red]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Docker apply failed: {e}[/red]\n")

    @work(thread=True)
    def execute_vps_apply(self, vps_name: str) -> None:
        self.call_from_thread(self.log_message, f"\n[bold cyan]▶ Running: cstation vps apply {vps_name} --yes[/bold cyan]")
        try:
            proc = subprocess.Popen(
                ["cstation", "vps", "apply", vps_name, "--yes"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if proc.stdout:
                for line in iter(proc.stdout.readline, ""):
                    cleaned = line.rstrip()
                    if cleaned:
                        self.call_from_thread(self.log_message, f"  {cleaned}")
                proc.stdout.close()
            code = proc.wait()
            if code == 0:
                self.call_from_thread(self.log_message, f"[bold green]✓ VPS apply succeeded for {vps_name}[/bold green]\n")
            else:
                self.call_from_thread(self.log_message, f"[bold red]✗ VPS apply exited with code {code}[/bold red]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ VPS apply failed: {e}[/red]\n")

    @work(thread=True)
    def execute_docker_logs(self, vps_name: str, container_name: str) -> None:
        self.call_from_thread(self.log_message, f"\n[bold cyan]▶ Fetching logs: {container_name} on {vps_name}...[/bold cyan]")
        try:
            vps_dir = _resolve_vps_dir(Path(vps_name))
            vps_data = _load_vps_config(vps_dir)
            ssh = _ssh_from_config(vps_data)
            res = ssh.run(f"docker logs --tail 40 {container_name}", hide=True)
            out = (res.stdout + "\n" + res.stderr).strip() if res else ""
            if out:
                for line in out.splitlines():
                    self.call_from_thread(self.log_message, f"  {line}")
            else:
                self.call_from_thread(self.log_message, "  [dim](no log output)[/dim]")
            self.call_from_thread(self.log_message, f"[bold green]✓ Logs end for {container_name}[/bold green]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Failed to get logs: {e}[/red]\n")

    @work(thread=True)
    def execute_docker_restart(self, vps_name: str, container_name: str) -> None:
        self.call_from_thread(self.log_message, f"\n[bold yellow]▶ Restarting container {container_name} on {vps_name}...[/bold yellow]")
        try:
            vps_dir = _resolve_vps_dir(Path(vps_name))
            vps_data = _load_vps_config(vps_dir)
            ssh = _ssh_from_config(vps_data)
            res = ssh.run(f"docker restart {container_name}", hide=True)
            out = res.stdout.strip() if res else ""
            self.call_from_thread(self.log_message, f"  {out}")
            self.call_from_thread(self.log_message, f"[bold green]✓ Restarted {container_name}[/bold green]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Failed to restart: {e}[/red]\n")

    @work(thread=True)
    def execute_odoo_backup(self, vps_name: str) -> None:
        self.call_from_thread(self.log_message, f"\n[bold cyan]▶ Running: cstation odoo backup {vps_name}...[/bold cyan]")
        try:
            proc = subprocess.Popen(
                ["cstation", "odoo", "backup", vps_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if proc.stdout:
                for line in iter(proc.stdout.readline, ""):
                    cleaned = line.rstrip()
                    if cleaned:
                        self.call_from_thread(self.log_message, f"  {cleaned}")
                proc.stdout.close()
            proc.wait()
            self.call_from_thread(self.log_message, f"[bold green]✓ Finished Odoo backup operation for {vps_name}[/bold green]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Odoo backup failed: {e}[/red]\n")

    @work(thread=True)
    def execute_config_export(self) -> None:
        self.call_from_thread(self.log_message, "\n[bold cyan]▶ Running: cstation config export...[/bold cyan]")
        try:
            res = subprocess.run(["cstation", "config", "export"], capture_output=True, text=True)
            for line in res.stdout.strip().splitlines():
                self.call_from_thread(self.log_message, f"  {line}")
            self.call_from_thread(self.log_message, "[bold green]✓ Config bundle exported successfully[/bold green]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Export failed: {e}[/red]\n")

    @work(thread=True)
    def execute_state_audit(self) -> None:
        self.call_from_thread(self.log_message, "\n[bold cyan]▶ Running: cstation state audit --limit 15...[/bold cyan]")
        try:
            res = subprocess.run(["cstation", "state", "audit", "--limit", "15"], capture_output=True, text=True)
            for line in res.stdout.strip().splitlines():
                self.call_from_thread(self.log_message, f"  {line}")
            self.call_from_thread(self.log_message, "[bold green]✓ Audit log query complete[/bold green]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ State audit query failed: {e}[/red]\n")

    @work(thread=True)
    def execute_dns_zones(self) -> None:
        self.call_from_thread(self.log_message, "\n[bold cyan]▶ Running: cstation dns zones...[/bold cyan]")
        try:
            res = subprocess.run(["cstation", "dns", "zones"], capture_output=True, text=True)
            for line in res.stdout.strip().splitlines():
                self.call_from_thread(self.log_message, f"  {line}")
            self.call_from_thread(self.log_message, "[bold green]✓ DNS query complete[/bold green]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ DNS query failed: {e}[/red]\n")

    @work(thread=True)
    def execute_image_list(self) -> None:
        self.call_from_thread(self.log_message, "\n[bold cyan]▶ Running: cstation image list...[/bold cyan]")
        try:
            res = subprocess.run(["cstation", "image", "list"], capture_output=True, text=True)
            for line in res.stdout.strip().splitlines():
                self.call_from_thread(self.log_message, f"  {line}")
            self.call_from_thread(self.log_message, "[bold green]✓ Image list complete[/bold green]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Image query failed: {e}[/red]\n")

    @work(thread=True)
    def execute_cli_or_remote_command(self, cmd_text: str) -> None:
        mode, resolved_cmd = resolve_command_execution(cmd_text, self.selected_vps)
        if mode == "none" or not resolved_cmd:
            return

        if mode == "ssh" and self.selected_vps:
            vps_name = self.selected_vps
            self.call_from_thread(self.log_message, f"\n[bold cyan]▶ [{vps_name}] SSH: {resolved_cmd}[/bold cyan]")
            try:
                vps_dir = _resolve_vps_dir(Path(vps_name))
                vps_data = _load_vps_config(vps_dir)
                ssh = _ssh_from_config(vps_data)
                res = ssh.run(resolved_cmd, hide=True)
                out = ""
                if res:
                    out = (res.stdout or "").strip()
                    if res.stderr and res.stderr.strip():
                        out += ("\n" if out else "") + res.stderr.strip()
                if out:
                    for line in out.splitlines():
                        self.call_from_thread(self.log_message, f"  {line}")
                else:
                    self.call_from_thread(self.log_message, "  [dim](command executed, no output)[/dim]")
                self.call_from_thread(self.log_message, f"[bold green]✓ Done ({vps_name})[/bold green]\n")
            except Exception as e:
                self.call_from_thread(self.log_message, f"[red]✗ Remote SSH command failed on {vps_name}: {e}[/red]\n")
        else:
            self._run_local_cli(resolved_cmd)

    def _run_local_cli(self, cmd_text: str) -> None:
        parts = cmd_text.split()
        if parts and parts[0] == "cstation":
            parts = parts[1:]
        if not parts:
            return

        cli_cmd = ["cstation"] + parts
        self.call_from_thread(self.log_message, f"\n[bold cyan]▶ CLI: {' '.join(cli_cmd)}[/bold cyan]")
        try:
            proc = subprocess.Popen(
                cli_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if proc.stdout:
                for line in iter(proc.stdout.readline, ""):
                    cleaned = line.rstrip()
                    if cleaned:
                        self.call_from_thread(self.log_message, f"  {cleaned}")
                proc.stdout.close()
            code = proc.wait()
            if code == 0:
                self.call_from_thread(self.log_message, "[bold green]✓ Command succeeded[/bold green]\n")
            else:
                self.call_from_thread(self.log_message, f"[bold red]✗ Exited with code {code}[/bold red]\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Failed to execute CLI command: {e}[/red]\n")

    def action_lint_fleet(self) -> None:
        """Run pre-flight configuration linting."""
        self.execute_lint()

    @work(thread=True)
    def execute_lint(self) -> None:
        self.call_from_thread(self.log_message, "\n[bold cyan]▶ Running pre-flight configuration lint...[/bold cyan]")
        try:
            from cstation.commands.lint.main import run_lint_checks
            results = run_lint_checks()
            passed = results.get("passed", False)
            total = results.get("total_checks", 0)
            errs = results.get("error_count", 0)
            warns = results.get("warning_count", 0)

            if passed:
                self.call_from_thread(self.log_message, f"[bold green]✓ All {total} checks passed successfully![/bold green]\n")
            else:
                self.call_from_thread(self.log_message, f"[bold yellow]⚠ Lint finished with {errs} errors, {warns} warnings across {total} checks.[/bold yellow]")
                for issue in results.get("issues", []):
                    self.call_from_thread(
                        self.log_message,
                        f"  [{issue['severity']}] [bold]{issue['target']}[/bold] ({issue['rule']}): {issue['message']}"
                    )
                self.call_from_thread(self.log_message, "")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Lint failed: {e}[/red]\n")

    def action_add_vps(self) -> None:
        self.log_message("\n[bold cyan]▶ Adding a New VPS or Remote Server:[/bold cyan]")
        self.log_message("  [white]1. Interactive Wizard:[/white] Run [cyan]cstation vps add[/cyan] in your terminal")
        self.log_message("  [white]2. Non-interactive:[/white]   Run [cyan]cstation vps add <name> --host <ip> --user root[/cyan]")
        self.log_message("  [white]3. Offline / Pre-boot:[/white] Run [cyan]cstation vps add <name> --host <ip> --skip-facts[/cyan]")
        self.log_message("  [dim]After adding, press 'r' to refresh the dashboard fleet view.[/dim]\n")

    @work(thread=True)
    def execute_remove_vps(self, vps_name: str) -> None:
        self.call_from_thread(self.log_message, f"\n[bold yellow]⚠ Removing VPS {vps_name} from local configuration...[/bold yellow]")
        try:
            vps_dir = _resolve_vps_dir(Path(vps_name))
            if not vps_dir.exists():
                self.call_from_thread(self.log_message, f"[red]✗ Directory not found: {vps_dir}[/red]\n")
                return

            shutil.rmtree(vps_dir)
            secrets_removed = _remove_vps_secrets(vps_name)
            record_audit(
                command="vps remove (tui)",
                target=vps_name,
                status="success",
                message=f"Removed {vps_dir} via TUI (secrets_removed={secrets_removed})",
            )
            self.call_from_thread(self.log_message, f"  [green]✓[/green] Deleted {vps_dir}/")
            if secrets_removed:
                self.call_from_thread(self.log_message, "  [green]✓[/green] Removed secrets from config.yaml")
            self.call_from_thread(self.log_message, f"[bold green]✓ Successfully removed {vps_name}[/bold green]\n")
            self.app.call_from_thread(self.action_refresh_fleet)
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Failed to remove {vps_name}: {e}[/red]\n")

    def get_palette_commands(self) -> list[tuple[str, str, Callable[[], None]]]:
        """Generate list of searchable commands for the Command Palette."""
        commands: list[tuple[str, str, Callable[[], None]]] = [
            ("Fleet: Refresh Servers & Facts", "Reload all VPS configs and cached facts", self.action_refresh_fleet),
            ("Fleet: Lint All Configurations", "Run offline schema & reference validator", self.action_lint_fleet),
            ("Fleet: Clear Output Logs", "Wipe the execution log terminal pane", self.action_clear_logs),
            ("VPS: Add New VPS / Remote Server", "Guide to add a server via cstation vps add", self.action_add_vps),
            ("Config: Export Configuration Archive", "Bundle ~/.config/cstation into a .tar.gz", self.execute_config_export),
            ("State: View Audit Log", "Inspect recent operational audit history", self.execute_state_audit),
            ("DNS: List Cloudflare Zones", "Enumerate managed Cloudflare DNS zones", self.execute_dns_zones),
            ("Image: List Image Recipes", "Enumerate multi-arch Docker image recipes", self.execute_image_list),
        ]

        # Per-VPS actions
        for v in self.vps_list:
            v_name = v["name"]
            # Quick health
            commands.append((
                f"VPS: Check Uptime & Health ({v_name})",
                f"Query live uptime, RAM, and disk for {v_name}",
                lambda name=v_name: self.execute_server_uptime(name),
            ))
            # SSH shell
            commands.append((
                f"VPS: Open SSH Shell ({v_name})",
                f"Drop directly into an interactive SSH session on {v_name}",
                lambda name=v_name: self.action_server_ssh_target(name),
            ))
            # Apply OS baseline
            commands.append((
                f"VPS: Apply 12-Phase OS Setup ({v_name})",
                f"Execute OS setup and baseline hardening on {v_name}",
                lambda name=v_name: self.execute_vps_apply(name),
            ))
            # Docker plan
            commands.append((
                f"Docker: Plan Containers ({v_name})",
                f"Dry-run inspect container drift on {v_name}",
                lambda name=v_name: self.execute_plan_for_vps(name),
            ))
            # Docker apply
            commands.append((
                f"Docker: Apply Container Stacks ({v_name})",
                f"Deploy/update declared containers on {v_name}",
                lambda name=v_name: self.execute_docker_apply(name),
            ))
            # Odoo backup
            commands.append((
                f"Odoo: Backup Database ({v_name})",
                f"Backup PostgreSQL database for Odoo services on {v_name}",
                lambda name=v_name: self.execute_odoo_backup(name),
            ))
            # Hindsight status
            commands.append((
                f"Hindsight: Status Check ({v_name})",
                f"Inspect Hindsight memory service & backups on {v_name}",
                lambda name=v_name: self.execute_hindsight_status(name),
            ))
            # Remove VPS
            commands.append((
                f"VPS: Remove Server Config ({v_name})",
                f"Permanently delete local config & secrets for {v_name}",
                lambda name=v_name: self.execute_remove_vps(name),
            ))

        return commands

    @work(thread=True)
    def execute_hindsight_status(self, vps_name: str) -> None:
        self.call_from_thread(self.log_message, f"\n[bold cyan]▶ Checking Hindsight status on {vps_name}...[/bold cyan]")
        try:
            from cstation.commands.hindsight.main import _find_vps_dir
            vps_dir = _find_vps_dir(vps_name)
            vps_data = _load_vps_config(vps_dir)
            ssh = _ssh_from_config(vps_data)

            res_ps = ssh.run("docker ps --filter 'name=HINDSIGHT' --format '{{.Names}}|{{.Status}}|{{.Ports}}'", hide=True)
            res_bk = ssh.run("ls -lh /root/backups/hindsight_*.dump* 2>/dev/null | tail -1", hide=True)

            ps_out = res_ps.stdout.strip() if res_ps else "None detected"
            bk_out = res_bk.stdout.strip() if res_bk else "None found"

            self.call_from_thread(self.log_message, f"  Container: [bold green]{ps_out}[/bold green]")
            self.call_from_thread(self.log_message, f"  Latest Backup: {bk_out}\n")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]✗ Hindsight check failed: {e}[/red]\n")
