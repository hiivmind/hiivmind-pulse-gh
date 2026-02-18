# Installation

## Prerequisites

- **gh** (GitHub CLI) — [cli.github.com](https://cli.github.com)
- **jq** 1.6+ — `sudo apt install jq` / `brew install jq`
- **yq** 4.0+ — [github.com/mikefarah/yq](https://github.com/mikefarah/yq)

### Authenticate gh CLI

```bash
gh auth login
```

Required token scopes: `repo`, `read:org`, `read:project`, `project`

Verify:
```bash
gh auth status
```

## Install by Agent

### Claude Code - In active Session

```bash
# Add the marketplace
/plugin marketplace add hiivmind/hiivmind-pulse-gh-mp

# Install the plugin
/plugin install hiivmind-pulse-gh-mp@hiivmind-pulse-gh
```

### Claude Code - CLI

```bash
# Install the plugin
claude plugin install hiivmind-pulse-gh@hiivmind-pulse-gh
```


### OpenClaw

```bash
git clone https://github.com/hiivmind/hiivmind-pulse-gh.git ~/.openclaw/skills/hiivmind-pulse-gh
```

### ZeroClaw

```bash
git clone https://github.com/hiivmind/hiivmind-pulse-gh.git ~/.zeroclaw/workspace/skills/hiivmind-pulse-gh
```

### OpenCode

```bash
git clone https://github.com/hiivmind/hiivmind-pulse-gh.git ~/.config/opencode/skills/hiivmind-pulse-gh
```

### VS Code Copilot

```bash
git clone https://github.com/hiivmind/hiivmind-pulse-gh.git .github/skills/hiivmind-pulse-gh
```

### Generic (any Agent Skills compatible agent)

Clone into your agent's skills directory:

```bash
git clone https://github.com/hiivmind/hiivmind-pulse-gh.git <agent-skills-dir>/hiivmind-pulse-gh
```

The directory name **must** be `hiivmind-pulse-gh` to match the `name` field in `SKILL.md`.

## Post-Install: Initialize Workspace

After installation, initialize your workspace by running the init skill:

```
skills/gh-init/SKILL.md
```

This discovers your GitHub organization/user, projects, fields, milestones, and labels, caching everything to `.hiivmind/github/config.yaml`.

## Verify Installation

1. `gh auth status` — shows required scopes
2. `jq --version` — 1.6+
3. `yq --version` — 4.0+
4. `.hiivmind/github/config.yaml` exists after init
5. Run any operation (e.g., list issues) to confirm enrichment works
