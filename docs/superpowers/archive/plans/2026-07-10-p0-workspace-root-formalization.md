> **ARCHIVED 2026-08-17.** Implementation complete — kept for historical
> reference only. See
> `docs/superpowers/archive/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md`
> §8.9 for original phase tracking.
>
> ---

# P0 — Workspace Root Formalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Formalize the workspace root — `.hiivmind/github/` in the parent folder of an org's repo clones, versioned as its own small git repo — as the normative config location, resolved by walk-up from any depth, for **any org** (the mechanism is reusable; the hiivmind parent folder is only the dogfood instance validated at the end).

**Architecture:** A single normative resolution algorithm (`resolve_workspace_root`: walk up to the first `.hiivmind/github/config.yaml` carrying a `workspace:` section) is defined once in `lib/patterns/workspace-detection.md` and adopted by the heartbeat hook, all skills, and the gateway command. `gh-init` gains a workspace-root placement flow (init a fresh parent, or *promote* an existing repo-local config) that git-inits `.hiivmind/github/` as the workspace repo with a shared-vs-per-machine gitignore split, and offers a private GitHub remote (`{login}-workspace`). Repo-level `.hiivmind/github/` is demoted to an overlay (no `workspace:` section).

**Tech Stack:** Bash (hooks, embedded skill snippets), Markdown skills/patterns, yq/jq/gh.

**Spec:** `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md` — Part 3 (D1–D4, §3.2 layout, §3.3 topology) and Part 8 §P0.

## Global Constraints

- **Reusable-first:** every mechanism must work for an arbitrary org/user login. No `hiivmind` hardcoding anywhere except the dogfood task (Task 5). Copy for prompts uses `{login}` placeholders.
- **D1 (decided):** the workspace repo is rooted at `{workspace_root}/.hiivmind/github/` — NOT the whole parent folder. Default remote name: `{login}-workspace`, private, creation offered (never forced) during init.
- **D2:** workspace config is the base layer; repo-level `.hiivmind/github/` is an optional overlay. The `workspace:` top-level key is the marker that distinguishes a workspace config from an overlay; overlays MUST NOT contain it. Scalar conflicts: repo overlay wins within its repo's scope.
- **D3:** heartbeat walks up to the workspace root; sessions inside repo X get an X-filtered slice (repo-scoped sources poll only X); org-wide summary is a follow-up, not the default.
- **D4:** headless skills never discover — explicit `workspace_path`/`repo` inputs. Stated as a convention now; enforced when headless skills land in P3.
- **Never delete or move a `.hiivmind/` directory itself** — it is a multi-plugin namespace. Only operate on `.hiivmind/github/`.
- **Per-machine transients** (`user.yaml`, `poll-state.yaml`, `project-snapshot.json`, `*-result.yaml`, `log/`) are gitignored inside the workspace repo; everything else in `.hiivmind/github/` is committed (spec §3.2, invariant I2).
- No test framework exists in this repo (tests live in hiivmind-pulse-gh-tests); each task carries fixture-based verification with exact commands run from a temp dir.
- Commit after every task. Plugin version bump to `4.4.0` happens once, in Task 6.

---

### Task 1: Normative workspace-root resolution in `workspace-detection.md` (P0.1 + P0.5)

**Files:**
- Modify: `lib/patterns/workspace-detection.md`

**Interfaces:**
- Produces: `resolve_workspace_root()` — bash function; arg 1 optional start dir (default `$PWD`); prints the workspace root directory (the dir *containing* `.hiivmind/`) on stdout, exit 0; exit 1 if none found. Marker: config file contains a top-level `workspace:` key (`grep -q '^workspace:'`). Every later task copies this function verbatim.
- Produces: the terms **workspace config (base)** / **repo overlay**, and the D4 headless-inputs convention, referenced by Tasks 2–4.

- [x] **Step 1: Replace the "Config Location Strategy" section**

In `lib/patterns/workspace-detection.md`, replace everything from the heading `## Config Location Strategy` through the end of the "Search Order" section (i.e., up to but not including `## Prerequisites`) with:

````markdown
## Workspace Root Resolution (Normative)

This section is the single source of truth for locating configuration.
All skills, hooks, and commands MUST use this algorithm. The two-level
check (`.` then `..`) is retired.

### CRITICAL: `.hiivmind/` Is a Multi-Plugin Namespace

The `.hiivmind/` directory is shared across multiple hiivmind plugins:
- `.hiivmind/github/` — hiivmind-pulse-gh (this plugin)
- `.hiivmind/corpus/` — hiivmind-corpus
- Other plugins may add their own subdirectories

