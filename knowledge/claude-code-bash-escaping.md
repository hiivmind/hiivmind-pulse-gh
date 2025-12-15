# Claude Code Bash Tool Escaping Bug

> **Document ID:** KB-001
> **Created:** 2025-12-10
> **Status:** Active
> **Related Issue:** #8

## Summary

Claude Code's Bash tool has a bug that mangles command syntax when specific patterns are combined. This causes syntax errors that appear to originate from shell functions but are actually caused by improper command transformation.

## The Bug

When a Bash command contains **all** of the following elements:
1. Variable assignment (`VAR="value"`)
2. Command substitution with variable interpolation (`RESULT=$(command "$VAR")`)
3. A pipe operator (`|`) later in the command

The Bash tool transforms the command incorrectly:
- `$` in `$(...)` becomes `\$`
- Parentheses get spaces added around them
- Variable references like `"$VAR"` become empty strings `''`
- Stdin redirection `< /dev/null` is injected

### Example

**Input command:**
```bash
LOGIN="discreteds" && TYPE="user" && source lib/functions.sh && PROJECTS=$(discover_projects "$LOGIN" "$TYPE") && echo "$PROJECTS" | format_list
```

**What Claude Code executes:**
```bash
LOGIN=discreteds && TYPE=user && source lib/functions.sh && PROJECTS=\$ ( discover_projects '' '' ) && echo '' < /dev/null | format_list
```

**Result:** `syntax error near unexpected token '('`

## Conditions

| Element | Bug Triggered? |
|---------|---------------|
| `VAR=$(command)` alone | No |
| `VAR=$(command "$X")` alone | No |
| `VAR=$(command) && echo "$VAR"` | No |
| `VAR=$(command "$X") \| pipe` | **YES** |

The pipe operator at the end appears to trigger different escaping behavior that corrupts the entire command.

## Workarounds

### 1. Use Pipe-First Design (Recommended)

Instead of capturing to a variable then piping:
```bash
# BAD - triggers bug
PROJECTS=$(discover_projects "$LOGIN" "$TYPE") && echo "$PROJECTS" | format_list
```

Pipe directly:
```bash
# GOOD - works correctly
discover_projects "$LOGIN" "$TYPE" | format_list
```

### 2. Split Into Separate Commands

If you need the variable, use two separate Bash tool calls:
```bash
# First call - capture
PROJECTS=$(discover_projects "$LOGIN" "$TYPE")
```
```bash
# Second call - use
echo "$PROJECTS" | format_list
```

### 3. Avoid Variable Interpolation in Substitution

Use literal values instead of variables:
```bash
# GOOD - works
PROJECTS=$(discover_projects "discreteds" "user") && echo "$PROJECTS" | format_list
```

## Architectural Implications

This bug has implications for how shell function libraries should be designed for use with Claude Code:

### Pipe-First Pattern (Recommended)

Design functions as stdin→stdout transformers that compose via pipes:

```bash
# Functions produce stdout
fetch_data() { gh api ... }

# Functions consume stdin, produce stdout
format_output() { jq '...' }

# Composition via pipes - no intermediate variables needed
fetch_data | filter_items | format_output
```

### Assignment Pattern (Avoid)

Avoid patterns that require intermediate variable capture:

```bash
# This pattern is fragile with Claude Code
DATA=$(fetch_data)
FILTERED=$(echo "$DATA" | filter_items)
echo "$FILTERED" | format_output
```

## Detection

If you see errors like:
- `syntax error near unexpected token '('`
- Command shows `\$ (` instead of `$(`
- Variables appear as empty strings `''`
- Unexpected `< /dev/null` in the executed command

The cause is likely this Bash tool escaping bug, not your shell code.

## Related Files

- `lib/github/gh-project-functions.sh` - Uses pipe-first design, not affected
- `lib/github/gh-workspace-functions.sh` - Uses assignment pattern, affected
- `skills/hiivmind-pulse-gh-workspace-init/SKILL.md` - Documents assignment pattern

---

## Bug #2: `!=` Operator Escaping

> **Discovered:** 2025-12-15
> **Status:** Active
> **Related Issue:** #44

### Summary

Claude Code's Bash tool incorrectly escapes the `!=` operator in bash conditionals, transforming it to `\!=` which causes a syntax error.

### The Bug

When a bash `[[ ]]` conditional contains `!=`:

**Input command:**
```bash
if [[ "$LAST_SYNC" != "null" && -n "$LAST_SYNC" ]]; then
  echo "valid"
fi
```

**What Claude Code executes:**
```bash
if [[ "$LAST_SYNC" \!= "null" && -n "$LAST_SYNC" ]]; then
```

**Result:**
```
/bin/bash: eval: line 41: conditional binary operator expected
/bin/bash: eval: line 41: syntax error near `\!='
```

### Root Cause

The `!` character has special meaning in bash (history expansion). Claude Code's Bash tool appears to escape it in certain contexts where it shouldn't, specifically within `[[ ]]` conditionals.

### Affected File

`commands/hiivmind-pulse-gh.md` line 61 (Step 2b: Check Freshness):

```bash
if [[ "$LAST_SYNC" != "null" && -n "$LAST_SYNC" ]]; then
```

### Workarounds

#### 1. Negate Equality Instead (Recommended)

```bash
# BAD - triggers bug
if [[ "$LAST_SYNC" != "null" ]]; then

