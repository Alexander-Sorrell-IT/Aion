"""Click subcommand group for `aion plugin ...`.

Wires the manager.py operations to a clean CLI surface. Mounted in
src/aion/cli.py via `main.add_command(plugin_group)`.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..config import load_brand_config
from . import manager
from .marketplace import load_known_marketplaces, load_marketplace_manifest


console = Console()


def _resolve_config_dir(ctx: click.Context) -> Path:
    """Read brand.config.json from the install dir to find the config dir."""
    install_dir = ctx.obj.get("install_dir") if ctx.obj else None
    if install_dir is None:
        # Best effort: use the same resolver the main CLI uses
        from ..cli import _resolve_install_dir
        install_dir = _resolve_install_dir()
    brand = load_brand_config(install_dir)
    return brand.resolved_config_dir


@click.group(name="plugin")
@click.pass_context
def plugin_group(ctx: click.Context) -> None:
    """Manage aion plugins (install, enable, list, marketplaces)."""
    ctx.ensure_object(dict)


@plugin_group.command(name="list")
@click.pass_context
def plugin_list(ctx: click.Context) -> None:
    """List installed plugins and their enable/load status."""
    config_dir = _resolve_config_dir(ctx)
    rows = manager.list_status(config_dir)
    if not rows:
        console.print("[dim]No plugins installed.[/dim]")
        console.print("  Try: [cyan]aion plugin marketplace add <path>[/cyan]")
        console.print("  Then: [cyan]aion plugin install <name>@<marketplace>[/cyan]")
        return

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Plugin", style="bold")
    table.add_column("Version")
    table.add_column("Status")
    table.add_column("Description", overflow="fold")

    for r in rows:
        if not r.loads:
            status = "[red]✘ failed to load[/red]"
        elif not r.enabled:
            status = "[yellow]✘ disabled[/yellow]"
        else:
            status = "[green]✔ enabled[/green]"
        table.add_row(r.key, r.version, status, r.description or "")

    console.print(table)


@plugin_group.command(name="install")
@click.argument("plugin_key")
@click.pass_context
def plugin_install(ctx: click.Context, plugin_key: str) -> None:
    """Install a plugin by '<name>@<marketplace>' key. Auto-enables it."""
    config_dir = _resolve_config_dir(ctx)
    try:
        installed = manager.install_plugin(config_dir, plugin_key)
    except (LookupError, FileNotFoundError, ValueError) as e:
        console.print(f"[red]✘ Failed to install {plugin_key}: {e}[/red]")
        raise click.exceptions.Exit(1) from e
    console.print(f"[green]✔ Installed[/green] {installed.key}  v{installed.version}")
    console.print(f"  source: [dim]{installed.install_path}[/dim]")
    console.print(f"  status: [green]✔ enabled[/green]")


@plugin_group.command(name="uninstall")
@click.argument("plugin_key")
@click.pass_context
def plugin_uninstall(ctx: click.Context, plugin_key: str) -> None:
    """Uninstall a plugin by '<name>@<marketplace>' key."""
    config_dir = _resolve_config_dir(ctx)
    if manager.uninstall_plugin(config_dir, plugin_key):
        console.print(f"[green]✔ Uninstalled[/green] {plugin_key}")
    else:
        console.print(f"[yellow]Plugin {plugin_key} was not installed.[/yellow]")


@plugin_group.command(name="enable")
@click.argument("plugin_key")
@click.pass_context
def plugin_enable(ctx: click.Context, plugin_key: str) -> None:
    """Enable an installed plugin (does not install it)."""
    config_dir = _resolve_config_dir(ctx)
    manager.enable_plugin(config_dir, plugin_key)
    console.print(f"[green]✔ Enabled[/green] {plugin_key}")


@plugin_group.command(name="disable")
@click.argument("plugin_key")
@click.pass_context
def plugin_disable(ctx: click.Context, plugin_key: str) -> None:
    """Disable an installed plugin without uninstalling it."""
    config_dir = _resolve_config_dir(ctx)
    manager.disable_plugin(config_dir, plugin_key)
    console.print(f"[yellow]✘ Disabled[/yellow] {plugin_key}")


# ── marketplace subcommands ─────────────────────────────────────────────────


@plugin_group.group(name="marketplace")
def marketplace_group() -> None:
    """Manage plugin marketplaces."""


@marketplace_group.command(name="list")
@click.pass_context
def marketplace_list(ctx: click.Context) -> None:
    """List registered marketplaces and the plugins each offers."""
    config_dir = _resolve_config_dir(ctx)
    regs = load_known_marketplaces(config_dir)
    if not regs:
        console.print("[dim]No marketplaces registered.[/dim]")
        return

    for r in regs:
        console.print(f"[bold cyan]{r.name}[/bold cyan]  [dim]({r.source_kind})[/dim]")
        console.print(f"  location: [dim]{r.install_location}[/dim]")
        try:
            entries = load_marketplace_manifest(r)
        except FileNotFoundError as e:
            console.print(f"  [red]✘ {e}[/red]")
            continue
        if not entries:
            console.print(f"  [dim](empty — no plugin entries)[/dim]")
            continue
        for e in entries:
            console.print(f"    • [bold]{e.name}[/bold] — {e.description}")
        console.print()


@marketplace_group.command(name="add")
@click.argument("source", type=click.Path())
@click.pass_context
def marketplace_add(ctx: click.Context, source: str) -> None:
    """Register a local marketplace by directory path."""
    config_dir = _resolve_config_dir(ctx)
    try:
        name = manager.add_marketplace(config_dir, Path(source))
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]✘ Failed to add marketplace: {e}[/red]")
        raise click.exceptions.Exit(1) from e
    console.print(f"[green]✔ Registered marketplace[/green] '{name}' from {source}")


@marketplace_group.command(name="remove")
@click.argument("name")
@click.pass_context
def marketplace_remove(ctx: click.Context, name: str) -> None:
    """Unregister a marketplace."""
    config_dir = _resolve_config_dir(ctx)
    if manager.remove_marketplace(config_dir, name):
        console.print(f"[green]✔ Removed marketplace[/green] '{name}'")
    else:
        console.print(f"[yellow]Marketplace '{name}' was not registered.[/yellow]")