**NEVER delete, move, or replace a `.hiivmind/` directory.** Only operate on
`.hiivmind/github/`, which is this plugin's subdirectory — and, when placed at
a workspace root, its own git repository (see "The Workspace Repo" below).

### The two config layers (D2)

| Layer | Location | Marker | Role |
|-------|----------|--------|------|
| **Workspace config (base)** | `{workspace_root}/.hiivmind/github/config.yaml` | HAS a top-level `workspace:` section | Workspace identity, project/repo catalogs, teams, relationships, org-wide workflows, poll-state, runs |
| **Repo overlay (optional)** | `{repo}/.hiivmind/github/config.yaml` | MUST NOT have a `workspace:` section | Repo-scoped workflows and setting overrides only |

The `workspace_root` is typically the parent folder holding all of an org's
repo clones (`~/git/{org}/`), but for a standalone single-repo setup it may be
the repo itself. What makes a directory the workspace root is the marker, not
its position.

Precedence: the workspace config is the base; a repo overlay wins for scalar
conflicts **within its own repo's scope**. An overlay never carries workspace
identity — resolution skips any config lacking the `workspace:` marker and
keeps walking up.

### Resolution algorithm

```bash
# Resolve the workspace root: walk up from a start dir to the first directory
# whose .hiivmind/github/config.yaml carries a top-level `workspace:` section.
# Prints the workspace root (the dir CONTAINING .hiivmind/); exit 1 if none.
resolve_workspace_root() {
    local dir="${1:-$PWD}"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/.hiivmind/github/config.yaml" ]] \
           && grep -q '^workspace:' "$dir/.hiivmind/github/config.yaml"; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}

WORKSPACE_ROOT=$(resolve_workspace_root) || WORKSPACE_ROOT=""
CONFIG_PATH="${WORKSPACE_ROOT:+$WORKSPACE_ROOT/.hiivmind/github/config.yaml}"
```

Overlay discovery (only meaningful when inside a git repo that is not itself
the workspace root):

```bash
REPO_TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
OVERLAY_DIR=""
if [[ -n "$REPO_TOPLEVEL" && "$REPO_TOPLEVEL" != "$WORKSPACE_ROOT" \
      && -d "$REPO_TOPLEVEL/.hiivmind/github" ]]; then
    OVERLAY_DIR="$REPO_TOPLEVEL/.hiivmind/github"
fi
```

**Result interpretation:**
- `WORKSPACE_ROOT` non-empty → use `$CONFIG_PATH` as the base config; apply
  `$OVERLAY_DIR` overrides if present.
- `WORKSPACE_ROOT` empty → workspace not initialized; prompt for `gh-init`.

### D4: Headless skills never discover

Directory discovery is an **interactive-only** convenience. Any headless skill
(P3+) MUST take explicit `workspace_path` (and, where relevant, `repo`) inputs
in its frontmatter and MUST NOT call `resolve_workspace_root`. In CI or a
scheduled runtime a single repo is checked out and no parent workspace exists;
discovery there is undefined behavior.

### The Workspace Repo (D1)

`{workspace_root}/.hiivmind/github/` is itself a small git repository — the
"workspace repo" — shared by the team via a private remote (default name
`{login}-workspace`). It versions the human-authored and shared assets;
per-machine transients are gitignored:

| Committed (shared) | Gitignored (per-machine) |
|--------------------|--------------------------|
| `config.yaml`, `freshness.yaml` | `user.yaml` |
| `workflows/`, `views/`, `repos/`, `automations/` | `poll-state.yaml` |
| `teams.yaml`, `relationships.yaml`, `healthcheck.yaml` | `project-snapshot.json`, `*-result.yaml` |
| `runs/` (run ledger) | `log/` |

Repo clone directories are siblings of `.hiivmind/`, outside the workspace
repo entirely — no nested-repo or ignore gymnastics.

### Multi-machine, multi-actor topology

Each machine's workspace root holds its own **clone** of the shared workspace
repo plus its own set of repo clones, possibly at different states. The team
is M:M across individuals, GitHub profiles, and physical machines. Rules:

- **Shared vs. per-machine split:** committed workspace-repo content is the
  *only* shared state. `poll-state.yaml`, snapshots, and result files are
  per-machine advisory caches — two machines legitimately hold different
  poll-state. Never commit them; never treat them as authority.
