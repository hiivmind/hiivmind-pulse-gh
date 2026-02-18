---
name: gh-operations
version: 4.0.0
description: >
  Execute GitHub operations with automatic context enrichment from cached workspace. Use this for ANY
  GitHub operation, not just complex ones. Simple operations like creating issues are enriched with
  project linking, milestone resolution, and field assignments. Direct `gh issue create` misses these
  benefits. This skill should be used when: creating issues, closing issues, merging PRs, setting
  milestones, adding labels, updating project status, protecting branches, triggering workflows,
  creating releases, managing secrets. Trigger phrases: "create issue", "close issue #", "merge PR",
  "set milestone on", "add label to", "update project status", "add to project board", "protect branch",
  "trigger workflow", "create release", "set secret", "list PRs", "merge pull request", "remove label",
  "create milestone", "archive project item", "rerun workflow", "cancel action", "github issue",
  "github pr", "github milestone", "make a new issue", "open pull request", "start workflow",
  "new issue for", "assign to milestone", "move to column", "update issue", "request review",
  "approve PR", "comment on issue", "link issue to project", "simple github operation", "quick issue",
  "fast PR". Domains: issues, PRs, milestones, labels, projects, protection, rulesets, actions,
  secrets, variables, releases, repositories, collaborators, teams, checks, deployments, search.
---

# GitHub Operations Execution

Execute GitHub operations with automatic context enrichment from cached workspace config.

## Path Convention

`{PLUGIN_ROOT}` = Plugin root directory (where plugin.json lives)

When this skill references files like `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`,
read from the plugin root, not relative to this skill folder.

## Why Use This Skill (Even for Simple Operations)

This skill enriches ALL operations with cached context:

| Simple Operation | Enrichment Provided |
|------------------|---------------------|
| Create issue | Auto-link to default project, set Status field |
| Close issue | Update project Status to "Done" |
| Set milestone | Use pre-cached milestone ID (no lookup needed) |
| Add label | Apply team-standard labels from config |

**Direct `gh issue create` creates orphan issues.** This skill creates issues linked to your project board.

## Scope

| Does | Does NOT |
|------|----------|
| Execute GitHub operations | Modify local config files |
| Resolve IDs from cached config | Initialize workspaces |
| Support all domains (issues, PRs, etc.) | Refresh stale configs |
| Report operation results | Detect user intent (gateway does this) |

## Expected Context

When invoked by the gateway command, expect:

