# Pattern: Capability Awareness

## Purpose

Master reference for all hiivmind-pulse-gh capabilities, detection rules, and CLAUDE.md snippets. Used by the awareness skill to auto-detect relevant capabilities and generate awareness sections.

## When to Use

- Adding capability awareness to CLAUDE.md
- Auto-detecting relevant capabilities from project context
- Generating awareness snippets for specific capabilities

---

## Capability Registry

### Skills (5 active)

| ID | Name | Trigger Keywords | Description |
|----|------|------------------|-------------|
| `init` | Workspace Init | init, initialize, setup workspace, configure github | One-time workspace setup, discovers projects and caches IDs |
| `refresh` | Config Refresh | refresh, sync, update config, stale config, ID not found | Sync cached config with GitHub, update stale sections |
| `operations` | Operations | (see domains below) | Execute GitHub operations across all domains |
| `adr` | ADR | ADR, architecture decision, document decision, design decision, why did we | Create and manage Architecture Decision Records |
| `corpus` | API Corpus | find in docs, GraphQL schema, REST endpoint, API syntax | GitHub API documentation lookup |

### Domains (12 via Operations)

| ID | Name | Trigger Keywords | Description |
|----|------|------------------|-------------|
| `issues` | Issues | issue, bug, feature, task, ticket | Create, update, close, comment, label issues |
| `prs` | Pull Requests | pr, pull request, merge, review | Create, merge, review pull requests |
| `milestones` | Milestones | milestone, version, due date | Create and manage milestones |
| `labels` | Labels | label, tag, categorize | Create and manage labels |
| `projects` | Projects v2 | project, board, kanban, status, field | Project boards with custom fields |
| `protection` | Branch Protection | protect, protection, branch rule | Configure branch protection rules |
| `rulesets` | Rulesets | ruleset, rules, enforcement | Repository rulesets |
| `actions` | Actions | workflow, action, run, ci, trigger | Trigger and view workflows |
| `secrets` | Secrets | secret, credential, encrypted | Manage repository secrets |
| `variables` | Variables | variable, env, config | Manage environment variables |
| `releases` | Releases | release, publish, asset, changelog | Create and manage releases |
| `adr` | ADR | architecture decision, decision record | Architecture Decision Records |

---

## Detection Rules

### Signal → Capability Mapping

| Signal | Detection Method | Enables |
|--------|------------------|---------|
| `.github/workflows/*.yml` | Glob for files | actions |
| `.github/ISSUE_TEMPLATE/` | Directory exists | issues |
| `.github/PULL_REQUEST_TEMPLATE*` | Glob for file | prs |
| `.github/labeler.yml` | File exists | labels |
| `.github/CODEOWNERS` | File exists | protection, prs |
| `doc/adr/*.md` | Glob for files | adr |
| `.hiivmind/github/config.yaml` | File exists with `projects:` | projects |
| `semantic-release` in package.json | Grep in file | releases |
| `release` in workflow filename | Grep workflow names | releases |
| `${{ secrets.*` in workflows | Grep in workflow files | secrets |
| `${{ vars.*` in workflows | Grep in workflow files | variables |

### Detection Algorithm

```
1. PARALLEL SCAN
   - Glob: .github/workflows/*.yml → count
   - Glob: .github/ISSUE_TEMPLATE/** → exists
   - Glob: .github/PULL_REQUEST_TEMPLATE* → exists
   - Read: .github/labeler.yml → exists
   - Read: .github/CODEOWNERS → exists
   - Glob: doc/adr/*.md → count
   - Read: .hiivmind/github/config.yaml → has projects

2. WORKFLOW ANALYSIS (if workflows found)
   For each workflow file:
   - Grep: \$\{\{ secrets\. → enable secrets
   - Grep: \$\{\{ vars\. → enable variables
   - Check filename for "release" → enable releases

3. PACKAGE.JSON ANALYSIS (if exists)
   - Grep: semantic-release → enable releases

4. BUILD CAPABILITY LIST
   Return: { detected: [...], available: [...] }
```

### Using Claude Tools

**Parallel detection:**
```
Glob: .github/workflows/*.yml
Glob: .github/ISSUE_TEMPLATE/**
Glob: .github/PULL_REQUEST_TEMPLATE*
Glob: doc/adr/*.md
```

**File checks:**
```
Read: .github/labeler.yml (check exists)
Read: .github/CODEOWNERS (check exists)
Read: .hiivmind/github/config.yaml (check for projects:)
Read: package.json (check for semantic-release)
```

**Workflow analysis:**
```
Grep: \$\{\{ secrets\. in .github/workflows/
Grep: \$\{\{ vars\. in .github/workflows/
```

