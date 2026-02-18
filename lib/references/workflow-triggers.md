# Reference: Workflow Triggers

Trigger type lookup table for workflow definitions.

---

## Trigger Types

| Type | Fires When | Source Required | Hook |
|------|-----------|-----------------|------|
| `session_poll` | Session starts, polled state differs from cached | Yes | SessionStart (heartbeat.sh) |
| `post_operation` | A matching `gh` operation completes | Yes (operation pattern) | PostToolUse (post-operation-check.sh) |
| `freshness` | Config section exceeds staleness threshold | No (uses freshness.yaml) | SessionStart (heartbeat.sh) |
| `on_demand` | User explicitly runs the workflow | No | None (manual via workflows skill) |

---

## `session_poll` Sources

| Source | What Gets Polled | API Call |
|--------|------------------|----------|
| `pull_requests` | Open PR count, latest updated PR | `GET /repos/{owner}/{repo}/pulls?state=open&per_page=1&sort=updated` |
| `issues` | Open issue count, latest updated issue | `GET /repos/{owner}/{repo}/issues?state=open&per_page=1&sort=updated` |
| `actions` | Latest workflow run ID, status, conclusion | `GET /repos/{owner}/{repo}/actions/runs?per_page=1` |
| `releases` | Latest release ID, tag name | `GET /repos/{owner}/{repo}/releases?per_page=1` |
| `dependabot` | Open alert count | `GET /repos/{owner}/{repo}/dependabot/alerts?state=open&per_page=1&sort=updated` |
| `deployments` | Latest deployment ID, environment | `GET /repos/{owner}/{repo}/deployments?per_page=1` |
| `projects` | Project item count | GraphQL `ProjectV2.items.totalCount` (uses default project from config) |

### Conditions

| Condition | Meaning |
|-----------|---------|
| `state_changed` | Any tracked field differs from cached value |
| `count_increased` | Count is higher than cached (new items) |
| `count_decreased` | Count is lower than cached (items closed/merged) |
| `new_failure` | Latest action run conclusion is `failure` (was not before) |

### Filters

Optional narrowing of trigger scope:

```yaml
filter:
  label: "bug"          # Only trigger for items with this label
  branch: "main"        # Only trigger for this branch
  author: "dependabot"  # Only trigger for this author
```

> **Note:** Filters are evaluated by the heartbeat skill after polling, not by the API call. The poll fetches minimal data; filtering happens client-side.

---

## `post_operation` Sources

| Source | Matches When |
|--------|-------------|
| `issue_created` | `gh issue create` completes |
| `issue_closed` | `gh issue close` completes |
| `pr_created` | `gh pr create` completes |
| `pr_merged` | `gh pr merge` completes |
| `workflow_triggered` | `gh workflow run` completes |

### Pattern Matching

The PostToolUse hook extracts the operation from the completed command:

```bash
# Match patterns in the executed command
case "$COMMAND" in
    *"gh issue create"*) SOURCE="issue_created" ;;
    *"gh issue close"*)  SOURCE="issue_closed" ;;
    *"gh pr create"*)    SOURCE="pr_created" ;;
    *"gh pr merge"*)     SOURCE="pr_merged" ;;
    *"gh workflow run"*) SOURCE="workflow_triggered" ;;
    *)                   SOURCE="" ;;
esac
```

---

## `freshness` Triggers

No source required — reads directly from `.hiivmind/github/freshness.yaml`:

```yaml
trigger:
  type: freshness
  condition: threshold_exceeded  # Any section past its threshold
```

The heartbeat hook checks freshness.yaml and fires this trigger when any section is stale.

---

## `on_demand` Triggers

No hook involvement — the user explicitly runs the workflow:

```
/hiivmind-pulse-gh workflows run pr-lifecycle
```

On-demand workflows ignore cooldown when explicitly invoked by the user.
