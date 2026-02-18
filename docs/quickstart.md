# Quickstart: hiivmind-pulse-gh

End-to-end walkthrough from initialization to your first enriched operation.

## Prerequisites

- `gh` CLI authenticated (`gh auth status`)
- `jq` (1.6+) and `yq` (4.0+) installed
- A GitHub repository with a Projects v2 board

## Step 1: Initialize Workspace

```
/gh init
```

This will:
1. Detect your git remote → owner/repo
2. Determine workspace type (organization or user)
3. Discover Projects v2 boards and their field configurations
4. Cache all IDs in `.hiivmind/github/config.yaml`

**Expected output:** Config file created with workspace, project, and field IDs.

## Step 2: Verify Config

Check the generated config:

```bash
cat .hiivmind/github/config.yaml
```

You should see your workspace ID, project IDs, and Status field option IDs.

## Step 3: Create an Enriched Issue

```
/gh create issue "Fix login timeout" with label bug and milestone v2.0
```

Without the plugin, `gh issue create` would create an orphan issue. With it, the issue is:
- Created with title and label
- Automatically linked to your default project
- Project Status set to "Backlog"
- Milestone resolved from name to ID and applied

## Step 4: Update Project Status

```
/gh set status "In progress" on issue #42
```

The plugin resolves "In progress" to the cached option ID and updates the project field via GraphQL.

## Step 5: Close with Enrichment

```
/gh close issue #42
```

This closes the issue AND updates the project Status to "Done" automatically.

## What's Next

- `/gh discover` — Browse all available operations
- `/gh refresh` — Sync config after GitHub changes
- See `CLAUDE.md` for full skill reference
