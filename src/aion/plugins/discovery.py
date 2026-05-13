"""Walk plugin directories to discover skills, commands, and agents.

Each plugin lives at `<install_path>/` with a `.claude-plugin/plugin.json`
manifest. Its components live in:

    <plugin>/skills/<name>/SKILL.md
    <plugin>/commands/<name>.md
    <plugin>/agents/<name>.md

Hooks and MCP servers are declared in plugin.json or sibling files — those
loaders live in separate modules (hooks.py, mcp.py) added later.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .registry import active_plugin_keys, load_installed
from .types import Agent, Command, InstalledPlugin, Plugin, Skill


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown file into (frontmatter-dict, body).

    Frontmatter is YAML between leading `---` markers. We parse it with a
    tiny scalar-only YAML reader (key: value lines + simple lists) instead
    of pulling in PyYAML — this covers everything the SKILL.md / agent.md
    contracts need without a dependency.

    If parsing fails or there's no frontmatter, returns ({}, original_text).
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    fm_raw, body = m.group(1), m.group(2)
    fm: dict[str, object] = {}
    for line in fm_raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        # Inline list shorthand: `tools: Read, Grep, Glob`
        if "," in value and key in {"tools", "allowed-tools", "allowedTools", "keywords"}:
            fm[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            fm[key] = value
    return fm, body


def _load_plugin_manifest(plugin_path: Path) -> dict:
    """Read plugin.json from a plugin's root. Returns {} if missing/invalid."""
    manifest = plugin_path / ".claude-plugin" / "plugin.json"
    if not manifest.exists():
        return {}
    try:
        return json.loads(manifest.read_text())
    except json.JSONDecodeError:
        return {}


def _discover_skills(plugin_path: Path, plugin_key: str) -> list[Skill]:
    skills_dir = plugin_path / "skills"
    if not skills_dir.is_dir():
        return []
    skills: list[Skill] = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            text = skill_md.read_text(errors="replace")
        except OSError:
            continue
        fm, body = _parse_frontmatter(text)
        name = str(fm.get("name") or entry.name)
        description = str(fm.get("description") or "")
        skills.append(
            Skill(
                name=name,
                description=description,
                body=body,
                path=skill_md,
                plugin_key=plugin_key,
            )
        )
    return skills


def _discover_commands(plugin_path: Path, plugin_key: str) -> list[Command]:
    cmd_dir = plugin_path / "commands"
    if not cmd_dir.is_dir():
        return []
    commands: list[Command] = []
    for entry in sorted(cmd_dir.rglob("*.md")):
        if not entry.is_file():
            continue
        try:
            text = entry.read_text(errors="replace")
        except OSError:
            continue
        fm, body = _parse_frontmatter(text)
        # Command name is the filename stem (e.g. commands/foo.md → "foo");
        # nested: commands/sub/bar.md → "sub:bar"
        rel = entry.relative_to(cmd_dir).with_suffix("")
        name = ":".join(rel.parts)
        description = str(fm.get("description") or "")
        allowed_tools = fm.get("allowed-tools") or fm.get("allowedTools")
        if isinstance(allowed_tools, str):
            allowed_tools = [t.strip() for t in allowed_tools.split(",") if t.strip()]
        commands.append(
            Command(
                name=name,
                description=description,
                body=body,
                path=entry,
                plugin_key=plugin_key,
                allowed_tools=allowed_tools if isinstance(allowed_tools, list) else None,
            )
        )
    return commands


def _discover_agents(plugin_path: Path, plugin_key: str) -> list[Agent]:
    agents_dir = plugin_path / "agents"
    if not agents_dir.is_dir():
        return []
    agents: list[Agent] = []
    for entry in sorted(agents_dir.glob("*.md")):
        if not entry.is_file():
            continue
        try:
            text = entry.read_text(errors="replace")
        except OSError:
            continue
        fm, body = _parse_frontmatter(text)
        name = str(fm.get("name") or entry.stem)
        description = str(fm.get("description") or "")
        tools = fm.get("tools")
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",") if t.strip()]
        model = fm.get("model")
        agents.append(
            Agent(
                name=name,
                description=description,
                body=body,
                path=entry,
                plugin_key=plugin_key,
                tools=tools if isinstance(tools, list) else None,
                model=str(model) if model else None,
            )
        )
    return agents


def discover_plugin(installed: InstalledPlugin) -> Plugin:
    """Build a Plugin object by walking an installed plugin's directory."""
    manifest = _load_plugin_manifest(installed.install_path)
    description = str(manifest.get("description", ""))
    return Plugin(
        name=installed.name,
        marketplace=installed.marketplace,
        install_path=installed.install_path,
        version=installed.version,
        description=description,
        skills=tuple(_discover_skills(installed.install_path, installed.key)),
        commands=tuple(_discover_commands(installed.install_path, installed.key)),
        agents=tuple(_discover_agents(installed.install_path, installed.key)),
    )


def discover_active_plugins(config_dir: Path) -> list[Plugin]:
    """Return Plugin objects for every plugin that's installed AND enabled."""
    installed = load_installed(config_dir)
    active_keys = active_plugin_keys(config_dir)
    return [discover_plugin(installed[k]) for k in active_keys if k in installed]
