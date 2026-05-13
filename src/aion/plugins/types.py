"""Typed dataclasses for plugins, marketplaces, and their components.

These mirror the JSON shapes on disk (marketplace.json, plugin.json,
installed_plugins.json, SKILL.md frontmatter, etc.) so the rest of the
plugin system can work with typed values instead of dict[str, Any] soup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MarketplaceRegistration:
    """One entry in known_marketplaces.json — a marketplace the user has registered."""
    name: str
    install_location: Path  # absolute path to <marketplace-root>/
    source_kind: str  # "directory" | "github" | "git" | "local"
    last_updated: str | None = None


@dataclass(frozen=True)
class MarketplaceEntry:
    """One plugin entry inside a marketplace's marketplace.json. Describes a
    plugin that IS available in the marketplace, not necessarily installed."""
    name: str
    description: str
    source: str  # relative path within the marketplace (e.g. "./plugins/foo")
    author: str | None = None
    category: str | None = None
    version: str | None = None
    marketplace_name: str = ""

    @property
    def key(self) -> str:
        """Globally-unique plugin key: '<name>@<marketplace>'."""
        return f"{self.name}@{self.marketplace_name}"


@dataclass(frozen=True)
class InstalledPlugin:
    """One entry in installed_plugins.json — a plugin the user has installed."""
    key: str  # '<name>@<marketplace>'
    install_path: Path  # absolute path to the plugin's root directory
    version: str
    scope: str  # 'user' | 'project' | 'local'
    installed_at: str
    last_updated: str

    @property
    def name(self) -> str:
        return self.key.split("@", 1)[0]

    @property
    def marketplace(self) -> str:
        parts = self.key.split("@", 1)
        return parts[1] if len(parts) > 1 else ""


@dataclass(frozen=True)
class Skill:
    """A skill is a description-triggered chunk of expertise. The agent reads
    only the frontmatter `description` before deciding to load the body."""
    name: str
    description: str
    body: str
    path: Path  # path to the SKILL.md file
    plugin_key: str  # '<plugin>@<marketplace>' this skill came from


@dataclass(frozen=True)
class Command:
    """A slash command — a markdown file with optional frontmatter that
    expands into a prompt the agent runs."""
    name: str
    description: str
    body: str
    path: Path
    plugin_key: str
    allowed_tools: list[str] | None = None


@dataclass(frozen=True)
class Agent:
    """A subagent — invoked via the Agent tool with its own context."""
    name: str
    description: str
    body: str
    path: Path
    plugin_key: str
    tools: list[str] | None = None
    model: str | None = None


@dataclass(frozen=True)
class Plugin:
    """A loaded plugin with all its components enumerated. Built by discovery
    after the plugin is confirmed installed AND enabled."""
    name: str
    marketplace: str
    install_path: Path
    version: str
    description: str
    skills: tuple[Skill, ...] = field(default_factory=tuple)
    commands: tuple[Command, ...] = field(default_factory=tuple)
    agents: tuple[Agent, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        return f"{self.name}@{self.marketplace}"
