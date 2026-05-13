---
description: Prune local branches whose upstream remote branch has been deleted. Lists candidates first, then deletes after confirmation.
---

Use the branch-hygiene skill to identify branches in the `[gone]` category (upstream remote deleted) and present them as deletion candidates. After user confirms, delete with `git branch -D <name>` for each. Pass-through: $ARGUMENTS
