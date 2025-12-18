# Expanded Introspection Architecture for hiivmind-pulse-gh

> **Status**: Planning
> **Created**: 2025-12-15
> **Related Issues**: #36 (Views), to be created for other phases

## Overview

Extend the plugin's introspection capabilities with a **modular config structure** and **per-section freshness tracking** to enable complex workflows like cross-repo coordination, mandatory field enforcement, and automation awareness.

---

## Modular File Structure

```
.hiivmind/github/
├── config.yaml              # Core workspace (unchanged, backwards compat)
├── user.yaml                # Personal config (unchanged)
├── freshness.yaml           # NEW: Centralized freshness tracking
├── views/
│   └── project-{N}.yaml     # NEW: Per-project view configs
├── automations/
│   └── project-{N}.yaml     # NEW: Per-project automation rules
├── repos/
│   └── {repo-name}.yaml     # NEW: Per-repo settings
├── relationships.yaml       # NEW: Cross-repo/project links
└── teams.yaml               # NEW: Team membership and permissions
```

---

## Per-Section Freshness Thresholds

| Section | Threshold | Rationale |
|---------|-----------|-----------|
| workspace | 30 days | Rarely changes |
| projects | 7 days | Fields/options may change |
| views | 1 day | Frequently updated |
| automations | 3 days | Moderate change rate |
| repositories | 7 days | New repos occasionally |
| repo_settings | 3 days | Protection rules may change |
| relationships | 7 days | Links change with work |
| teams | 7 days | Membership infrequent |

---

## Implementation Phases

### Phase 1: Foundation (freshness.yaml)

**Files to create/modify:**
- `templates/freshness.yaml.template` (new)
- `skills/hiivmind-pulse-gh-init/SKILL.md` (add freshness.yaml creation)
- `skills/hiivmind-pulse-gh-refresh/SKILL.md` (add --section flag support)
- `commands/hiivmind-pulse-gh.md` (per-section freshness checking)

**freshness.yaml schema:**
```yaml
defaults:
  threshold_hours: 168

sections:
  workspace:
    threshold_hours: 720
    last_checked: "2025-12-08T22:05:29Z"
    stale: false
  views:
    threshold_hours: 24
    last_checked: null
    stale: true
    projects_covered: []
  # ... per section
```

---

### Phase 2: Project Views (Issue #36)

**Files to create/modify:**
- `templates/views.yaml.template` (new)
- `skills/hiivmind-pulse-gh-refresh/SKILL.md` (add view fetch)
- `skills/hiivmind-pulse-gh-operations/SKILL.md` (view-aware helpers)
- `reference/config-schema.md` (document views schema)

**GraphQL query:**
```graphql
query GetProjectViews($owner: String!, $number: Int!) {
  organization(login: $owner) {
    projectV2(number: $number) {
      views(first: 20) {
        nodes {
          id, number, name, layout, filter
          fields(first: 50) { nodes { ... on ProjectV2Field { id name } } }
          groupByFields(first: 10) { nodes { ... } }
          sortByFields(first: 10) { nodes { direction field { ... } } }
        }
      }
    }
  }
}
```

**views/project-{N}.yaml schema:**
```yaml
project:
  number: 2
  id: PVT_...
views:
  - number: 1
    name: "Backlog"
    layout: BOARD_LAYOUT
    filter: "status:open"
    visible_fields: [Title, Status, Priority]
    hidden_fields: [Estimate, Start date]  # Derived
    group_by: [{field: Status}]
    sort_by: [{field: Priority, direction: ASC}]
```

---

### Phase 3: Repository Settings

**Files to create/modify:**
- `templates/repo.yaml.template` (new)
- `skills/hiivmind-pulse-gh-refresh/SKILL.md` (add repo settings fetch)
- `skills/hiivmind-pulse-gh-operations/SKILL.md` (protection-aware ops)

**REST endpoints:**
```bash
gh api "/repos/$OWNER/$REPO/branches/$BRANCH/protection"
gh api "/repos/$OWNER/$REPO/rulesets"
gh api "/repos/$OWNER/$REPO/labels"
gh api "/repos/$OWNER/$REPO" --jq '{allow_merge_commit, allow_squash_merge, ...}'
```

**repos/{name}.yaml schema:**
```yaml
repository:
  name: hiivmind-pulse-gh
  id: R_kgDO...
branch_protection:
  main:
    enabled: true
    required_reviews: 1
    required_status_checks: [ci/build]
merge_settings:
  allow_squash_merge: true
  delete_branch_on_merge: true
labels:
  - name: bug
    color: d73a4a
```

---

### Phase 4: Project Automations

