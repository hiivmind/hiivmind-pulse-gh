# Pattern: Poll State Management

## Purpose

Efficiently track GitHub state between sessions to detect changes without excessive API calls.

## When to Use

- SessionStart heartbeat hook needs to detect what changed since last session
- Workflow triggers need to compare current vs. cached state
- Cooldown enforcement needs to check last execution time

## Prerequisites

- **config-parsing.md** — Read/write YAML files
- **authentication.md** — Verify gh auth before API calls

---

## Poll State Location

```
.hiivmind/github/poll-state.yaml
```

Initialize from `{PLUGIN_ROOT}/templates/poll-state.yaml.template` if missing.

---

## Efficient Polling Strategy

### Minimize API Calls

Each `session_poll` workflow source maps to ONE lightweight API call:

| Source | API Call | Fields Checked |
|--------|----------|----------------|
| `pull_requests` | `gh api /repos/{owner}/{repo}/pulls?state=open&per_page=1&sort=updated` | count, latest ID, updated_at |
| `issues` | `gh api /repos/{owner}/{repo}/issues?state=open&per_page=1&sort=updated` | count, latest ID, updated_at |
| `actions` | `gh api /repos/{owner}/{repo}/actions/runs?per_page=1` | latest run ID, status, conclusion |
| `projects` | Batched GraphQL query across all catalog projects | item count, user assignments per project |

### Deduplicate Sources

If multiple workflows poll the same source, make ONE API call and share the result:

```bash
# Group workflows by source
SOURCES=$(yq -r '.trigger.source' .hiivmind/github/workflows/*.yaml 2>/dev/null | sort -u)

for SOURCE in $SOURCES; do
    # One API call per unique source
    poll_source "$SOURCE"
done
```

---

## Change Detection (Diff)

Compare polled values against cached state:

```bash
PREV_PR_COUNT=$(yq -r '.state.pull_requests.open_count' .hiivmind/github/poll-state.yaml)
CURR_PR_COUNT=$(echo "$PR_RESPONSE" | jq -r '. | length')

if [[ "$PREV_PR_COUNT" != "$CURR_PR_COUNT" ]]; then
    # State changed — trigger matching workflows
    CHANGED_SOURCES+=("pull_requests")
fi
```

### What Counts as "Changed"

| Source | Change Detected When |
|--------|---------------------|
| `pull_requests` | Open count differs OR latest updated_at is newer |
| `issues` | Open count differs OR latest updated_at is newer |
| `actions` | Latest run ID differs OR conclusion changed |
| `projects` | Item count differs OR user's assignment list changed |

---

## Cooldown Enforcement

Before triggering a workflow, check its cooldown:

```bash
LAST_RUN=$(yq -r ".workflows.\"${WORKFLOW_NAME}\".last_run_at" .hiivmind/github/poll-state.yaml)
COOLDOWN=$(yq -r '.cooldown_minutes' "$WORKFLOW_FILE")
NOW=$(date -u +%s)

if [[ "$LAST_RUN" != "null" ]]; then
    LAST_EPOCH=$(date -d "$LAST_RUN" +%s 2>/dev/null)
    ELAPSED_MINUTES=$(( (NOW - LAST_EPOCH) / 60 ))
    if (( ELAPSED_MINUTES < COOLDOWN )); then
        # Skip — cooldown not elapsed
        continue
    fi
fi
```

---

## Updating State

After polling, update the cached state:

```bash
yq -i ".last_polled_at = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" .hiivmind/github/poll-state.yaml
yq -i ".state.pull_requests.open_count = $CURR_PR_COUNT" .hiivmind/github/poll-state.yaml
```

After workflow execution, record the result:

```bash
yq -i ".workflows.\"${WORKFLOW_NAME}\".last_run_at = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" .hiivmind/github/poll-state.yaml
yq -i ".workflows.\"${WORKFLOW_NAME}\".last_result = \"$RESULT\"" .hiivmind/github/poll-state.yaml
yq -i ".workflows.\"${WORKFLOW_NAME}\".run_count += 1" .hiivmind/github/poll-state.yaml
```

---

## Rate Limit Awareness

Before polling, check remaining rate limit:

```bash
REMAINING=$(gh api /rate_limit | jq -r '.rate.remaining')
if (( REMAINING < 50 )); then
    echo '{"skipped": true, "reason": "rate_limit_low", "remaining": '$REMAINING'}' >&2
    exit 0
fi
```

---

## Related Patterns

- **config-parsing.md** — YAML read/write operations
- **workflow-execution.md** — How workflows are executed after triggers fire
- **error-handling.md** — Handle API errors during polling
