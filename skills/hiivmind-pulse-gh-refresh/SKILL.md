---
name: hiivmind-pulse-gh-refresh
description: >
  Sync workspace config with current GitHub state. Updates project fields, options, and
  repository metadata in config.yaml. Run when operations fail with "ID not found" errors
  or after making changes in GitHub (new fields, renamed options, new projects).
---

# GitHub Workspace Refresh

Synchronize cached IDs with current GitHub state. Run when config becomes stale.

## Usage

```bash
# Refresh all sections (default)
# Use this skill without arguments

# Refresh specific section only
# Pass section name: workspace, projects, views, automations, repositories, repo_settings, relationships, teams
```

## When to Refresh

| Trigger | Symptom | Section |
|---------|---------|---------|
| Field ID changed | "Field not found" errors | projects |
| Option renamed | "Option not found" errors | projects |
| New project added | Project not in config | projects |
| Fields added/removed | Missing field in config | projects |
| View layout changed | View settings outdated | views (Phase 2) |
| Protection rules changed | Rule not found | repo_settings (Phase 3) |
| Automation changed | Unexpected behavior | automations (Phase 4) |

---

## Quick Status Check

### Overall Status (Legacy)

```bash
CONFIG=".hiivmind/github/config.yaml"

echo "Last synced: $(yq '.cache.last_synced_at' "$CONFIG")"
echo "Projects cached: $(yq '.projects.catalog | length' "$CONFIG")"
echo "Default project: $(yq '.projects.default' "$CONFIG")"
```

### Per-Section Freshness (Phase 1+)

```bash
FRESHNESS=".hiivmind/github/freshness.yaml"

echo "=== Freshness Status ==="
yq '.sections | to_entries | .[] | "\(.key): stale=\(.value.stale), last_checked=\(.value.last_checked // "never")"' "$FRESHNESS"

echo ""
echo "=== Stale Sections ==="
yq '.sections | to_entries | .[] | select(.value.stale == true) | .key' "$FRESHNESS"
```

---

## Refresh Project Views (Phase 2)

Fetch and cache view configurations for a project.

### Fetch Views for a Project

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
PROJECT_NUM=2

# Create views directory if needed
mkdir -p .hiivmind/github/views

