---
name: hook-development
description: Write hooks for plugin lifecycle events (PreToolUse, PostToolUse, SessionStart, SessionEnd, UserPromptSubmit, etc.). Use when the user asks to "create a hook", "add a PreToolUse hook", "block dangerous commands", or mentions any hook event name.
---

# hook-development

A hook is a shell command (or prompt) the runtime invokes when a specific event fires. Hooks live in `hooks/hooks.json` inside a plugin (or in `~/.proteus/settings.json` for user-level hooks).

## Events

| Event | Fires when | Common use |
|---|---|---|
| `PreToolUse` | Before a tool call | Validate input, block dangerous commands |
| `PostToolUse` | After a tool call | Log, autocommit, post-process |
| `SessionStart` | New session begins | First-run setup, status messages |
| `SessionEnd` | Session ends | Push memory, flush logs |
| `UserPromptSubmit` | User submits a prompt | Inject context, reject patterns |
| `PreCompact` | Before context compaction | Save state |
| `SubagentStop` | A subagent completes | Aggregate results |
| `Notification` | Runtime notification | External signaling |

## Format

```json
{
  "hooks": {
    "<EventName>": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "your shell command here"
          }
        ]
      }
    ]
  }
}
```

`matcher` is a regex against the tool name (for tool-use events) or `"startup"` etc. (for lifecycle events).

## Hook contract

- Must exit `0` (or the agent treats it as a block)
- Stdout is fed back to the agent as additional context (for PreToolUse / UserPromptSubmit) or shown to the user (SessionStart)
- Exit code is your gate: non-zero blocks the action (for blocking events)
- Should be fast — sub-100ms ideal, hooks run on every event match

## Path conventions

Hooks invoked from a plugin should reference resources via:
- `${CLAUDE_PLUGIN_ROOT}` — the plugin's own install directory
- `${CLAUDE_CONFIG_DIR}` — the user's config directory (`~/.proteus`)
- `$HOME` — never; prefer `$CLAUDE_CONFIG_DIR`

```json
{
  "type": "command",
  "command": "\"${CLAUDE_PLUGIN_ROOT}/scripts/my-hook.sh\" \"$CLAUDE_CONFIG_DIR/memory\""
}
```

## Prompt-based hooks

A hook can return a prompt the agent then runs:

```json
{
  "type": "prompt",
  "prompt": "Check the changed files for hardcoded secrets before continuing."
}
```

The agent receives this as a system message and acts on it. Useful for guidance that needs reasoning, not just a shell action.

## Common patterns

**Block dangerous commands:**
```json
{
  "matcher": "Bash",
  "hooks": [{
    "type": "command",
    "command": "echo \"$1\" | grep -qE 'rm -rf /|dd if=' && { echo 'blocked'; exit 1; } || exit 0"
  }]
}
```

**Autocommit memory:**
```json
{
  "matcher": "Write|Edit",
  "hooks": [{
    "type": "command",
    "command": "\"$CLAUDE_CONFIG_DIR/scripts/memory-autocommit.sh\""
  }]
}
```

## Common mistakes

- **Slow hooks** — adds latency to every matching event; profile if it feels sluggish
- **Hooks that block on network** — never; fire-and-forget with `&`
- **Forgetting `exit 0`** — non-zero exit blocks the agent unexpectedly
- **Mutating shared state** — concurrent hooks can race; use file locks if state matters
