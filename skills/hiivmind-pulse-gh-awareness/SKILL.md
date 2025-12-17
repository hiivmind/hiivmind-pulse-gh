---
name: hiivmind-pulse-gh-awareness
description: >
  Add GitHub capability awareness to CLAUDE.md files. Auto-detects relevant capabilities
  from project context (workflows, issue templates, ADRs), then offers guided tour of
  remaining features. Modifies CLAUDE.md directly with preview and confirmation.
  Trigger when: "add awareness", "capability awareness", "what can pulse-gh do",
  "configure Claude for GitHub", "setup CLAUDE.md", "enable GitHub features",
  "GitHub capabilities", "pulse-gh tour".
---

# Capability Awareness

Configure CLAUDE.md with hiivmind-pulse-gh capability awareness through auto-detection and guided tour.

## Scope

| Does | Does NOT |
|------|----------|
| Scan project for capability signals | Initialize workspace (use init skill) |
| Auto-detect relevant capabilities | Execute GitHub operations |
| Guide through remaining capabilities | Create GitHub resources |
| Edit CLAUDE.md with confirmation | Modify other files |
| Generate awareness snippets | Replace existing CLAUDE.md content |

## Phase Overview

```
1. CONTEXT    -> 2. DETECT     -> 3. TOUR      -> 4. INJECT    -> 5. CONFIRM
   (analyze)      (auto-match)     (guided)       (edit)          (verify)
      |              |                |              |               |
   Scan project   Match signals    STOP for       Preview +      STOP: show
   for signals    to capabilities  each cap       confirm        summary
```

---

## Phase 1: CONTEXT

**Goal:** Analyze project to understand context and check for existing awareness.

**See:** `lib/github/patterns/capability-awareness.md`

### What to Do

1. Check if CLAUDE.md exists
2. Check for existing hiivmind-pulse-gh awareness section
3. Scan project for capability signals (parallel)

### Parallel Scans

Execute these in parallel:

```
Glob: .github/workflows/*.yml
Glob: .github/ISSUE_TEMPLATE/**
Glob: .github/PULL_REQUEST_TEMPLATE*
Glob: doc/adr/*.md
Read: .github/labeler.yml (exists?)
Read: .github/CODEOWNERS (exists?)
Read: .hiivmind/github/config.yaml (has projects?)
Read: package.json (has semantic-release?)
```

### STOP Point - No CLAUDE.md

```
No CLAUDE.md found in this project.

Would you like to:
  1. Create CLAUDE.md with GitHub awareness section
  2. Cancel

[Select option]
```

### STOP Point - Existing Awareness

If CLAUDE.md already has hiivmind-pulse-gh section:

```
CLAUDE.md already has GitHub capability awareness.

Found existing section with:
  - Issues
  - Pull Requests
  - Actions

Would you like to:
  1. Update existing configuration (add more capabilities)
  2. Replace existing configuration
  3. View current configuration
  4. Cancel

[Select option]
```

---

## Phase 2: DETECT

**Goal:** Auto-match capabilities based on project signals.

**See:** `lib/github/patterns/capability-awareness.md` (Detection Rules)

### Detection Logic

| Signal Found | Enable Capability |
|--------------|-------------------|
| `.github/workflows/*.yml` exists | actions |
| `.github/ISSUE_TEMPLATE/` exists | issues |
| `.github/PULL_REQUEST_TEMPLATE*` exists | prs |
| `.github/labeler.yml` exists | labels |
| `.github/CODEOWNERS` exists | protection, prs |
| `doc/adr/*.md` files exist | adr |
| `.hiivmind/github/config.yaml` has `projects:` | projects |
| `semantic-release` in package.json | releases |
| `${{ secrets.*` in workflows | secrets |
| `${{ vars.*` in workflows | variables |

### Workflow Deep Scan

If workflows found, scan each for:
- `${{ secrets.` → enable secrets
- `${{ vars.` → enable variables
- `release` in filename → enable releases

### STOP Point - Present Auto-Detected

```
Based on your project, I detected these relevant capabilities:

Auto-enabled (signals found):
  [x] Issues (found: .github/ISSUE_TEMPLATE/)
  [x] Pull Requests (found: .github/PULL_REQUEST_TEMPLATE.md)
  [x] Actions (found: 3 workflow files)
  [x] Secrets (found: secrets referenced in workflows)
  [x] ADR (found: doc/adr/ with 1 record)

Not detected (no signals, but available):
  [ ] Milestones
  [ ] Labels
  [ ] Projects v2
  [ ] Branch Protection
  [ ] Rulesets
  [ ] Variables
  [ ] Releases

Options:
  1. Accept auto-detected only
  2. Take guided tour of remaining capabilities
  3. Enable all capabilities
  4. Customize selection

[Select option]
```

---

## Phase 3: TOUR

**Goal:** Walk through non-detected capabilities one-by-one.

**Only runs if user selected "guided tour" in Phase 2.**

### Tour Order

Present capabilities in logical groups:

1. **Issue Tracking:** milestones, labels
2. **Code Review:** protection, rulesets
3. **Project Management:** projects
4. **CI/CD:** variables, releases
5. **Documentation:** (adr if not detected)

### STOP Point - Per Capability

For each capability not auto-detected:

