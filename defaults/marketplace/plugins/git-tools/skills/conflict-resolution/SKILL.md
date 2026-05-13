---
name: conflict-resolution
description: Resolve a git merge or rebase conflict. Use when the user encounters a conflict marker, says "conflict", "merge conflict", "rebase failed", or has files with `<<<<<<<` markers.
---

# conflict-resolution

A merge conflict means git can't auto-pick between two changes. Resolving it means choosing or combining intentionally — not just deleting markers until it compiles.

## When to act

- User mentions a conflict, failed merge/rebase, or files with `<<<<<<<` markers
- `git status` shows files in "Unmerged paths"

## When not to act

- Conflict-free merges (just run the merge, no skill needed)
- User wants to abort, not resolve (`git merge --abort`, `git rebase --abort`)

## The procedure

1. **Understand the operation in flight.**
   - `git status` — what are we doing? Merge? Rebase? Cherry-pick?
   - In rebase: which commit are we replaying? `git rebase --show-current-patch | head`
2. **List the conflicted files.**
   - `git diff --name-only --diff-filter=U`
3. **For each conflicted file: understand BOTH sides.**
   - The `<<<<<<< HEAD` block is YOUR current branch.
   - The `>>>>>>> <ref>` block is the OTHER side.
   - Read the surrounding code. What was each side trying to do?
4. **Decide:** keep one side, the other, or combine.
   - "Combine" is the usual answer for genuine conflicts. Not "concatenate both" — actually merge the intent.
   - If you can't tell which to keep, ASK THE USER. Don't guess.
5. **Remove the markers** including `<<<<<<<`, `=======`, `>>>>>>>`.
6. **Test the file.** Run the relevant test or linter. A "compiles" check is not enough — the merged code may be wrong.
7. **Stage**: `git add <file>`
8. **Continue the operation**: `git merge --continue` or `git rebase --continue`. NOT `git commit` directly during a rebase.

## Common mistakes

- **Markers left in code** — file appears resolved but markers stayed; tests catch this if you actually run them
- **Picking by "looks newer"** — newer code isn't necessarily right; understand intent
- **Aborting mid-rebase by running `git commit`** — that creates a detached commit and breaks the rebase
- **Resolving without testing** — code compiles but behavior is broken; merged tests give you a checkpoint
- **Bulk-accepting one side via `git checkout --theirs <file>`** — sometimes correct, often hides real conflicts

## When the conflict is too tangled

- Abort: `git merge --abort` or `git rebase --abort`
- Re-approach: maybe a different merge strategy, or splitting the work, or rebasing piecemeal commit-by-commit
- Ask the user how to proceed before doing anything destructive

## Output

For each file resolved, report:
- Which side you kept, kept both, or how you combined
- Why
- What test you ran to verify

Don't just say "resolved" — show your reasoning so the user can spot a wrong choice before it ships.
