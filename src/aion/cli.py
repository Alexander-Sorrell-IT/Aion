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
    _print_header(brand)
    while True:
        try:
            user_in = console.input(f"[bold cyan]{brand.binary}>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not user_in:
            continue
        if user_in in {"exit", "quit", ":q"}:
            break

        try:
            agent.execute(user_in)
        except KeyboardInterrupt:
            console.print("\n[yellow]interrupted[/yellow]")
            continue
        except Exception as e:  # noqa: BLE001 — top-level REPL boundary
            console.print(f"[red]error: {e}[/red]")
            continue


def _one_shot(agent: Agent, prompt: str) -> None:
    try:
        agent.execute(prompt)
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]error: {e}[/red]")
        sys.exit(1)


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_help_option=True,
)
@click.argument("prompt", required=False, nargs=-1)
@click.option("--version", "show_version", is_flag=True, help="Print version and exit.")
@click.option("--install-dir", type=click.Path(exists=True, file_okay=False), help="Override brand install directory (otherwise auto-detected).")
def main(prompt: tuple[str, ...], show_version: bool, install_dir: str | None) -> None:
    """Configurable agent CLI.

    Run with no args for an interactive REPL. Pass a quoted prompt for one-shot.
    """
    if show_version:
        try:
            install = Path(install_dir) if install_dir else _resolve_install_dir()
            brand = load_brand_config(install)
            click.echo(f"{brand.version.label} ({brand.display})")
        except FileNotFoundError:
            click.echo(f"{__version__} (aion — brand.config.json not found)")
        return

    install = Path(install_dir) if install_dir else _resolve_install_dir()
    brand = load_brand_config(install)

    agent = Agent(brand=brand)
    on_think, on_assistant_text, on_tool_result = _make_ui_hooks()
    agent.on_think = on_think
    agent.on_assistant_text = on_assistant_text
    agent.on_tool_result = on_tool_result

    if prompt:
        _one_shot(agent, " ".join(prompt))
    else:
        _repl(agent, brand)


if __name__ == "__main__":
    main()
