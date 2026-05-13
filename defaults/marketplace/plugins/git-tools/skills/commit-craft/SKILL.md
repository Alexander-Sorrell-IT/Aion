---
name: commit-craft
description: Write a good commit message. Use when the user asks to "commit", "write a commit message", or has staged changes and is about to commit.
---

# commit-craft

A commit message is documentation that ships with the change forever. The diff shows WHAT changed. A good message explains WHY.

## When to act

- User says "commit", "git commit", "make a commit"
- User has staged changes (`git diff --cached` non-empty) and is about to run commit

## When not to act

- User is just exploring git state ("show me status", "what changed")
- User is amending an existing commit (different skill needed for that)
- User explicitly says "commit with message X" — they've already authored it

## The procedure

1. Read what's staged: `git diff --cached --stat` for shape, `git diff --cached` for detail.
2. Read recent commits: `git log --oneline -10` to learn this repo's style — imperative vs past tense, prefix conventions, line lengths.
3. Determine the change type:
   - `add` — new feature, new file, new capability that didn't exist before
   - `fix` — corrects a bug; should reference the bug if a ticket exists
   - `refactor` — rearranges code; behavior unchanged (verify with tests!)
   - `docs` — only documentation changed
   - `test` — only tests changed
   - `chore` — deps, build config, formatting; no behavior change
4. Write the message in two parts:
   - Subject: one line, imperative, <= 72 chars, capitalized, no trailing period
   - Body (when needed): blank line, then paragraphs explaining WHY this change, not what

## Subject quality

| Bad | Why bad | Better |
|---|---|---|
| `update file.py` | What did you change about it? | `fix off-by-one in pagination cursor` |
| `bug fixes` | Which bug? | `fix race condition in session cleanup` |
| `wip` | Don't ship WIP commits | wait until it's done; then squash |
| `Fixed the thing where users couldn't log in.` | Past tense + period | `fix login regression for users with expired tokens` |

## Body quality

Include a body when:
- The WHY isn't obvious from the subject
- The change has subtle implications another reader should know
- There's a non-obvious test plan
- It fixes an issue worth referencing (e.g., `Fixes #1234`)

Skip the body when:
- The subject is self-explanatory and complete
- The change is trivial

## Anti-patterns

- **Including the diff in the message** — git already has the diff
- **Speculative future work** — "this will eventually..." (cut)
- **Apologies** — "sorry for the big change" (cut)
- **Generated tags you don't own** — don't add Co-Authored-By unless the user asked

## Output

Show the user the proposed message FIRST, then commit only after they accept (or you have prior authorization). Format the proposed message clearly so they can scan it. If they request changes, redo.
