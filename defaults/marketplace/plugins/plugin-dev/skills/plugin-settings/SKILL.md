---
name: plugin-settings
description: Make a plugin user-configurable. Use when the user asks about "plugin settings", "user-configurable plugin", per-project plugin config, or wants to store plugin state across sessions.
---

# plugin-settings

A plugin that does the same thing for every user is boring. A plugin that lets each user dial it in is useful. Three places to store config, three reasons to pick each.

## Three storage locations

| Location | Lifetime | Use for |
|---|---|---|
| `~/.<config-dir>/settings.json` (user level) | Persistent, global | User-wide preferences (theme, keybindings) |
| `<project>/.<config-dir>/settings.local.json` | Persistent, per-project | Project-specific overrides (target API, env) |
| `<project>/.<config-dir>/<plugin>.local.md` | Persistent, per-project | Free-form plugin state with YAML frontmatter |

The third pattern (per-project plugin state file) is most flexible. Format:

```markdown
---
enabled: true
api_target: https://staging.example.com
last_sync: 2026-05-13T08:21:00Z
---

# Notes section (markdown, ignored by the plugin)

The user can write notes here that won't break the YAML parsing.
```

The plugin reads/writes the frontmatter; the markdown body is for the user.

## Reading config from a skill

A skill in your plugin can read the per-project state file via the agent:

```markdown
Before proceeding, read `.<config-dir>/my-plugin.local.md` for project-specific configuration. If `enabled: false` in the frontmatter, abort the operation with a message and don't continue.
```

The agent does the actual file read — your skill just tells it where to look and how to interpret.

## Writing config from a command

A `/configure-myplugin` command can write the local file:

```markdown
---
description: Configure my-plugin for this project
---

Walk the user through the my-plugin configuration:
1. Ask which API target (production / staging / local)
2. Ask whether to enable autocommit
3. Write `.<config-dir>/my-plugin.local.md` with their answers
```

## settings.json format (user-level)

If your plugin needs to register hooks, modify allowed-tools, or set env vars, it goes through user-level settings:

```json
{
  "hooks": { ... },
  "env": { "MY_PLUGIN_FLAG": "true" },
  "enabledPlugins": {
    "my-plugin@my-marketplace": true
  }
}
```

Merge carefully — don't clobber existing keys. Use a JSON merge tool or Python `json` module.

## When to use which

- **User-level (`~/...`)** — settings the user wants across all their projects (e.g., default model, keybindings)
- **Project local** — overrides for *this* project (e.g., this project uses staging)
- **Plugin `.local.md`** — anything you don't want in the user's main settings.json

## Common mistakes

- **Plugin state in the user-wide settings.json** — clutters the file, hard to remove cleanly
- **Hardcoded paths in stored config** — breaks portability across machines
- **No defaults** — first-run experience is "set 12 things before anything works"; pick sane defaults
- **Schema drift** — old config files don't have new fields; version your config and migrate explicitly
