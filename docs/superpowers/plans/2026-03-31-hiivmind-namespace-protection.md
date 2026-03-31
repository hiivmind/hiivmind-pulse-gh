# .hiivmind Namespace Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent the model from recommending deletion of `.hiivmind/` directories during init by adding namespace warnings and concrete symlink implementation steps.

**Architecture:** Three Markdown file edits — init skill gets rewritten parent-detection block with symlink option, two pattern files get namespace warnings. All changes are LLM instruction documents, not runtime code.

**Tech Stack:** Markdown only.

---

### Task 1: Add namespace warning and rewrite parent-detection block in gh-init

**Files:**
- Modify: `skills/gh-init/SKILL.md:60-86`

- [ ] **Step 1: Replace the existing "Check for Existing Config" section**

In `skills/gh-init/SKILL.md`, replace lines 60-86 (from `### Check for Existing Config` through the end of the options block, up to but not including `### What to Do`) with:

```markdown
### Check for Existing Config

**IMPORTANT:** Before initializing, check if config already exists in current or parent directory:

```bash
if [[ -f ".hiivmind/github/config.yaml" ]]; then
    echo "Config found in current directory"
    EXISTING_CONFIG=".hiivmind/github/config.yaml"
elif [[ -f "../.hiivmind/github/config.yaml" ]]; then
    echo "Config found in parent directory"
    EXISTING_CONFIG="../.hiivmind/github/config.yaml"
fi
```

**CRITICAL — NEVER delete a `.hiivmind/` directory.** It is a shared namespace used by multiple plugins (github, corpus, etc.). Only `.hiivmind/github/` is managed by this plugin. The `.hiivmind/` directory may contain configurations for other plugins besides this one.

**If config exists in parent:**
```
Found existing workspace config in parent directory: ../.hiivmind/github/config.yaml

This is common for workspace setups where multiple repos share one config.

Options:
1. Symlink to parent (recommended for workspace setup)
2. Create local config for this repo only
3. Re-initialize parent config
4. Do nothing (use parent config via relative path resolution)

Which would you like? [1/2/3/4]
```

**Option 1 implementation (symlink to parent):**

```bash
# If .hiivmind/github already exists locally, back it up
if [[ -d ".hiivmind/github" && ! -L ".hiivmind/github" ]]; then
    mv .hiivmind/github .hiivmind/github.bak
fi
mkdir -p .hiivmind
ln -sfn ../.hiivmind/github .hiivmind/github
```

This creates a symlink at `.hiivmind/github` pointing to `../.hiivmind/github`, preserving any other content in the local `.hiivmind/` directory (e.g., corpus configs). After symlinking, verify with `ls -la .hiivmind/github` and confirm it points to the parent. Then skip to Phase 6 (VERIFY).

**Option 2:** Proceed with normal initialization — creates a separate `.hiivmind/github/config.yaml` in this repo.

**Option 3:** Use `$EXISTING_CONFIG` path and re-run discovery against it, overwriting the parent config.

**Option 4:** Do nothing — other skills already resolve config from parent directories via relative path. Skip to Phase 6 (VERIFY).
```

- [ ] **Step 2: Verify the edit**

Read `skills/gh-init/SKILL.md` lines 54-110 and confirm:
- The CRITICAL warning is present before the options
- There are 4 options (not 3)
- Option 1 has concrete bash implementation steps
- The `### What to Do` section (line 88 onwards in the original) is intact

- [ ] **Step 3: Commit**

```bash
git add skills/gh-init/SKILL.md
git commit -m "fix: add namespace protection and symlink option to gh-init parent detection"
```

---

### Task 2: Add namespace warning to workspace-detection pattern

**Files:**
- Modify: `lib/patterns/workspace-detection.md:13-20`

- [ ] **Step 1: Insert namespace warning after the "Config Location Strategy" heading**

In `lib/patterns/workspace-detection.md`, insert the following block immediately after line 13 (`## Config Location Strategy`) and before line 15 (`**IMPORTANT:** The `.hiivmind/github/config.yaml`...`):

```markdown

### CRITICAL: `.hiivmind/` Is a Multi-Plugin Namespace

The `.hiivmind/` directory is shared across multiple hiivmind plugins:
- `.hiivmind/github/` — hiivmind-pulse-gh (this plugin)
- `.hiivmind/corpus/` — hiivmind-corpus
- Other plugins may add their own subdirectories

**NEVER delete, move, or replace a `.hiivmind/` directory.** Only operate on `.hiivmind/github/` which is this plugin's subdirectory.

```

- [ ] **Step 2: Verify the edit**

Read `lib/patterns/workspace-detection.md` lines 13-30 and confirm:
- The CRITICAL section appears under `## Config Location Strategy`
- The existing `**IMPORTANT:**` note about parent directories follows after
- No content was accidentally deleted

- [ ] **Step 3: Commit**

```bash
git add lib/patterns/workspace-detection.md
git commit -m "fix: add multi-plugin namespace warning to workspace-detection pattern"
```

---

### Task 3: Add namespace warning to config-parsing pattern

**Files:**
- Modify: `lib/patterns/config-parsing.md:19-21`

- [ ] **Step 1: Insert namespace warning after the existing IMPORTANT note**

In `lib/patterns/config-parsing.md`, insert the following line immediately after line 20 (`**IMPORTANT:** The config may exist in a parent directory (workspace/monorepo setups).`) and before line 22 (`### Find Config Path`):

```markdown

**CRITICAL:** This plugin only manages `.hiivmind/github/`. The parent `.hiivmind/` directory is a shared namespace across plugins — NEVER delete or replace it.

```

- [ ] **Step 2: Verify the edit**

Read `lib/patterns/config-parsing.md` lines 19-26 and confirm:
- The IMPORTANT note about parent directories is on one line
- The CRITICAL note about namespace follows on the next line
- `### Find Config Path` follows after

- [ ] **Step 3: Commit**

```bash
git add lib/patterns/config-parsing.md
git commit -m "fix: add multi-plugin namespace warning to config-parsing pattern"
```
