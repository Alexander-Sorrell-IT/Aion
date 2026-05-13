"""Installed plugin registry + enable/disable state.

Three files together represent "what plugins are active":

  <config>/plugins/installed_plugins.json   — which plugins are installed (and where)
  <config>/settings.json `enabledPlugins`   — which installed plugins are enabled
  <config>/plugins/marketplaces/<n>/*       — the source files (managed elsewhere)

A plugin is "active" (loads at runtime) iff it appears in installed_plugins.json
AND has `enabledPlugins[<key>] = true` in settings.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .types import InstalledPlugin


# ── installed_plugins.json ────────────────────────────────────────────────────


def _installed_path(config_dir: Path) -> Path:
    return config_dir / "plugins" / "installed_plugins.json"


def load_installed(config_dir: Path) -> dict[str, InstalledPlugin]:
    """Read installed_plugins.json. Keyed by '<name>@<marketplace>'."""
    path = _installed_path(config_dir)
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}

    raw = data.get("plugins", {}) or {}
    result: dict[str, InstalledPlugin] = {}
    for key, entries in raw.items():
        # Schema: each key maps to a list (for future multi-scope support);
        # current code only uses the first entry.
        if not entries or not isinstance(entries, list):
            continue
        e = entries[0]
        install_path = e.get("installPath")
        if not install_path:
            continue
        result[key] = InstalledPlugin(
            key=str(key),
            install_path=Path(install_path),
            version=str(e.get("version", "unknown")),
            scope=str(e.get("scope", "user")),
            installed_at=str(e.get("installedAt", "")),
            last_updated=str(e.get("lastUpdated", "")),
        )
    return result


def _save_installed(config_dir: Path, installed: dict[str, InstalledPlugin]) -> None:
    path = _installed_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "plugins": {
            key: [
                {
                    "scope": p.scope,
                    "installPath": str(p.install_path),
                    "version": p.version,
                    "installedAt": p.installed_at,
                    "lastUpdated": p.last_updated,
                }
            ]
            for key, p in installed.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def register_install(
    config_dir: Path,
    key: str,
    install_path: Path,
    version: str,
    scope: str = "user",
) -> InstalledPlugin:
    """Mark a plugin installed. Preserves original installedAt if already present."""
    installed = load_installed(config_dir)
    now = datetime.now(timezone.utc).isoformat()
    prior = installed.get(key)
    entry = InstalledPlugin(
        key=key,
        install_path=install_path,
        version=version,
        scope=scope,
        installed_at=prior.installed_at if prior else now,
        last_updated=now,
    )
    installed[key] = entry
    _save_installed(config_dir, installed)
    return entry


def unregister_install(config_dir: Path, key: str) -> bool:
    """Remove a plugin from installed_plugins.json. Returns True if removed."""
    installed = load_installed(config_dir)
    if key not in installed:
        return False
    del installed[key]
    _save_installed(config_dir, installed)
    return True


# ── settings.json `enabledPlugins` ───────────────────────────────────────────


def _settings_path(config_dir: Path) -> Path:
    return config_dir / "settings.json"


def load_enabled_map(config_dir: Path) -> dict[str, bool]:
    """Read enabledPlugins from settings.json. Returns empty dict if missing."""
    path = _settings_path(config_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return dict(data.get("enabledPlugins", {}) or {})


def set_enabled(config_dir: Path, key: str, enabled: bool) -> None:
    """Set enabledPlugins[key] = enabled in settings.json. Creates the file if missing."""
    path = _settings_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    ep = data.get("enabledPlugins") or {}
    ep[key] = bool(enabled)
    data["enabledPlugins"] = ep
    path.write_text(json.dumps(data, indent=2) + "\n")


def is_enabled(config_dir: Path, key: str) -> bool:
    return bool(load_enabled_map(config_dir).get(key, False))


def active_plugin_keys(config_dir: Path) -> list[str]:
    """The set of plugin keys that are BOTH installed AND enabled. These are
    the plugins the runtime should actually load skills/commands/agents from."""
    installed = load_installed(config_dir)
    enabled = load_enabled_map(config_dir)
    return [key for key in installed if enabled.get(key, False)]
