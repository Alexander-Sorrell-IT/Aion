---
name: branch-hygiene
description: Manage branch state — list active vs stale, prune merged branches, identify branches whose upstream is gone. Use when the user says "clean up branches", "what branches do I have", "delete merged branches", or "branch went stale".
---

# branch-hygiene

Most repos accumulate dead branches: merged-and-forgotten, abandoned, or with a remote that no longer exists. Cleaning them up keeps `git branch` readable and prevents pushing to dead refs.

## When to act

- User says "clean up branches", "delete old branches", "branches are a mess"
- After a merge, when the user wants to remove the merged branch
- "Why does git say my branch is gone?"

## When not to act

- User is asking about branch naming conventions (different skill)
- User wants to create a new branch (just create it)
- Repo has < 5 branches (no hygiene needed)

## Categories of branches

| Category | How to detect | Action |
|---|---|---|
| **Active** | Has commits ahead of main, recent activity | Leave alone |
| **Merged** | `git branch --merged main` lists it | Safe to delete (`git branch -d`) |
| **Gone** | `git branch -vv` shows `[gone]` after the name — upstream was deleted | Safe to delete, possibly with prejudice (`-D`) |
| **Stale-active** | Has unmerged commits but no activity in months | Ask user — might be in-progress, might be abandoned |
| **Current** | Currently checked out | Never delete this one |

## The pipeline

1. `git fetch --prune` — sync remote state and clean up dead remote-tracking branches
2. `git branch -vv` — shows each branch with its upstream and a `[gone]` marker if upstream is gone
3. `git branch --merged main` — branches whose tip is reachable from main
4. List candidates by category, get user approval, then delete

## Safe deletion

- `git branch -d <name>` — refuses to delete if branch has unmerged commits (safe default)
- `git branch -D <name>` — forces delete (use only when sure, e.g. after explicit confirmation or for `[gone]` branches)

## What NEVER to delete without asking

- The current branch (you can't anyway)
- main / master / trunk / your team's default
- Anything tagged or referenced by an open PR
- Branches with `WIP` in the name (might be in-progress work)

## Output

Group by category. Ask for confirmation before each deletion, OR ask once with a bullet list and a "proceed?" — never delete branches in bulk without explicit user approval.

```
Branches found (12 total):
  Active (3): feature-x, hotfix-y, refactor-z
  Merged (5): old-feature-1, old-feature-2, ...
  Gone (3): pr-1234, dead-experiment, abandoned-poc
  Stale-active (1): six-month-old-wip — what should I do with this one?

Proceed with deleting the 5 merged + 3 gone branches? (y/n)
```
