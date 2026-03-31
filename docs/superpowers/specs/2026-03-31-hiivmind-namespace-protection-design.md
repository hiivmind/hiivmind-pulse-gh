# Design: .hiivmind Namespace Protection During Init

**Date:** 2026-03-31
**Status:** Approved

## Problem

During `gh-init`, when a parent `.hiivmind/github/config.yaml` exists, the model sometimes recommends deleting the child repo's entire `.hiivmind/` directory. This destroys configurations for other plugins (e.g., hiivmind-corpus) that also store data under `.hiivmind/`.

### Root Cause

Two gaps in the init skill's parent-detection block (lines 60-86 of `skills/gh-init/SKILL.md`):

1. **Option 1 ("Use parent config") has no implementation steps.** The model improvises, and sometimes concludes that the local `.hiivmind/` is "redundant" and should be deleted.
2. **Nothing explains that `.hiivmind/` is a shared namespace.** The model treats it as if it belongs entirely to hiivmind-pulse-gh.

## Solution

Add explicit namespace protection and concrete implementation steps across three files.

### Change 1: `skills/gh-init/SKILL.md` (lines 60-86)

Rewrite the parent-detection block:

**Add warning before options:**

```markdown
**CRITICAL — NEVER delete a `.hiivmind/` directory.** It is a shared namespace used by
multiple plugins (github, corpus, etc.). Only `.hiivmind/github/` is managed by this plugin.
The `.hiivmind/` directory may contain configurations for other plugins besides this one.
```

**Rewrite options from 3 to 4, with concrete steps for Option 1:**

```
Options:
1. Symlink to parent (recommended for workspace setup)
2. Create local config for this repo only
3. Re-initialize parent config
4. Do nothing (use parent config via relative path resolution)
```

**Option 1 implementation:**

```bash
# If .hiivmind/github already exists locally, back it up
if [[ -d ".hiivmind/github" && ! -L ".hiivmind/github" ]]; then
    mv .hiivmind/github .hiivmind/github.bak
fi
mkdir -p .hiivmind
ln -sfn ../.hiivmind/github .hiivmind/github
```

This creates a symlink at `.hiivmind/github` pointing to `../.hiivmind/github`, preserving any other content in the local `.hiivmind/` directory.

### Change 2: `lib/patterns/workspace-detection.md`

Add a "CRITICAL" section near the top of the parent directory detection section:

```markdown
### CRITICAL: `.hiivmind/` Is a Multi-Plugin Namespace

The `.hiivmind/` directory is shared across multiple hiivmind plugins:
- `.hiivmind/github/` — hiivmind-pulse-gh (this plugin)
- `.hiivmind/corpus/` — hiivmind-corpus
- Other plugins may add their own subdirectories

**NEVER delete, move, or replace a `.hiivmind/` directory.** Only operate on
`.hiivmind/github/` which is this plugin's subdirectory.
```

No changes to the detection algorithm — it already correctly looks for `.hiivmind/github/config.yaml`.

### Change 3: `lib/patterns/config-parsing.md`

Add a one-liner warning alongside the existing "IMPORTANT" note about parent directories:

```markdown
**CRITICAL:** This plugin only manages `.hiivmind/github/`. The parent `.hiivmind/`
directory is a shared namespace across plugins — NEVER delete or replace it.
```

## Scope

### What changes
- 3 files: init skill, workspace-detection pattern, config-parsing pattern
- All changes are to instruction documents (Markdown), not runtime code

### What does NOT change
- Detection algorithm (already correct)
- Other skills (`gh-operations`, `gh-refresh`, etc.) — they only read config, never create/delete folders
- Any runtime behavior — these are LLM instruction documents

## Success Criteria

- The model never recommends deleting `.hiivmind/` during init
- Option 1 creates a symlink instead of leaving implementation to the model's discretion
- Existing `.hiivmind/` content (corpus configs, etc.) is preserved in all scenarios
