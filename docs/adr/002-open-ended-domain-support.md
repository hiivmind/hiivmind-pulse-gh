# ADR 002: Open-Ended GitHub Domain Support

**Status:** Proposed
**Date:** 2025-12-17
**Milestone:** [v5.2.0 - Open-Ended Domain Support](https://github.com/hiivmind/hiivmind-pulse-gh/milestone/11)
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

This approach has limitations:

1. **Limited coverage** - The bundled corpus documents 30+ additional GitHub domains (repos, teams, deployments, security scanning, etc.) that users cannot access
2. **Maintenance burden** - Each new domain requires manual keyword additions
3. **Architecture mismatch** - The LLM-first + corpus fallback architecture can already handle any domain
4. **Artificial constraints** - Users with permissions are blocked from valid operations

### Corpus Coverage

The bundled GitHub API corpus includes:

| Tier | Domains | Examples |
|------|---------|----------|
| High-value | 8 | Repositories, Collaborators, Teams, Checks, Deployments |
| Security | 5 | Code Scanning, Secret Scanning, Dependabot, Security Advisories |
| CI/CD Extended | 4 | Workflow Artifacts, Environments, Self-Hosted Runners |
| Organization | 4 | Org Settings, Webhooks, Audit Log, Billing |
| Specialized | 8 | Pages, Codespaces, Packages, Copilot, Git Data |
| Informational | 7 | Activity, Reactions, Users, Licenses, Rate Limit |

All of these have REST and/or GraphQL documentation in the corpus.

## Decision

### 1. Remove hardcoded domain list

Replace the explicit domain detection table with open-ended intent detection:

```markdown
Analyze the user's request to determine:
1. **Resource** - What GitHub entity (issue, repo, team, deployment, etc.)
2. **Operation** - What action (create, update, delete, list, etc.)
3. **Target** - Specific entity if any
```

The LLM can interpret any reasonable GitHub request without a predefined list.

### 2. Add operation blocklist for safety

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

### 3. Update operations skill for unknown domains

Add fallback path in `skills/hiivmind-pulse-gh-operations/SKILL.md`:

```markdown
1. Check `reference/api-routing.md` for known domain routing
2. If domain not documented → Default to REST API
3. Use corpus lookup for exact endpoint syntax
4. Confirm with user before execution
```

### 4. Keep common domains documented

The `api-routing.md` guide continues to document the 11 common domains for quick reference. Add note:

> This guide covers common domains. For unlisted domains, use corpus lookup with REST API as default.

## Consequences

### Benefits

- **Future-proof** - New GitHub features supported automatically via corpus
- **No code changes** - Adding domain support requires no plugin updates
- **Leverages architecture** - Uses the LLM + corpus pattern as designed
- **User empowerment** - Any operation the user has permissions for can be attempted

### Risks

- **Less predictable** - Unknown domains rely on corpus accuracy
- **Potential failures** - Some edge cases may not work correctly first time
- **Safety concerns** - Mitigated by operation blocklist

### Files Affected

| File | Change |
|------|--------|
| `commands/hiivmind-pulse-gh.md` | Replace domain table with open-ended detection + blocklist |
| `skills/hiivmind-pulse-gh-operations/SKILL.md` | Add corpus fallback for unknown domains |
| `reference/api-routing.md` | Add note about unlisted domains |
| `reference/operation-blocklist.md` | NEW - Define blocked operations |
| `README.md` | Update Supported Domains section |
| `CLAUDE.md` | Update domain table note |

### Migration Notes

- Existing domain keywords remain valid (LLM will still detect them)
- No breaking changes for current usage patterns
- New domains become immediately available