# GOOD - works correctly
if [[ ! "$LAST_SYNC" = "null" ]]; then
```

#### 2. Use Single Bracket Test

```bash
# Alternative - use [ ] instead of [[ ]]
if [ "$LAST_SYNC" != "null" ]; then
```

#### 3. Split Conditions

```bash
# Separate the checks
if [[ "$LAST_SYNC" = "null" ]]; then
  echo "STALE=unknown"
else
  # ... process valid date
fi
```

### Detection

If you see errors like:
- `conditional binary operator expected`
- `syntax error near '\!='`
- The executed command shows `\!=` instead of `!=`

The cause is this escaping bug.

---

## Recommended Patterns

> **Updated:** 2025-12-16
> **Based on:** Complete refactoring of init, refresh, and operations skills

### Function-Based Pattern (Safest)

To avoid both Bug #1 and Bug #2, use parameterized functions with local scope:

**Good Example:**
```bash
fetch_project_fields() {
  local owner="$1"
  local project_num="$2"

  gh api graphql -f query='...' \
    -f owner="$owner" \
    -F number="$project_num" | jq '.data.organization.projectV2'
}

# Usage:
fetch_project_fields "hiivmind" 2
```

**Benefits:**
- ✅ No intermediate variable capture (avoids Bug #1)
- ✅ Clear parameter contract
- ✅ Testable and reusable
- ✅ Local scope prevents variable conflicts
- ✅ Pipe-first design (stdout composition)

### Key Rules

1. **Always use `local`** for function variables
   ```bash
   # GOOD
   fetch_data() {
     local owner="$1"
     local repo="$2"
     gh api "/repos/$owner/$repo"
   }

   # BAD - global variables
   fetch_data() {
     OWNER="$1"
     REPO="$2"
     gh api "/repos/$OWNER/$REPO"
   }
   ```

2. **Avoid `VAR=$(... | pipe)` patterns**
   ```bash
   # BAD - triggers Bug #1
   REVIEWERS=$(get_repo_writers "$REPO" | head -3 | tr '\n' ',')

   # GOOD - encapsulate in function
   format_reviewers() {
     local repo="$1"
     get_repo_writers "$repo" | head -3 | tr '\n' ','
   }
   REVIEWERS=$(format_reviewers "$REPO")
   ```

3. **Use `! ... =` instead of `!=`**
   ```bash
   # BAD - triggers Bug #2
   if [[ "$VAR" != "null" ]]; then

   # GOOD - avoids Bug #2
   if [[ ! "$VAR" = "null" ]]; then
   ```

4. **Declare variables before assignment**
   ```bash
   # GOOD - separate declaration from complex assignment
   local admin_teams write_teams all_teams

   admin_teams=$(yq "..." "$teams_file" 2>/dev/null)
   write_teams=$(yq "..." "$teams_file" 2>/dev/null)
   all_teams=$(printf "%s\n%s" "$admin_teams" "$write_teams" | sort -u)
   ```

### Examples from Refactoring

#### Init Skill
```bash
discover_projects() {
  local login="$1"
  local type="$2"  # "organization" or "user"

  if [[ "$type" = "organization" ]]; then
    gh api graphql -f query='...' -f login="$login" --jq '...'
  else
    gh api graphql -f query='...' -f login="$login" --jq '...'
  fi
}
```

#### Refresh Skill
```bash
refresh_project_views() {
  local config="$1"
  local project_num="$2"
  local owner view_data project_id project_title

  owner=$(yq '.workspace.login' "$config")
  view_data=$(gh api graphql -f query='...' -f owner="$owner" -F number="$project_num")

  # Process and generate YAML
  cat > ".hiivmind/github/views/project-$project_num.yaml" << EOF
...
EOF
}
```

#### Operations Skill
```bash
add_project_item() {
  local project_id="$1"
  local content_id="$2"

  gh api graphql -f query='mutation($projectId: ID!, $contentId: ID!) { ... }' \
    -f projectId="$project_id" -f contentId="$content_id" --jq '.data.addProjectV2ItemById.item.id'
}
```

### Pattern Decision Tree

```
Is it a simple gh CLI command without variables?
├─ Yes → Use directly (e.g., gh issue create ...)
└─ No → Does it need variable substitution?
    ├─ Yes → Does it have pipes or complex logic?
    │   ├─ Yes → Wrap in a parameterized function
    │   └─ No → Direct command is safe
    └─ No → Use directly
```

---

## References

- GitHub Issue: hiivmind/hiivmind-pulse-gh#8 (pipe escaping bug)
- GitHub Issue: hiivmind/hiivmind-pulse-gh#44 (inequality operator bug)
- Refactoring Summary: `docs/refactoring-summary.md`
- Example Pattern: `lib/corpus/patterns/scanning.md`
- Claude Code GitHub: https://github.com/anthropics/claude-code/issues (report if needed)