---

## Snippet Templates

### Per-Capability Snippets

#### Issues
```markdown
| **Issues** | Create, update, close, comment, label | issue, bug, task, ticket |
```
Commands: `create issue for [desc]`, `close issue #N`, `add label to #N`

#### Pull Requests
```markdown
| **Pull Requests** | Create, merge, review, comment | pr, pull request, merge, review |
```
Commands: `create PR`, `merge PR #N`, `request review on #N`

#### Milestones
```markdown
| **Milestones** | Create, assign, track progress | milestone, version, due date |
```
Commands: `create milestone v2.0`, `set milestone on #N`

#### Labels
```markdown
| **Labels** | Create, add/remove from issues | label, tag, categorize |
```
Commands: `create label`, `add bug label to #N`

#### Projects v2
```markdown
| **Projects v2** | Add items, update fields, set status | project, board, kanban, status |
```
Commands: `add #N to project`, `set status "In Progress" on #N`

#### Branch Protection
```markdown
| **Branch Protection** | Configure rules, require reviews | protect, branch rule, required reviews |
```
Commands: `protect main branch`, `require 2 reviews on main`

#### Rulesets
```markdown
| **Rulesets** | Repository-wide rules, enforcement | ruleset, rules, enforcement |
```
Commands: `create ruleset`, `list rulesets`

#### Actions
```markdown
| **Actions** | Trigger workflows, view runs | workflow, action, ci, trigger |
```
Commands: `trigger ci workflow`, `view workflow runs`

#### Secrets
```markdown
| **Secrets** | Manage repository secrets | secret, credential, encrypted |
```
Commands: `set secret API_KEY`, `list secrets`

#### Variables
```markdown
| **Variables** | Manage environment variables | variable, env, config |
```
Commands: `set variable ENV=production`, `list variables`

#### Releases
```markdown
| **Releases** | Create releases, add assets | release, publish, asset, changelog |
```
Commands: `create release v1.0.0`, `list releases`

#### ADR
```markdown
| **ADR** | Document architecture decisions | ADR, architecture decision, decision record |
```
Commands: `create ADR for [topic]`, `list ADRs`
Proactive: Suggest when milestone has 5+ issues or major refactoring planned

---

## CLAUDE.md Section Template

### Full Template

```markdown
## GitHub Operations (hiivmind-pulse-gh)

This project uses [hiivmind-pulse-gh](https://github.com/hiivmind/hiivmind-pulse-gh) for GitHub automation.

### Available Capabilities

| Capability | When to Use | Trigger Keywords |
|------------|-------------|------------------|
{{CAPABILITY_TABLE}}

### Quick Commands

```
{{COMMAND_EXAMPLES}}
```

### Configuration

- **Config:** `.hiivmind/github/config.yaml`
- **Status:** {{INIT_STATUS}}
{{#if DEFAULT_PROJECT}}
- **Default Project:** {{DEFAULT_PROJECT}}
{{/if}}

### Proactive Suggestions

Suggest GitHub operations when:
{{PROACTIVE_TRIGGERS}}
```

### Proactive Triggers by Capability

| Capability | Trigger Condition |
|------------|-------------------|
| issues | User mentions bugs, features, or tasks |
| prs | User discusses code changes or reviews |
| milestones | User plans releases or versions |
| projects | User discusses work tracking or status |
| adr | Major refactoring planned, milestone has 5+ issues |
| actions | CI/CD or deployment discussed |

---

## Capability Groupings

### Core (always relevant)
- init, refresh, operations

### Issue Tracking
- issues, labels, milestones

### Code Review
- prs, protection, rulesets

### Project Management
- projects, adr

### CI/CD
- actions, secrets, variables, releases

### Documentation
- adr, corpus

---

## Integration Notes

### Existing Awareness Check

Before adding awareness, check CLAUDE.md for existing section:

```
Grep: "## GitHub Operations" in CLAUDE.md
Grep: "hiivmind-pulse-gh" in CLAUDE.md
```

If found, offer to update rather than duplicate.

### Placement Preference

1. After existing tool/automation sections
2. Before development/contributing sections
3. End of file if no clear section structure

### Preserving Existing Content

Always:
- Read full CLAUDE.md before editing
- Preview changes to user
- Use Edit tool to insert, not Write to overwrite

---

## Related Patterns

- **adr-awareness.md** - ADR-specific awareness (subset of this)
- **config-parsing.md** - Read cached config for project detection
- **workspace-detection.md** - Detect repository context

## Related Skills

- **hiivmind-pulse-gh-awareness** - Uses this pattern for detection and snippets
- **hiivmind-pulse-gh-init** - Should be suggested if not initialized
