"""CLI entry point. Provides:

    aion              — start an interactive REPL session
    aion "<prompt>"   — one-shot non-interactive prompt
    aion --version    — print version
    aion --help       — usage
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from . import __version__
from .agent import Agent
from .config import BrandConfig, load_brand_config
from .plugins.cli_commands import plugin_group


def _resolve_install_dir() -> Path:
    """Find brand.config.json by walking up from the script location.

    For `pip install -e .` installs, the package source is the editable repo.
    For `pipx install`, the source is in the venv site-packages and brand.config.json
    lives next to it via AION_INSTALL_DIR (set by the installer) — fall back
    to the editable-install heuristic if that env var is missing.
    """
    env = os.environ.get("AION_INSTALL_DIR")
    if env:
        p = Path(env).expanduser()
        if (p / "brand.config.json").exists():
            return p

    # Walk up from this file's location looking for brand.config.json
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "brand.config.json").exists():
            return parent

    # Last resort: cwd
    cwd = Path.cwd()
    if (cwd / "brand.config.json").exists():
        return cwd

    raise FileNotFoundError(
        "Couldn't locate brand.config.json. "
        "Set AION_INSTALL_DIR to the directory containing it."
    )


console = Console()


def _print_header(brand: BrandConfig) -> None:
    title = Text(f" {brand.display} ", style="bold cyan on grey15")
    sub = f"  {brand.tagline}" if brand.tagline else ""
    console.print()
    console.print(title, sub, style="dim")
    console.print(f"  [dim]{brand.version.label}  ·  type 'exit' or Ctrl-D to quit[/dim]")
    console.print()


def _make_ui_hooks():
    """Build the agent's UI callbacks. Pulled out so the REPL and one-shot
    paths can share them."""

    def on_think():
        # Subtle in-progress indicator. Cleared on next print.
        console.print("[dim]  ⋯ thinking[/dim]", end="\r")

    def on_assistant_text(text: str):
        # Clear the thinking line if present, then render markdown.
        console.print(" " * 40, end="\r")
        console.print(Markdown(text))

    def on_tool_result(name: str, args: dict, content: str, ok: bool):
        console.print(" " * 40, end="\r")
        head_style = "green" if ok else "red"
        head = f"[{head_style}]●[/{head_style}] [bold]{name}[/bold]"
        # Show args compactly — first 100 chars
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        if len(args_str) > 100:
            args_str = args_str[:100] + "…"
        console.print(f"{head} [dim]({args_str})[/dim]")
        # Truncate long results in the UI; the agent still sees the full content.
        snippet = content if len(content) < 800 else content[:800] + "\n[…truncated…]"
        console.print(Panel(snippet, border_style="dim", padding=(0, 1), expand=False))

    return on_think, on_assistant_text, on_tool_result


def _repl(agent: Agent, brand: BrandConfig) -> None:
    from .permissions import status_short

    _print_header(brand)
    if agent.hooks:
        agent.hooks.session_start()
    try:
        while True:
            # Compact status line above the prompt so the user always knows
            # the active permission flags.
            if agent.permissions:
                console.print(f"[dim]{status_short(agent.permissions)}[/dim]")
            try:
                user_in = console.input(f"[bold cyan]{brand.binary}>[/bold cyan] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break
            if not user_in:
                continue
            if user_in in {"exit", "quit", ":q"}:
                break

            # Slash commands handled directly by the REPL — they never reach
            # the LLM. Lightweight; Phase 2 expands this with prompt_toolkit
            # key bindings for Ctrl+A/B/P + Shift+Tab.
            if user_in.startswith("/"):
                handled = _handle_slash_command(user_in, agent, brand)
                if handled:
                    continue

            try:
                agent.execute(user_in)
            except KeyboardInterrupt:
                console.print("\n[yellow]interrupted[/yellow]")
                continue
            except Exception as e:  # noqa: BLE001 — top-level REPL boundary
                console.print(f"[red]error: {e}[/red]")
                continue
    finally:
        if agent.hooks:
            agent.hooks.session_end()
        if agent.mcp:
            agent.mcp.shutdown()


def _handle_slash_command(line: str, agent: Agent, brand: BrandConfig) -> bool:
    """Process REPL-internal slash commands. Returns True if the command was
    recognized (caller should `continue` the loop). Returns False to let the
    line fall through to the LLM (for future plugin-provided commands)."""
    from .permissions import (
        PRESETS,
        cycle_preset,
        find_matching_preset,
        status_explained,
    )

    parts = line.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/perms":
        console.print(status_explained())
        if agent.permissions and agent.permissions.tool_overrides:
            console.print("\nCurrent tool overrides:")
            for tool, decision in agent.permissions.tool_overrides.items():
                console.print(f"  {tool}: {decision}")
        return True

    if cmd == "/auto":
        if agent.permissions:
            agent.permissions.auto_accept_edits = not agent.permissions.auto_accept_edits
            state = "ON" if agent.permissions.auto_accept_edits else "OFF"
            console.print(f"[dim]auto-accept edits: {state}[/dim]")
        return True

    if cmd == "/bypass":
        if agent.permissions:
            agent.permissions.bypass_permissions = not agent.permissions.bypass_permissions
            state = "ON" if agent.permissions.bypass_permissions else "OFF"
            color = "yellow" if agent.permissions.bypass_permissions else "dim"
            console.print(f"[{color}]bypass permissions: {state}[/{color}]")
        return True

    if cmd == "/plan":
        if agent.permissions:
            agent.permissions.plan_mode = not agent.permissions.plan_mode
            state = "ON" if agent.permissions.plan_mode else "OFF"
            console.print(f"[dim]plan mode: {state}[/dim]")
        return True

    if cmd == "/preset":
        if not arg and agent.permissions:
            # No arg → cycle to next preset
            preset = cycle_preset(agent.permissions)
            console.print(f"[dim]preset: {preset.name} — {preset.description}[/dim]")
            return True
        if agent.permissions:
            for p in PRESETS:
                if p.name.lower() == arg.lower():
                    agent.permissions.auto_accept_edits = p.auto_accept_edits
                    agent.permissions.bypass_permissions = p.bypass_permissions
                    agent.permissions.plan_mode = p.plan_mode
                    console.print(f"[dim]preset: {p.name} — {p.description}[/dim]")
                    return True
            console.print(f"[red]unknown preset '{arg}'[/red]")
            console.print(f"available: {', '.join(p.name for p in PRESETS)}")
        return True

    if cmd in {"/help", "/?"}:
        console.print("Slash commands:")
        console.print("  /perms                — show permission flags and what they mean")
        console.print("  /auto                 — toggle auto-accept-edits")
        console.print("  /bypass               — toggle bypass-permissions (CAUTION)")
        console.print("  /plan                 — toggle plan mode")
        console.print("  /preset [name]        — cycle named preset, or jump to named one")
        console.print("  /help, /?             — this list")
        console.print("  exit, quit, :q        — leave the REPL")
        return True

    return False


def _one_shot(agent: Agent, prompt: str) -> None:
    try:
        agent.execute(prompt)
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]error: {e}[/red]")
        sys.exit(1)


def _build_agent(install_dir: str | None, *, noninteractive: bool = False) -> tuple[Agent, BrandConfig]:
    """Resolve install dir, load brand, discover plugins, init memory-git,
    construct the hook engine, build the agent."""
    install = Path(install_dir) if install_dir else _resolve_install_dir()
    brand = load_brand_config(install)

    # Initialize the memory git repo if needed (idempotent — does nothing
    # if already initialized or if memoryGit.enabled is false).
    from .memory_git import init_memory_repo
    init_memory_repo(brand.resolved_config_dir, brand)

    # Load every plugin that's both installed AND enabled.
    from .plugins.discovery import discover_active_plugins
    plugins = discover_active_plugins(brand.resolved_config_dir)

    # Build the hook engine — wires memory-git autocommit + user-defined hooks.
    from .hooks import make_engine
    hook_engine = make_engine(brand)

    # Discover + spawn MCP servers (user-level + plugin-bundled).
    from .mcp import MCPManager, load_plugin_mcp_servers, load_user_mcp_servers
    server_configs = list(load_user_mcp_servers(brand.resolved_config_dir))
    for p in plugins:
        server_configs.extend(load_plugin_mcp_servers(p.install_path))
    mcp_manager = MCPManager(server_configs) if server_configs else None
    if mcp_manager:
        start_results = mcp_manager.start_all()
        for srv_name, err in start_results.items():
            if err:
                console.print(f"[yellow]  ⚠ MCP server '{srv_name}' failed to start: {err}[/yellow]")

    # Permission state. Starts at Standard (auto on, bypass off, plan off) —
    # the daily-driver default that matches typical user expectations. In
    # non-interactive mode, mark it so the gate auto-allows where it can.
    from .permissions import PermissionState
    permissions = PermissionState(
        auto_accept_edits=True,
        bypass_permissions=False,
        plan_mode=False,
        noninteractive=noninteractive,
    )

    agent = Agent(
        brand=brand,
        plugins=plugins,
        hooks=hook_engine,
        mcp=mcp_manager,
        permissions=permissions,
    )
    on_think, on_assistant_text, on_tool_result = _make_ui_hooks()
    agent.on_think = on_think
    agent.on_assistant_text = on_assistant_text
    agent.on_tool_result = on_tool_result

    # Interactive mode gets a console-based y/n permission prompt callback.
    # Non-interactive (one-shot) skips this and relies on the gate's
    # auto-allow-where-safe behavior.
    if not noninteractive:
        agent.on_permission_prompt = _console_permission_prompt

    return agent, brand


def _console_permission_prompt(tool_name: str, arguments: dict, reason: str) -> str:
    """Synchronous y/n permission prompt. Used by interactive REPL until
    Phase 2 wires up prompt_toolkit's richer UI."""
    # Compact argument preview so the prompt fits on one line for common cases.
    args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    if len(args_str) > 100:
        args_str = args_str[:100] + "…"
    console.print(
        f"[yellow]Permission needed[/yellow]: [bold]{tool_name}[/bold]({args_str})  "
        f"[dim]— {reason}[/dim]"
    )
    console.print(
        "  [bold]y[/bold]es / [bold]n[/bold]o / [bold]a[/bold]llow-session / [bold]d[/bold]eny-session"
    )
    try:
        choice = console.input("  > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "deny"
    if choice in {"y", "yes", ""}:
        return "allow"
    if choice in {"a", "allow-session", "always"}:
        return "allow_session"
    if choice in {"d", "deny-session", "never"}:
        return "deny_session"
    return "deny"


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.option("--version", "show_version", is_flag=True, help="Print version and exit.")
@click.option("--install-dir", type=click.Path(exists=True, file_okay=False), help="Override brand install directory (otherwise auto-detected).")
@click.pass_context
def main(ctx: click.Context, show_version: bool, install_dir: str | None) -> None:
    """Configurable agent CLI.

    Run with no args for an interactive REPL.
    Run `aion run "<prompt>"` for one-shot.
    Run `aion plugin list` etc. to manage plugins.
    """
    # Stash install_dir for subcommands
    ctx.ensure_object(dict)
    if install_dir is not None:
        ctx.obj["install_dir"] = Path(install_dir)

    if show_version:
        try:
            install = Path(install_dir) if install_dir else _resolve_install_dir()
            brand = load_brand_config(install)
            click.echo(f"{brand.version.label} ({brand.display})")
        except FileNotFoundError:
            click.echo(f"{__version__} (aion — brand.config.json not found)")
        return

    # No subcommand AND no --version → default to REPL.
    if ctx.invoked_subcommand is None:
        agent, brand = _build_agent(install_dir)
        _repl(agent, brand)


@main.command(name="run")
@click.argument("prompt", nargs=-1, required=True)
@click.pass_context
def run_cmd(ctx: click.Context, prompt: tuple[str, ...]) -> None:
    """Run a one-shot prompt non-interactively."""
    install_dir = ctx.obj.get("install_dir") if ctx.obj else None
    install_dir_str = str(install_dir) if install_dir else None
    # One-shot is non-interactive: gate auto-allows where it can; otherwise
    # the tool call is denied so the agent doesn't hang on stdin.
    agent, _ = _build_agent(install_dir_str, noninteractive=True)
    _one_shot(agent, " ".join(prompt))


# Register subcommand groups
main.add_command(plugin_group)


if __name__ == "__main__":
    main()
