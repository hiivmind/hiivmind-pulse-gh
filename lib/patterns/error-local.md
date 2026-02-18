# Pattern: Local & Config Errors

## Purpose

Detect and recover from local configuration, tool availability, and YAML parsing errors.

## When to Use

- When config files are missing or malformed
- When required tools (gh, jq, yq) are not found
- When workspace is not initialized

**Parent:** See `error-handling.md` for the error detection overview and recovery flow.

---

## Config File Not Found

**Error:**
```
Configuration file not found at .hiivmind/github/config.yaml
```

**Detection:**
```bash
if [[ ! -f ".hiivmind/github/config.yaml" ]]; then
  echo "Config not found - workspace not initialized"
fi
```

**Recovery:**
```
Run: /hiivmind-pulse-gh init
```

---

## YAML Parse Error

**Error:**
```
yaml: line 5: did not find expected key
```

**Detection:**
```bash
if ! yq '.' .hiivmind/github/config.yaml >/dev/null 2>&1; then
  echo "Config file is malformed"
fi
```

**Recovery:**
- Check for tab characters (YAML requires spaces)
- Check indentation consistency
- Validate with: `yq '.' config.yaml`

---

## Tool Not Found

**Error:**
```
yq: command not found
jq: command not found
```

**Detection:** See `tool-detection.md` for detection patterns.

**Recovery:**
```bash
# yq installation
# macOS: brew install yq
# Linux: snap install yq

# jq installation
# macOS: brew install jq
# Linux: apt install jq
```

---

## gh CLI Errors

CLI commands return non-zero exit codes on failure:

```bash
if ! OUTPUT=$(gh issue list 2>&1); then
  echo "Command failed: $OUTPUT"
  exit 1
fi
```

---

## Related Patterns

- **tool-detection.md** - Proactive tool availability checks
- **config-parsing.md** - Config file read/write patterns
- **error-handling.md** - Error detection overview and recovery flow
