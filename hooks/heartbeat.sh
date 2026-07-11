#!/usr/bin/env bash
# hiivmind-pulse-gh - SessionStart heartbeat hook (thin wrapper)
# Resolves interactive context (workspace root, repo, overlay) and delegates
# all polling to lib/pulse/scripts/poll.py. See: lib/patterns/poll-state.md

set -euo pipefail

# Resolve workspace root: walk up to the first .hiivmind/github/config.yaml
# carrying a `workspace:` section (repo overlays lack it and are skipped).
# See: lib/patterns/workspace-detection.md § Workspace Root Resolution
WORKSPACE_ROOT=""
DIR="$PWD"
while [[ "$DIR" != "/" ]]; do
    if [[ -f "$DIR/.hiivmind/github/config.yaml" ]] \
       && grep -q '^workspace:' "$DIR/.hiivmind/github/config.yaml"; then
        WORKSPACE_ROOT="$DIR"
        break
    fi
    DIR="$(dirname "$DIR")"
done

# Exit early if not initialized
if [[ -z "$WORKSPACE_ROOT" ]]; then
    exit 0
fi

# Check required tools (exit 0 with error JSON so hook doesn't crash the session)
for tool in gh uv; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "{\"error\": \"missing_tool\", \"tool\": \"$tool\"}"
        exit 0
    fi
done

# Repo overlay workflows (D2)
OVERLAY_WORKFLOWS=""
REPO_TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -n "$REPO_TOPLEVEL" && "$REPO_TOPLEVEL" != "$WORKSPACE_ROOT" \
      && -d "$REPO_TOPLEVEL/.hiivmind/github/workflows" ]]; then
    OVERLAY_WORKFLOWS="$REPO_TOPLEVEL/.hiivmind/github/workflows"
fi

# Detect owner/repo from git remote (D3: repo-filtered slice)
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
OWNER_REPO=""
if [[ -n "$REMOTE_URL" ]]; then
    OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's#.*[:/]([^/]+/[^/.]+)(\.git)?$#\1#')
fi

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

exec uv run "$PLUGIN_ROOT/lib/pulse/scripts/poll.py" \
    --workspace "$WORKSPACE_ROOT" \
    --plugin-root "$PLUGIN_ROOT" \
    ${OWNER_REPO:+--repo "$OWNER_REPO"} \
    ${OVERLAY_WORKFLOWS:+--overlay-workflows "$OVERLAY_WORKFLOWS"}
