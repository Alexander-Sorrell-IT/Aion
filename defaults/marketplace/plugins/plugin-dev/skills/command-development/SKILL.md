---
name: command-development
description: Write a slash command — frontmatter, arguments, file references, interactive prompts. Use when the user asks to "create a slash command", "add a command", "write a custom command", or asks about command frontmatter, $ARGUMENTS, or command organization.
---

# command-development

A slash command is a single Markdown file. It's invoked as `/<command-name>` (or `/<plugin>:<command-name>` when scoped to a plugin) and expands into a prompt the agent then runs.

## File format

```markdown
---
description: One-line description shown in the command picker.
allowed-tools: Bash, Read, Edit   # optional whitelist
---

The prompt body. This is what the agent sees as a user message when the command fires.

Use $ARGUMENTS to interpolate whatever the user typed after the command name.
Use @<path> to inline a file's contents into the prompt at expansion time.
```

## Frontmatter fields

| Field | Required | Effect |
|---|---|---|
| `description` | yes | Shown in the picker; must be one line |
| `allowed-tools` | no | Comma-separated allow-list. If present, the agent can only use these tools during the command. |
| `argument-hint` | no | Placeholder text shown in the picker (`/cmd <argument-hint here>`) |
| `model` | no | Override which model runs this command |

## Arguments

`$ARGUMENTS` expands to everything after the command name. The user types `/audit memory.json` and your body sees `$ARGUMENTS = "memory.json"`.

For commands that take no arguments, omit `$ARGUMENTS` entirely.

## File references

`@path/to/file` inlines the file contents into the prompt at expansion time. Useful for commands that always operate on a specific config file.

```markdown
Review the current settings: @~/.proteus/settings.json

Suggest changes given the user's request: $ARGUMENTS
```

## Interactive commands

A command body can ask the user a question. The agent will use whatever question-asking mechanism is available (e.g., AskUserQuestion). Frame the question explicitly in the prompt:

```markdown
Ask the user which file to operate on, then run the analysis on the selected file.
```

## Organization

Commands live in `commands/`. Subdirectories ARE supported; they show up as `/sub:name` in the picker.

```
commands/
├── audit.md           → /audit
├── memory/
│   └── revise.md      → /memory:revise
└── debug/
    └── trace.md       → /debug:trace
```

## Common mistakes

- **Multi-line description** — the picker truncates; keep it one line
- **Missing `description`** — command loads but is hidden from the picker
- **Tool over-permission** — `allowed-tools: *` defeats the point; pin to what the command actually needs
- **`$ARGUMENTS` typo** — `${ARGUMENTS}` and `$ARG` don't work; only `$ARGUMENTS`
