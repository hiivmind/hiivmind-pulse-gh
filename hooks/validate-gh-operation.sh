#!/bin/bash
# validate-gh-operation.sh
# PreToolUse hook to block dangerous GitHub operations
#
# Exit codes (per Claude Code docs):
#   0 = allow (success)
#   2 = block (stderr shown to Claude)
#   1 = non-blocking continue

# Read input from stdin
input=$(cat 2>/dev/null) || input='{}'

# Extract command using jq
command=$(echo "$input" | jq -r '.tool_input.command // ""' 2>/dev/null) || command=""

# Exit early if not a gh command - ALLOW all non-gh commands
if [[ -z "$command" ]] || [[ ! "$command" =~ ^gh[[:space:]] ]]; then
  exit 0
fi

# Blocked patterns (case-insensitive)
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
    # Exit 2 blocks, stderr shown to Claude
    echo "BLOCKED: This operation is too dangerous for automation. Use GitHub web UI." >&2
    exit 2
  fi
done

# Allow - exit 0
exit 0
