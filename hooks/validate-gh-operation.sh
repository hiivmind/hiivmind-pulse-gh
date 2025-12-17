#!/bin/bash
# validate-gh-operation.sh
# PreToolUse hook to block dangerous GitHub operations
#
# This script provides defense-in-depth safety by blocking dangerous
# operations at execution time, even if the LLM or skill-level checks fail.

# Read input - default to empty if fails
input=$(cat 2>/dev/null || echo '{}')

# Extract command - default to empty string if jq fails
command=$(echo "$input" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")

# Exit early if not a gh command - ALLOW all non-gh commands
if [[ -z "$command" ]] || [[ ! "$command" =~ ^gh[[:space:]] ]]; then
  echo '{"decision": "allow"}'
  exit 0
fi

# Blocked patterns (case-insensitive)
# Each pattern targets a specific dangerous operation
BLOCKED_PATTERNS=(
  # Repository deletion - irreversible data loss
  "gh api.*-X DELETE.*/repos/[^/]+/[^/]+$"

  # Repository transfer - ownership change
  "gh api.*/repos/[^/]+/[^/]+/transfer"

  # Repository archive - can break CI/CD workflows
  "gh api.*archived.*true"

  # Organization deletion - catastrophic
  "gh api.*-X DELETE.*/orgs/"

  # Bulk member removal - dangerous bulk operation
  "gh api.*/orgs/[^/]+/members.*-X DELETE"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if echo "$command" | grep -qiE "$pattern" 2>/dev/null; then
    # Output to STDOUT (not stderr) for Claude Code to read
    echo '{"decision": "block", "reason": "BLOCKED: This operation is too dangerous for automation. Please use the GitHub web UI instead."}'
    exit 0
  fi
done

# Allow if no blocked pattern matched
echo '{"decision": "allow"}'
exit 0
