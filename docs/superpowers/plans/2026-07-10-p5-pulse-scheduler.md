# P5 — hiivmind-pulse-scheduler Implementation Plan (completes goal 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scheduler repo mirroring hiivmind-corpus-scheduler: one shared `TEMPLATE-workspace-maintenance.md` composing the P3 headless skills (status pre-check → refresh → fleet healthcheck → commit/PR against the workspace repo), plus one thin stub for the hiivmind workspace — unattended fleet maintenance with a PR-body fleet report.

**Architecture:** Straight port of corpus-scheduler's proven shape: all process logic in one template at the repo root; per-workspace stubs supply exactly three Constants and a relative symlink to the template; task dirs are symlinked into `~/.claude/scheduled-tasks/`. The template reads result **files** (never prose), validates each with `validate_result.py`, and applies the supersede pattern for stale automated PRs. The pre-check is an optimization, never a gate.

**Tech Stack:** Markdown routine template + stubs, git/gh CLI, P1 validator, P3 headless skills.

**Spec:** `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md` — Part 6.2, §P5 (P5.1–P5.4).

## Global Constraints

- **P3 must be executed first** (the skills this template composes: `gh-status-headless`, `gh-refresh-headless`, `gh-healthcheck-headless`). P4.3 (`gh-workflow-run-headless`) is optional: the template's Phase 5b runs scheduled workflows only when the workspace config opts in AND the skill exists.
- **Reusable-first:** the template is fully generic (`WORKSPACE_PATH` / `WORKSPACE_REPO` / `BRANCH_PREFIX` constants; no `hiivmind` anywhere in it). Only the stub (Task 3) and live verification (Task 4) are dogfood.
- **Workspace repo = `{WORKSPACE_PATH}/.hiivmind/github/`** (D1): that directory is the git repo the template branches/commits/PRs against. `WORKSPACE_PATH` itself is NOT a git repo.
- **Result files are read from disk and validated before consumption** (`uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py <file> --kind <k>`); they are gitignored (`*-result.yaml`), so `git add -A` never stages them.
- **Multi-machine rules** (workspace-detection.md): pull before reconcile; superseded PRs closed only *after* the new PR exists; no force-push; commit only what the run produced.
- This plan touches two repos: the new `hiivmind-pulse-scheduler` (Tasks 1–3) and `hiivmind-pulse-gh` (Task 5 spec close-out only — no plugin code changes, **no version bump**).

## File Structure (new repo: `/Users/nathanielramm/git/hiivmind/hiivmind-pulse-scheduler`)

```
TEMPLATE-workspace-maintenance.md      # the single task definition (all phases)
CLAUDE.md                              # repo guide + deployment docs
.gitignore
workspace-maintenance-hiivmind/        # dogfood stub
  SKILL.md                             # frontmatter + 3 Constants + pointer
  TEMPLATE-workspace-maintenance.md    # symlink → ../TEMPLATE-workspace-maintenance.md
```

---

### Task 1: Repo skeleton + CLAUDE.md (P5.1)

**Files:**
- Create: `/Users/nathanielramm/git/hiivmind/hiivmind-pulse-scheduler/{CLAUDE.md,.gitignore}` (+ `git init`)

**Interfaces:**
- Produces: the repo Tasks 2–3 populate; the deployment conventions (symlink, never copy) operators follow.

- [ ] **Step 1: Initialize the repo**

```bash
mkdir -p /Users/nathanielramm/git/hiivmind/hiivmind-pulse-scheduler
cd /Users/nathanielramm/git/hiivmind/hiivmind-pulse-scheduler
git init
```

- [ ] **Step 2: Write `.gitignore`**

```
.DS_Store
.claude/
```

- [ ] **Step 3: Write `CLAUDE.md`** with exactly this content:

````markdown
# hiivmind-pulse-scheduler

