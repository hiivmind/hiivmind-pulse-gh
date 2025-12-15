# Archived Skills (v2 Architecture)

> **ARCHIVED:** These skills are from v2 architecture and have been replaced by the v3 approach.

## Why Archived

In v3 architecture, domain-specific skills are no longer needed. Instead:

1. **Run `hiivmind-pulse-gh-init`** once to cache workspace config
2. **Check `reference/api-routing.md`** for which API to use
3. **Search corpus** using keywords for exact syntax
4. **Execute with `gh`** directly

## Archived Skills

### Merged into `hiivmind-pulse-gh-init`

| Skill | Original Purpose |
|-------|------------------|
| `hiivmind-pulse-gh-user-init` | CLI checks, auth validation, user.yaml creation |
| `hiivmind-pulse-gh-workspace-init` | Project discovery, config.yaml creation |

### Replaced by `hiivmind-pulse-gh-refresh`

| Skill | Original Purpose |
|-------|------------------|
| `hiivmind-pulse-gh-workspace-refresh` | Sync config with GitHub state |

### Replaced by Routing + Corpus

| Skill | Original Purpose | v3 Alternative |
|-------|------------------|----------------|
| `hiivmind-pulse-gh-projects` | Projects v2 operations | `reference/api-routing.md` → Projects v2 |
| `hiivmind-pulse-gh-milestones` | Milestone CRUD | `reference/api-routing.md` → Milestones |
| `hiivmind-pulse-gh-branch-protection` | Branch rules, rulesets | `reference/api-routing.md` → Protection |
| `hiivmind-pulse-gh-investigate` | Deep entity analysis | Direct `gh api` queries |

## If You Need These

These skills still work if sourced manually, but the v3 approach is recommended:

```bash
# v2 (archived) - sourcing skill functions
# Not recommended

# v3 (current) - direct gh usage
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")

# Check routing guide for API, search corpus for syntax
gh api graphql -f query='...'
```

## Related Documentation

| Document | Purpose |
|----------|---------|
| `reference/api-routing.md` | Which API for each operation |
| `reference/config-schema.md` | How to use config.yaml |
| `reference/workflows/` | Multi-step examples |
| `skills/hiivmind-pulse-gh-init/` | Current init skill |
| `skills/hiivmind-pulse-gh-refresh/` | Current refresh skill |
