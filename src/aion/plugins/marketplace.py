"""Marketplace loading + plugin enumeration.

A marketplace is a directory containing:
    <root>/.claude-plugin/marketplace.json    — manifest listing plugins
    <root>/plugins/<plugin-name>/             — plugin source dirs

Marketplaces are tracked in `<config>/plugins/known_marketplaces.json`,
which the user manipulates via `aion plugin marketplace add/remove/list`.
This module reads + validates that state.
"""

from __future__ import annotations

import json
from pathlib import Path

from .types import MarketplaceEntry, MarketplaceRegistration


def _known_marketplaces_path(config_dir: Path) -> Path:
    return config_dir / "plugins" / "known_marketplaces.json"


def load_known_marketplaces(config_dir: Path) -> list[MarketplaceRegistration]:
    """Read known_marketplaces.json. Returns empty list if file is absent."""
    path = _known_marketplaces_path(config_dir)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []

    result: list[MarketplaceRegistration] = []
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        install_location = entry.get("installLocation")
        if not install_location:
            continue
        source = entry.get("source", {}) or {}
        result.append(
            MarketplaceRegistration(
                name=name,
                install_location=Path(install_location),
                source_kind=str(source.get("source", "directory")),
                last_updated=entry.get("lastUpdated"),
            )
        )
    return result


def register_marketplace(
    config_dir: Path,
    name: str,
    install_location: Path,
    source_kind: str = "directory",
) -> None:
    """Add or refresh a marketplace registration. Idempotent.

    Used by `aion plugin marketplace add` and by install-defaults during
    first-run setup.
    """
    from datetime import datetime, timezone

    path = _known_marketplaces_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except json.JSONDecodeError:
        data = {}

    data[name] = {
        "source": {"source": source_kind, "path": str(install_location)},
        "installLocation": str(install_location),
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
    }

    path.write_text(json.dumps(data, indent=2) + "\n")


def unregister_marketplace(config_dir: Path, name: str) -> bool:
    """Remove a marketplace from the registry. Returns True if a removal happened."""
    path = _known_marketplaces_path(config_dir)
    if not path.exists():
        return False

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return False

    if name not in data:
        return False
    del data[name]
    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def load_marketplace_manifest(registration: MarketplaceRegistration) -> list[MarketplaceEntry]:
    """Read the marketplace's marketplace.json and return its plugin entries.

    Raises FileNotFoundError if the marketplace is missing its manifest —
    that means the registration is stale (the directory got moved/deleted
    without unregistering) and the caller should consider that a real error.
    """
    manifest_path = registration.install_location / ".claude-plugin" / "marketplace.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Marketplace '{registration.name}' is registered but its manifest is missing at {manifest_path}. "
            "Run `aion plugin marketplace remove {registration.name}` to clean up, or restore the directory."
        )

    raw = json.loads(manifest_path.read_text())
    entries_raw = raw.get("plugins", [])
    entries: list[MarketplaceEntry] = []
    for e in entries_raw:
        if not isinstance(e, dict):
            continue
        name = e.get("name")
        source = e.get("source")
        if not name or not source:
            continue
        author = None
        author_raw = e.get("author")
        if isinstance(author_raw, dict):
            author = author_raw.get("name")
        elif isinstance(author_raw, str):
            author = author_raw

        entries.append(
            MarketplaceEntry(
                name=str(name),
                description=str(e.get("description", "")),
                source=str(source),
                author=author,
                category=e.get("category"),
                version=e.get("version"),
                marketplace_name=registration.name,
            )
        )
    return entries


def resolve_plugin_path(registration: MarketplaceRegistration, entry: MarketplaceEntry) -> Path:
    """Compute the on-disk path to a plugin inside its marketplace."""
    # source is a relative path like "./plugins/foo"
    return (registration.install_location / entry.source).resolve()
