# plugin-dev

Toolkit for building plugins.

| Component | Triggered by |
|---|---|
| `plugin-structure` skill | "create a plugin", "scaffold plugin", "set up plugin.json" |
| `skill-development` skill | "create a skill", "add a skill" |
| `command-development` skill | "create a slash command", "add a command" |
| `agent-development` skill | "create an agent", "add a subagent" |
| `hook-development` skill | "create a hook", any hook event name |
| `mcp-integration` skill | "add MCP server", "integrate MCP" |
| `plugin-settings` skill | "configure plugin", "per-project plugin state" |
| `plugin-validator` agent | "validate my plugin", "check plugin structure" |
| `/create-plugin` command | Scaffold a new plugin |

Skills teach the patterns; the validator agent enforces structural correctness; the command scaffolds the boilerplate.
