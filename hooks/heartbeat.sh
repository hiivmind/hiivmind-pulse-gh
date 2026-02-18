#!/usr/bin/env bash
# hiivmind-pulse-gh - SessionStart heartbeat hook
# Polls for state changes and outputs triggered workflows as JSON
# See: lib/patterns/poll-state.md

set -euo pipefail

CONFIG_PATH=""
if [[ -f ".hiivmind/github/config.yaml" ]]; then
    CONFIG_PATH=".hiivmind/github/config.yaml"
elif [[ -f "../.hiivmind/github/config.yaml" ]]; then
    CONFIG_PATH="../.hiivmind/github/config.yaml"
fi

# Exit early if not initialized
if [[ -z "$CONFIG_PATH" ]]; then
    exit 0
fi

CONFIG_DIR=$(dirname "$CONFIG_PATH")
WORKFLOWS_DIR="${CONFIG_DIR}/workflows"
POLL_STATE="${CONFIG_DIR}/poll-state.yaml"
FRESHNESS="${CONFIG_DIR}/freshness.yaml"

# Exit early if no workflows directory
if [[ ! -d "$WORKFLOWS_DIR" ]]; then
    exit 0
fi

# Check rate limit before polling
REMAINING=$(gh api /rate_limit 2>/dev/null | jq -r '.rate.remaining // 100' 2>/dev/null || echo "100")
if (( REMAINING < 50 )); then
    echo '{"skipped": true, "reason": "rate_limit_low", "remaining": '"$REMAINING"'}'
    exit 0
fi

# Collect stale sections from freshness.yaml
STALE_SECTIONS="[]"
if [[ -f "$FRESHNESS" ]]; then
    STALE_SECTIONS=$(yq -o=json -r '[.sections | to_entries[] | select(.value.stale == true) | .key]' "$FRESHNESS" 2>/dev/null || echo "[]")
fi

# Detect owner/repo from git remote
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [[ -z "$REMOTE_URL" ]]; then
    exit 0
fi
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's#.*[:/]([^/]+/[^/.]+)(\.git)?$#\1#')

# Initialize poll state if missing
if [[ ! -f "$POLL_STATE" ]]; then
    cp "${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$0")")}/templates/poll-state.yaml.template" "$POLL_STATE" 2>/dev/null || exit 0
    # First run — no previous state to diff against, just initialize
    echo '{"first_run": true, "stale_sections": '"$STALE_SECTIONS"'}'
    exit 0
fi

NOW=$(date -u +%s)
TRIGGERED=()
AUTO_WORKFLOWS=()

# Process enabled workflows
for WF_FILE in "$WORKFLOWS_DIR"/*.yaml; do
    [[ -f "$WF_FILE" ]] || continue

    ENABLED=$(yq -r '.enabled // true' "$WF_FILE")
    [[ "$ENABLED" == "true" ]] || continue

    WF_NAME=$(yq -r '.name' "$WF_FILE")
    TRIGGER_TYPE=$(yq -r '.trigger.type' "$WF_FILE")
    AUTO=$(yq -r '.auto // false' "$WF_FILE")
    COOLDOWN=$(yq -r '.cooldown_minutes // 5' "$WF_FILE")

    # Check cooldown
    LAST_RUN=$(yq -r ".workflows.\"${WF_NAME}\".last_run_at // \"null\"" "$POLL_STATE" 2>/dev/null || echo "null")
    if [[ "$LAST_RUN" != "null" ]]; then
        LAST_EPOCH=$(date -d "$LAST_RUN" +%s 2>/dev/null || echo 0)
        ELAPSED=$(( (NOW - LAST_EPOCH) / 60 ))
        if (( ELAPSED < COOLDOWN )); then
            continue
        fi
    fi

    SHOULD_TRIGGER=false

    case "$TRIGGER_TYPE" in
        session_poll)
            SOURCE=$(yq -r '.trigger.source' "$WF_FILE")
            CONDITION=$(yq -r '.trigger.condition // "state_changed"' "$WF_FILE")

            case "$SOURCE" in
                pull_requests)
                    CURR=$(gh api "/repos/${OWNER_REPO}/pulls?state=open&per_page=1&sort=updated" 2>/dev/null || echo "[]")
                    CURR_COUNT=$(echo "$CURR" | jq 'length')
                    PREV_COUNT=$(yq -r '.state.pull_requests.open_count // 0' "$POLL_STATE")
                    if [[ "$CURR_COUNT" != "$PREV_COUNT" ]]; then
                        SHOULD_TRIGGER=true
                        yq -i ".state.pull_requests.open_count = $CURR_COUNT" "$POLL_STATE"
                    fi
                    ;;
                issues)
                    CURR=$(gh api "/repos/${OWNER_REPO}/issues?state=open&per_page=1&sort=updated" 2>/dev/null || echo "[]")
                    CURR_COUNT=$(echo "$CURR" | jq 'length')
                    PREV_COUNT=$(yq -r '.state.issues.open_count // 0' "$POLL_STATE")
                    if [[ "$CURR_COUNT" != "$PREV_COUNT" ]]; then
                        SHOULD_TRIGGER=true
                        yq -i ".state.issues.open_count = $CURR_COUNT" "$POLL_STATE"
                    fi
                    ;;
                actions)
                    CURR=$(gh api "/repos/${OWNER_REPO}/actions/runs?per_page=1" 2>/dev/null || echo '{"workflow_runs":[]}')
                    CURR_ID=$(echo "$CURR" | jq -r '.workflow_runs[0].id // empty')
                    PREV_ID=$(yq -r '.state.actions.latest_run_id // "null"' "$POLL_STATE")
                    if [[ -n "$CURR_ID" && "$CURR_ID" != "$PREV_ID" ]]; then
                        SHOULD_TRIGGER=true
                        CONCLUSION=$(echo "$CURR" | jq -r '.workflow_runs[0].conclusion // "null"')
                        yq -i ".state.actions.latest_run_id = \"$CURR_ID\"" "$POLL_STATE"
                        yq -i ".state.actions.latest_run_conclusion = \"$CONCLUSION\"" "$POLL_STATE"
                    fi
                    ;;
            esac
            ;;
        freshness)
            if [[ "$STALE_SECTIONS" != "[]" ]]; then
                SHOULD_TRIGGER=true
            fi
            ;;
    esac

    if [[ "$SHOULD_TRIGGER" == "true" ]]; then
        TRIGGERED+=("$WF_NAME")
        if [[ "$AUTO" == "true" ]]; then
            AUTO_WORKFLOWS+=("$WF_NAME")
        fi
    fi
done

# Update poll timestamp
yq -i ".last_polled_at = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$POLL_STATE"

# Output JSON summary
TRIGGERED_JSON=$(printf '%s\n' "${TRIGGERED[@]:-}" | jq -R . | jq -s .)
AUTO_JSON=$(printf '%s\n' "${AUTO_WORKFLOWS[@]:-}" | jq -R . | jq -s .)

echo "{\"stale_sections\": ${STALE_SECTIONS}, \"triggered_workflows\": ${TRIGGERED_JSON}, \"auto_workflows\": ${AUTO_JSON}}"
