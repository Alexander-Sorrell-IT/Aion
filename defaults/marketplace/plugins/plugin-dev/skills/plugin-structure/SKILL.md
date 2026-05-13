---
name: plugin-structure
description: Lay out a new plugin's directory and manifest. Use when the user asks to "create a plugin", "scaffold a plugin", "set up plugin.json", or asks about plugin directory layout, component organization, or manifest fields.
---

# plugin-structure

A plugin is a directory with a manifest and any combination of skills, commands, agents, hooks, MCP servers, and settings. The runtime discovers and loads them by walking known sub-directories.

## Required layout

```
<plugin-name>/
├── .claude-plugin/
│   └── plugin.json        ← required manifest
├── skills/                ← optional
│   └── <skill>/SKILL.md
├── commands/              ← optional
│   └── <name>.md
├── agents/                ← optional
│   └── <name>.md
├── hooks/                 ← optional
│   └── hooks.json
├── README.md              ← optional but recommended
└── LICENSE                ← optional
```

The plugin's directory name = the plugin's identifier. The `name` field in `plugin.json` should match.

## plugin.json fields

```json
{
  "name": "kebab-case-name",
  "description": "One-paragraph description used by the marketplace and plugin listings.",
  "version": "semver",
  "author": { "name": "...", "email": "..." },
  "keywords": ["tag1", "tag2"],
  "homepage": "https://...",       // optional
  "repository": "https://...",     // optional
  "license": "MIT"                 // optional
}
```

`name` and `description` are required. Everything else is optional but recommended.

## Component discovery

The runtime looks for these patterns:

| Component | Path pattern | Loaded as |
|---|---|---|
| Skills | `skills/<name>/SKILL.md` | Skill (description-triggered) |
| Commands | `commands/<name>.md` | Slash command `/<plugin>:<name>` |
| Agents | `agents/<name>.md` | Subagent invoked via Agent tool |
| Hooks | `hooks/hooks.json` | Event handlers (PreToolUse, PostToolUse, etc.) |
| MCP servers | declared in `plugin.json` or alongside | Tool/resource providers |

If a sub-directory doesn't exist, the corresponding components simply aren't contributed — no error.

## Naming

- Plugin name: kebab-case, no brand prefix unless the plugin is brand-specific
- Skill names: descriptive of the triggering situation, not the technique
- Command names: imperative ("create-plugin", "audit-memory")
- Agent names: noun describing role ("skill-reviewer", "plugin-validator")

## Common mistakes

- **Manifest in wrong place** — must be in `.claude-plugin/plugin.json`, not at plugin root
- **Skill in wrong nesting** — must be `skills/<name>/SKILL.md`, not `skills/<name>.md`
- **`name` mismatch** — directory name and `plugin.json.name` disagree, runtime gets confused
- **Missing description** — plugin loads but is invisible in `plugin list` and not discoverable
