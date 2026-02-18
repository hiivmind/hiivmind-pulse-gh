#!/usr/bin/env bash
# hiivmind-pulse-gh - PostToolUse hook for post-operation workflow triggers
# Detects completed gh commands and matches against workflow triggers
# See: lib/references/workflow-triggers.md

set -euo pipefail

# Read tool input from stdin
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null || echo "")
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")

# Only process Bash tool calls containing gh commands
if [[ "$TOOL_NAME" != "Bash" ]] || [[ "$COMMAND" != *"gh "* ]]; then
    exit 0
fi

# Detect operation source from command
SOURCE=""
case "$COMMAND" in
    *"gh issue create"*|*"gh api"*"issues"*"-X POST"*) SOURCE="issue_created" ;;
    *"gh issue close"*)  SOURCE="issue_closed" ;;
    *"gh pr create"*)    SOURCE="pr_created" ;;
    *"gh pr merge"*)     SOURCE="pr_merged" ;;
    *"gh workflow run"*) SOURCE="workflow_triggered" ;;
esac

if [[ -z "$SOURCE" ]]; then
    exit 0
fi

# Find config
CONFIG_DIR=""
if [[ -d ".hiivmind/github/workflows" ]]; then
    CONFIG_DIR=".hiivmind/github"
elif [[ -d "../.hiivmind/github/workflows" ]]; then
    CONFIG_DIR="../.hiivmind/github"
else
    exit 0
fi

# Match against post_operation workflow triggers
MATCHED=()
for WF_FILE in "$CONFIG_DIR/workflows"/*.yaml; do
    [[ -f "$WF_FILE" ]] || continue

    ENABLED=$(yq -r '.enabled // true' "$WF_FILE")
    [[ "$ENABLED" == "true" ]] || continue

    TRIGGER_TYPE=$(yq -r '.trigger.type' "$WF_FILE")
    [[ "$TRIGGER_TYPE" == "post_operation" ]] || continue

    WF_SOURCE=$(yq -r '.trigger.source' "$WF_FILE")
    if [[ "$WF_SOURCE" == "$SOURCE" ]]; then
        WF_NAME=$(yq -r '.name' "$WF_FILE")
        MATCHED+=("$WF_NAME")
    fi
done

if [[ ${#MATCHED[@]} -gt 0 ]]; then
    MATCHED_JSON=$(printf '%s\n' "${MATCHED[@]}" | jq -R . | jq -s .)
    echo "{\"post_operation_source\": \"$SOURCE\", \"triggered_workflows\": ${MATCHED_JSON}}"
fi
