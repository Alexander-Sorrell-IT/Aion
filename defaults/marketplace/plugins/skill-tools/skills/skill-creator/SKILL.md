---
name: skill-creator
description: Create new skills from scratch, modify existing skills, and benchmark skill triggering accuracy. Use when the user asks to "create a skill", "make a skill for X", "improve this skill's description", or "test whether my skill triggers correctly".
---

# skill-creator

A skill is a self-contained chunk of expertise that activates when its description matches the task. The skill machinery is simple; the discipline is in the writing.

## What makes a skill trigger reliably

The triggering decision happens *before* the skill is loaded. The system reads only the `description` frontmatter and decides whether to load the file. So the description does double duty: it summarizes what the skill knows, and it advertises the situations in which the skill applies.

The two failure modes:

1. **Underspecified description** — skill never triggers because the description doesn't mention the situations users actually invoke. Symptom: users keep asking for the thing the skill does, the skill never loads.
2. **Overbroad description** — skill triggers on everything, drowning out other skills. Symptom: the skill loads constantly, including in contexts where it's wrong.

The fix for both is *specific triggering language* — name the situations, the phrasings, the tasks. Not "use this when working with files" (too broad). "Use when the user asks to delete, batch-rename, or recover a file" (specific).

## Skill structure

```
skills/<skill-name>/
├── SKILL.md          (required — the content)
└── references/       (optional — files SKILL.md links into for details)
```

`SKILL.md` frontmatter:
- `name` — kebab-case, matches the directory
- `description` — see above; this is the triggering signal

After the frontmatter, the body has no enforced format. Good bodies have:
- A one-paragraph "what this is" lead
- A "when to act / when not to act" section
- The actual technique or rules
- Common failure modes

## When creating a skill

1. **Name the situation, not the technique.** Skills are named by what triggers them, not by what they do internally. "git-conflict-resolver" beats "three-way-merge".
2. **Description is half the work.** Spend at least as long on the description as on the body. Test it by asking yourself: would I expect this skill to load in this specific context? Would I expect it NOT to load in this nearby context?
3. **Body should answer "how" not just "what".** A skill that says "use TDD" without saying how TDD is applied is dead weight.
4. **Failure modes section is high-leverage.** Most skills are corrected after their first failure. Bake the correction into the skill so it doesn't recur.

## When reviewing a skill

Ask:
- Does the description name *specific* situations or just topics?
- Does the body teach a *procedure*, or just gesture at one?
- Are the failure modes documented, or do you have to learn them by failing?
- Is there content that should be in `references/` to keep the main file scannable?

## When benchmarking a skill

Run the skill against 10–20 prompts: some that should trigger it, some that shouldn't, some adjacent cases that test the boundary. Score:
- True positives (triggered when it should)
- False positives (triggered when it shouldn't)
- False negatives (didn't trigger when it should)

The skill needs adjustment if false-positive rate > 10% or false-negative rate > 20%. Adjust the description first, body second.

## Common failure modes

- **Description hedging** — "may be useful for", "can sometimes apply to" — the trigger needs assertion, not equivocation
- **Body bloat** — repeating the description, restating the obvious, instead of teaching the actual technique
- **Buried trigger** — the actual triggering scenario is mentioned in paragraph 3 of the body, not in the description
