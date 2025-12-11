# Bash Subshell Variable Tracking

## Problem

When using command substitution `$(...)` in Bash, the command runs in a **subshell**. Any modifications to global variables inside that subshell are **lost** when the subshell exits.

This caused a critical bug in our resource tracking system where resources created via setup functions weren't being cleaned up.

## The Bug

```bash
# Global tracking variable
declare -g TRACKED_RESOURCES=""

track_resource() {
    TRACKED_RESOURCES+="${type}:${identifier} "  # This update is LOST in subshells
}

create_milestone() {
    # ... create milestone via API ...
    track_resource "milestone" "${owner}/${repo}/${number}"  # Called in subshell!
    echo "$number"
}

# In the caller:
local result=$(create_milestone "$org" "$repo" "$title")  # Runs in SUBSHELL
# TRACKED_RESOURCES is still empty here!
```

## Why It Happens

Command substitution `$(command)` creates a subshell to capture stdout. The subshell:
1. Gets a **copy** of all variables
2. Can modify its copy freely
3. Returns only stdout to the parent
4. All variable changes are **discarded** when subshell exits

This is fundamental to how Bash works and cannot be changed.

## Solution: Separate Raw Functions

Create "raw" versions of functions that don't track, then track in the parent shell:

```bash
# Raw function - no tracking, safe for subshells
create_milestone_raw() {
    local owner="$1"
    local repo="$2"
    local title="$3"

    local result=$(gh api "repos/${owner}/${repo}/milestones" -f "title=${title}")
    local number=$(echo "$result" | jq -r '.number')

    echo "$number"  # Only output to stdout
}

# Tracking wrapper - calls raw, then tracks in parent shell
create_milestone() {
    local owner="$1"
    local repo="$2"
    local number
    number=$(create_milestone_raw "$@")  # Subshell, but no tracking inside
    if [[ $? -eq 0 ]]; then
        track_resource "milestone" "${owner}/${repo}/${number}"  # Track in PARENT shell
        echo "$number"
    else
        return 1
    fi
}
```

## When to Use Raw Functions

Use `_raw` functions when you need to:
1. Capture the result in a variable with `$(...)`
2. Track the resource in the parent shell's context
3. Ensure cleanup will work properly

```bash
# In setup code that needs cleanup:
local result=$(create_milestone_raw "$org" "$repo" "$title")
track_resource "milestone" "${org}/${repo}/${result}"  # Tracked in correct scope
```

## Alternative Solutions (Not Recommended)

### 1. Temp Files
```bash
# Write tracking info to temp file, read back in parent
create_milestone() {
    # ... create ...
    echo "milestone:${owner}/${repo}/${number}" >> "$TRACKING_FILE"
}
```
Downsides: File I/O overhead, cleanup complexity, race conditions

### 2. Named Pipes / FIFOs
Complex to implement correctly, overkill for this use case.

### 3. Process Substitution
Doesn't solve the fundamental issue of variable scope.

## Related Issue: Pipe Fallbacks

Another related bug was in our sanitization code:

```bash
# BROKEN: Fallback doesn't work with pipes
sanitize_timestamps() {
    jq '..complex query..' 2>/dev/null || cat
    # If jq fails, 'cat' has nothing to read - stdin was consumed by jq
}

# FIXED: Buffer input first
sanitize_timestamps() {
    local input
    input=$(cat)  # Buffer entire input
    echo "$input" | jq '...' 2>/dev/null || echo "$input"
}
```

## Testing for Subshell Issues

Debug with verbose tracking:

```bash
export RESOURCE_DEBUG=true
./record_fixtures.bash --fixture milestone list_populated
```

Look for:
- `[TRACK]` messages showing resources being tracked
- `[CLEANUP]` messages showing cleanup running
- Empty identifiers like `milestone:owner/repo/` (missing ID = subshell bug)

## Key Takeaways

1. **Never modify global state inside `$(...)`** if you need to preserve it
2. **Separate concerns**: output vs side effects should be in different functions
3. **Buffer stdin** before using it in fallback scenarios
4. **Test cleanup explicitly** - silent failures are the worst kind
