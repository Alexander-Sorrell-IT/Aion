---
name: dispatching-parallel-agents
description: Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies. Dispatch them in parallel via subagents instead of doing them serially.
---

# dispatching-parallel-agents

Two independent investigations run serially take 2x the time of running them in parallel. The harness can dispatch multiple subagents in a single message and run them concurrently. This skill exists to make sure that happens when it should.

## When to act

You have 2+ tasks where:
- Each task is bounded (clear input, clear output)
- No task depends on another task's output
- Each task is large enough to be worth a subagent's startup cost (not "look up one symbol")

Typical patterns:
- **Multi-area investigation** — survey logging, survey error handling, survey type usage; results inform a refactor
- **Multi-target audit** — check 5 files for the same kind of issue
- **Independent research** — what does library X do for Y, what does library Z do for Y; pick the right one

## When not to act

- Tasks have a dependency chain (B needs A's output)
- One task is much bigger than the others — just do the big one yourself, parallelism doesn't help
- The work is small enough that subagent startup costs more than the savings
- Tasks share mutable state (file writes, branch changes); parallel writes race

## How

In a single message, emit multiple Agent tool calls. They run concurrently and you receive their results together.

```
Agent: investigate logging in src/api/  → report findings
Agent: investigate error handling in src/api/  → report findings
Agent: investigate type usage in src/api/  → report findings
```

All three run in parallel; you get three reports back.

## Brief each subagent well

Each subagent starts cold — no memory of this conversation. Give them:
- The specific question to answer
- Where to look (paths, patterns)
- The output format you want
- A word-count cap on the report

Bad brief: "look at the API layer"
Good brief: "Survey src/api/**/*.ts for raw try/catch blocks. For each, report the file, the catch block's behavior, and whether it swallows the error vs re-throws. Under 200 words."

## Don't duplicate work yourself

If you delegated research to subagents, don't also do the research yourself. Their job is to insulate your context from the raw tool output. Wait for their reports, then synthesize.

## Common failure modes

- **Sequential when parallel was possible** — three Agent calls in three messages instead of one
- **Parallel with dependencies** — second task needed the first's output; you fork a wasted run
- **Under-briefed subagents** — vague task in, vague report out
- **Over-parallelism** — dispatching 8 subagents for what could be one; coordination overhead exceeds the parallelism win
- **Synthesizing badly** — three reports come back, you concatenate them instead of distilling them
