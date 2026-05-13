---
name: brainstorming
description: Use BEFORE any creative or design work — creating features, building components, adding functionality, modifying behavior. Explores user intent, requirements, and design before implementation. Activates on "let's build", "design a system for", "add a feature that", "I want to make".
---

# brainstorming

You and the user are about to build something. Before you write code, you need to be sure you're building the right thing. This skill exists because the default failure mode is to start implementing before the problem is understood, then refactor or rewrite when the assumptions break.

## When to act

- User says "let's build X", "design a system for Y", "I want to add Z"
- User describes a problem and you're about to propose a solution
- You're about to start coding and don't have a written shape of what you're building

## When not to act

- The work is mechanical: rename a variable, fix a typo, apply a known recipe
- The user has already specified shape concretely and just wants execution
- Continuing an in-progress build where shape was already decided

## The pass

Don't just ask questions. Probe specific dimensions:

1. **What problem does this solve?** Not "what does it do" — what user pain or system gap is being addressed. If you can't name it, the feature is speculative.
2. **Who is the user?** Same product can have wildly different shapes depending on whether it's for an end-user, an admin, an integrator, or yourself.
3. **What's the minimum that's useful?** Strip until you find the version that gets value to the user. Often half of what was proposed.
4. **What's the failure mode?** Every feature has a way it ends badly. Name it now.
5. **What's already there?** Does this overlap with existing code? Can the existing thing be extended instead of adding new?
6. **What's the boundary?** What's NOT included that you might think is included?

## Output

After the pass, produce a one-paragraph summary back to the user:

> Building **X**. Users **A** can **B** in order to **C**. Out of scope: **D**, **E**. Main risk: **F**. Smallest useful version: **G**.

Get user agreement on this before any code. If they push back, redo the pass.

## Common failure modes

- **Asking too many questions** — five questions when two would do. Be specific, not exhaustive.
- **Asking abstract questions** — "what's the goal?" gets vague answers. "Will this be used by humans clicking buttons or by another service via API?" gets useful answers.
- **Building anyway** — running the pass, then ignoring what it surfaced, is worse than skipping it.
- **Premature solutioning** — proposing implementations during the pass. The pass is about the problem; the solution comes after.
