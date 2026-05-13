"""High-level plugin operations used by the CLI subcommands.

The lower-level modules (marketplace.py, registry.py, discovery.py) handle
specific file shapes. This module composes them into user-facing operations:
list, install, uninstall, enable, disable, and add/remove marketplaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .discovery import discover_plugin
from .marketplace import (
    load_known_marketplaces,
    load_marketplace_manifest,
    register_marketplace,
    resolve_plugin_path,
    unregister_marketplace,
)
from .registry import (
    is_enabled,
    load_enabled_map,
    load_installed,
    register_install,
    set_enabled,
    unregister_install,
)
from .types import InstalledPlugin, Plugin


@dataclass(frozen=True)
class PluginStatus:
    """Snapshot of one plugin's combined installed + enabled + load-success state.
    What `aion plugin list` ultimately renders."""
    key: str
    name: str
    marketplace: str
    version: str
    scope: str
    installed: bool
    enabled: bool
    loads: bool  # discovery walked the directory successfully
    description: str | None = None


def list_status(config_dir: Path) -> list[PluginStatus]:
    """Build status rows for every installed plugin."""
    installed = load_installed(config_dir)
    enabled_map = load_enabled_map(config_dir)

    rows: list[PluginStatus] = []
    for key, ip in sorted(installed.items()):
        plugin: Plugin | None = None
        loads = False
        try:
            plugin = discover_plugin(ip)
            # "Loads" means the install dir exists and has a parseable manifest.
            # We can't fully validate without simulating the runtime, but presence
            # of a non-empty plugin object is a strong signal.
            loads = ip.install_path.is_dir() and (ip.install_path / ".claude-plugin" / "plugin.json").exists()
        except Exception:
            loads = False
        rows.append(
            PluginStatus(
                key=key,
                name=ip.name,
                marketplace=ip.marketplace,
                version=ip.version,
                scope=ip.scope,
                installed=True,
                enabled=enabled_map.get(key, False),
                loads=loads,
                description=plugin.description if plugin else None,
            )
        )
    return rows


def install_plugin(config_dir: Path, plugin_key: str) -> InstalledPlugin:
    """Install a plugin by '<name>@<marketplace>' key.

    Reads the marketplace manifest, resolves the plugin source path, registers
    it in installed_plugins.json, and auto-enables it (matching what users
    expect after `proteus plugin install`).
    """
    if "@" not in plugin_key:
        raise ValueError(f"Plugin key must be '<name>@<marketplace>' (got {plugin_key!r})")
    name, marketplace_name = plugin_key.split("@", 1)

    registrations = {r.name: r for r in load_known_marketplaces(config_dir)}
    registration = registrations.get(marketplace_name)
    if registration is None:
        raise LookupError(
            f"Marketplace '{marketplace_name}' is not registered. "
            f"Available: {', '.join(sorted(registrations)) or '(none)'}"
        )

    entries = {e.name: e for e in load_marketplace_manifest(registration)}
    entry = entries.get(name)
    if entry is None:
        raise LookupError(
            f"Plugin '{name}' not found in marketplace '{marketplace_name}'. "
            f"Available: {', '.join(sorted(entries)) or '(none)'}"
        )

    plugin_path = resolve_plugin_path(registration, entry)
    if not plugin_path.is_dir():
        raise FileNotFoundError(
            f"Plugin '{plugin_key}' resolved to {plugin_path} but that directory doesn't exist. "
            "Marketplace manifest may be out of date."
        )

    # Read version from the plugin's own plugin.json (the marketplace entry may
    # have a stale or absent version)
    import json as _json
    manifest_path = plugin_path / ".claude-plugin" / "plugin.json"
    version = "unknown"
    if manifest_path.exists():
        try:
            version = str(_json.loads(manifest_path.read_text()).get("version", "unknown"))
        except _json.JSONDecodeError:
            pass

    installed = register_install(config_dir, plugin_key, plugin_path, version)
    set_enabled(config_dir, plugin_key, True)
    return installed


def uninstall_plugin(config_dir: Path, plugin_key: str) -> bool:
    """Uninstall a plugin. Removes from installed_plugins.json and disables
    in settings.json. Returns True if anything was removed."""
    removed_registry = unregister_install(config_dir, plugin_key)
    # Disabling on uninstall keeps settings.json clean. If the user reinstalls,
    # install_plugin re-enables; if they don't, the dangling 'true' would have
    # been a confusing leftover.
    if is_enabled(config_dir, plugin_key):
        set_enabled(config_dir, plugin_key, False)
    return removed_registry


def enable_plugin(config_dir: Path, plugin_key: str) -> None:
    set_enabled(config_dir, plugin_key, True)


def disable_plugin(config_dir: Path, plugin_key: str) -> None:
    set_enabled(config_dir, plugin_key, False)


def add_marketplace(
    config_dir: Path,
    source_path: Path,
) -> str:
    """Register a local-directory marketplace. Reads its name from its own
    marketplace.json. Returns the marketplace name."""
    source_path = source_path.expanduser().resolve()
    manifest = source_path / ".claude-plugin" / "marketplace.json"
    if not manifest.exists():
        raise FileNotFoundError(
            f"No marketplace manifest at {manifest}. "
            "A marketplace dir must contain .claude-plugin/marketplace.json."
        )

    import json as _json
    raw = _json.loads(manifest.read_text())
    name = raw.get("name")
    if not name:
        raise ValueError(f"Marketplace at {source_path} has no 'name' field in its manifest.")

    register_marketplace(config_dir, str(name), source_path, source_kind="directory")
    return str(name)


def remove_marketplace(config_dir: Path, name: str) -> bool:
    return unregister_marketplace(config_dir, name)
