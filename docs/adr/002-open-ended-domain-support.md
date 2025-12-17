# ADR 002: Expanded GitHub Domain Support

**Status:** Proposed
**Date:** 2025-12-17
**Milestone:** [v5.2.0 - Expanded Domain Support](https://github.com/hiivmind/hiivmind-pulse-gh/milestone/11)
**Issues:** #85, #86, #87, #88, #89

## Context

The hiivmind-pulse-gh plugin currently hardcodes 11 GitHub domains in its gateway command:

- Issues, Pull Requests, Milestones, Labels, Projects v2
- Branch Protection, Rulesets, Actions, Secrets, Variables, Releases

Each domain has explicit keyword detection in `commands/hiivmind-pulse-gh.md`:

```markdown
| Keywords | Domain |
|----------|--------|
| issue, bug, feature, task, ticket | `issues` |
| pr, pull request, merge, review | `pull_requests` |
...
```

**This approach has significant value:**

1. **Fast routing** - Known domains route immediately without corpus lookup
2. **Predictable behavior** - Users get consistent, expected results
3. **API optimization** - Pre-mapped GraphQL vs REST decisions

**But also limitations:**

1. **Limited coverage** - The bundled corpus documents 30+ additional GitHub domains
2. **Maintenance burden** - Each new domain requires manual keyword additions

### Corpus Coverage

The bundled GitHub API corpus includes domains beyond the current 11:

| Tier | Count | Examples |
|------|-------|----------|
| High-value | 8 | Repositories, Collaborators, Teams, Checks, Deployments |
| Security | 5 | Code Scanning, Secret Scanning, Dependabot, Security Advisories |
| CI/CD Extended | 4 | Workflow Artifacts, Environments, Self-Hosted Runners |
| Organization | 4 | Org Settings, Webhooks, Audit Log, Billing |
| Specialized | 8 | Pages, Codespaces, Packages, Copilot, Git Data |
| Informational | 7 | Activity, Reactions, Users, Licenses, Rate Limit |

All of these have REST and/or GraphQL documentation in the corpus.

## Decision

### 1. Keep and expand domain detection table

**Keep** the existing keyword-to-domain detection table (it provides valuable fast routing) and **expand** it with 9 high-value Tier 1-2 domains:

| Keywords | Domain | Tier |
|----------|--------|------|
| repo, repository, fork, clone | `repositories` | 1 |
| collaborator, contributor, invite | `collaborators` | 1 |
| team, membership | `teams` | 1 |
| check, check run, status check | `checks` | 1 |
| deploy, deployment | `deployments` | 1 |
| scan, alert, security, vulnerability | `security` | 2 |
| dependabot, dependency | `dependabot` | 2 |
| search, find, query | `search` | 1 |
| gist | `gists` | 1 |

This expands coverage from 11 to ~20 domains while maintaining fast routing.

### 2. Add fallback for unlisted domains

For domains not in the detection table:

1. Route to operations skill
2. Operations skill uses corpus lookup for syntax
3. Default to REST API
4. Confirm with user before execution

This provides graceful handling of edge cases without requiring constant table updates.

### 3. Add operation blocklist for safety

Create `reference/operation-blocklist.md` to block dangerous operations:

| Resource | Operation | Reason |
|----------|-----------|--------|
| Repository | delete | Irreversible data loss |
| Repository | transfer | Ownership change |
| Repository | archive | Can break CI/CD workflows |
| Organization | delete | Catastrophic |
| Organization | remove all members | Bulk dangerous operation |
| Branch | delete default | Breaks repository |
| Release | delete all | Bulk data loss |

When a blocked operation is requested:
1. Explain why it's blocked
2. Offer alternative if available
3. Suggest manual UI action

### 4. Add PreToolUse hook for defense-in-depth

Create a command-based PreToolUse hook that intercepts Bash commands before execution:

**File:** `hooks/hooks.json`

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/validate-gh-operation.sh",
        "timeout": 5
      }]
    }]
  }
}
```

**File:** `hooks/validate-gh-operation.sh`

Pattern-matches against blocked operations and returns `{"decision": "deny", "reason": "..."}` for dangerous commands.

This provides **two safety layers**:
1. **Skill-level** (soft) - LLM checks blocklist before attempting operation
2. **Hook-level** (hard) - Deterministic blocking at execution time

### 5. Update api-routing.md with new domains

Expand the routing guide to include the 9 new domains with their API preferences:

| Domain | Read | Create | Update | Delete | API |
|--------|------|--------|--------|--------|-----|
| Repositories | Both | REST | REST | REST | REST for mutations |
| Collaborators | REST | REST | - | REST | REST only |
| Teams | REST | REST | REST | REST | REST only |
| Checks | Both | REST | REST | - | REST for mutations |
| Deployments | REST | REST | REST | - | REST only |
| Security Scanning | REST | - | REST | - | REST only |
| Dependabot | REST | - | REST | REST | REST only |
| Search | Both | - | - | - | Read-only |
| Gists | REST | REST | REST | REST | REST only |

Add fallback section for unlisted domains.

## Consequences

### Benefits

- **Fast routing preserved** - Known domains route without corpus lookup
- **Expanded coverage** - 9 new high-value domains supported
- **Graceful fallback** - Unlisted domains handled via corpus
- **Defense-in-depth safety** - Skill + hook blocking layers
- **Predictable behavior** - Explicit domain handling is more reliable

### Risks

- **Maintenance overhead** - Domain lists need occasional updates (infrequent)
- **Potential gaps** - Unlisted domains may not work perfectly first time

### Files Affected

| File | Change |
|------|--------|
| `commands/hiivmind-pulse-gh.md` | Expand domain table + add blocklist + add fallback |
| `skills/hiivmind-pulse-gh-operations/SKILL.md` | Add corpus fallback for unknown domains |
| `reference/api-routing.md` | Expand to ~20 domains + unlisted domain guidance |
| `reference/operation-blocklist.md` | NEW - Define blocked operations |
| `hooks/hooks.json` | NEW - PreToolUse hook configuration |
| `hooks/validate-gh-operation.sh` | NEW - Command hook for blocking |
| `README.md` | Update Supported Domains section |
| `CLAUDE.md` | Update domain table note |

### Migration Notes

- Existing domain keywords remain valid
- No breaking changes for current usage patterns
- New domains become immediately available
- Hook provides safety even for direct `gh api` calls
