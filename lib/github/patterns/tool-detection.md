# Pattern: Tool Detection

## Purpose

Establish available tool capabilities at the start of GitHub operations, enabling runtime adaptation to the environment.

## When to Use

- At the start of any GitHub skill (init, refresh, operations)
- Once per session (cache results mentally for reuse)
- Before suggesting commands to the user

## Tool Capability Matrix

| Capability | Required For | Preferred | Alternatives | Fallback |
|------------|--------------|-----------|--------------|----------|
| GitHub API | All operations | gh CLI | curl + token | (none) |
| JSON parsing | gh output | jq | python+json | grep (fragile) |
| YAML parsing | Config files | yq | python+pyyaml | grep (fragile) |

## Tool Tiers

### Tier 1: Required (no alternative)

**gh CLI** - Required for all GitHub API operations (GraphQL and REST). Cannot proceed without it.

### Tier 2: Strongly Recommended (degraded without)

**jq** - Essential for parsing JSON output from `gh api` commands. Python fallback exists but is verbose.

**yq** (Mike Farah's Go version) - Essential for reading/writing config.yaml reliably. Grep-based fallback exists but is fragile and may fail on complex YAML structures.

### Tier 3: Optional (fallback available)

**python3** - Alternative for JSON/YAML parsing when jq/yq unavailable.

## Detection Commands

### Detect gh CLI

**Using bash:**
```bash
command -v gh >/dev/null 2>&1 && gh --version | head -1
```

**Using PowerShell:**
```powershell
if (Get-Command gh -ErrorAction SilentlyContinue) { gh --version | Select-Object -First 1 }
```

### Detect jq

**Using bash:**
```bash
command -v jq >/dev/null 2>&1 && jq --version
```

**Using PowerShell:**
```powershell
if (Get-Command jq -ErrorAction SilentlyContinue) { jq --version }
```

### Detect yq

**Using bash:**
```bash
command -v yq >/dev/null 2>&1 && yq --version | head -1
```

**Using PowerShell:**
```powershell
if (Get-Command yq -ErrorAction SilentlyContinue) { yq --version | Select-Object -First 1 }
```

### Detect Python + PyYAML

**Using bash:**
```bash
# Check for Python
command -v python3 >/dev/null 2>&1 && echo "python3:available"

# Check for PyYAML
python3 -c "import yaml; print('pyyaml:available')" 2>/dev/null
```

**Using PowerShell:**
```powershell
# Check for Python
if (Get-Command python3 -ErrorAction SilentlyContinue) { Write-Output "python3:available" }

# Check for PyYAML
python3 -c "import yaml; print('pyyaml:available')" 2>$null
```

## Decision Flow

```
┌─────────────────────────────────────────────────────────┐
│              Start GitHub Operation                      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Check for gh CLI                       │
└─────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
     gh available               gh not available
            │                           │
            │                           ▼
            │               ┌───────────────────────┐
            │               │ BLOCK: Cannot proceed │
            │               │ (show install help)   │
            │               └───────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│                    Check for jq                          │
└─────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
      jq available              jq not available
            │                           │
            ▼                           ▼
   Use jq for JSON          Check for python3
                                       │
                          ┌────────────┴────────────┐
                          │                         │
                          ▼                         ▼
                   python3 available         neither available
                          │                         │
                          ▼                         ▼
                 Use python for JSON        WARN: Using grep
                                           fallback (unreliable)
```

Similar flow for YAML parsing (yq → python+pyyaml → grep).

## Recommendation Messages

### Critical (blocks operation)

When gh CLI is not found:

```
GitHub CLI (gh) is required but wasn't found.

Install gh:
- Linux (Debian/Ubuntu): sudo apt install gh
- Linux (Fedora): sudo dnf install gh
- macOS: brew install gh
- Windows: winget install GitHub.cli

After installation, authenticate with: gh auth login

Cannot proceed without gh CLI.
```

### Strong (degraded experience)

When jq is not found:

```
jq not found. JSON parsing will use Python fallback (slower, more verbose).

For best results, install jq:
- Linux (Debian/Ubuntu): sudo apt install jq
- Linux (Fedora): sudo dnf install jq
- macOS: brew install jq
- Windows: winget install jqlang.jq

Proceeding with fallback method...
```

When no YAML parser is found:

```
No YAML parsing tool found (yq or python+pyyaml).
Operations will use grep-based fallback which may be unreliable for complex YAML.

For best results, install one of:
- yq (recommended): https://github.com/mikefarah/yq#install
- Python PyYAML: pip install pyyaml

Proceeding with fallback method...
```

### Informational (no action needed)

```
Using Python for JSON parsing (jq not found).
This works fine but commands will be more verbose.
```

## Version Compatibility Notes

### gh CLI

- **gh 2.x** - Current version, syntax documented here
- Minimum recommended: gh 2.0+
- Check version: `gh --version`

Verify gh is authenticated:
```bash
gh auth status
```

### jq

- **jq 1.6+** - Recommended
- **jq 1.5** - Works for most operations
- Check version: `jq --version`

### yq

- **yq 4.x** (Mike Farah's Go version): Current syntax documented here
- **yq 3.x**: Different syntax - avoid or upgrade
- **yq (Python version)**: Different project entirely

Verify yq 4.x:
```bash
yq --version  # Should show: yq (https://github.com/mikefarah/yq/) version v4.x.x
```

## Cross-Platform Notes

| Aspect | Unix (Linux/macOS) | Windows |
|--------|-------------------|---------|
| Tool detection | `command -v {tool}` | `Get-Command {tool}` |
| Shell | bash, zsh | PowerShell, cmd |
| Path separator | `/` | `\` (PowerShell accepts `/`) |
| Home directory | `$HOME`, `~` | `$env:USERPROFILE` |
| Package manager | apt, brew, dnf | winget, choco, scoop |

## Examples

### Example 1: Full Environment Detection

**Detection output (well-equipped system):**
```
gh: gh version 2.83.1 (2025-11-13)
jq: jq-1.8.1
yq: yq (https://github.com/mikefarah/yq/) version v4.49.2
python3: available
pyyaml: available
```

**Adaptation**: Use gh, jq, yq for all operations.

### Example 2: Minimal Environment

**Detection output:**
```
gh: gh version 2.40.0
jq: not found
yq: not found
python3: available
pyyaml: available
```

**Adaptation**: Use gh for API, python for JSON/YAML parsing.

### Example 3: Missing gh CLI

**Detection output:**
```
gh: not found
```

**Response**:
```
GitHub CLI (gh) is required but wasn't found.

Install gh:
- Linux (Debian/Ubuntu): sudo apt install gh
- macOS: brew install gh
- Windows: winget install GitHub.cli

After installation, authenticate with: gh auth login

Cannot proceed without gh CLI.
```

## Error Handling

### Tool Not Found

- Clearly state which tool is missing
- Provide installation instructions for user's platform (if detectable)
- Explain consequences (blocked vs degraded)
- Offer alternatives if available

### Tool Found But Wrong Version

- yq 3.x vs 4.x: Show version, explain incompatibility, suggest upgrade
- Detect via version output differences

### Tool Available But Fails

- Could be permissions, path issues, or broken installation
- Show actual error message
- Suggest reinstallation

### gh Not Authenticated

When `gh auth status` fails:
```
gh CLI found but not authenticated.

Run: gh auth login

This will open a browser to authenticate with GitHub.
Required scopes: repo, read:org, project (for Projects v2)
```

## Related Patterns

- **authentication.md** - Uses gh CLI detected here for auth verification
- **config-parsing.md** - Uses tool detection to choose YAML extraction method
- **workspace-detection.md** - Requires gh CLI for git remote operations
- **graphql-queries.md** - Requires gh CLI for API queries
