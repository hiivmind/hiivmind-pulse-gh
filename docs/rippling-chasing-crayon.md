# Plan: Make hiivmind-pulse-gh portable across coding agents

## Context

OpenClaw/Kimi Claw uses the same SKILL.md convention (YAML frontmatter + markdown body) as Claude Code. The plugin is already ~40% portable (lib/patterns, lib/references, templates, intent-mapping). The agent-specific surface is thin: manifests, frontmatter fields, and ~12 tool name references.

## Approach: Union frontmatter + adapter manifest (no restructuring)

### 1. Add OpenClaw manifest — `claw.json` (new file)

```json
{
  "name": "hiivmind-pulse-gh",
  "version": "4.0.0",
  "description": "GitHub workspace automation with context enrichment across 25 domains",
  "author": "hiivmind",
  "skills_dir": "skills",
  "commands_dir": "commands"
}
```

### 2. Add `trigger` + `tools` fields to all SKILL.md frontmatter

Edit 7 files (root SKILL.md + 6 skills). Add fields; don't remove existing ones. Unknown fields are ignored by each platform.

- `SKILL.md` — root
- `skills/gh-init/SKILL.md`
- `skills/gh-refresh/SKILL.md`
- `skills/gh-operations/SKILL.md`
- `skills/gh-discover/SKILL.md`
- `skills/gh-workflows/SKILL.md`
- `skills/gh-heartbeat/SKILL.md`

Example addition:
```yaml
trigger: "create issue|close issue|merge PR|set milestone|..."
tools: [shell, filesystem]
author: hiivmind
```

### 3. Update gateway command frontmatter — `commands/gh.md`

Add `trigger` and `tools` fields. Remove `allowed-tools` (Claude-specific; Claude auto-discovers tools from skill context anyway).

### 4. Abstract ~12 Claude-specific tool references in markdown bodies

| Find | Replace with |
|------|-------------|
| `AskUserQuestion` | "ask the user" / "prompt the user to choose" |
| `Skill(hiivmind-pulse-gh:gh-operations, ...)` | "invoke skill: gh-operations" |

Files to edit:
- `commands/gh.md` (~4 occurrences)
- `skills/gh-workflows/SKILL.md` (~3 occurrences)
- `skills/gh-heartbeat/SKILL.md` (~1 occurrence)
- `lib/patterns/workflow-execution.md` (~2 occurrences)

### 5. No changes to:
- `.claude-plugin/plugin.json` — keep Claude Code working
- `lib/patterns/` — already portable
- `lib/references/` — already portable
- `hooks/` — bash scripts are portable; trigger config is deferred until OpenClaw publishes hook spec
- `intent-mapping.yaml` — pure data, already portable
- `templates/` — already portable

## Verification

1. Run `/gh discover` to confirm Claude Code still works
2. Validate all SKILL.md files have valid YAML frontmatter: `for f in skills/*/SKILL.md SKILL.md; do yq '.name' "$f"; done`
3. Grep for remaining Claude-specific references: `grep -r 'AskUserQuestion\|Skill(' skills/ commands/ lib/`
4. Verify claw.json is valid JSON: `jq . claw.json`