```
=== Capability: Milestones ===

Track release cycles and group related issues.

When to use:
  - Plan releases with due dates
  - Group issues by version
  - Track progress toward goals

Trigger keywords: milestone, version, due date, release

Example commands:
  /hiivmind-pulse-gh create milestone v2.0
  /hiivmind-pulse-gh set milestone v2.0 on #42
  /hiivmind-pulse-gh list milestones

Enable this capability? [Yes / Skip / Stop tour]
```

### Tour Flow

- **Yes** → Add to enabled list, continue
- **Skip** → Don't add, continue to next
- **Stop tour** → End tour, proceed with current selections

---

## Phase 4: INJECT

**Goal:** Generate awareness snippet and edit CLAUDE.md.

**See:** `lib/github/patterns/capability-awareness.md` (Templates)

### Step 1: Build Capability Table

From enabled capabilities, build table:

```markdown
| Capability | When to Use | Trigger Keywords |
|------------|-------------|------------------|
| **Issues** | Create, update, close, comment | issue, bug, task |
| **Pull Requests** | Create, merge, review | pr, merge, review |
| **Actions** | Trigger, view workflow runs | workflow, ci |
| **ADR** | Document architecture decisions | ADR, decision record |
```

### Step 2: Build Command Examples

Select 3-5 most relevant commands:

```
/hiivmind-pulse-gh create issue for [description]
/hiivmind-pulse-gh merge PR #N
/hiivmind-pulse-gh trigger workflow ci.yml
/hiivmind-pulse-gh create ADR for [topic]
```

### Step 3: Build Proactive Triggers

Based on enabled capabilities:

```markdown
Suggest GitHub operations when:
- User mentions bugs, features, or tasks (issues)
- User discusses code changes or reviews (prs)
- Major refactoring planned (suggest ADR)
- Milestone has 5+ issues (suggest ADR)
```

### Step 4: Check Initialization Status

```bash
# Check if initialized
if [[ -f ".hiivmind/github/config.yaml" ]]; then
  INIT_STATUS="Initialized"
  # Extract default project if set
  DEFAULT_PROJECT=$(yq '.projects.default // ""' .hiivmind/github/config.yaml 2>/dev/null)
else
  INIT_STATUS="Not initialized (run /hiivmind-pulse-gh init)"
fi
```

### Step 5: Generate Full Section

```markdown
## GitHub Operations (hiivmind-pulse-gh)

This project uses [hiivmind-pulse-gh](https://github.com/hiivmind/hiivmind-pulse-gh) for GitHub automation.

### Available Capabilities

| Capability | When to Use | Trigger Keywords |
|------------|-------------|------------------|
{capability_table}

### Quick Commands

```
{command_examples}
```

### Configuration

- **Config:** `.hiivmind/github/config.yaml`
- **Status:** {init_status}

### Proactive Suggestions

Suggest GitHub operations when:
{proactive_triggers}
```

### STOP Point - Preview

```
=== CLAUDE.md Addition Preview ===

The following section will be added to CLAUDE.md:

---
## GitHub Operations (hiivmind-pulse-gh)

This project uses hiivmind-pulse-gh for GitHub automation.

### Available Capabilities

| Capability | When to Use | Trigger Keywords |
|------------|-------------|------------------|
| **Issues** | Create, update, close, comment | issue, bug, task |
| **Pull Requests** | Create, merge, review | pr, merge, review |
| **Actions** | Trigger, view workflow runs | workflow, ci |
| **ADR** | Document architecture decisions | ADR, decision record |

[... rest of section ...]
---

Insert location: End of file

Options:
  1. Add to CLAUDE.md
  2. Choose different location
  3. Edit content
  4. Cancel

[Select option]
```

### Step 6: Execute Edit

Use Claude's Edit tool to modify CLAUDE.md:

**If appending:**
- Read current CLAUDE.md
- Append generated section with blank line separator

**If inserting at location:**
- Find target header
- Insert after that section

---

## Phase 5: CONFIRM

**Goal:** Confirm changes and offer next steps.

### STOP Point - Success

```
CLAUDE.md updated successfully!

Added GitHub capability awareness:
  - Issues
  - Pull Requests
  - Actions (3 workflows detected)
  - Secrets
  - ADR (1 existing record)

File: CLAUDE.md

Next steps:
  1. Initialize workspace (/hiivmind-pulse-gh init) [if not initialized]
  2. Create your first ADR
  3. Done

[Select option or press Enter to finish]
```

### If Not Initialized

Offer to run init:

```
Note: Workspace is not initialized yet.

Some features (Projects v2, cached IDs) require initialization.

Run /hiivmind-pulse-gh init now? [Yes / Later]
```

---

## Quick Reference

### Add Awareness

```
/hiivmind-pulse-gh add awareness
/hiivmind-pulse-gh configure Claude for GitHub
/hiivmind-pulse-gh what can you do
```

### Update Awareness

```
/hiivmind-pulse-gh update awareness
```

### View Capabilities

```
/hiivmind-pulse-gh list capabilities
```

---

## Related Skills

- **hiivmind-pulse-gh-init** - Initialize workspace after adding awareness
- **hiivmind-pulse-gh-adr** - ADR creation (often suggested after awareness)
- **hiivmind-pulse-gh-operations** - All GitHub operations

## Pattern Library

| Pattern | Purpose |
|---------|---------|
| `lib/github/patterns/capability-awareness.md` | Detection rules, capability registry, templates |
| `lib/github/patterns/adr-awareness.md` | ADR-specific awareness (subset) |
| `lib/github/patterns/config-parsing.md` | Read cached config for init status |
