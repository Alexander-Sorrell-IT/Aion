---
name: release-tagging
description: Tag and version a release. Use when the user says "cut a release", "bump version", "tag a release", or is about to ship code. Covers semver decisions, tag commands, and changelog discipline.
---

# release-tagging

A release is the artifact users install. The tag is how they find it. This skill prevents the usual mistakes: version-bump-but-no-tag, tag-but-no-changelog, breaking-change-in-a-patch-version.

## When to act

- User says "release", "cut a release", "tag a release", "bump version"
- Code is ready to ship and the version/tag hasn't moved yet

## When not to act

- Pre-1.0 hobby projects where versioning doesn't matter (just use git SHAs)
- The user just wants to push to main without a release artifact

## Semver decisions

Given a current version `MAJOR.MINOR.PATCH`:

- **PATCH bump** (1.2.3 → 1.2.4): bug fixes only. No new features, no API changes, no behavior changes a user would notice as different.
- **MINOR bump** (1.2.3 → 1.3.0): new features. Backwards-compatible. Existing users don't have to change anything.
- **MAJOR bump** (1.2.3 → 2.0.0): breaking changes. Users will have to update their code/config. Includes removals, renames, behavior changes that aren't bug fixes.

When in doubt, bump higher. Going from 1.2.3 → 1.3.0 when 1.2.4 would have done is harmless; the reverse is poisonous.

## The procedure

1. **Decide the version.** Read the diff since the last tag. Categorize: patch/minor/major.
2. **Update the version in code.** `package.json`, `pyproject.toml`, `Cargo.toml`, whatever the project uses. ONE source of truth.
3. **Update CHANGELOG.md.** New section for the new version. Group entries: Added / Changed / Fixed / Removed / Security.
4. **Commit the version bump.** Subject: `release: 1.3.0` (or your repo's convention).
5. **Tag the commit.** `git tag -a v1.3.0 -m "Release 1.3.0"`. Annotated tags (with `-a`) include the author + date.
6. **Push the tag.** `git push origin v1.3.0`. CI usually picks this up to build artifacts.
7. **Build and publish the artifact** (npm publish, docker push, github release, etc.). This is what users actually install.

## Tag naming

- `v1.2.3` (with the `v` prefix) is the dominant convention for Git tags
- `1.2.3` (no prefix) is the dominant convention for package.json/Cargo.toml versions

Yes this is inconsistent. Live with it.

## Changelog discipline

Keep CHANGELOG.md in the repo. Format:

```markdown
# Changelog

## [1.3.0] — 2026-05-13

### Added
- Foo subcommand for bar
- --json output mode

### Fixed
- Race condition in baz cleanup

## [1.2.4] — 2026-05-01

### Fixed
- Crash on empty input

## [1.2.3] — 2026-04-12
...
```

A user should be able to read CHANGELOG.md and decide whether to upgrade. If you can't write a useful changelog entry, the change probably wasn't worth releasing as its own version.

## Common mistakes

- **Version in code but no tag** — package shows 1.3.0 but `git log` doesn't have a tag; users can't pin
- **Tag but no version bump** — `git log` has v1.3.0 but package.json still says 1.2.4; users get the wrong version
- **Breaking change in a minor bump** — users on auto-update get surprised
- **No changelog** — users have to read the diff to know what changed
- **Tagging mid-flight** — tag points at a commit that doesn't include the version bump
