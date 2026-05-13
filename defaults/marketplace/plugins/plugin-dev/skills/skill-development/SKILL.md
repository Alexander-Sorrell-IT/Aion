---
name: skill-development
description: Write a new skill — frontmatter, body structure, triggering language, progressive disclosure. Use when the user asks to "create a skill", "write a new skill", or "add a skill to my plugin".
---

# skill-development

A skill is a self-contained chunk of expertise that loads when its description matches the task. The wire format is two pieces: YAML frontmatter (read for triggering) and Markdown body (read after loading).

## Frontmatter

```yaml
---
name: kebab-case-matching-directory
description: One paragraph naming the SITUATIONS this skill applies to — phrasings, tasks, contexts.
---
```

`description` is the triggering signal — it's all the runtime sees before deciding to load. Two failure modes:
- **Too narrow** → skill never loads; users repeatedly ask for what the skill handles
- **Too broad** → skill loads constantly, drowning others out

Name specific phrasings: "use when the user asks to delete, batch-rename, or recover a file" beats "use when working with files".

## Body structure

No enforced format, but good skills have:

1. **One-paragraph lead** — what this is
2. **When to act / when not to act** — the contract
3. **The technique** — actual procedure, not "use TDD" without saying how
4. **Output discipline** — how to present results
5. **Failure modes** — what previously went wrong; prevents recurrence

## Progressive disclosure

For long reference material, split into a `references/` subdirectory:

```
skills/<name>/
├── SKILL.md          ← main file, scannable
└── references/
    ├── deep-topic.md  ← linked from SKILL.md when needed
    └── examples.md
```

`SKILL.md` references them with relative links: `see [examples.md](references/examples.md)`. The runtime loads SKILL.md immediately; reference files are only read on demand.

## Voice and discipline

- Write to your future self, not to an imagined reader
- Skip the marketing tone ("powerful", "robust", "comprehensive")
- Procedures > principles. Concrete > abstract.
- Document failure modes as you discover them; don't wait for the rewrite

## Testing the trigger

Take 5 prompts where the skill *should* fire and 5 where it shouldn't. For each, read only the description and decide: would I load this? Adjust the description until your simulated decisions match your intent. The `skill-grader` agent automates this if available.
