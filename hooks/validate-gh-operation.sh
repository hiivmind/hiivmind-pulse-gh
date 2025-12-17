#!/bin/bash
# validate-gh-operation.sh
# PreToolUse hook to block dangerous GitHub operations
#
# This script provides defense-in-depth safety by blocking dangerous
# operations at execution time, even if the LLM or skill-level checks fail.

set -euo pipefail

input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Exit early if not a gh command
if [[ ! "$command" =~ ^gh[[:space:]] ]]; then
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
  if echo "$command" | grep -qiE "$pattern"; then
    echo '{"decision": "deny", "reason": "BLOCKED: This operation is too dangerous for automation. Please use the GitHub web UI instead."}' >&2
    exit 2
  fi
done

# Allow if no blocked pattern matched
echo '{"decision": "allow"}'
exit 0