- **Pull before reconcile:** any run that reads or writes shared markers
  (config catalogs, workflow definitions, dismissals, run ledger, binding
  state) pulls the workspace repo first. Local caches are never authority.
- **Cooldowns are advisory:** poll-state cooldown bookkeeping is per-machine
  and cannot enforce a global rate across machines. It is a politeness
  optimization only; global correctness comes from idempotent runs plus the
  supersede pattern, not from cooldowns.
- **Actor attribution:** every run records the human, the GitHub profile
  (`gh auth` identity), and the machine — in run records and result files.
  Identity-sensitive logic ("you touched this", self-assignment) resolves
  against the recorded actor, not whatever profile the current machine holds.
- **Local clones are never sync sources:** skills read pushed commits and API
  state; a dirty or unpushed repo clone is surfaced as a finding, never
  consumed as truth.
````

- [x] **Step 2: Verify the resolution function against fixtures**

Run this end-to-end check (copy-paste as one block):

```bash
FIX=$(mktemp -d)
mkdir -p "$FIX/ws/.hiivmind/github" "$FIX/ws/repo-a/.hiivmind/github" "$FIX/ws/repo-a/src/deep" "$FIX/plain"
printf 'workspace:\n  login: testorg\n' > "$FIX/ws/.hiivmind/github/config.yaml"
printf 'overrides:\n  projects:\n    default: 9\n' > "$FIX/ws/repo-a/.hiivmind/github/config.yaml"
resolve_workspace_root() {
    local dir="${1:-$PWD}"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/.hiivmind/github/config.yaml" ]] \
           && grep -q '^workspace:' "$dir/.hiivmind/github/config.yaml"; then
            echo "$dir"; return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}
[[ "$(resolve_workspace_root "$FIX/ws/repo-a/src/deep")" == "$FIX/ws" ]] && echo "PASS deep walk-up skips overlay"
[[ "$(resolve_workspace_root "$FIX/ws")" == "$FIX/ws" ]] && echo "PASS at root"
resolve_workspace_root "$FIX/plain" || echo "PASS not-found exits 1"
rm -rf "$FIX"
```

Expected output: the three `PASS ...` lines and nothing else.

The function in the pattern doc must be byte-identical to the one tested above.

- [x] **Step 3: Commit**

```bash
git add lib/patterns/workspace-detection.md
git commit -m "docs(patterns): normative workspace-root resolution, layering, multi-machine topology

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Heartbeat walk-up + repo-filtered scope (P0.2)

**Files:**
- Modify: `hooks/heartbeat.sh:8-13` (config discovery), `hooks/heartbeat.sh:35-38` (workflows-dir guard), `hooks/heartbeat.sh:53-58` (remote detection), `hooks/heartbeat.sh:73` (workflow loop), and the `session_poll` source guard (after line 98)

**Interfaces:**
- Consumes: `resolve_workspace_root` logic from Task 1 (inlined — hooks can't source pattern docs).
- Produces: heartbeat that runs from any depth under a workspace root; `WORKSPACE_ROOT`, `OVERLAY_WORKFLOWS` shell vars; repo-scoped sources skipped when the session is not inside a repo clone.

- [x] **Step 1: Replace the two-level config check**

In `hooks/heartbeat.sh`, replace:

```bash
CONFIG_PATH=""
if [[ -f ".hiivmind/github/config.yaml" ]]; then
    CONFIG_PATH=".hiivmind/github/config.yaml"
elif [[ -f "../.hiivmind/github/config.yaml" ]]; then
    CONFIG_PATH="../.hiivmind/github/config.yaml"
fi
```

with:

```bash
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

CONFIG_PATH=""
if [[ -n "$WORKSPACE_ROOT" ]]; then
    CONFIG_PATH="$WORKSPACE_ROOT/.hiivmind/github/config.yaml"
fi
```

- [x] **Step 2: Add overlay workflows and fix the workflows-dir guard**

Replace:

```bash
# Exit early if no workflows directory
if [[ ! -d "$WORKFLOWS_DIR" ]]; then
    exit 0
fi
```

with:

```bash
# Repo overlay workflows (D2): a repo-level .hiivmind/github/workflows/ inside
# the current clone is scanned in addition to the workspace workflows.
OVERLAY_WORKFLOWS=""
REPO_TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -n "$REPO_TOPLEVEL" && "$REPO_TOPLEVEL" != "$WORKSPACE_ROOT" \
      && -d "$REPO_TOPLEVEL/.hiivmind/github/workflows" ]]; then
    OVERLAY_WORKFLOWS="$REPO_TOPLEVEL/.hiivmind/github/workflows"
