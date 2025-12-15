---
name: hiivmind-pulse-gh-refresh
description: >
  Sync workspace config with current GitHub state. Updates project fields, options, and
  repository metadata in config.yaml. Run when operations fail with "ID not found" errors
  or after making changes in GitHub (new fields, renamed options, new projects).
---

# GitHub Workspace Refresh

Synchronize cached IDs with current GitHub state. Run when config becomes stale.

## When to Refresh

| Trigger | Symptom |
|---------|---------|
| Field ID changed | "Field not found" errors |
| Option renamed | "Option not found" errors |
| New project added | Project not in config |
| Fields added/removed | Missing field in config |

---

## Quick Status Check

```bash
CONFIG=".hiivmind/github/config.yaml"

echo "Last synced: $(yq '.cache.last_synced_at' "$CONFIG")"
echo "Projects cached: $(yq '.projects.catalog | length' "$CONFIG")"
echo "Default project: $(yq '.projects.default' "$CONFIG")"
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

## Update Sync Timestamp

After any refresh:

```bash
CONFIG=".hiivmind/github/config.yaml"
yq -i ".cache.last_synced_at = \"$(date -Iseconds)\"" "$CONFIG"
```

---

## Detect Staleness

Check if config is older than N days:

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