- **Domain**: issues, pull_requests, milestones, labels, projects, branch_protection, rulesets, actions, secrets, variables, releases, repositories, collaborators, teams, checks, deployments, security, dependabot, search, gists, or **any unlisted domain**
- **Operation**: create, read, update, delete, link, trigger, merge
- **Target**: Specific entity (issue #42, milestone "v2.0", etc.)
- **Config**: `.hiivmind/github/config.yaml`

---

## Execution Flow

### 1. Verify Workspace

Check for `.hiivmind/github/config.yaml` in current directory OR parent directories:

```bash
# Check current and parent directory (covers workspace setups)
if [[ -f ".hiivmind/github/config.yaml" ]]; then
    CONFIG_PATH=".hiivmind/github/config.yaml"
elif [[ -f "../.hiivmind/github/config.yaml" ]]; then
    CONFIG_PATH="../.hiivmind/github/config.yaml"
else
    CONFIG_PATH=""
fi
```

**If config found in parent:** Use that config path for all operations. This is common in:
- Monorepo setups where config lives at root
- Workspace directories containing multiple repositories
- Child projects within an initialized workspace

**If not found in current or parent:**

```
Workspace not initialized.

Config file not found in current or parent directory.

Run: /gh init
```

**See:** `{PLUGIN_ROOT}/lib/patterns/config-parsing.md` for full search algorithm

### 2. Determine Approach

| Situation | Action |
|-----------|--------|
| Known CLI command (`gh issue`, `gh pr`, etc.) | Execute directly with enrichment |
| Known API pattern | Execute via `gh api` |
| Uncertain about syntax | Consult resources, then execute |
| Unknown domain | Corpus lookup required |

**Fast path:** For common operations listed below, proceed directly to execution.

### 3. Execute with Enrichment

1. **Resolve IDs** from cached config (project ID, field IDs, milestone ID)
2. **Apply enrichment** (link to project, set status field, etc.)
3. **Execute:**
   - CLI: `gh issue create`, `gh pr merge`, etc.
   - GraphQL: temp file pattern via `gh api graphql`
   - REST: `gh api /repos/{owner}/{repo}/endpoint -X METHOD`

### 4. Report Result

**Success:**
```
Operation successful!

{Domain}: {Operation}
Target: {entity}
Result: {summary}

{Link to GitHub}
```

**Error:** Include suggested fix based on error type.

---

## Common Operations (No Lookup Needed)

These commands are well-known - execute directly with enrichment:

| Operation | CLI Command |
|-----------|-------------|
| Create issue | `gh issue create` |
| Close issue | `gh issue close NUMBER` |
| Comment on issue | `gh issue comment NUMBER --body TEXT` |
| Create PR | `gh pr create` |
| Merge PR | `gh pr merge NUMBER` |
| Review PR | `gh pr review NUMBER` |
| Set secret | `gh secret set NAME` |
| Trigger workflow | `gh workflow run WORKFLOW` |
| Create release | `gh release create TAG` |
| List issues/PRs | `gh issue list`, `gh pr list` |

**Note:** CLI commands handle authentication, pagination, and formatting automatically.

### Domains WITHOUT CLI Support

These domains have NO `gh` CLI commands - use REST API via `gh api`:

| Domain | REST Endpoint Pattern |
|--------|----------------------|
| **Milestones** | `/repos/{owner}/{repo}/milestones` |
| Branch Protection | `/repos/{owner}/{repo}/branches/{branch}/protection` |
| Collaborators | `/repos/{owner}/{repo}/collaborators/{username}` |
| Teams | `/orgs/{org}/teams` |
| Webhooks | `/repos/{owner}/{repo}/hooks` |
| Checks | `/repos/{owner}/{repo}/check-runs` |
| Deployments | `/repos/{owner}/{repo}/deployments` |
| Environments | `/repos/{owner}/{repo}/environments/{name}` |
| Dependabot | `/repos/{owner}/{repo}/dependabot/alerts` |
| Code Scanning | `/repos/{owner}/{repo}/code-scanning/alerts` |
| Secret Scanning | `/repos/{owner}/{repo}/secret-scanning/alerts` |
| Notifications | `/notifications` |
| Reactions | `/repos/{owner}/{repo}/issues/{number}/reactions` |
| Rulesets | `/repos/{owner}/{repo}/rulesets` (read via `gh ruleset list`) |

> **Common mistake:** `gh milestone create`, `gh webhook create`, etc. do not exist.
> Always check `{PLUGIN_ROOT}/lib/references/api-routing.md` for CLI availability.

---

## When to Consult Resources

Only read files when you have a **knowledge gap**:

| Knowledge Gap | Resource |
|---------------|----------|
| Which API (GraphQL vs REST)? | `{PLUGIN_ROOT}/lib/references/api-routing.md` |
| Domain-specific syntax/gotchas | `{PLUGIN_ROOT}/lib/references/domains/{domain}.md` |
| Exact mutation/endpoint syntax | Corpus: `hiivmind-corpus-github-docs-navigate` |
| ID resolution from cache | `{PLUGIN_ROOT}/lib/patterns/id-resolution.md` |
| GraphQL execution pattern | `{PLUGIN_ROOT}/lib/patterns/graphql-execution.md` |
| Error recovery | `{PLUGIN_ROOT}/lib/patterns/error-handling.md` |

**Context-aware:** If you already read a resource earlier in the conversation, don't re-read it.

---

## Enrichment Details

### What Gets Applied

From `.hiivmind/github/config.yaml`:

| Config Section | Enrichment |
|----------------|------------|
| `projects.default` | Auto-link new issues/PRs to default project |
| `projects.catalog[].fields.Status` | Set Status field on project items |
| `milestones` | Resolve milestone names to IDs |
| `labels` | Apply team-standard labels |

### Cache-First ID Resolution

1. Check config.yaml for cached ID
2. If found → use directly
3. If not found → corpus lookup to query, then cache result

---

## Unknown Domains

For domains not in the routing guide:

1. **Default to REST API** - Most GitHub features use REST for mutations
2. **Invoke corpus** for endpoint syntax: `hiivmind-corpus-github-docs-navigate`
3. **Confirm with user** before executing unknown patterns
4. **Endpoint pattern:** `gh api /repos/{owner}/{repo}/{resource}`

---

## Related Skills

| Skill | Use For |
|-------|---------|
| **init** | First-time workspace setup |
| **refresh** | Update stale config sections |
| **discover** | Explore available operations |
| **gateway** | Intent detection and routing |

---

## Resources

### Patterns (HOW to do things)

| Pattern | Purpose |
|---------|---------|
| `{PLUGIN_ROOT}/lib/patterns/config-parsing.md` | Read/write YAML config files |
| `{PLUGIN_ROOT}/lib/patterns/id-resolution.md` | Resolve names to IDs (cache-first) |
| `{PLUGIN_ROOT}/lib/patterns/graphql-execution.md` | Execute queries via temp file |
| `{PLUGIN_ROOT}/lib/patterns/error-handling.md` | Handle API errors |
| `{PLUGIN_ROOT}/lib/patterns/corpus-lookup.md` | Look up API syntax when uncertain |

### References (WHAT exists)

| Reference | Purpose |
|-----------|---------|
| `{PLUGIN_ROOT}/lib/references/api-routing.md` | API routing decisions (GraphQL vs REST) |
| `{PLUGIN_ROOT}/lib/references/domains/*.md` | Domain-specific operation matrices |

### External

| Resource | Purpose |
|----------|---------|
| `hiivmind-corpus-github-docs-navigate` | GitHub corpus skill for syntax lookup |