fi

# Exit early if no workflows anywhere
if [[ ! -d "$WORKFLOWS_DIR" && -z "$OVERLAY_WORKFLOWS" ]]; then
    exit 0
fi
```

- [x] **Step 3: Make repo detection non-fatal (D3 scope)**

Replace:

```bash
# Detect owner/repo from git remote
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [[ -z "$REMOTE_URL" ]]; then
    exit 0
fi
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's#.*[:/]([^/]+/[^/.]+)(\.git)?$#\1#')
```

with:

```bash
# Detect owner/repo from git remote (D3: repo-filtered slice). Empty when the
# session is not inside a repo clone (e.g. at the workspace root itself):
# repo-scoped sources are skipped; projects and freshness still run.
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
OWNER_REPO=""
if [[ -n "$REMOTE_URL" ]]; then
    OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's#.*[:/]([^/]+/[^/.]+)(\.git)?$#\1#')
fi
```

- [x] **Step 4: Loop over both workflow dirs and guard repo-scoped sources**

Replace the loop opener:

```bash
for WF_FILE in "$WORKFLOWS_DIR"/*.yaml; do
    [[ -f "$WF_FILE" ]] || continue
```

with:

```bash
for WF_FILE in "$WORKFLOWS_DIR"/*.yaml ${OVERLAY_WORKFLOWS:+"$OVERLAY_WORKFLOWS"/*.yaml}; do
    [[ -f "$WF_FILE" ]] || continue
```

Then, inside `session_poll)`, immediately after `SOURCE=$(yq -r '.trigger.source' "$WF_FILE")`, insert:

```bash
            # Repo-scoped sources need a repo context (D3)
            case "$SOURCE" in
                pull_requests|issues|actions|releases|dependabot|deployments)
                    if [[ -z "$OWNER_REPO" ]]; then
                        continue
                    fi
                    ;;
            esac
```

- [x] **Step 5: Verify against a fixture workspace**

```bash
FIX=$(mktemp -d)
mkdir -p "$FIX/ws/.hiivmind/github/workflows" "$FIX/ws/repo-a/src/deep"
printf 'workspace:\n  login: testorg\n' > "$FIX/ws/.hiivmind/github/config.yaml"
cd "$FIX/ws/repo-a/src/deep"
CLAUDE_PLUGIN_ROOT=/Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh \
  bash /Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh/hooks/heartbeat.sh
echo "exit=$?"
ls "$FIX/ws/.hiivmind/github/poll-state.yaml" && echo "PASS poll-state at workspace root"
cd /Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh && rm -rf "$FIX"
```

Expected: first invocation prints `{"first_run": true, "stale_sections": []}`, `exit=0`, and the `PASS poll-state at workspace root` line (poll-state bootstrapped **at the workspace**, not in `deep/`). A second invocation from the same dir prints a normal summary JSON (`{"stale_sections": [], "triggered_workflows": [], "auto_workflows": []}`) because there are no workflow files.

Also verify no-workspace behavior:

```bash
cd "$(mktemp -d)" && bash /Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh/hooks/heartbeat.sh; echo "exit=$?"
```

Expected: no output, `exit=0`.

- [x] **Step 6: Run shellcheck and commit**

```bash
shellcheck hooks/heartbeat.sh || true   # pre-existing warnings OK; no NEW errors
git add hooks/heartbeat.sh
git commit -m "feat(heartbeat): resolve workspace root by walk-up with repo-filtered scope

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `gh-init` workspace-root placement, workspace repo init, promotion flow (P0.4 + reusable half of P0.3)

**Files:**
- Create: `templates/workspace-gitignore.template`
- Modify: `skills/gh-init/SKILL.md` (Phase 1 "Check for Existing Config"; Phase 5 output-files table; new Phase 5.9)

**Interfaces:**
- Consumes: `resolve_workspace_root` (Task 1), the base/overlay terminology.
- Produces: `templates/workspace-gitignore.template`; gh-init flows `INIT-AT-WORKSPACE-ROOT` (fresh parent) and `PROMOTE` (existing repo-local config → workspace root). Task 5 executes PROMOTE verbatim for the dogfood.

- [x] **Step 1: Create the workspace-repo gitignore template**

Write `templates/workspace-gitignore.template`:

```
# hiivmind-pulse-gh workspace repo
# Per-machine transient state — never commit (two machines legitimately differ)
user.yaml
poll-state.yaml
project-snapshot.json
*-result.yaml
log/
.assignments-tmp.json
```

- [x] **Step 2: Replace Phase 1's "Check for Existing Config" section in `skills/gh-init/SKILL.md`**

Replace everything from `### Check for Existing Config` up to (not including) `### What to Do` with:

````markdown
### Resolve Existing Workspace

**See:** `{PLUGIN_ROOT}/lib/patterns/workspace-detection.md` § Workspace Root Resolution

```bash
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
```

**CRITICAL — NEVER delete a `.hiivmind/` directory.** It is a shared namespace
used by multiple plugins (github, corpus, etc.). Only `.hiivmind/github/` is
managed by this plugin.

**If a workspace root is found:** the workspace is already initialized.

```
Found workspace config at {WORKSPACE_ROOT}/.hiivmind/github/config.yaml
(workspace: {login}, {type})

Options:
1. Refresh it (run gh-refresh)
2. Add a repo-level overlay for this repo (repo-scoped workflows/overrides only)
3. Re-initialize the workspace config (overwrites catalogs; workspace repo history preserved)

Which would you like? [1/2/3]
```

An overlay (option 2) is a `.hiivmind/github/` inside the current repo
**without** a `workspace:` section — it never carries workspace identity.

**If no workspace root is found — choose placement:**

```bash
GIT_TOP=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -n "$GIT_TOP" ]]; then
    CANDIDATE_ROOT=$(dirname "$GIT_TOP")
else
    CANDIDATE_ROOT="$PWD"
fi
# Count sibling repo clones under the candidate root
SIBLING_CLONES=$(find "$CANDIDATE_ROOT" -mindepth 2 -maxdepth 2 -name .git 2>/dev/null | wc -l | tr -d ' ')
```

| Situation | Default placement |
|-----------|-------------------|
| `SIBLING_CLONES` ≥ 2 (multi-repo parent) | **Workspace root = `$CANDIDATE_ROOT`** (recommended default) |
| Single repo, no siblings | Workspace root = the repo itself (config committed to the host repo; no separate workspace repo) |
| Repo-local config with a `workspace:` section exists at `$GIT_TOP` AND siblings exist | Offer **promotion** (below) |

```
No workspace found. This looks like a multi-repo parent:
  {CANDIDATE_ROOT} contains {N} repo clones.

Where should the workspace live?
1. {CANDIDATE_ROOT}/.hiivmind/github/  — shared workspace repo, serves all clones (recommended)
2. {GIT_TOP}/.hiivmind/github/          — this repo only

Which would you like? [1/2]
```

**Promotion flow** (existing repo-local workspace config, multi-repo parent):

```
Found a workspace config inside {repo}, but {CANDIDATE_ROOT} holds {N} sibling
clones. Promote it to the workspace root? This will:
  1. Move .hiivmind/github/ content to {CANDIDATE_ROOT}/.hiivmind/github/
  2. Initialize it as the workspace repo (Phase 5.9)
  3. Remove the tracked copy from {repo} (git rm) — or keep a slimmed overlay
     if this repo has repo-scoped workflows/overrides

Proceed? [Y/n]
```

Implementation (after user confirms; run from `$GIT_TOP`):

```bash
mkdir -p "$CANDIDATE_ROOT/.hiivmind"
cp -R .hiivmind/github "$CANDIDATE_ROOT/.hiivmind/github"
git rm -r -q .hiivmind/github
rmdir .hiivmind 2>/dev/null || true
# Clean host-repo .gitignore entries that referenced .hiivmind/github/*
```

Then continue to Phase 5.9 to git-init the promoted directory, and remind the
user to commit the removal in the host repo. Per-machine transients that were
copied (`poll-state.yaml`, `log/`, `user.yaml`) are excluded by the workspace
repo's `.gitignore` automatically.
````

- [x] **Step 3: Add Phase 5.9 (WORKSPACE REPO) to `skills/gh-init/SKILL.md`**

Insert between Phase 5.7 and Phase 6:

````markdown
## Phase 5.9: WORKSPACE REPO

**Goal:** Version the workspace so the team can share it (D1). Skip this phase
entirely when placement was repo-local (the host repo versions the config).

### What to Do

```bash
cd "$WORKSPACE_ROOT/.hiivmind/github"
if [[ ! -d .git ]]; then
    git init
    cp "{PLUGIN_ROOT}/templates/workspace-gitignore.template" .gitignore
    git add -A
    git commit -m "chore: initialize hiivmind workspace repo for {login}"
fi
```

The `.gitignore` keeps per-machine transients (`user.yaml`, `poll-state.yaml`,
snapshots, result files, `log/`) out of the shared repo. Everything else —
config, freshness, workflows, views, teams, relationships, healthcheck, runs —
is committed.

### STOP Point

```
Workspace repo initialized at {WORKSPACE_ROOT}/.hiivmind/github/

Create a private GitHub remote so your team can share it?
  gh repo create {login}/{login}-workspace --private --source=. --push

[Y/n — you can also do this later]
```

If yes, run the command and confirm the push succeeded. If the repo name is
taken or the user prefers another name, ask for one. Teammates join with:

    git clone git@github.com:{login}/{login}-workspace.git {workspace_root}/.hiivmind/github
````

- [x] **Step 4: Update the Phase 5 output-files table**

In the `### Output Files` table of `skills/gh-init/SKILL.md`, replace the table with:

```markdown
| File | Purpose | Git Status |
|------|---------|------------|
| `{WORKSPACE_ROOT}/.hiivmind/github/config.yaml` | Workspace config (shared) | Committed (workspace repo) |
| `{WORKSPACE_ROOT}/.hiivmind/github/user.yaml` | User identity (personal) | Gitignored |
| `{WORKSPACE_ROOT}/.hiivmind/github/freshness.yaml` | Staleness tracking | Committed (workspace repo) |
| `{WORKSPACE_ROOT}/.hiivmind/github/.gitignore` | Per-machine transient split | Committed (workspace repo) |
| `{WORKSPACE_ROOT}/.hiivmind/github/workflows/*.yaml` | Heartbeat workflow configs | Committed (workspace repo) |
| `{WORKSPACE_ROOT}/.hiivmind/github/log/` | Heartbeat run logs | Gitignored |
| `.claude/settings.json` (per repo, optional) | Plugin dependencies | Committed to each repo |
```

Also in Phase 5 "What to Do", change step 5 from "Update `.gitignore` to exclude `user.yaml`" to: "Copy `{PLUGIN_ROOT}/templates/workspace-gitignore.template` to `{WORKSPACE_ROOT}/.hiivmind/github/.gitignore` (workspace placement); for repo-local placement, add `.hiivmind/github/user.yaml`, `.hiivmind/github/poll-state.yaml`, and `.hiivmind/github/log/` to the host repo's `.gitignore` instead." And note on the `.claude/settings.json` step: "repo-scoped — apply to each repo where the team should get the marketplace prompt, not to the workspace repo."

- [x] **Step 5: Verify skill-doc consistency**

```bash
grep -n "workspace-gitignore.template" skills/gh-init/SKILL.md templates/workspace-gitignore.template >/dev/null && echo "PASS template referenced"
grep -c "Phase 5.9" skills/gh-init/SKILL.md   # expect >= 2 (heading + any reference)
grep -n '\.\./\.hiivmind' skills/gh-init/SKILL.md && echo "FAIL two-level remnants" || echo "PASS no two-level remnants"
```

Expected: `PASS template referenced`, a count ≥ 1 for Phase 5.9, `PASS no two-level remnants`.

- [x] **Step 6: Commit**

```bash
git add templates/workspace-gitignore.template skills/gh-init/SKILL.md
git commit -m "feat(gh-init): workspace-root placement, workspace repo init, promotion flow

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Align remaining config-discovery snippets (P0.1 adoption)

**Files:**
- Modify: `lib/patterns/config-parsing.md:25-56`
- Modify: `skills/gh-operations/SKILL.md:73-84`
- Modify: `skills/gh-workflows/SKILL.md:54-62`
- Modify: `commands/gh.md:160-170` and `commands/gh.md:292-301`

**Interfaces:**
- Consumes: `resolve_workspace_root` (Task 1) — inlined identically at each site; each block keeps the variable names its surrounding doc already uses (`CONFIG_PATH`, `CONFIG_DIR`, `initialized`).

- [x] **Step 1: `lib/patterns/config-parsing.md`** — replace the `find_config_path` function AND the "Quick check (2 levels ...)" block with:

````markdown
```bash
# Resolve config via the workspace root (normative algorithm:
# lib/patterns/workspace-detection.md § Workspace Root Resolution)
find_config_path() {
    local dir="${1:-$PWD}"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/.hiivmind/github/config.yaml" ]] \
           && grep -q '^workspace:' "$dir/.hiivmind/github/config.yaml"; then
            echo "$dir/.hiivmind/github/config.yaml"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}

CONFIG_PATH=$(find_config_path) || { echo "Config not found"; exit 1; }
```

A config **without** a top-level `workspace:` section is a repo overlay
(repo-scoped overrides), not the workspace config — the search skips it and
keeps walking up.
````

- [x] **Step 2: `skills/gh-operations/SKILL.md:73-81`** — replace the if/elif/else block with:

```bash
# Resolve workspace root (see lib/patterns/workspace-detection.md)
CONFIG_PATH=""
DIR="$PWD"
while [[ "$DIR" != "/" ]]; do
    if [[ -f "$DIR/.hiivmind/github/config.yaml" ]] \
       && grep -q '^workspace:' "$DIR/.hiivmind/github/config.yaml"; then
        CONFIG_PATH="$DIR/.hiivmind/github/config.yaml"
        break
    fi
    DIR="$(dirname "$DIR")"
done
```

And change the following line `**If config found in parent:** ...` to `**If config found at a workspace root above cwd:** use that config path for all operations. This is the normal case when repos live under a shared workspace root.`

- [x] **Step 3: `skills/gh-workflows/SKILL.md:55-61`** — replace with the same walk-up, assigning `CONFIG_DIR`:

```bash
# Resolve workspace root (see lib/patterns/workspace-detection.md)
CONFIG_DIR=""
DIR="$PWD"
while [[ "$DIR" != "/" ]]; do
    if [[ -f "$DIR/.hiivmind/github/config.yaml" ]] \
       && grep -q '^workspace:' "$DIR/.hiivmind/github/config.yaml"; then
        CONFIG_DIR="$DIR/.hiivmind/github"
        break
    fi
    DIR="$(dirname "$DIR")"
done
```

- [x] **Step 4: `commands/gh.md` — both blocks (lines 160-170 and 292-301)** — replace each if/elif/else with:

```bash
# Resolve workspace root (see lib/patterns/workspace-detection.md)
CONFIG_PATH=""
initialized="no"
DIR="$PWD"
while [[ "$DIR" != "/" ]]; do
    if [[ -f "$DIR/.hiivmind/github/config.yaml" ]] \
       && grep -q '^workspace:' "$DIR/.hiivmind/github/config.yaml"; then
        CONFIG_PATH="$DIR/.hiivmind/github/config.yaml"
        initialized="yes"
        break
    fi
    DIR="$(dirname "$DIR")"
done
```

- [x] **Step 5: Verify no stragglers**

```bash
grep -rn '\.\./\.hiivmind/github/config.yaml' skills/ commands/ lib/ hooks/ && echo "FAIL" || echo "PASS no two-level checks remain"
```

Expected: `PASS no two-level checks remain`. (`skills/gh-init/SKILL.md` was cleaned in Task 3.)

- [x] **Step 6: Commit**

```bash
git add lib/patterns/config-parsing.md skills/gh-operations/SKILL.md skills/gh-workflows/SKILL.md commands/gh.md
git commit -m "refactor: adopt workspace-root resolution in all config-discovery sites

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Dogfood — promote the hiivmind workspace (P0.3 instance + exit criteria)

This task executes Task 3's PROMOTE flow on the real hiivmind parent folder. It is the **only** task allowed to reference `hiivmind` concretely.

**Files:**
- Create: `~/git/hiivmind/.hiivmind/github/` (workspace repo, from this repo's copy)
- Modify: `.gitignore` (remove `.hiivmind/github/*` entries), delete tracked `.hiivmind/github/` from this repo
- Remote: create private `hiivmind/hiivmind-workspace` and push (⚠️ outward-facing — confirm with the user immediately before `gh repo create`)

- [x] **Step 1: Copy the config to the workspace root and git-init it**

```bash
cd /Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh
mkdir -p ../.hiivmind
cp -R .hiivmind/github ../.hiivmind/github
cd ../.hiivmind/github
git init
cp /Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh/templates/workspace-gitignore.template .gitignore
git add -A
git status --short   # verify: poll-state.yaml, log/, user.yaml NOT staged (gitignored)
git commit -m "chore: initialize hiivmind workspace repo (promoted from hiivmind-pulse-gh)"
```

Expected in `git status --short` before commit: `config.yaml`, `freshness.yaml` (if present), `teams.yaml`, `relationships.yaml`, `healthcheck.yaml`, `workflows/*`, `views/*`, `repos/*`, `automations/*`, `.gitignore` staged; **no** `poll-state.yaml`.

- [x] **Step 2: Create and push the remote (confirm with user first)**

```bash
gh repo create hiivmind/hiivmind-workspace --private --source=. --push
```

Expected: repo created, `main` pushed. If the name is taken, stop and ask.

- [x] **Step 3: Remove the tracked copy from hiivmind-pulse-gh**

```bash
cd /Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh
git rm -r -q .hiivmind/github
rmdir .hiivmind 2>/dev/null || true
```

Then edit `.gitignore` — delete these lines (now meaningless here):

```
# User-specific config (contains personal GitHub identity)
.hiivmind/github/user.yaml

# Local state tracking (per-machine freshness)
.hiivmind/github/freshness.yaml
```

and the `.hiivmind/github/log/` line.

- [x] **Step 4: Validate the P0 exit criteria**

```bash
cd /Users/nathanielramm/git/hiivmind/hiivmind-corpus/skills   # a DIFFERENT repo, 2 levels deep
CLAUDE_PLUGIN_ROOT=/Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh \
  bash /Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh/hooks/heartbeat.sh
```

Expected: JSON summary (not silence) — heartbeat resolved `/Users/nathanielramm/git/hiivmind` as the workspace root and polled against `hiivmind-corpus` as the repo slice. Then confirm the same resolution from a deep dir of pulse-gh itself:

```bash
cd /Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh/lib/patterns
bash -c 'DIR="$PWD"; while [[ "$DIR" != "/" ]]; do if [[ -f "$DIR/.hiivmind/github/config.yaml" ]] && grep -q "^workspace:" "$DIR/.hiivmind/github/config.yaml"; then echo "$DIR"; break; fi; DIR="$(dirname "$DIR")"; done'
```

Expected output: `/Users/nathanielramm/git/hiivmind`

- [x] **Step 5: Commit the removal in hiivmind-pulse-gh**

```bash
cd /Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh
git add -A
git commit -m "chore: promote .hiivmind/github to workspace root (hiivmind-workspace repo)

Workspace config now lives at ~/git/hiivmind/.hiivmind/github (private repo
hiivmind/hiivmind-workspace). This repo no longer carries workspace identity.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Close out P0 in the spec + version bump

**Files:**
- Modify: `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md` (§3.1 D1 note, §P0 checkboxes, §8.9 table)
- Modify: `.claude-plugin/plugin.json` (version)

- [x] **Step 1: Record the D1 resolution in §3.1**

In the spec's D1 paragraph, after "or just its `.hiivmind/` directory) as a small git repository", append: ` **Resolved during P0: the workspace repo is rooted at `.hiivmind/github/` itself (not the whole parent folder — avoids nested-clone hazards and respects the multi-plugin `.hiivmind/` namespace); default remote `{login}-workspace`, private.**`

- [x] **Step 2: Tick the P0 deliverable checkboxes**

Change all five `- [ ] P0.x ...` items in §P0 to `- [x]`.

- [x] **Step 3: Update the §8.9 progress table**

Set the P0 row's status to `✅ complete` with today's date (2026-07-10); leave every other row unchanged.

- [x] **Step 4: Bump plugin version**

In `.claude-plugin/plugin.json`, change `"version": "4.3.0"` to `"version": "4.4.0"`.

- [x] **Step 5: Final verification sweep (plan self-check)**

```bash
cd /Users/nathanielramm/git/hiivmind/hiivmind-pulse-gh
grep -rn '\.\./\.hiivmind/github/config.yaml' skills/ commands/ lib/ hooks/ && echo FAIL || echo PASS
git status --short   # only the files from this task staged/modified
```

- [x] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md .claude-plugin/plugin.json
git commit -m "docs(spec): mark P0 complete; bump version to 4.4.0

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Deliverable → Task map (spec coverage)

| Spec deliverable | Task |
|------------------|------|
| P0.1 workspace-detection.md rewrite (walk-up, marker, D2, D4) | Task 1 (adoption: Tasks 2–4) |
| P0.2 heartbeat.sh walk-up, D3 scope | Task 2 |
| P0.3 workspace repo init, gitignore split, migration, derivation split | Task 3 (mechanism) + Task 5 (dogfood instance) |
| P0.4 gh-init workspace-root default, repo-local demoted to overlay | Task 3 |
| P0.5 multi-machine topology documented | Task 1 |
| Decision D1 closed | AskUserQuestion (this session) + Task 6 records it |
| Decisions D2/D3 closed; Part 9 "workspace repo hygiene"/"heartbeat scope" | Tasks 1/2 implement; Task 6 records |
| Exit criteria (any-depth resolution, heartbeat, fresh-parent layout) | Task 2 Step 5 (fixture) + Task 5 Step 4 (real) |
