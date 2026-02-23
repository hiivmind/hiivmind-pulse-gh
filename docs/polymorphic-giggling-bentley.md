# Plan: Lakehouse Architecture for Project Polling

## Context

The heartbeat's `projects` source currently fetches all items via a batched GraphQL query but only extracts assignee data. The GraphQL response already contains all field values — we're leaving data on the table. This plan introduces a lakehouse-style layering (RAW → BRONZE → SILVER → GOLD) so that a single API call feeds a rich local snapshot, derived views, and actionable change detection.

## Architecture

```
RAW                    BRONZE                       SILVER                    GOLD
───────────────        ──────────────────           ──────────────────        ──────────────
GitHub GraphQL    →    project-snapshot.json    →    poll-state.yaml      →   heartbeat output
(1 batched query)      Full items + all fields      .state.projects.*        project_changes{}
                       per project, unfiltered       enriched assignments     structured changeset
                                                    status distribution
                                                    my_summary aggregate
```

**Key principle:** Zero additional API calls. Same single batched query, more data extracted from the response.

## Changes

### 1. Expand GraphQL fragment in `hooks/heartbeat.sh` (line 178)

Add `ProjectV2ItemFieldSingleSelectValue` and `ProjectV2ItemFieldIterationValue` to the existing `fieldValues` fragment, plus `field { ... on ProjectV2FieldCommon { name } }` on all fragments so we know which field each value belongs to:

```graphql
fieldValues(first: 20) { nodes {
  ... on ProjectV2ItemFieldSingleSelectValue { name optionId field { ... on ProjectV2FieldCommon { name } } }
  ... on ProjectV2ItemFieldIterationValue { title startDate duration field { ... on ProjectV2FieldCommon { name } } }
  ... on ProjectV2ItemFieldUserValue { users(first: 10) { nodes { login } } field { ... on ProjectV2FieldCommon { name } } }
} }
```

No option ID reverse-lookup needed — `SingleSelectValue.name` gives us human-readable names directly from the API.

### 2. Write BRONZE snapshot: `${CONFIG_DIR}/project-snapshot.json`

After the GraphQL call succeeds, pipe `$RESULT` through a jq transformation that extracts ALL items with ALL field values into a structured JSON file. No user filtering at this stage.

```json
{
  "captured_at": "2026-02-19T10:00:00Z",
  "projects": {
    "2": {
      "title": "Hiivmind Pulse Feature Planner",
      "items": [
        {
          "id": "PVTI_...",
          "content_type": "Issue",
          "number": 29,
          "title": "Fix Schema Differences...",
          "fields": {
            "Status": "In progress",
            "Priority": "P1",
            "Size": "M",
            "Iteration": "Sprint 4",
            "Assignees": ["nathanielramm"]
          }
        }
      ]
    }
  }
}
```

Bronze change detection: SHA256 hash of the snapshot, stored as `state.projects.snapshot_hash` in poll-state. If hash unchanged, skip silver derivation entirely (fast path).

### 3. Derive SILVER views from bronze → `poll-state.yaml`

Replace the current assignment extraction (lines 189-248) with silver derivation from the bronze file. Three views:

**a) `my_assignments`** (enriched, replaces current):
```yaml
my_assignments:
  - project: "Hiivmind Pulse Feature Planner"
    project_number: 2
    items:
      - id: "PVTI_..."
        number: 29
        title: "Fix Schema Differences..."
        type: issue
        status: "In progress"
        priority: "P1"
        size: "M"
        iteration: "Sprint 4"
```

**b) `status_distribution`** (new):
```yaml
status_distribution:
  - project: "Hiivmind Pulse Feature Planner"
    project_number: 2
    counts:
      Backlog: 12
      "In progress": 8
      "In review": 2
      Done: 25
    total: 47
```

**c) `my_summary`** (new, cross-project aggregate):
```yaml
my_summary:
  total_assigned: 3
  by_status: { "In progress": 2, "In review": 1 }
  by_priority: { P1: 2, P2: 1 }
```

Silver change detection: compare sorted JSON of each view against previous. Triggers on:
- Assignment list changed (items added/removed)
- Status/priority/iteration changed on an assigned item
- Status distribution shifted

### 4. Compute GOLD changeset in heartbeat output

Diff previous vs current `my_assignments` to produce a structured changeset included in the heartbeat JSON:

```json
{
  "triggered_workflows": ["project-sync"],
  "project_changes": {
    "status_changes": [{"item": "#29", "from": "In progress", "to": "In review"}],
    "new_assignments": [],
    "removed_assignments": [],
    "priority_changes": []
  }
}
```

Write changeset to `${CONFIG_DIR}/.project-changes.json` so workflows can reference it.

### 5. Update templates, workflows, and docs

- **`templates/poll-state.yaml.template`** — Add `snapshot_hash`, enriched `my_assignments`, `status_distribution`, `my_summary` structure
- **`.hiivmind/github/workflows/project-sync.yaml`** — Update action to reference enriched data and changeset
- **`lib/patterns/poll-state.md`** — Document the three layers (bronze/silver/gold) and new change detection semantics
- **Add `templates/workflows/project-status-report.yaml`** — Optional workflow for status distribution reports (disabled by default)

## Files to Modify

| File | Change |
|------|--------|
| `hooks/heartbeat.sh` | Expand GraphQL fragment, add bronze write, silver derivation, gold changeset |
| `templates/poll-state.yaml.template` | Add new silver view structure |
| `lib/patterns/poll-state.md` | Document lakehouse layers |
| `.hiivmind/github/workflows/project-sync.yaml` | Update action text |
| `templates/workflows/project-sync.yaml` | Update template to match live |
| `templates/workflows/project-status-report.yaml` | New optional workflow (disabled) |

## Verification

1. Run `bash hooks/heartbeat.sh` — should create `project-snapshot.json` and populate enriched views in poll-state
2. Check `.hiivmind/github/project-snapshot.json` — verify full item data with status/priority/size fields
3. Check `.hiivmind/github/poll-state.yaml` — verify `my_assignments` includes status/priority, `status_distribution` is populated, `my_summary` aggregates correctly
4. Run heartbeat again — snapshot hash unchanged, no trigger (fast path)
5. Change an item's status in GitHub UI → run heartbeat → should detect status change and trigger project-sync with changeset
