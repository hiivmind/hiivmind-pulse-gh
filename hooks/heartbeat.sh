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

# Check required tools (exit 0 with error JSON so hook doesn't crash the session)
for tool in gh jq yq; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "{\"error\": \"missing_tool\", \"tool\": \"$tool\"}"
        exit 0
    fi
done

CONFIG_DIR=$(dirname "$CONFIG_PATH")
WORKFLOWS_DIR="${CONFIG_DIR}/workflows"
POLL_STATE="${CONFIG_DIR}/poll-state.yaml"
FRESHNESS="${CONFIG_DIR}/freshness.yaml"
LOG_DIR="${CONFIG_DIR}/log"
LOG_FILE="${LOG_DIR}/heartbeat.log"

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
        LAST_EPOCH=$(date -jf "%Y-%m-%dT%H:%M:%SZ" "$LAST_RUN" +%s 2>/dev/null || date -d "$LAST_RUN" +%s 2>/dev/null || echo 0)
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
                releases)
                    CURR=$(gh api "/repos/${OWNER_REPO}/releases?per_page=1" 2>/dev/null || echo "[]")
                    CURR_ID=$(echo "$CURR" | jq -r '.[0].id // empty')
                    PREV_ID=$(yq -r '.state.releases.latest_id // "null"' "$POLL_STATE")
                    if [[ -n "$CURR_ID" && "$CURR_ID" != "$PREV_ID" ]]; then
                        SHOULD_TRIGGER=true
                        CURR_TAG=$(echo "$CURR" | jq -r '.[0].tag_name // "null"')
                        yq -i ".state.releases.latest_id = \"$CURR_ID\"" "$POLL_STATE"
                        yq -i ".state.releases.latest_tag = \"$CURR_TAG\"" "$POLL_STATE"
                    fi
                    ;;
                dependabot)
                    CURR=$(gh api "/repos/${OWNER_REPO}/dependabot/alerts?state=open&per_page=1&sort=updated" 2>/dev/null || echo "SKIP")
                    if [[ "$CURR" != "SKIP" ]]; then
                        CURR_COUNT=$(echo "$CURR" | jq 'length' 2>/dev/null || echo "0")
                        PREV_COUNT=$(yq -r '.state.dependabot.open_count // 0' "$POLL_STATE")
                        if [[ "$CURR_COUNT" != "$PREV_COUNT" ]]; then
                            SHOULD_TRIGGER=true
                            yq -i ".state.dependabot.open_count = $CURR_COUNT" "$POLL_STATE"
                        fi
                    fi
                    ;;
                deployments)
                    CURR=$(gh api "/repos/${OWNER_REPO}/deployments?per_page=1" 2>/dev/null || echo "[]")
                    CURR_ID=$(echo "$CURR" | jq -r '.[0].id // empty')
                    PREV_ID=$(yq -r '.state.deployments.latest_id // "null"' "$POLL_STATE")
                    if [[ -n "$CURR_ID" && "$CURR_ID" != "$PREV_ID" ]]; then
                        SHOULD_TRIGGER=true
                        CURR_ENV=$(echo "$CURR" | jq -r '.[0].environment // "null"')
                        yq -i ".state.deployments.latest_id = \"$CURR_ID\"" "$POLL_STATE"
                        yq -i ".state.deployments.latest_environment = \"$CURR_ENV\"" "$POLL_STATE"
                    fi
                    ;;
                projects)
                    # Get current user login
                    GH_USER=$(gh api /user --jq '.login' 2>/dev/null || echo "")
                    if [[ -z "$GH_USER" ]]; then
                        break
                    fi

                    # Build batched GraphQL query with aliases for all catalog projects
                    PROJECT_IDS=$(yq -r '.projects.catalog[].id' "$CONFIG_PATH" 2>/dev/null)
                    if [[ -z "$PROJECT_IDS" ]]; then
                        break
                    fi

                    QUERY="query {"
                    ALIAS_IDX=0
                    ALIAS_KEYS=""
                    ALIAS_VALS=""
                    while IFS= read -r PID; do
                        [[ -z "$PID" ]] && continue
                        P_NUM=$(yq -r ".projects.catalog[] | select(.id == \"$PID\") | .number" "$CONFIG_PATH")
                        P_TITLE=$(yq -r ".projects.catalog[] | select(.id == \"$PID\") | .title" "$CONFIG_PATH")
                        ALIAS="p${ALIAS_IDX}"
                        ALIAS_KEYS="${ALIAS_KEYS}${ALIAS_KEYS:+ }${ALIAS}"
                        ALIAS_VALS="${ALIAS_VALS}${ALIAS_VALS:+ }${P_NUM}|${P_TITLE}"
                        QUERY+=" ${ALIAS}: node(id: \"${PID}\") { ... on ProjectV2 { items(first: 100) { nodes { id content { __typename ... on Issue { number title } ... on PullRequest { number title } ... on DraftIssue { title } } fieldValues(first: 20) { nodes { ... on ProjectV2ItemFieldUserValue { users(first: 10) { nodes { login } } } } } } } } }"
                        ALIAS_IDX=$((ALIAS_IDX + 1))
                    done <<< "$PROJECT_IDS"
                    QUERY+=" }"

                    # Execute single batched query
                    RESULT=$(gh api graphql -f query="$QUERY" 2>/dev/null || echo "")
                    if [[ -z "$RESULT" ]]; then
                        break
                    fi

                    # Extract assignments for current user across all projects
                    CURR_ASSIGNMENTS="[]"
                    IDX=0
                    for ALIAS in $ALIAS_KEYS; do
                        VAL=$(echo "$ALIAS_VALS" | tr ' ' '\n' | sed -n "$((IDX + 1))p")
                        IFS='|' read -r P_NUM P_TITLE <<< "$VAL"
                        IDX=$((IDX + 1))
                        # Filter items where current user is in fieldValues users
                        ITEMS=$(echo "$RESULT" | jq -r --arg alias "$ALIAS" --arg user "$GH_USER" --arg pnum "$P_NUM" --arg ptitle "$P_TITLE" '
                            [.data[$alias].items.nodes[] |
                             select(.fieldValues.nodes | any(.users?.nodes? // [] | any(.login == $user))) |
                             {
                               id: .id,
                               number: (.content.number // null),
                               title: (.content.title // "Draft"),
                               type: (if .content.__typename == "Issue" then "issue" elif .content.__typename == "PullRequest" then "pull_request" else "draft" end)
                             }] |
                            if length > 0 then
                              {project: $ptitle, project_number: ($pnum | tonumber), items: .}
                            else empty end
                        ' 2>/dev/null || echo "")
                        if [[ -n "$ITEMS" && "$ITEMS" != "null" ]]; then
                            CURR_ASSIGNMENTS=$(echo "$CURR_ASSIGNMENTS" | jq --argjson item "$ITEMS" '. + [$item]')
                        fi
                    done

                    # Also track total item count on default project for backward compat
                    DEFAULT_PROJECT=$(yq -r '.projects.default // ""' "$CONFIG_PATH")
                    CURR_COUNT=""
                    if [[ -n "$DEFAULT_PROJECT" && "$DEFAULT_PROJECT" != "null" ]]; then
                        IDX=0
                        for ALIAS in $ALIAS_KEYS; do
                            VAL=$(echo "$ALIAS_VALS" | tr ' ' '\n' | sed -n "$((IDX + 1))p")
                            IFS='|' read -r P_NUM _ <<< "$VAL"
                            IDX=$((IDX + 1))
                            if [[ "$P_NUM" == "$DEFAULT_PROJECT" ]]; then
                                CURR_COUNT=$(echo "$RESULT" | jq -r --arg alias "$ALIAS" '.data[$alias].items.nodes | length' 2>/dev/null || echo "")
                                break
                            fi
                        done
                    fi

                    # Compare assignments
                    PREV_ASSIGNMENTS=$(yq -o=json -r '.state.projects.my_assignments // "[]"' "$POLL_STATE" 2>/dev/null || echo "[]")
                    CURR_ASSIGNMENTS_SORTED=$(echo "$CURR_ASSIGNMENTS" | jq -S '.' 2>/dev/null || echo "[]")
                    PREV_ASSIGNMENTS_SORTED=$(echo "$PREV_ASSIGNMENTS" | jq -S '.' 2>/dev/null || echo "[]")

                    if [[ "$CURR_ASSIGNMENTS_SORTED" != "$PREV_ASSIGNMENTS_SORTED" ]]; then
                        SHOULD_TRIGGER=true
                    fi

                    # Compare item count (backward compat)
                    PREV_COUNT=$(yq -r '.state.projects.item_count // 0' "$POLL_STATE")
                    if [[ -n "$CURR_COUNT" && "$CURR_COUNT" != "$PREV_COUNT" ]]; then
                        SHOULD_TRIGGER=true
                    fi

                    # Update state
                    if [[ -n "$CURR_COUNT" ]]; then
                        yq -i ".state.projects.item_count = $CURR_COUNT" "$POLL_STATE"
                    fi
                    # Write assignments to poll-state via temp file in config dir
                    ASSIGNMENTS_FILE="${CONFIG_DIR}/.assignments-tmp.json"
                    echo "$CURR_ASSIGNMENTS" > "$ASSIGNMENTS_FILE"
                    yq -i ".state.projects.my_assignments = load(\"$ASSIGNMENTS_FILE\")" "$POLL_STATE"
                    rm -f "$ASSIGNMENTS_FILE"

                    unset ALIAS_KEYS ALIAS_VALS
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
if (( ${#TRIGGERED[@]} == 0 )); then
    TRIGGERED_JSON="[]"
else
    TRIGGERED_JSON=$(printf '%s\n' "${TRIGGERED[@]}" | jq -R . | jq -s .)
fi
if (( ${#AUTO_WORKFLOWS[@]} == 0 )); then
    AUTO_JSON="[]"
else
    AUTO_JSON=$(printf '%s\n' "${AUTO_WORKFLOWS[@]}" | jq -R . | jq -s .)
fi

# Log the run
mkdir -p "$LOG_DIR"
LOG_ENTRY="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] {\"stale_sections\": ${STALE_SECTIONS}, \"triggered_workflows\": ${TRIGGERED_JSON}, \"auto_workflows\": ${AUTO_JSON}}"
echo "$LOG_ENTRY" >> "$LOG_FILE"

# Trim log if over 500 lines
if [[ $(wc -l < "$LOG_FILE") -gt 500 ]]; then
    tail -n 250 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

echo "{\"stale_sections\": ${STALE_SECTIONS}, \"triggered_workflows\": ${TRIGGERED_JSON}, \"auto_workflows\": ${AUTO_JSON}}"