# Fetch project views
VIEW_DATA=$(gh api graphql -f query='
  query($owner: String!, $number: Int!) {
    organization(login: $owner) {
      projectV2(number: $number) {
        id
        title
        views(first: 20) {
          nodes {
            id
            number
            name
            layout
            filter
            fields(first: 50) {
              nodes {
                ... on ProjectV2Field {
                  id
                  name
                }
                ... on ProjectV2SingleSelectField {
                  id
                  name
                }
                ... on ProjectV2IterationField {
                  id
                  name
                }
              }
            }
            groupByFields(first: 10) {
              nodes {
                ... on ProjectV2Field {
                  id
                  name
                }
              }
            }
            sortByFields(first: 10) {
              nodes {
                direction
                field {
                  ... on ProjectV2Field {
                    id
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
  }
' -f owner="$OWNER" -F number="$PROJECT_NUM")

# Extract project info
PROJECT_ID=$(echo "$VIEW_DATA" | jq -r '.data.organization.projectV2.id')
PROJECT_TITLE=$(echo "$VIEW_DATA" | jq -r '.data.organization.projectV2.title')

# Build views.yaml
cat > ".hiivmind/github/views/project-$PROJECT_NUM.yaml" << EOF
# hiivmind-pulse-gh - Project Views Configuration
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

project:
  number: $PROJECT_NUM
  id: $PROJECT_ID
  title: "$PROJECT_TITLE"

views:
EOF

# Process each view
echo "$VIEW_DATA" | jq -r '.data.organization.projectV2.views.nodes[] | @json' | while read -r view; do
  VIEW_NUM=$(echo "$view" | jq -r '.number')
  VIEW_ID=$(echo "$view" | jq -r '.id')
  VIEW_NAME=$(echo "$view" | jq -r '.name')
  VIEW_LAYOUT=$(echo "$view" | jq -r '.layout')
  VIEW_FILTER=$(echo "$view" | jq -r '.filter // ""')

  # Get visible fields
  VISIBLE_FIELDS=$(echo "$view" | jq -r '.fields.nodes[].name' | sed 's/^/    - /')

  # Get group by fields
  GROUP_BY=$(echo "$view" | jq -r '.groupByFields.nodes[] | "    - field: \(.name)"')

  # Get sort by fields
  SORT_BY=$(echo "$view" | jq -r '.sortByFields.nodes[] | "    - field: \(.field.name)\n      direction: \(.direction)"')

  cat >> ".hiivmind/github/views/project-$PROJECT_NUM.yaml" << VIEWEOF
  - number: $VIEW_NUM
    id: $VIEW_ID
    name: "$VIEW_NAME"
    layout: $VIEW_LAYOUT
    filter: "$VIEW_FILTER"
    visible_fields:
$VISIBLE_FIELDS
    group_by:
$GROUP_BY
    sort_by:
$SORT_BY

VIEWEOF
done

# Add metadata
cat >> ".hiivmind/github/views/project-$PROJECT_NUM.yaml" << EOF
cache:
  synced_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
  schema_version: "1.0"
EOF

echo "Views cached to .hiivmind/github/views/project-$PROJECT_NUM.yaml"
```

### Update Freshness Tracking

After refreshing views:

```bash
FRESHNESS=".hiivmind/github/freshness.yaml"
PROJECTS_REFRESHED="$PROJECT_NUM"

# Mark views section as fresh
yq -i ".sections.views.last_checked = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$FRESHNESS"
yq -i ".sections.views.stale = false" "$FRESHNESS"
yq -i ".sections.views.projects_covered = [$PROJECTS_REFRESHED]" "$FRESHNESS"
yq -i ".cache.last_updated_at = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$FRESHNESS"
```

---

## Refresh Repository Settings (Phase 3)

Fetch and cache repository settings including branch protection, merge settings, and labels.

### Fetch Settings for a Repository

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
REPO="hiivmind-pulse-gh"

# Create repos directory if needed
mkdir -p .hiivmind/github/repos

# Fetch repository metadata and merge settings
REPO_DATA=$(gh api "/repos/$OWNER/$REPO" --jq '{
  name: .name,
  id: .node_id,
  full_name: .full_name,
  default_branch: .default_branch,
  visibility: .visibility,
  archived: .archived,
  merge_settings: {
    allow_merge_commit: .allow_merge_commit,
    allow_squash_merge: .allow_squash_merge,
    allow_rebase_merge: .allow_rebase_merge,
    allow_auto_merge: .allow_auto_merge,
    delete_branch_on_merge: .delete_branch_on_merge,
    allow_update_branch: .allow_update_branch,
    squash_merge_commit_title: .squash_merge_commit_title,
    squash_merge_commit_message: .squash_merge_commit_message,
    merge_commit_title: .merge_commit_title,
    merge_commit_message: .merge_commit_message
  }
}')

# Extract basic info
REPO_ID=$(echo "$REPO_DATA" | jq -r '.id')
DEFAULT_BRANCH=$(echo "$REPO_DATA" | jq -r '.default_branch')
VISIBILITY=$(echo "$REPO_DATA" | jq -r '.visibility')
ARCHIVED=$(echo "$REPO_DATA" | jq -r '.archived')

# Build repo config file
cat > ".hiivmind/github/repos/$REPO.yaml" << EOF
# hiivmind-pulse-gh - Repository Settings Configuration
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

repository:
  name: $REPO
  id: $REPO_ID
  full_name: $OWNER/$REPO
  default_branch: $DEFAULT_BRANCH
  visibility: $VISIBILITY
  archived: $ARCHIVED

branch_protection:
EOF

# Fetch branch protection for default branch
PROTECTION=$(gh api "/repos/$OWNER/$REPO/branches/$DEFAULT_BRANCH/protection" 2>/dev/null || echo "null")

if [[ "$PROTECTION" != "null" ]]; then
  cat >> ".hiivmind/github/repos/$REPO.yaml" << EOF
  $DEFAULT_BRANCH:
    enabled: true
    required_pull_request_reviews:
$(echo "$PROTECTION" | jq -r '.required_pull_request_reviews | if . then "      required_approving_review_count: \(.required_approving_review_count // 0)\n      dismiss_stale_reviews: \(.dismiss_stale_reviews // false)\n      require_code_owner_reviews: \(.require_code_owner_reviews // false)\n      require_last_push_approval: \(.require_last_push_approval // false)" else "      required_approving_review_count: 0" end')
    required_status_checks:
$(echo "$PROTECTION" | jq -r '.required_status_checks | if . then "      strict: \(.strict)\n      contexts:\n" + (.contexts | map("        - \"" + . + "\"") | join("\n")) else "      strict: false\n      contexts: []" end')
    enforce_admins:
$(echo "$PROTECTION" | jq -r '.enforce_admins.enabled // false')
    required_linear_history:
$(echo "$PROTECTION" | jq -r '.required_linear_history.enabled // false')
    allow_force_pushes:
$(echo "$PROTECTION" | jq -r '.allow_force_pushes.enabled // false')
    allow_deletions:
$(echo "$PROTECTION" | jq -r '.allow_deletions.enabled // false')
    required_conversation_resolution:
$(echo "$PROTECTION" | jq -r '.required_conversation_resolution.enabled // false')
    lock_branch:
$(echo "$PROTECTION" | jq -r '.lock_branch.enabled // false')
    allow_fork_syncing:
$(echo "$PROTECTION" | jq -r '.allow_fork_syncing.enabled // false')
    restrictions:
$(echo "$PROTECTION" | jq -r '.restrictions | if . then "      users:\n" + (.users | map("        - " + .login) | join("\n")) + "\n      teams:\n" + (.teams | map("        - " + .slug) | join("\n")) + "\n      apps:\n" + (.apps | map("        - " + .slug) | join("\n")) else "      users: []\n      teams: []\n      apps: []" end')

EOF
else
  cat >> ".hiivmind/github/repos/$REPO.yaml" << EOF
  $DEFAULT_BRANCH:
    enabled: false

EOF
fi

# Fetch rulesets
RULESETS=$(gh api "/repos/$OWNER/$REPO/rulesets" --jq '.[] | {
  id: .id,
  name: .name,
  target: .target,
  enforcement: .enforcement,
  conditions: .conditions,
  rules: .rules
}')

cat >> ".hiivmind/github/repos/$REPO.yaml" << EOF
rulesets:
EOF

if [[ -n "$RULESETS" ]]; then
  echo "$RULESETS" | jq -c '.' | while read -r ruleset; do
    RULESET_ID=$(echo "$ruleset" | jq -r '.id')
    RULESET_NAME=$(echo "$ruleset" | jq -r '.name')
    TARGET=$(echo "$ruleset" | jq -r '.target')
    ENFORCEMENT=$(echo "$ruleset" | jq -r '.enforcement')

    cat >> ".hiivmind/github/repos/$REPO.yaml" << RULESETEOF
  - id: $RULESET_ID
    name: "$RULESET_NAME"
    target: $TARGET
    enforcement: $ENFORCEMENT
    conditions:
$(echo "$ruleset" | jq -r '.conditions | to_entries | map("      \(.key): \(.value | @json)") | join("\n")')
    rules:
$(echo "$ruleset" | jq -r '.rules | map("      - type: \(.type)\n        parameters: \(.parameters | @json)") | join("\n")')

RULESETEOF
  done
else
  echo "  []" >> ".hiivmind/github/repos/$REPO.yaml"
fi

# Add merge settings
cat >> ".hiivmind/github/repos/$REPO.yaml" << EOF

merge_settings:
$(echo "$REPO_DATA" | jq -r '.merge_settings | to_entries | map("  \(.key): \(.value)") | join("\n")')
EOF

# Fetch labels
LABELS=$(gh api "/repos/$OWNER/$REPO/labels" --jq '.[] | {
  name: .name,
  color: .color,
  description: .description,
  default: .default
}')

cat >> ".hiivmind/github/repos/$REPO.yaml" << EOF

labels:
EOF

if [[ -n "$LABELS" ]]; then
  echo "$LABELS" | jq -c '.' | while read -r label; do
    LABEL_NAME=$(echo "$label" | jq -r '.name')
    LABEL_COLOR=$(echo "$label" | jq -r '.color')
    LABEL_DESC=$(echo "$label" | jq -r '.description // ""')
    LABEL_DEFAULT=$(echo "$label" | jq -r '.default // false')

    cat >> ".hiivmind/github/repos/$REPO.yaml" << LABELEOF
  - name: "$LABEL_NAME"
    color: $LABEL_COLOR
    description: "$LABEL_DESC"
    default: $LABEL_DEFAULT
LABELEOF
  done
fi

# Add metadata
cat >> ".hiivmind/github/repos/$REPO.yaml" << EOF

cache:
  synced_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
  schema_version: "1.0"
EOF

echo "Repository settings cached to .hiivmind/github/repos/$REPO.yaml"
```

### Update Freshness Tracking

After refreshing repository settings:

```bash
FRESHNESS=".hiivmind/github/freshness.yaml"
REPOS_REFRESHED="\"$REPO\""

# Mark repo_settings section as fresh
yq -i ".sections.repo_settings.last_checked = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$FRESHNESS"
yq -i ".sections.repo_settings.stale = false" "$FRESHNESS"
yq -i ".sections.repo_settings.repos_covered = [$REPOS_REFRESHED]" "$FRESHNESS"
yq -i ".cache.last_updated_at = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$FRESHNESS"
```

---

## Refresh Projects

### List Current vs Cached Projects

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
TYPE=$(yq '.workspace.type' "$CONFIG")

echo "=== Cached Projects ==="
yq '.projects.catalog[] | "\(.number): \(.title)"' "$CONFIG"

echo ""
echo "=== GitHub Projects ==="
if [[ "$TYPE" == "organization" ]]; then
  gh api graphql -f query='
    query($login: String!) {
      organization(login: $login) {
        projectsV2(first: 20) {
          nodes { number title closed }
        }
      }
    }
  ' -f login="$OWNER" --jq '.data.organization.projectsV2.nodes[] | select(.closed == false) | "\(.number): \(.title)"'
else
  gh api graphql -f query='
    query($login: String!) {
      user(login: $login) {
        projectsV2(first: 20) {
          nodes { number title closed }
        }
      }
    }
  ' -f login="$OWNER" --jq '.data.user.projectsV2.nodes[] | select(.closed == false) | "\(.number): \(.title)"'
fi
```

### Refresh Single Project Fields

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
PROJECT_NUM=2

# Fetch fresh field data
gh api graphql -f query='
  query($owner: String!, $number: Int!) {
    organization(login: $owner) {
      projectV2(number: $number) {
        id
        title
        fields(first: 50) {
          nodes {
            ... on ProjectV2SingleSelectField {
              id
              name
              options { id name }
            }
            ... on ProjectV2Field {
              id
              name
            }
          }
        }
      }
    }
  }
' -f owner="$OWNER" -F number="$PROJECT_NUM" --jq '.data.organization.projectV2.fields.nodes'
```

Compare output with cached fields and update config.yaml as needed.

---

## Refresh Specific Field

If a single field changed:

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
PROJECT_NUM=2
FIELD_NAME="Status"

# Get fresh field data
gh api graphql -f query='
  query($owner: String!, $number: Int!) {
    organization(login: $owner) {
      projectV2(number: $number) {
        field(name: "'"$FIELD_NAME"'") {
          ... on ProjectV2SingleSelectField {
            id
            name
            options { id name }
          }
        }
      }
    }
  }
' -f owner="$OWNER" -F number="$PROJECT_NUM"
```

Then update config.yaml:

```bash
# Update field ID
yq -i '.projects.catalog[] | select(.number == 2) | .fields.Status.id = "NEW_ID"' "$CONFIG"

# Update option ID
yq -i '.projects.catalog[] | select(.number == 2) | .fields.Status.options["In Progress"] = "NEW_OPTION_ID"' "$CONFIG"
```

---

## Full Config Regeneration

For major changes, regenerate the entire config:

```bash
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
TYPE=$(yq '.workspace.type' "$CONFIG")
DEFAULT=$(yq '.projects.default' "$CONFIG")

# Backup current config
cp "$CONFIG" "$CONFIG.bak"

# Re-run init process (see hiivmind-pulse-gh-init)
# This regenerates config.yaml with fresh data
```

---

## Update Freshness Tracking

After refreshing any section, update freshness.yaml:

### Update Specific Section

```bash
FRESHNESS=".hiivmind/github/freshness.yaml"
SECTION="projects"  # or workspace, views, automations, etc.

# Mark section as fresh
yq -i ".sections.$SECTION.last_checked = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$FRESHNESS"
yq -i ".sections.$SECTION.stale = false" "$FRESHNESS"

# Update cache metadata
yq -i ".cache.last_updated_at = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$FRESHNESS"
```

### Update Projects Section with Coverage

```bash
FRESHNESS=".hiivmind/github/freshness.yaml"
PROJECTS_REFRESHED="2 3"  # Space-separated project numbers

# Mark as fresh and record which projects were covered
yq -i ".sections.projects.last_checked = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$FRESHNESS"
yq -i ".sections.projects.stale = false" "$FRESHNESS"
yq -i ".sections.projects.projects_covered = [$PROJECTS_REFRESHED]" "$FRESHNESS"
yq -i ".cache.last_updated_at = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$FRESHNESS"
```

### Legacy Timestamp (Backwards Compatibility)

Also update the legacy config.yaml timestamp:

```bash
CONFIG=".hiivmind/github/config.yaml"
yq -i ".cache.last_synced_at = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$CONFIG"
```

---

## Detect Staleness

### Per-Section Staleness (Phase 1+)

Check which sections are stale based on their individual thresholds:

```bash
FRESHNESS=".hiivmind/github/freshness.yaml"

# Function to check if a section is stale
check_section_staleness() {
  local section=$1
  local last_checked=$(yq ".sections.$section.last_checked" "$FRESHNESS")
  local threshold_hours=$(yq ".sections.$section.threshold_hours" "$FRESHNESS")

  if [[ "$last_checked" = "null" ]] || [[ -z "$last_checked" ]]; then
    echo "STALE (never checked)"
    yq -i ".sections.$section.stale = true" "$FRESHNESS"
    return 1
  fi

  local last_epoch=$(date -d "$last_checked" +%s 2>/dev/null || echo 0)
  local now_epoch=$(date +%s)
  local age_hours=$(( (now_epoch - last_epoch) / 3600 ))

  if [[ $age_hours -gt $threshold_hours ]]; then
    echo "STALE (${age_hours}h old, threshold: ${threshold_hours}h)"
    yq -i ".sections.$section.stale = true" "$FRESHNESS"
    return 1
  else
    echo "FRESH (${age_hours}h old, threshold: ${threshold_hours}h)"
    yq -i ".sections.$section.stale = false" "$FRESHNESS"
    return 0
  fi
}

# Check all sections
for section in workspace projects views automations repositories repo_settings relationships teams; do
  echo -n "$section: "
  check_section_staleness "$section"
done
```

### Legacy Staleness Check

For backwards compatibility with existing workflows:

```bash
CONFIG=".hiivmind/github/config.yaml"
LAST_SYNC=$(yq '.cache.last_synced_at' "$CONFIG")
DAYS_OLD=$(( ($(date +%s) - $(date -d "$LAST_SYNC" +%s)) / 86400 ))

if [[ $DAYS_OLD -gt 7 ]]; then
  echo "Config is $DAYS_OLD days old - consider refreshing"
else
  echo "Config is fresh ($DAYS_OLD days old)"
fi
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Field not found" | Refresh project fields |
| "Option not found" | Refresh single-select field options |
| "Project not found" | Check project number, add to catalog |
| yq syntax errors | Verify config.yaml structure |

---

## Corpus Lookup

Search the corpus index using these keywords:

| Need | Keywords |
|------|----------|
| Project fields | `ProjectV2Field`, `ProjectV2SingleSelectField` |
| Field options | `options`, `singleSelectOptions`, `id`, `name` |
| Project query | `projectV2`, `fields`, `nodes` |

Start with `reference/api-routing.md` → "Projects v2" section.
