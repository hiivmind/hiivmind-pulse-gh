# Pattern: Plugin Skill Awareness

## Purpose

Define what skills hiivmind-pulse-gh provides, when to use each skill, and how to invoke them. Used by the awareness skill to generate CLAUDE.md sections that teach Claude when to use this plugin.

## When to Use

- Adding plugin awareness to CLAUDE.md
- Teaching Claude when to invoke each skill
- Generating awareness documentation

---

## WHAT - Plugin Skills

hiivmind-pulse-gh provides 5 skills:

| Skill | Name | Purpose |
|-------|------|---------|
| `hiivmind-pulse-gh-init` | Init | Discover GitHub workspace, cache project/field IDs for fast operations |
| `hiivmind-pulse-gh-refresh` | Refresh | Sync stale config sections, fix "ID not found" errors |
| `hiivmind-pulse-gh-operations` | Operations | Execute GitHub operations (issues, PRs, milestones, projects, labels, etc.) |
| `hiivmind-corpus-github` | Corpus | Look up GitHub API syntax (GraphQL schema, REST endpoints, gh CLI) |
| `hiivmind-pulse-gh-adr` | ADR | Create Architecture Decision Records linked to milestones and issues |

### Skill Descriptions

#### Init
- **What:** One-time workspace setup
- **Does:** Discovers org/user, queries Projects v2, caches field IDs and option IDs
- **Output:** `.hiivmind/github/config.yaml`, `user.yaml`, `freshness.yaml`
- **Run when:** First time in a workspace, or after major GitHub project restructuring

#### Refresh
- **What:** Config synchronization
- **Does:** Checks staleness per section, re-queries GitHub for stale data
- **Run when:** "ID not found" errors, config stale warnings, after GitHub UI changes

#### Operations
- **What:** Execute GitHub operations
- **Does:** Issues, PRs, milestones, labels, projects, branch protection, actions, secrets, variables, releases
- **Run when:** User wants to create/update/delete/list any GitHub entity

#### Corpus
- **What:** API documentation lookup
- **Does:** Searches 70k+ line GraphQL schema, REST docs, gh CLI reference
- **Run when:** Need exact mutation syntax, REST endpoint path, or gh command options

#### ADR
- **What:** Architecture Decision Records
- **Does:** Creates ADR markdown files in `doc/adr/`, creates linked GitHub issues, assigns to milestones
- **Run when:** Documenting architecture decisions, major refactoring, milestone planning

---

## WHEN - Trigger Mapping

Maps operational needs to skills:

### Operations Triggers

| User Says / Needs | Skill | Confidence |
|-------------------|-------|------------|
| "create issue", "open bug", "new feature request" | operations | High |
| "close issue", "resolve #42" | operations | High |
| "create PR", "open pull request" | operations | High |
| "merge PR", "squash merge" | operations | High |
| "set milestone", "add to v2.0" | operations | High |
| "add label", "tag as bug" | operations | High |
| "add to project", "set status" | operations | High |
| "protect branch", "require reviews" | operations | High |
| "trigger workflow", "run CI" | operations | High |
| "create release", "publish v1.0" | operations | High |

### Corpus Triggers

| User Says / Needs | Skill | Confidence |
|-------------------|-------|------------|
| "what's the GraphQL syntax for..." | corpus | High |
| "REST endpoint for milestones" | corpus | High |
| "how do I use updateIssue mutation" | corpus | High |
| "gh command for..." | corpus | Medium |
| API syntax uncertainty during operations | corpus | Medium |

### ADR Triggers

| User Says / Needs | Skill | Confidence |
|-------------------|-------|------------|
| "document decision", "create ADR" | adr | High |
| "architecture decision", "design decision" | adr | High |
| "why did we choose...", "record rationale" | adr | High |
| Major refactoring planned (3+ files) | adr | Medium (proactive) |
| Milestone has 5+ issues | adr | Medium (proactive) |
| Keywords: restructure, migrate, redesign | adr | Medium (proactive) |

### Init/Refresh Triggers

| User Says / Needs | Skill | Confidence |
|-------------------|-------|------------|
| "initialize", "setup workspace" | init | High |
| "first time setup" | init | High |
| "ID not found", "project not in config" | refresh | High |
| "config stale", "refresh config" | refresh | High |
| "sync with GitHub" | refresh | Medium |

---

## HOW - Invocation Methods

### Gateway Command (Recommended)

```
/hiivmind-pulse-gh [describe what you want]
```

The gateway auto-detects intent and routes to the appropriate skill.

**Examples:**
```
/hiivmind-pulse-gh create issue for login timeout bug
/hiivmind-pulse-gh set milestone v2.0 on #42
/hiivmind-pulse-gh document decision about using GraphQL
/hiivmind-pulse-gh refresh config
```

### Direct Skill Invocation

When you know exactly which skill is needed:

```
Invoke skill: hiivmind-pulse-gh:hiivmind-pulse-gh-operations
Invoke skill: hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs
Invoke skill: hiivmind-pulse-gh:hiivmind-pulse-gh-adr
```

### Interactive Menu

```
/hiivmind-pulse-gh
```

Without arguments, presents numbered menu of all operations.

---

## CLAUDE.md Template

Generate this section for CLAUDE.md:

```markdown
## GitHub Operations (hiivmind-pulse-gh)

This project uses [hiivmind-pulse-gh](https://github.com/hiivmind/hiivmind-pulse-gh) for GitHub automation.

### What This Plugin Provides

| Skill | What It Does |
|-------|--------------|
| **Init** | Discover workspace, cache project/field IDs for fast operations |
| **Operations** | Execute GitHub operations (issues, PRs, milestones, projects, etc.) |
| **Corpus** | Look up GitHub API syntax (GraphQL schema, REST endpoints) |
| **ADR** | Create Architecture Decision Records linked to milestones/issues |
| **Refresh** | Sync config when stale or IDs not found |

### When to Use Each Skill

| You Need To... | Use This |
|----------------|----------|
| Create, update, close issues or PRs | `/hiivmind-pulse-gh [action]` |
| Set milestones, labels, project status | `/hiivmind-pulse-gh [action]` |
| Look up GraphQL/REST syntax | Corpus skill |
| Fix "ID not found" errors | Refresh skill |
| Document an architecture decision | ADR skill |
| First-time workspace setup | Init skill |

### Proactive Suggestions

Suggest using this plugin when:
- User mentions GitHub operations (issues, PRs, milestones, projects)
- User asks about GitHub API syntax or mutations
- Major refactoring is planned (suggest ADR)
- Milestone has 5+ issues (suggest documenting decisions)
- "ID not found" or stale config errors occur

### How to Invoke

**Gateway (recommended):**
```
/hiivmind-pulse-gh create issue for [description]
/hiivmind-pulse-gh document decision about [topic]
```

**Direct skill invocation** when you know which skill:
```
Skill: hiivmind-pulse-gh-operations
Skill: hiivmind-corpus-github
```
```

---

## Related Patterns

- **adr-awareness.md** - ADR-specific triggers and proactive suggestions
- **config-parsing.md** - Read cached config for init status

## Related Skills

- **hiivmind-pulse-gh-awareness** - Uses this pattern to generate CLAUDE.md sections
