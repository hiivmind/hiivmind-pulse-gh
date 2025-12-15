# GitHub Function Libraries (Reference Only)

> **DEPRECATED:** These bash functions are from v2 architecture. For v3, use `gh` CLI directly with the routing guide and corpus.

These functions are **reference implementations** showing how to interact with GitHub APIs. They are NOT required for Claude Code operations.

## Recommended Approach (v3)

Instead of sourcing these functions, use:

1. **Routing guide:** `reference/api-routing.md` - which API for what operation
2. **Corpus:** Search using keywords for exact syntax
3. **Direct execution:** `gh api` or `gh` commands

## Why These Exist

- **Historical:** Originally the primary interface (v2 architecture)
- **Reference:** Show correct patterns for complex operations
- **Debugging:** Useful for understanding API behavior

## If You Need Them

For complex multi-step operations, you CAN still source these functions:

```bash
source _deprecated/github/gh-project-functions.sh
```

But prefer composing `gh` commands directly using the routing guide and corpus.

---

## Function Index

| File | Domain | Purpose |
|------|--------|---------|
| `gh-identity-functions.sh` | Identity | User/org lookups, viewer queries |
| `gh-repo-functions.sh` | Repository | Repo info, branches, visibility |
| `gh-issue-functions.sh` | Issues | Issue CRUD, labels, assignments |
| `gh-pr-functions.sh` | Pull Requests | PR operations, reviews, merges |
| `gh-milestone-functions.sh` | Milestones | Milestone CRUD (REST + GraphQL) |
| `gh-project-functions.sh` | Projects v2 | Items, fields, status updates, views |
| `gh-protection-functions.sh` | Protection | Branch rules, rulesets |
| `gh-action-functions.sh` | Actions | Workflows, runs, jobs |
| `gh-secret-functions.sh` | Secrets | Encrypted secrets management |
| `gh-variable-functions.sh` | Variables | Configuration variables |
| `gh-release-functions.sh` | Releases | Tags, assets, release notes |
| `gh-investigate-functions.sh` | Investigation | Deep-dive into entities |
| `gh-user-functions.sh` | User Setup | CLI checks, auth validation |
| `gh-workspace-functions.sh` | Workspace | Config generation, discovery |
| `gh-rest-functions.sh` | REST | Generic REST API helpers |

## Supporting Files

| File | Purpose |
|------|---------|
| `*-index.md` | Function documentation for each domain |
| `*-graphql-queries.yaml` | GraphQL query templates |
| `*-jq-filters.yaml` | jq filter templates |
| `gh-branch-protection-templates.yaml` | Branch protection JSON templates |
| `gh-rest-endpoints.yaml` | REST endpoint templates |

---

## Migration to v3

For each operation, follow this flow:

1. **Check routing:** Read `reference/api-routing.md`
2. **Find keywords:** Note the search keywords for your operation
3. **Search corpus:** Use keywords to find documentation
4. **Execute directly:** Use `gh api` or `gh` commands

### Example: Create Milestone

**v2 (deprecated):**
```bash
source _deprecated/github/gh-milestone-functions.sh
create_milestone "owner" "repo" "v2.0" "Release milestone" "2025-06-30"
```

**v3 (recommended):**
```bash
# From routing guide: Milestones → REST for CRUD
# Keywords: milestones, POST, due_on
gh api "/repos/$OWNER/$REPO/milestones" \
  -f title="v2.0" \
  -f description="Release milestone" \
  -f due_on="2025-06-30T00:00:00Z"
```

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| `reference/api-routing.md` | Which API for each operation |
| `reference/config-schema.md` | How to read config.yaml |
| `reference/workflows/` | Multi-step workflow examples |
| `.claude-plugin/skills/hiivmind-corpus-github/` | Documentation corpus |
