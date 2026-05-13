---
description: Scaffold a new plugin with manifest, README, and optional skill/command/agent skeletons.
---

Scaffold a new plugin. Walk the user through:

1. **Name** — kebab-case, no brand prefix unless brand-specific.
2. **Description** — one paragraph for `plugin.json`.
3. **Components** — which to include: skill, command, agent, hook, MCP server (any combination).

Then create the directory structure:

```
<name>/
├── .claude-plugin/
│   └── plugin.json
├── README.md
├── skills/<name>/SKILL.md   (if skill chosen)
├── commands/<name>.md       (if command chosen)
└── agents/<name>.md         (if agent chosen)
```

For each chosen component, write a skeleton file with frontmatter and a brief "fill in the body" comment. Don't write filler — leave it for the author to fill in their actual content.

After scaffolding, suggest the user invoke the `plugin-validator` agent to verify structure, then write the actual content.

Pass-through: $ARGUMENTS
