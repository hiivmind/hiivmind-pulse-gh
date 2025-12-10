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

## References

- GitHub Issue: hiivmind/hiivmind-pulse-gh#8
- Claude Code GitHub: https://github.com/anthropics/claude-code/issues (report if needed)
