---
name: md-improver
description: Audit and improve the project's primary memory file (the one auto-loaded into every session — PROTEUS.md, CLAUDE.md, or whatever the active brand configures). Use when the user asks to update, refresh, fix, or check project memory, or after a session that taught a durable, non-obvious fact about the codebase.
---

# md-improver

The project memory file is the single most-loaded document each session — every line costs context every turn. Words there have to earn their place.

## When to act

- User asks: "update memory", "audit memory file", "fix the project doc"
- After a session revealed something durable and non-obvious — a load-bearing convention, a hidden constraint, a decision the user defended that contradicts a default
- When the file claims something the code no longer supports

## When not to act

- After every session — most teach nothing durable
- For ephemeral state (that's the conversation)
- To duplicate `git log`, `git blame`, or the root README

## The audit pass

Read the file. For each section ask:

1. **Still true?** If the code moved past it, mark stale.
2. **Derivable?** If `grep`, `git log`, or the README would teach this in 60 seconds, it doesn't belong here.
3. **Why visible?** A rule without a reason rots. Add the why or drop the rule.
4. **Specific?** "Write good tests" is noise. "Tests in `tests/integration/` must hit a real DB — mocks masked a broken migration last quarter" is signal.

Cut anything that fails any check.

## The capture pass

After cutting, sweep the session for content that belongs:

- Constraints surfaced explicitly ("never do X because Y")
- Architecture decisions not documented elsewhere
- Collaboration preferences that affect HOW to work ("single bundled PR over many small ones for this repo")
- Pointers to authoritative external info (Linear project, dashboard URL)

Each entry: lead with the rule. Add **Why:** for reasoning. Add **How to apply:** when non-obvious.

## Format discipline

- Sections by topic, not chronology
- One-line index entries; details in sub-files when needed
- Top-level file lines past ~200 may get truncated — keep the master tight
- Link related sections; sub-files live in a `memory/` subdirectory

## Output

Show a unified diff before writing. If the user redirects, redo — don't argue judgment calls about their own project memory.

## Failure modes to watch

- **Recency bias** — promoting one-session revelations to permanent memory before they recur
- **Over-documenting** — capturing what the code already shows
- **Tone drift** — writing for an imagined audience instead of your future self
