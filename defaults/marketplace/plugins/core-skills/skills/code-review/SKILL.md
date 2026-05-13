---
name: code-review
description: Use when reviewing a diff/PR/change-set, or when receiving review feedback on your own work. Covers both sides — spotting real issues without bikeshed, and responding to feedback without performative agreement or blind implementation.
---

# code-review

Code review is two-sided. This skill covers both sides because they're skills of the same shape: distinguishing real issues from noise, and updating your model when warranted.

## When to act (reviewing)

- User asks "review this PR", "look at this diff", "check this change"
- A diff was just produced and the user wants quality control before commit
- Working through an existing PR with review tools

## When to act (receiving)

- The user passes review feedback to you and asks you to address it
- You're about to implement a reviewer's suggestion

## When not to act

- Code generation tasks where the user just wants the code, not a quality pass
- Trivial mechanical changes

## Reviewing — what to look for

In priority order:

1. **Correctness.** Does it do what it says? Read the diff and trace the logic. Look for off-by-one, missing branches, wrong default.
2. **Safety.** Security issues, data loss, race conditions, unhandled errors that matter.
3. **Tests.** Is the change covered? Would the test catch a regression? Is the test testing behavior or implementation?
4. **Design.** Does the change fit? Is there an abstraction being violated? Is there a simpler shape?
5. **Style.** Names, formatting, conventions. Lowest priority — don't lead with style.

Skip:
- Comments about preferences ("I'd have used a map here") that don't materially help
- Restating what the code does ("this function reads the file")
- Nitpicks below the level the user cares about

## Reviewing — output format

```
Critical:
- <file>:<line> — <issue and why it matters>

Suggestions:
- <file>:<line> — <change and rationale>

Questions:
- <file>:<line> — <what you don't understand or want confirmed>
```

Lead with critical. If there are none, say so explicitly — "no critical issues, just suggestions" — so the user doesn't have to scan.

## Receiving — the discipline

The default failure mode for receiving review is performative agreement: thank reviewer, implement all suggestions, ship. That's bad in two directions: you implement bad suggestions, and you fail to defend good decisions.

For each piece of feedback:

1. **Understand it.** What is the reviewer claiming? If you don't understand, ask. Don't guess and implement.
2. **Evaluate it.** Is the reviewer right? Use evidence — re-read the code, check the test, run the thing. Don't yield because the reviewer is senior; don't dig in because they're junior.
3. **Act, defer, or push back.**
   - **Act**: the suggestion is right. Implement.
   - **Defer**: it's right but out of scope. Open a follow-up issue; don't expand the PR.
   - **Push back**: the suggestion is wrong (or right but for the wrong reason). Reply with your reasoning. Reviewers update when shown evidence.

## Receiving — common failure modes

- **Blind implementation** — accepting all feedback without evaluation; ends up with worse code than before
- **Defensive rejection** — dismissing feedback to protect your work; misses real issues
- **Implementing the literal suggestion when the underlying concern was different** — reviewer says "use a Map" because they're worried about lookup performance; you use a Map but the actual hot path was elsewhere
- **Performative thanks** — "great feedback, will do" without actually doing; reviewer notices, trust erodes

## Reviewing — common failure modes

- **Style bikeshed** — leading with formatting issues when there's a correctness bug below
- **Vague feedback** — "this feels off"; if you can't say why, you can't help
- **Reviewing against your preferences** — you'd do it differently is not the same as it's wrong
- **Missing the diff scope** — flagging existing issues in unchanged code; out of scope
- **Approving without reading** — the worst version of review