**Files to create/modify:**
- `templates/automations.yaml.template` (new)
- `skills/hiivmind-pulse-gh-refresh/SKILL.md` (add automation fetch)
- `skills/hiivmind-pulse-gh-operations/SKILL.md` (automation-aware ops)

**automations/project-{N}.yaml schema:**
```yaml
project:
  number: 2
  id: PVT_...
automations:
  auto_add:
    - trigger: {type: issue_created, repository: repo-name}
      actions: [{set_field: {field: Status, value: Backlog}}]
  auto_set:
    - trigger: {type: item_closed}
      action: {field: Status, value: Done}
  auto_archive:
    - trigger: {type: item_status_change, to: Done}
      delay_days: 14
```

---

### Phase 5: Cross-Repo Relationships

**Files to create/modify:**
- `templates/relationships.yaml.template` (new)
- `skills/hiivmind-pulse-gh-refresh/SKILL.md` (add relationship fetch)

**relationships.yaml schema:**
```yaml
project_repo_links:
  2:  # Project number
    linked_repos:
      - name: hiivmind-pulse-gh
        auto_add_enabled: true
repo_dependencies:
  hiivmind-pulse-gh:
    depends_on: []
    depended_by: [hiivmind-pulse-gh-tests]
```

---

### Phase 6: Teams

**Files to create/modify:**
- `templates/teams.yaml.template` (new)
- `skills/hiivmind-pulse-gh-refresh/SKILL.md` (add teams fetch)
- `skills/hiivmind-pulse-gh-operations/SKILL.md` (team-aware ops)

**GraphQL query:**
```graphql
query GetOrgTeams($login: String!) {
  organization(login: $login) {
    teams(first: 100) {
      nodes {
        id, slug, name, privacy
        members(first: 100) { nodes { login id } edges { role } }
        repositories(first: 50) { nodes { name } edges { permission } }
      }
    }
  }
}
```

**teams.yaml schema:**
```yaml
teams:
  - slug: core-maintainers
    id: T_...
    members: [{login: user1, role: maintainer}]
    repo_permissions:
      hiivmind-pulse-gh: admin
repo_team_access:
  hiivmind-pulse-gh:
    admin: [core-maintainers]
    write: [contributors]
```

---

### Phase 7: Gateway & Operations Integration

**Gateway changes (commands/hiivmind-pulse-gh.md):**
- Check freshness per-section based on operation domain
- Map domains to required sections
- Warn on soft staleness, block mutations on hard staleness

**Operations skill changes (skills/hiivmind-pulse-gh-operations/SKILL.md):**
- Add `load_views()`, `load_repo_settings()`, `load_teams()` helpers
- Add `validate_field_visible()` for view-respecting updates
- Add `get_repo_writers()` for team-aware reviewer suggestions

---

## Complex Workflows Enabled

1. **Mandatory field enforcement** - Check view's visible_fields before creating issues
2. **Cross-repo milestone coordination** - Use relationships.yaml to find linked repos
3. **Automation-aware operations** - Don't duplicate what automations will do
4. **Smart PR creation** - Know merge methods, required checks from repo settings
5. **Team-based reviewer suggestions** - Suggest reviewers from teams with access

---

## Backwards Compatibility

- Existing `config.yaml` and `user.yaml` unchanged
- New files are optional - operations degrade gracefully
- Migration: Create `freshness.yaml` from existing `cache.last_synced_at`

---

## Critical Files to Modify

| File | Changes |
|------|---------|
| `templates/freshness.yaml.template` | New - per-section tracking |
| `templates/views.yaml.template` | New - view schema |
| `templates/repo.yaml.template` | New - repo settings schema |
| `templates/automations.yaml.template` | New - automation schema |
| `templates/relationships.yaml.template` | New - cross-repo links |
| `templates/teams.yaml.template` | New - team membership |
| `skills/hiivmind-pulse-gh-init/SKILL.md` | Create freshness.yaml, --full flag |
| `skills/hiivmind-pulse-gh-refresh/SKILL.md` | Modular --section refresh |
| `skills/hiivmind-pulse-gh-operations/SKILL.md` | Extended config loading, view/team helpers |
| `commands/hiivmind-pulse-gh.md` | Per-section freshness checking |
| `reference/config-schema.md` | Document all new schemas |

---

## Estimated Scope

- **Phase 1 (Foundation)**: ~200 lines across 4 files
- **Phase 2 (Views)**: ~300 lines across 4 files
- **Phase 3 (Repo Settings)**: ~250 lines across 3 files
- **Phase 4 (Automations)**: ~200 lines across 3 files
- **Phase 5 (Relationships)**: ~150 lines across 2 files
- **Phase 6 (Teams)**: ~250 lines across 3 files
- **Phase 7 (Integration)**: ~200 lines across 2 files

**Total**: ~1,550 lines of new/modified content across 7 phases
