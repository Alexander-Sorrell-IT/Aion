---
name: cli-design
description: Design or improve a command-line tool — argument parsing, help text, error messages, exit codes, output formats. Use when the user is building a CLI, asks "what should this CLI accept?", "how should I structure the commands?", or has a tool with bad UX.
---

# cli-design

Most agent-built CLIs share the same failure modes: no `--help`, opaque error messages, output that's neither human-readable nor machine-parseable, no exit codes. This skill is the checklist.

## When to act

- User is building a new CLI tool
- User says their CLI is hard to use, has bad output, isn't scriptable
- User is designing a subcommand structure ("how should I organize `mytool X Y Z`?")

## When not to act

- User is using an existing well-designed CLI (no design needed; just use it)
- This is a library API, not a CLI

## The checklist

### 1. Help text

EVERY CLI must respond to `--help`, `-h`, and no-args-when-required-args-missing. Help text shows:
- One-line description (what the tool does)
- Usage line: `mytool [OPTIONS] COMMAND ARGS`
- List of subcommands with one-line descriptions
- List of global options
- Example invocation showing a common case

Bad: tool runs forever with no `--help`, exits silently when invoked with no args.

### 2. Subcommand structure

For multi-command CLIs:
- `tool <noun> <verb>` (e.g., `git branch list`, `git remote add`) — generally better when the tool has many object types
- `tool <verb> <noun>` (e.g., `npm install`, `npm publish`) — better when verbs are few and well-known

Pick one and be consistent. Mixing `tool show users` with `tool deploy create` is jarring.

### 3. Flag conventions

- `--long-form` always; `-x` shorthand only for the 5 most-used
- Boolean flags: `--enable-X` / `--disable-X` (paired), or `--X` / `--no-X`
- Path flags: accept absolute and relative; resolve to absolute before use
- File flags: support `-` to mean stdin/stdout where appropriate
- `--verbose` / `-v` for more output (cumulative: `-vv` is even more)
- `--quiet` / `-q` for less; suppresses non-error output but NOT errors

### 4. Error messages

Bad error: "Error" or a stack trace dumped to stdout.

Good error:
- One sentence naming what failed
- One sentence on why (if non-obvious)
- One concrete suggestion for how to recover
- Sent to stderr, not stdout
- Non-zero exit code

```
Error: cannot connect to database at postgres://localhost:5432
Reason: connection refused
Try:    is the database running? `docker compose up -d`
```

### 5. Output discipline

- HUMAN output: stdout, formatted for readability, default
- MACHINE output: opt-in via `--json` or `-o json`; emits parseable JSON, nothing else
- LOGS: stderr, NOT stdout
- NOTHING: don't print "operation complete" if there's no payload; absence of error IS the success signal

The principle: **stdout is for the result, stderr is for everything else**. Scripts pipe stdout; humans read both.

### 6. Exit codes

- 0: success
- 1: generic failure (no specific category)
- 2: misuse — wrong args, unknown flag (POSIX convention)
- 64–78: specific failure classes (see sysexits.h if you want to be rigorous)
- Anything > 128: signal kills

NEVER exit 0 on failure. The number-one CLI bug is exit 0 with an error message — scripts can't tell anything went wrong.

### 7. Scriptable defaults

- Don't ask interactive questions by default; require flags for inputs
- If you do prompt interactively, detect non-TTY (e.g., `isatty(0)`) and either error out or pick a safe default
- Don't paginate output by default; if you do, detect non-TTY and disable
- Don't colorize output by default if stdout isn't a TTY

### 8. Common smells

- Tool that requires CWD to be a specific dir (better: take a path arg, default to CWD)
- Tool that writes to CWD without asking
- Tool that needs root for things that don't need root
- Tool that writes a config to `~/.toolname` on first run without telling the user
- Tool whose `--help` is 3 lines and `--help-full` is 200

## Output

When reviewing a CLI design, run through the checklist and produce:

```
CLI design review for <tool>

Strong points (don't change):
- ...

Issues:
- [BLOCKER] no --help text — users can't discover commands
- [SUGGESTION] error messages don't include suggested fixes

Suggested commands:
- mytool <noun> <verb> ... (because <reason>)
```
