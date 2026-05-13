---
name: agent-development
description: Write a subagent — frontmatter, tool scoping, system prompt, when-to-use description. Use when the user asks to "create an agent", "add a subagent", "write an agent", or asks about agent tools, agent prompts, or autonomous-agent patterns.
---

# agent-development

A subagent is a Markdown file in `agents/`. It's spawned via the Agent tool, runs in its own context, and returns a single result to the parent agent.

## File format

```markdown
---
name: kebab-case-matching-filename
description: When the parent agent should dispatch this subagent. Triggers and use cases here.
tools: Read, Grep, Glob       # optional: tool whitelist
model: sonnet                 # optional: cheaper model
---

The system prompt the subagent runs with.

Be explicit about: what input it receives, what it should produce, how it should format output, and what it should NOT do (avoid scope creep).
```

## When to use a subagent vs handling inline

Use a subagent when:
- The work is **bounded** — clear input, clear output, no follow-up
- The work is **read-heavy** — would pollute the parent's context with tool results
- The work is **parallelizable** — multiple independent investigations
- The work uses a **specialized prompt** — different voice or constraint than the parent

Don't use a subagent when:
- The task requires back-and-forth with the user
- The task needs the parent's accumulated context
- It's a single tool call you could just make directly

## Description quality

The `description` is the triggering signal — the parent decides whether to dispatch based purely on this. Like skills, name specific situations:

> **Good:** Use this agent after a developer creates or modifies a skill, or asks to "review my skill", "check skill quality", or "improve skill description". Trigger proactively after skill creation.

> **Bad:** Use this agent for skill-related tasks.

Add concrete `<example>` blocks if the trigger is subtle:

```markdown
description: ...

<example>
user: "I've added documentation to these functions"
assistant: "Let me use the comment-analyzer agent to verify accuracy"
<commentary>User added comments — proactively audit for drift.</commentary>
</example>
```

## Tool scoping

`tools` whitelists what the subagent can use. Minimize: a code-reviewer that doesn't need Edit shouldn't have it. Common patterns:

- **Read-only investigators**: `Read, Grep, Glob, Bash` (and lock Bash to safe commands via permissions)
- **Doc generators**: `Read, Grep, Write`
- **Validators**: `Read, Bash, Grep`

If omitted, the subagent inherits everything the parent has — usually too broad.

## System prompt

Subagent system prompts should be short and contract-shaped:

1. What you receive (e.g., "You will be given a path to a plugin directory")
2. What you do (the procedure)
3. What you return (format, length cap)
4. What you don't do (scope creep, side effects)

A 50-line system prompt usually beats a 500-line one.

## Common mistakes

- **Vague description** → parent never dispatches; subagent is dead weight
- **No output format spec** → subagent returns prose that the parent then has to parse
- **Wide tool grant** → subagent takes side actions the parent didn't intend
- **Trying to do too much** → multiple bounded subagents > one mega-agent