Repository of scheduled tasks for automated GitHub-workspace maintenance
(hiivmind-pulse-gh's fleet). Each subdirectory is a self-contained Claude Code
Routine that gets symlinked into `~/.claude/scheduled-tasks/`.

## Structure

```
TEMPLATE-workspace-maintenance.md      # the single task definition: all phases, constraints, output contract
workspace-maintenance-{name}/          # one thin stub per workspace
  SKILL.md                             # frontmatter + Constants (3 values) + pointer to the template
  TEMPLATE-workspace-maintenance.md    # symlink → ../TEMPLATE-workspace-maintenance.md
```

All process logic lives in `TEMPLATE-workspace-maintenance.md`. Stubs supply only
`WORKSPACE_PATH`, `WORKSPACE_REPO`, and `BRANCH_PREFIX`.

The template is symlinked into each task directory (relative link) so the deployed
task can read it as a sibling of its `SKILL.md`. A running routine can only reach
files inside its own task directory (served through the `~/.claude/scheduled-tasks/`
symlink), plugin skills via CALL_SKILL, and host dirs granted with
`request_cowork_directory` — the sibling symlink (not an absolute path reference)
is what makes the shared template reachable.

Because the workspace *is* the fleet (`repositories[]` in its config is the fleet
manifest), one stub covers a whole org. Per-repo stubs exist only for repos needing
distinct schedules or policies.

## Deployment

```bash
ln -s /Users/nathanielramm/git/hiivmind/hiivmind-pulse-scheduler/{task-name} \
      ~/.claude/scheduled-tasks/{task-name}
```

Never copy files into `~/.claude/scheduled-tasks/` — always symlink so changes in
this repo propagate automatically.

## Dependencies

No per-task pyprojects. The plugin's Python scripts carry PEP 723 inline metadata
and are invoked with `uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/<script>.py` —
uv resolves each script's dependencies into a cached ephemeral environment.
Requires: `gh` (authenticated), `uv`, `yq`, `jq` on the routine host.

## Common tasks

- **Add a workspace:** copy any stub dir, substitute the three Constants + frontmatter
  name, add the template symlink (`ln -s ../TEMPLATE-workspace-maintenance.md {dir}/`),
  symlink the dir into `~/.claude/scheduled-tasks/`. Nothing else.
- **Change the maintenance process:** edit `TEMPLATE-workspace-maintenance.md` only.
  Stubs never change.
- **Change the headless behavior itself:** edit the skills in
  `hiivmind/hiivmind-pulse-gh` (`gh-status-headless`, `gh-refresh-headless`,
  `gh-healthcheck-headless`, `gh-workflow-run-headless`) — the template delegates to
  them via CALL_SKILL and reads their result files
  (see the plugin's `lib/patterns/headless-contract.md`).
- **Opt a workspace into scheduled workflow runs:** set
  `automation.scheduled_workflows: [name, ...]` in the workspace config.yaml
  (workflows must carry `headless.enabled: true`). The template's Phase 5b picks
  this up; the stub does not change.

## Related repos

- `hiivmind/hiivmind-pulse-gh` — the plugin containing the headless skills, the
  result contract, and validate_result.py
- `{login}/{login}-workspace` — the workspace repos these tasks maintain
  (`.hiivmind/github/` at each workspace root)
````

- [ ] **Step 4: Commit and create the private remote (dogfood remote)**

```bash
cd /Users/nathanielramm/git/hiivmind/hiivmind-pulse-scheduler
git add CLAUDE.md .gitignore
git commit -m "chore: scheduler repo skeleton

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
gh repo create hiivmind/hiivmind-pulse-scheduler --private --source=. --push
```

---

### Task 2: `TEMPLATE-workspace-maintenance.md` (P5.2 + P5.4)

**Files:**
- Create: `/Users/nathanielramm/git/hiivmind/hiivmind-pulse-scheduler/TEMPLATE-workspace-maintenance.md`

**Interfaces:**
- Consumes: P3 skills + result kinds (`status`: `refresh_needed`; `refresh`: `sections[].status`, `config_updated`; `healthcheck`: `repos[].{repo,score,total,grade,checks}`, `aggregate`); optional P4.3 `workflow-run` kind (`findings`, `proposed_actions`, `asks_recorded`); `automation.scheduled_workflows` from workspace config.
- Produces: the three-Constant contract stubs supply (`WORKSPACE_PATH`, `WORKSPACE_REPO`, `BRANCH_PREFIX`); the fleet-report PR body format.

- [ ] **Step 1: Write the template** with exactly this content:

````markdown
# Workspace Maintenance — Shared Task Template

Automated maintenance of a GitHub workspace (fleet). Delegates the work to the
hiivmind-pulse-gh headless skills, then handles branching, committing, and PR
creation against the **workspace repo** (`{WORKSPACE_PATH}/.hiivmind/github/`).

No user present — act autonomously, note judgment calls, end with `<run-summary>`.

> **This is not a runnable task.** It is the single source of truth executed by the
> thin per-workspace stubs (`workspace-maintenance-*/SKILL.md`), which supply the
> Constants. A process change edits this file only — never the stubs.

---

## State

```yaml
computed:
  config_dir: null              # {WORKSPACE_PATH}/.hiivmind/github
  branch_name: null
  stale_branches: []            # [{branch, pr_number, pr_age_days}] — unmerged {BRANCH_PREFIX}* branches
  superseded_prs: []
  status_result: null           # parsed status-result.yaml
  refresh_needed: null          # null when pre-check unavailable
  refresh_result: null          # parsed refresh-result.yaml
  previous_grades: {}           # {short-name: {grade, score, total}} from committed healthcheck.yaml
  healthcheck_result: null      # parsed healthcheck-result.yaml
  grade_deltas: []              # [{repo, was, now}] where changed
  workflow_results: []          # parsed workflow-run-result.yaml per scheduled workflow (Phase 5b)
  dismissals_due: []            # [{repo, check, review_after}] past their review date
  has_changes: false
  pr_url: null
  errors: []
  error: null                   # fatal → ABORT
```

## Constants

Provided by the invoking stub's Constants block:

```yaml
WORKSPACE_PATH:  # absolute path to the workspace root (parent of repo clones)
WORKSPACE_REPO:  # owner/name of the workspace repo on GitHub
BRANCH_PREFIX:   # e.g. automated/workspace-maintenance-{name}
```

Template defaults (edit here, not in stubs):

```yaml
HEALTHCHECK_INTERVAL_HOURS: 24   # skip the run entirely if last fleet audit is fresher
```

---

## Phase 1: Connect

**Outputs:** `computed.config_dir`

Verify `{WORKSPACE_PATH}/.hiivmind/github/config.yaml` exists and contains a top-level
`workspace:` key. Abort if not. Call `request_cowork_directory` on `WORKSPACE_PATH`
so file operations target the real workspace. Never clone into the sandbox — it has
no git credentials. Use `git` via Bash for local ops, `gh` CLI for remote ops.

## Phase 2: Branch Setup

**Outputs:** `computed.branch_name`, `computed.stale_branches`

All git commands run with `-C {computed.config_dir}` — the workspace repo is
`.hiivmind/github/` itself, not `WORKSPACE_PATH`.

Abort if `git status --porcelain` is non-empty (dirty workspace repo).
Checkout the default branch, pull (pull-before-reconcile — shared markers may have
moved on another machine).

Detect leftover automated branches and their open PRs (same pseudocode as
corpus-scheduler): for each `origin/{BRANCH_PREFIX}*` branch, `gh pr list
--repo {WORKSPACE_REPO} --head {branch} --state open --json number,createdAt`;
record `{branch, pr_number, pr_age_days}`. Proceed regardless — superseded PRs are
closed in Phase 6 *after* the new PR exists, never before.

Create `{BRANCH_PREFIX}-{YYYY-MM-DD}` (suffix `-2`, `-3`… on collision).

## Phase 3: Status Pre-Check

**Outputs:** `computed.status_result`, `computed.refresh_needed`

```
CALL_SKILL("hiivmind-pulse-gh:gh-status-headless",
           { workspace_path: WORKSPACE_PATH, mode: scheduled })
```

Read `{config_dir}/status-result.yaml`, validate:

```
uv run ${CLAUDE_PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py {config_dir}/status-result.yaml --kind status
```

Early exit ("already current"): if `refresh_needed: false` AND the committed
`healthcheck.yaml` `last_run.timestamp` is younger than `HEALTHCHECK_INTERVAL_HOURS`
AND `automation.scheduled_workflows` is empty/absent — clean up the branch
(`git checkout {default} && git branch -d {branch_name}`), report
"already current (pre-check)", go to SUMMARY. **If the pre-check itself fails
(invalid/missing result, skill error), log it and proceed with the full run — the
pre-check is an optimization, never a gate.**

## Phase 4: Refresh

**Outputs:** `computed.refresh_result`

Skip when `refresh_needed: false` (config already fresh). Otherwise:

```
CALL_SKILL("hiivmind-pulse-gh:gh-refresh-headless",
           { workspace_path: WORKSPACE_PATH, mode: scheduled })
```

Read + validate `{config_dir}/refresh-result.yaml` (`--kind refresh`). Log any
`failed` sections into `computed.errors` but continue — partial refreshes are still
worth committing.

## Phase 5: Fleet Healthcheck

**Outputs:** `computed.previous_grades`, `computed.healthcheck_result`,
`computed.grade_deltas`, `computed.dismissals_due`

1. Capture previous grades from the **committed** governance record (not working tree):

```bash
git -C {config_dir} show HEAD:healthcheck.yaml
```

   → `computed.previous_grades[short-name] = {grade, score, total}` per repo (empty
   map if the file didn't exist yet).

2. Run the fleet audit (iterates the whole `repositories[]` catalog):

```
CALL_SKILL("hiivmind-pulse-gh:gh-healthcheck-headless",
           { workspace_path: WORKSPACE_PATH, mode: scheduled })
```

3. Read + validate `{config_dir}/healthcheck-result.yaml` (`--kind healthcheck`).
   Compute `grade_deltas` = repos whose grade differs from `previous_grades`.
4. Collect `dismissals_due` from `healthcheck.yaml`: any dismissal whose
   `review_after` is non-null and ≤ today.

## Phase 5b: Scheduled Workflows (optional)

**Outputs:** `computed.workflow_results`

Read `automation.scheduled_workflows` from `{config_dir}/config.yaml`. Skip this
phase if absent/empty, or if the plugin has no `gh-workflow-run-headless` skill yet.

For each workflow name:

```
CALL_SKILL("hiivmind-pulse-gh:gh-workflow-run-headless",
           { workspace_path: WORKSPACE_PATH, workflow: {name}, mode: scheduled })
```

Read + validate `{config_dir}/workflow-run-result.yaml` (`--kind workflow-run`)
after each run and append the parsed result to `computed.workflow_results` (the
file is overwritten per run — parse before the next CALL_SKILL). Outcomes
`skipped-cooldown` are normal; log `failure`/`aborted` into `computed.errors`
and continue.

## Phase 6: Commit and PR

**Outputs:** `computed.has_changes`, `computed.pr_url`, `computed.superseded_prs`

`git -C {config_dir} status --porcelain` — if empty: `has_changes = false`, delete
the branch, go to SUMMARY (no PR; leave existing automated PRs open, report their age).

Stage with `git add -A` (result files are gitignored via `*-result.yaml`; poll-state
and snapshots via the workspace .gitignore — only refreshed catalogs, freshness
timestamps, and healthcheck.yaml land).

Commit: subject `workspace: maintenance {date}`, body listing refreshed sections and
the aggregate grade. Push with `-u`, then `gh pr create --repo {WORKSPACE_REPO}` with
the **fleet report** as body:

```markdown
## Workspace Maintenance — {date}

### Fleet health

| Repository | Grade | Score | Δ since last run |
|------------|-------|-------|------------------|
| {short-name} | {grade} | {score}/{total} | {was → now, or —} |

**Aggregate:** {grade} ({score}/{total}){, was {grade} if changed}

### Refresh

{sections refreshed / skipped / failed; config_updated. Or "skipped — config fresh".}

### Workflow runs        <!-- only when Phase 5b ran -->

| Workflow | Outcome | Findings |
|----------|---------|----------|
| {name} | {outcome} | {count} |

### Needs attention

<!-- the only items requiring human judgment — keep this heading even when empty -->
- Grade regressions: {repo was X now Y, failing checks listed}
- Dismissals due for review: {repo}/{check} (review_after {date})
- Checks marked `inferred: true`: {repo}/{check} — LLM judgment, verify
- `asks_recorded`: {workflow}: {question}          <!-- from Phase 5b results -->
- `proposed_actions`: {workflow}: {action}         <!-- mutations withheld headless -->
- Errors: {computed.errors}

{If truly nothing: "Nothing needs attention — routine sync."}
```

After the PR exists, close superseded automated PRs (each open PR in
`computed.stale_branches` was generated from older state; this PR replaces it):

```
gh pr close {n} --repo {WORKSPACE_REPO} --delete-branch \
  --comment "Superseded by {pr_url} (regenerated from current GitHub state)."
```

## SUMMARY

Always reached. Report: pre-check outcome, sections refreshed, per-repo grades +
deltas, workflow outcomes, PR URL or "already current" / "no changes", superseded
PRs closed, ages of automated PRs left open, errors. End with a `<run-summary>`
block for the scheduler log.

## ABORT

Fatal errors only (missing workspace, dirty repo). Report and emit `<run-summary>`
with `FAILED: {reason}`.

## Constraints

- **No force-push**, no history rewriting
- **No unrelated changes** — only commit what this run produced
- **Autonomous** — no prompts; judgment calls are logged, not asked
- **Read result files, never prose** — validate each with validate_result.py before
  consuming; an invalid result is an error for that phase, not a crash
````

- [ ] **Step 2: Commit**

```bash
cd /Users/nathanielramm/git/hiivmind/hiivmind-pulse-scheduler
git add TEMPLATE-workspace-maintenance.md
git commit -m "feat: workspace-maintenance shared template (pre-check → refresh → fleet audit → PR)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: hiivmind stub + deployment (P5.3) **(dogfood)**

**Files:**
- Create: `workspace-maintenance-hiivmind/SKILL.md` + template symlink
- Create: symlink in `~/.claude/scheduled-tasks/`

**Interfaces:**
- Consumes: the template's Constants contract (Task 2).

- [ ] **Step 1: Write the stub**

`workspace-maintenance-hiivmind/SKILL.md`:

```markdown
---
name: workspace-maintenance-hiivmind
description: Scheduled maintenance of the hiivmind GitHub workspace — delegates to the shared workspace-maintenance template
---

# Workspace Maintenance — hiivmind

## Constants

```yaml
WORKSPACE_PATH: /Users/nathanielramm/git/hiivmind
WORKSPACE_REPO: hiivmind/hiivmind-workspace
BRANCH_PREFIX: automated/workspace-maintenance-hiivmind
```

## Task

Read and execute the shared template that sits alongside this file (symlinked into
this directory), using the Constants above:

`TEMPLATE-workspace-maintenance.md`

It is the single source of truth (the real file lives at the scheduler repo root).
Every phase, constraint, and output contract is defined there. Do not deviate from
it and do not improvise steps that are not in the template.
```

- [ ] **Step 2: Symlinks**

```bash
cd /Users/nathanielramm/git/hiivmind/hiivmind-pulse-scheduler
ln -s ../TEMPLATE-workspace-maintenance.md workspace-maintenance-hiivmind/TEMPLATE-workspace-maintenance.md
mkdir -p ~/.claude/scheduled-tasks
ln -s /Users/nathanielramm/git/hiivmind/hiivmind-pulse-scheduler/workspace-maintenance-hiivmind \
      ~/.claude/scheduled-tasks/workspace-maintenance-hiivmind
```

- [ ] **Step 3: Verify symlink resolution and commit**

```bash
readlink workspace-maintenance-hiivmind/TEMPLATE-workspace-maintenance.md          # ../TEMPLATE-workspace-maintenance.md
head -1 ~/.claude/scheduled-tasks/workspace-maintenance-hiivmind/TEMPLATE-workspace-maintenance.md
```

Expected: the second command prints `# Workspace Maintenance — Shared Task Template` (relative link resolves through the scheduled-tasks symlink).

```bash
git add workspace-maintenance-hiivmind
git commit -m "feat: hiivmind workspace-maintenance stub + deployment symlink

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git push
```

---

### Task 4: End-to-end verification (exit criteria) **(dogfood verification)**

No new files — execute the template manually, in this session, exactly as the routine would.

- [ ] **Step 1: First run produces a fleet-report PR**

Execute `TEMPLATE-workspace-maintenance.md` phase-by-phase with the hiivmind stub's Constants. Expected outcomes to verify:

```bash
WS=/Users/nathanielramm/git/hiivmind
gh pr list --repo hiivmind/hiivmind-workspace --state open --json number,title,headRefName
```

- A PR exists on `hiivmind/hiivmind-workspace` from `automated/workspace-maintenance-hiivmind-{date}`.
- Its body contains the `### Fleet health` table and the `### Needs attention` heading.
- `git -C $WS/.hiivmind/github log --oneline -1` on the branch shows `workspace: maintenance {date}`.
- No `*-result.yaml`, `poll-state.yaml`, or `project-snapshot.json` in the PR diff.

- [ ] **Step 2: Second run exits at the pre-check without a PR**

Immediately re-execute the template (config now fresh; healthcheck < 24h old; no scheduled workflows configured). Expected: the run reports `already current (pre-check)` in its `<run-summary>`, the temporary branch is deleted, and `gh pr list` shows no *new* PR.

- [ ] **Step 3: Merge or close the verification PR**

Review the fleet report; merge it if the content is correct (it is a real maintenance commit), otherwise close it and note why in the run summary.

---

### Task 5: Spec close-out (in hiivmind-pulse-gh)

**Files:**
- Modify: `docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Spec**

1. Tick P5.1–P5.4 checkboxes to `- [x]`.
2. §8.9 table: P5 row → `✅ done` with the actual execution date. Goal 1 is complete — note it in the row title cell is already there (`(goal 1)`).

- [ ] **Step 2: CLAUDE.md**

In the "Testing" / related-repos area (after the `## Testing` section), add:

```markdown
## Scheduled Maintenance

Unattended fleet maintenance lives in a separate repo:
[hiivmind-pulse-scheduler](https://github.com/hiivmind/hiivmind-pulse-scheduler) —
a shared `TEMPLATE-workspace-maintenance.md` composes the headless skills
(status pre-check → refresh → fleet healthcheck → PR on the workspace repo);
thin per-workspace stubs are symlinked into `~/.claude/scheduled-tasks/`.
```

- [ ] **Step 3: Commit (no version bump — plugin code unchanged)**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-07-10-workspace-root-and-headless-orchestration-design.md
git commit -m "docs: mark P5 complete (pulse-scheduler, goal 1)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Deliverable → Task map (spec coverage)

| Spec deliverable | Task |
|------------------|------|
| P5.1 new repo: CLAUDE.md, symlink deployment docs (corpus-scheduler conventions) | Task 1 |
| P5.2 TEMPLATE-workspace-maintenance.md: pre-check (optimization-never-gate) → refresh → fleet healthcheck → commit/PR + superseded-PR cleanup | Task 2 |
| P5.3 one stub (workspace-maintenance-hiivmind) with 3 constants; symlinked into ~/.claude/scheduled-tasks/ | Task 3 |
| P5.4 fleet report PR body: per-repo grades + deltas; asks_recorded / proposed_actions under "Needs attention" | Task 2 Phase 6 (+ Phase 5b feeding it) |
| Exit criteria: one unattended run → PR with fleet report; second run exits at pre-check without a PR | Task 4 |
| Spec progress tracking rule | Task 5 |
