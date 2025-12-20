# Discover Skill Examples

Local references for the discover skill.

## Reference Files

| File | Location | Usage |
|------|----------|-------|
| API Routing | `lib/references/api-routing.md` | Quick reference table (Phase 1) |
| Domain Files | `lib/references/domains/*.md` | Operation matrices (Phase 3) |

---

## Domain Mapping

Map user input keywords to domain files:

| # | Domain | Keywords | File |
|---|--------|----------|------|
| 1 | Issues | issue, bug, ticket, task | `domains/issues.md` |
| 2 | Pull Requests | pr, pull, merge, review | `domains/pull-requests.md` |
| 3 | Milestones | milestone, version, due | `domains/milestones.md` |
| 4 | Labels | label, tag, categorize | `domains/labels.md` |
| 5 | Projects v2 | project, board, kanban, status | `domains/projects-v2.md` |
| 6 | Branch Protection | protect, branch rule | `domains/branch-protection.md` |
| 7 | Rulesets | ruleset, rules, enforcement | `domains/rulesets.md` |
| 8 | Actions | action, workflow, ci, run | `domains/actions.md` |
| 9 | Secrets | secret, credential, encrypted | `domains/secrets.md` |
| 10 | Variables | variable, env, config | `domains/variables.md` |
| 11 | Releases | release, publish, asset | `domains/releases.md` |
| 12 | Repository | repo, repository, fork | `domains/repository.md` |
| 13 | Gists | gist, snippet | `domains/gists.md` |
| 14 | Search | search, find, query | `domains/search.md` |
| 15 | Collaborators | collaborator, contributor, invite | `domains/collaborators.md` |
| 16 | Teams | team, membership | `domains/teams.md` |
| 17 | Webhooks | webhook, hook, callback | `domains/webhooks.md` |
| 18 | Checks | check, status check | `domains/checks.md` |
| 19 | Deployments | deploy, deployment | `domains/deployments.md` |
| 20 | Environments | environment, env config | `domains/environments.md` |
| 21 | Dependabot | dependabot, dependency | `domains/dependabot.md` |
| 22 | Code Scanning | code scan, security scan | `domains/code-scanning.md` |
| 23 | Secret Scanning | secret scan, leak | `domains/secret-scanning.md` |
| 24 | Notifications | notification, inbox | `domains/notifications.md` |
| 25 | Reactions | reaction, emoji | `domains/reactions.md` |

---

## Natural Language Parsing

When user describes a task instead of selecting a domain:

### Intent Detection Pattern

```
Input: "I want to trigger the CI workflow"

Parse:
  - Action verb: "trigger" → operation: trigger
  - Object: "CI workflow" → domain: actions
  - Target: "CI" → workflow name hint

Result:
  - Domain: actions
  - Operation: trigger
  - Ready for handoff
```

### Common Phrases → Domain

| Phrase | Domain | Operation |
|--------|--------|-----------|
| "create an issue for..." | issues | create |
| "merge the PR" | pull_requests | merge |
| "set milestone on..." | milestones | update |
| "add label to..." | labels | add |
| "trigger workflow" | actions | trigger |
| "protect branch" | branch_protection | create |
| "set secret" | secrets | create |
| "create release" | releases | create |

---

## Handoff Context

When handing off to operations skill, provide:

```yaml
domain: issues          # From Phase 2 navigation
operation: create       # From user selection or parsing
target: null           # User will specify in operations skill
source: discover       # Indicates came from discovery flow
```

The operations skill uses this context to:
1. Skip domain detection (already known)
2. Focus on target specification
3. Proceed directly to execution
