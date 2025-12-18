# Testing Framework Implementation Learnings

Lessons learned while implementing Phase 2 of the testing framework (fixture recording, drift detection, resource management).

## Bash Arithmetic and `set -e`

### Problem
Script exits unexpectedly after incrementing a counter:
```bash
set -e
count=0
((count++))  # Script exits here!
```

### Root Cause
In bash, `((expression))` returns the **value** of the expression as its exit code. When `count` is 0 and you do `((count++))`, the expression evaluates to 0 (the pre-increment value), which bash interprets as "false" (exit code 1).

With `set -e` enabled, any command returning non-zero exits the script.

### Solution
Append `|| true` to prevent the exit:
```bash
((count++)) || true
```

Or use `let` with a default:
```bash
let count+=1 || true
```

### Reference
- Bash manual: "The return status is 1 if the last expression evaluated to 0, and 0 otherwise."

---

## GitHub CLI GraphQL Variable Passing

### Problem
GraphQL variables passed via `--input` with yq output:
```bash
variables_json=$(yq -o=json ".variables" manifest.yaml)
gh api graphql --input <(echo "{\"query\": \"$query\", \"variables\": $variables_json}")
# Error: "A query attribute must be specified and must be a string."
```

### Root Cause
The `gh api graphql` command expects either:
1. A simple `-f query=...` with optional `-f`/`-F` variable flags
2. OR a complete request body via `--input`

Mixing `--input` with `-f query=` causes conflicts.

### Solution
Pass variables as individual flags:
```bash
args=(-f "query=$query")
while IFS='=' read -r key value; do
    if [[ "$value" =~ ^[0-9]+$ ]]; then
        args+=(-F "$key=$value")  # -F for numbers (raw JSON)
    else
        args+=(-f "$key=$value")  # -f for strings
    fi
done < <(echo "$variables_json" | jq -r 'to_entries[] | "\(.key)=\(.value)"')

gh api graphql "${args[@]}"
```

### Key Insight
- `-f` flag: Wraps value in quotes (for strings)
- `-F` flag: Passes value as raw JSON (for numbers, booleans)

---

## Stdin Consumption in Pipeline Fallbacks

### Problem
Fallback doesn't work when jq fails:
```bash
sanitize_timestamps() {
    jq '...' 2>/dev/null || cat  # Fallback to passthrough
}
```

When jq fails, `cat` outputs nothing.

### Root Cause
In a pipeline like `input | sanitize_timestamps`, stdin is consumed by `jq`. When jq fails, there's nothing left for `cat` to read - stdin is already exhausted.

### Solution
Buffer stdin before processing:
```bash
sanitize_timestamps() {
    local input
    input=$(cat)  # Capture all stdin first

    echo "$input" | jq '...' 2>/dev/null || echo "$input"
}
```

### Key Insight
When you need a fallback that re-reads input, always buffer stdin first.

---

## jq Paths and Null Values

### Problem
Schema comparison misses fields with null values:
```bash
# Fixture has: {"name": "Test User", ...}
# Live API has: {"name": null, ...}
# Drift detection reports "name" as missing from live!

jq '[paths(scalars)]'  # Only finds paths to scalar VALUES
```

### Root Cause
`paths(scalars)` only returns paths where the leaf value is a scalar (string, number, boolean). `null` is not a scalar in jq's type system.

### Solution
Include both scalars and nulls:
```bash
jq '[paths(scalars), paths(. == null)] | flatten(1) | unique'
```

### Key Insight
When comparing JSON schemas, remember that `null` is a distinct type, not a scalar.

---

## Manifest Defaults vs Script Defaults

### Problem
Fixtures being created on wrong repository:
```yaml
# Manifest defaults section (documentation only)
defaults:
  test_repo: "hiivmind-pulse-test-fixtures"
```
```bash
# Script defaults (actually used)
: "${TEST_REPO:=hiivmind-pulse-gh}"  # Wrong default!
```

### Root Cause
The manifest's `defaults:` section was intended as documentation/override capability, but the script had hardcoded different defaults. Fixtures without explicit `test_repo` used the script default.

### Solution
Either:
1. Add explicit `test_repo` to each fixture in manifest
2. Or load defaults from manifest in the script:
```bash
TEST_REPO=$(yq '.defaults.test_repo' "$MANIFEST_FILE")
```

### Key Insight
When configuration can come from multiple sources, ensure they're synchronized or clearly document which takes precedence.

---

## Sanitization Adding Extra Fields

### Problem
Sanitizer adds fields that didn't exist in original:
```bash
# Original: {"avatarUrl": "https://..."}
# After sanitize: {"avatarUrl": "...", "avatar_url": "..."}  # Extra field!
```

### Root Cause
Sanitizer code assumed both fields might exist and set both:
```bash
(if .avatarUrl or .avatar_url then
    .avatarUrl = "sanitized" |
    .avatar_url = "sanitized"  # Creates if doesn't exist!
else . end)
```

### Solution
Check each field independently:
```bash
(if .avatarUrl then .avatarUrl = "sanitized" else . end) |
(if .avatar_url then .avatar_url = "sanitized" else . end)
```

### Key Insight
In jq, assignment to a non-existent key creates it. Always check existence before assignment if you want to preserve structure.

---

## jq Comments Inside Bash Single Quotes

### Problem
Bash syntax error on line containing jq comment:
```bash
sanitize_generic() {
    jq '
        # This comment with (parentheses) causes problems
        (if .x then .x = "y" else . end)
    '
}
# Error: syntax error near unexpected token `)'
```

### Root Cause
While content inside single quotes shouldn't be parsed by bash, certain edge cases with blank lines followed by comments containing special characters can confuse the parser.

### Solution
Remove blank lines between jq expressions, or ensure comments don't have unbalanced special characters:
```bash
jq '
    (if .email then .email = "test" else . end) |
    # Comment here is fine when directly followed by expression
    (if .name then .name = "test" else . end)
'
```

### Key Insight
When embedding multi-line jq in bash, minimize blank lines within the quoted string and be cautious with comment content.

---

## Resource Tracking in Subshells

### Problem (from previous session)
Resources created in command substitution aren't tracked:
```bash
result=$(create_milestone "$org" "$repo" "Title")  # Runs in subshell
# TRACKED_RESOURCES not updated in parent!
```

### Root Cause
Command substitution `$(...)` runs in a subshell. Variable changes in subshells don't propagate to the parent.

### Solution
Use `_raw` functions that only return values, then track in parent:
```bash
result=$(create_milestone_raw "$org" "$repo" "Title")
track_resource "milestone" "$org/$repo/$result"  # Track in parent
```

### Reference
See `knowledge/bash-subshell-variable-tracking.md` for full details.

---

## Summary of Best Practices

1. **Arithmetic with `set -e`**: Always use `|| true` after `((expr))`
2. **gh CLI GraphQL**: Use `-f`/`-F` flags for variables, not `--input`
3. **Pipeline fallbacks**: Buffer stdin before processing
4. **jq schema comparison**: Include both `paths(scalars)` and `paths(. == null)`
5. **Multi-source config**: Document which source takes precedence
6. **jq sanitization**: Check field existence before assignment
7. **Subshell tracking**: Use `_raw` functions + explicit tracking in parent
