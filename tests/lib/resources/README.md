# Test Resource Management Library

Shared library for creating and cleaning up GitHub resources during testing.

## Purpose

This library is used by:
- **Fixture Recording** (`tests/fixtures/scripts/record_fixtures.bash`) - Creates test data before recording, cleans up after
- **E2E Testing** (`tests/e2e/sandbox.bash`) - Creates sandbox resources for live API tests

## Usage

```bash
# Source the libraries you need
source "tests/lib/resources/core.bash"
source "tests/lib/resources/milestone.bash"
source "tests/lib/resources/issue.bash"

# Setup cleanup trap (resources cleaned up on exit/error)
setup_cleanup_trap

# Create resources - automatically tracked for cleanup
milestone_num=$(create_milestone "owner" "repo" "My Milestone")
issue_num=$(create_issue "owner" "repo" "My Issue" "Issue body")

# Do your testing...

# Cleanup happens automatically when script exits
# Or call explicitly: cleanup_tracked_resources
```

## Available Resources

| File | Resource Type | Functions |
|------|--------------|-----------|
| `core.bash` | - | `track_resource`, `cleanup_tracked_resources`, `setup_cleanup_trap` |
| `milestone.bash` | Milestone | `create_milestone`, `delete_milestone`, `list_milestones` |
| `issue.bash` | Issue | `create_issue`, `close_issue`, `delete_issue`, `list_issues` |
| `label.bash` | Label | `create_label`, `delete_label`, `list_labels` |
| `pr.bash` | Pull Request | `create_pr`, `create_test_pr`, `close_pr`, `delete_pr` |
| `release.bash` | Release | `create_release`, `delete_release`, `list_releases` |
| `protection.bash` | Ruleset/Protection | `create_ruleset`, `delete_ruleset`, `list_rulesets` |
| `variable.bash` | Actions Variable | `create_variable`, `delete_variable`, `list_variables` |

## Core Functions

### Resource Tracking

```bash
# Track a resource for cleanup
track_resource "milestone" "owner/repo/123"

# Check tracking
count_tracked_resources  # Returns count
list_tracked_resources   # Lists all tracked

# Cleanup all tracked resources
cleanup_tracked_resources
```

### Automatic Cleanup

```bash
# Setup trap - cleanup runs on EXIT or ERR
setup_cleanup_trap

# Disable trap if needed
disable_cleanup_trap
```

### Utility Functions

```bash
# Generate unique resource names
name=$(generate_resource_name "milestone")  # test-milestone-1702345678

# Parse identifiers
parse_owner_repo "owner/repo/extra"
echo "$PARSED_OWNER"  # owner
echo "$PARSED_REPO"   # repo

# Ensure no resources exist (for empty-state fixtures)
ensure_empty "milestone" "owner" "repo"
```

## Resource Script Pattern

Each resource script follows the same pattern:

```bash
# Source core (idempotent)
if [[ -z "${TRACKED_RESOURCES+x}" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/core.bash"
fi

# CREATE_RAW - creates resource WITHOUT tracking (for use in subshells)
create_milestone_raw() {
    # ... create via API
    echo "$number"  # Only outputs the identifier
}

# CREATE - creates resource, tracks it, returns identifier
create_milestone() {
    local number=$(create_milestone_raw "$@")
    track_resource "milestone" "$owner/$repo/$number"
    echo "$number"
}

# READ - fetch resource data
get_milestone() { ... }
list_milestones() { ... }

# UPDATE - modify resource
update_milestone() { ... }
close_milestone() { ... }

# DELETE - delete by identifier (owner/repo/id format)
delete_milestone() {
    local identifier="$1"
    parse_owner_repo_number "$identifier"
    # ... delete via API
}
```

### Why `_raw` Functions?

When using command substitution `$(...)`, the command runs in a **subshell**. Any changes to global variables (like `TRACKED_RESOURCES`) inside the subshell are **lost**.

```bash
# BROKEN: tracking happens in subshell, lost when subshell exits
local result=$(create_milestone "$org" "$repo" "$title")

# FIXED: use _raw in subshell, track in parent shell
local result=$(create_milestone_raw "$org" "$repo" "$title")
track_resource "milestone" "$org/$repo/$result"
```

See `knowledge/bash-subshell-variable-tracking.md` for full details.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_ORG` | `hiivmind` | Default organization for tests |
| `TEST_REPO` | `hiivmind-pulse-gh` | Default repository for tests |
| `RESOURCE_PREFIX` | `test-` | Prefix for auto-generated names |
| `RESOURCE_DEBUG` | - | Set to `true` for verbose logging |

## Examples

### Recording Fixtures with Setup

```yaml
# tests/fixtures/recording_manifest.yaml
milestone:
  list_populated:
    type: rest
    endpoint: "/repos/{owner}/{repo}/milestones"
    setup:
      - resource: milestone
        params:
          title: "Test Milestone v1.0"
      - resource: milestone
        params:
          title: "Test Milestone v2.0"
    # teardown automatic via cleanup trap
```

### E2E Test Sandbox

```bash
# tests/e2e/sandbox.bash
source "../lib/resources/core.bash"
source "../lib/resources/milestone.bash"

setup_sandbox() {
    setup_cleanup_trap
    export TEST_MILESTONE=$(create_milestone "$TEST_ORG" "$TEST_REPO" "E2E Milestone")
}

teardown_sandbox() {
    cleanup_tracked_resources
}
```

## Error Handling

- All delete functions suppress errors (resources may already be deleted)
- Cleanup continues even if some deletions fail
- Resources are cleaned up in reverse order (LIFO)
- Exit traps ensure cleanup runs even on script errors
