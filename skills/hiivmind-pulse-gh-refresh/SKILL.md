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
