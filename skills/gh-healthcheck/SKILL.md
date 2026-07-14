---
name: gh-healthcheck
description: >
  On-demand governance audit for repository maturity. Evaluates branch protection, project linkage,
  triage labels, CI/CD, releases, documentation, CODEOWNERS, security policy, license, dependency
  management (Dependabot/Renovate), and secrets scanning. Multi-repo aware — evaluates all repos in config catalog or a specific repo.
  Dismissals persist across sessions so resolved decisions are not raised again. Read-only evaluation;
  fix actions route through gh-operations. Trigger phrases: "healthcheck", "health check", "governance",
  "audit", "best practices", "repo health", "readiness", "maturity", "governance audit", "repo readiness",
  "check repo health", "run healthcheck", "security audit", "compliance check".
trigger: "healthcheck|health check|governance|audit|best practices|repo health|readiness|maturity"
tools: [shell, filesystem]
author: hiivmind
---

# Repository Healthcheck

On-demand governance audit that evaluates repository maturity across security, governance,
automation, and documentation dimensions. Read-only — never mutates GitHub resources directly.

## Path Convention

`{PLUGIN_ROOT}` = Plugin root directory (where plugin.json lives)

When this skill references files like `{PLUGIN_ROOT}/lib/references/healthcheck-checks.md`,
read from the plugin root, not relative to this skill folder.

## Scope

| Does | Does NOT |
|------|----------|
| Evaluate 11 governance checks per repo | Mutate GitHub resources |
| Support multi-repo evaluation from catalog | Run on every session (on-demand only) |
| Persist results and dismissals in healthcheck.yaml | Replace heartbeat polling |
| Offer fix actions via gh-operations delegation | Modify config.yaml or freshness.yaml |
| Score and grade repositories | Block operations based on score |

## Expected Context

When invoked by the gateway command, expect:

- **Arguments**: Optional repo name to scope evaluation, or "clear" to manage dismissals
- **Config**: `.hiivmind/github/config.yaml` must exist
- **Healthcheck state**: `.hiivmind/github/healthcheck.yaml` (created if missing)

---

## Phase Overview

```
1. CONTEXT    → 1.5 CHECK TOOLS → 2. EVALUATE   → 3. PRESENT   → 4. RESOLVE   → 5. PERSIST
   (scope)        (gh/jq/yq)        (run checks)    (report)       (fix/dismiss)   (write)
     │                │                  │               │               │              │
  STOP if          STOP if            skip             grade          STOP for          —
  not init         gh missing        dismissed        + detail       user choice
```

---

## Phase 1: CONTEXT

**Goal:** Load config, determine repo scope, load existing healthcheck state.

**See:** `{PLUGIN_ROOT}/lib/patterns/config-parsing.md`

### What to Do

1. Check for `.hiivmind/github/config.yaml` (current and parent directories)
2. Load workspace context (owner, type)
3. Determine repo scope from arguments
4. Load existing `.hiivmind/github/healthcheck.yaml` if it exists

### Scope Resolution

Parse `$ARGUMENTS` to determine scope:

| Input | Scope |
|-------|-------|
| `/gh healthcheck` (no args) | All repos in config catalog |
| `/gh healthcheck repo-name` | Specific repo |
| `/gh healthcheck clear check-id` | Clear dismissal (not evaluation) |
| `/gh healthcheck clear all` | Clear all dismissals |

```pseudocode
IF arguments contain "clear":
  → Handle dismissal clearing (Phase 4 shortcut)
  → Then STOP

IF arguments contain a repo name:
  → Verify repo exists in config catalog
  → REPOS = [repo-name]
ELIF only one repo in catalog:
  → REPOS = [that-repo]
ELSE:
  → REPOS = all repos in catalog
```

### STOP Point

**If not initialized:**

```
Workspace not initialized.

Config file not found. Run: /gh init
```

**If specified repo not in catalog:**

```
Repository "{name}" not found in workspace catalog.

Available repositories:
  - repo-a
  - repo-b

Run: /gh refresh repositories to update the catalog.
```

---

## Phase 1.5: CHECK TOOLS

**Goal:** Verify gh, jq, yq are available.

**See:** `{PLUGIN_ROOT}/lib/patterns/tool-detection.md`

1. Check for `gh` CLI — **STOP if missing**
2. Check for `jq`, `yq` — **WARN if missing** (do not block)

---

## Phase 2: EVALUATE

**Goal:** Run each check for each repo in scope. Skip dismissed checks (unless review_after passed).

**See:** `{PLUGIN_ROOT}/lib/references/healthcheck-checks.md` for check definitions
**See:** `{PLUGIN_ROOT}/lib/patterns/healthcheck-evaluation.md` for evaluation logic

### What to Do

For each repo in `REPOS`:

1. Determine if repo is current repo (filesystem available) or remote (API only)
2. For each check in the catalog:
   a. Check dismissal status — skip if dismissed and not expired
   b. Try cache/filesystem data source first
   c. Fall back to API if cache miss
   d. Evaluate pass/warn/fail criteria
   e. Record result with status, detail, and timestamp

### Current Repo Detection

```bash
CURRENT_REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)")
```

If `CURRENT_REPO` matches the repo being evaluated → use filesystem checks where applicable.
Otherwise → use API for all checks.

### Check Execution Order

Execute checks in catalog order. For each check:

```pseudocode
FOR check IN healthcheck_catalog:
  # 1. Check dismissal
  IF is_dismissed(repo, check.id) AND NOT dismissal_expired(repo, check.id):
    results[check.id] = {
      status: "not_applicable",
      detail: "Dismissed: {reason}",
      data: {dismissed: true, reason: reason}
    }
    CONTINUE

  # 2. Evaluate
  IF repo == current_repo AND check.has_local_source:
    result = evaluate_local(check)
  ELSE:
    result = evaluate_api(check)

  # 3. Record
  results[check.id] = {
    status: result.status,      # pass | warn | fail | unknown | not_applicable | unsupported | error
    detail: result.detail,
    last_evaluated: now(),
    data: result.raw_data       # optional structured data for future reference
  }
```

### Rate Limiting

Space API calls to avoid hitting GitHub rate limits, especially for multi-repo evaluations:

- Batch filesystem checks first (zero API cost)
- Then run API checks sequentially per repo
- Use `--silent` flag on existence checks to minimize output

---

## Phase 3: PRESENT

**Goal:** Display per-repo report cards and aggregate score for multi-repo evaluations.

### Single-Repo Report

```
## Healthcheck: {repo-name}

Grade: {grade} ({score}/{total})

| Check | Status | Detail |
|-------|--------|--------|
| Branch Protection | ✅ pass | main: 1 required review |
| Project Linkage | ✅ pass | Linked to 2 project(s) |
| Issue Triage | ⚠️ warn | Bug labels present, no priority labels |
| CI/CD | ✅ pass | 3 workflow(s) configured |
| Releases | ❌ fail | No releases or tags |
| Documentation | ⚠️ warn | README ✓, no CONTRIBUTING.md |
| CODEOWNERS | ❌ fail | No CODEOWNERS file |
| Security Policy | ❌ fail | No security policy |
| License | ✅ pass | MIT |
| Dependency Mgmt | ✅ pass | Renovate configured |
| Secrets Scanning | ✅ pass | Scanning: enabled, Push protection: enabled |

Scorecard: {scorecard_id}
Coverage: {coverage_supported}/{coverage_total} supported
{dismissed_count} check(s) dismissed — reported as not_applicable and not counted in score.
```

**Status icons:**
- `pass` → ✅
- `warn` → ⚠️
- `fail` → ❌
- `unknown` → ❓
- `not_applicable` → ⏭️
- `unsupported` → 🚫
- `error` → 💥

### Multi-Repo Report

Show aggregate first, then per-repo breakdown:

```
## Healthcheck Summary

| Repository | Scorecard | Grade | Score | Coverage | Failing |
|------------|-----------|-------|-------|----------|---------|
| repo-a | python-library-v1 | B | 9/11 | 11/11 | codeowners, security_policy |
| repo-b | node-web-v1 | C | 7/10 | 8/10 | ci_cd, releases, documentation |

Aggregate: B (16/22)

---

[Per-repo details follow]
```

Grades are comparable only within the same scorecard revision. Compare coverage separately from
score so unsupported tooling is visible rather than silently lowering or inflating maturity.

---

## Phase 4: RESOLVE

**Goal:** Offer fix or dismiss actions for failing checks.

### STOP Point

After presenting the report, offer actions:

```
What would you like to do?

  1. Fix a failing check — I'll help set it up via gh-operations
  2. Dismiss a check — Record a team decision to skip it
  3. Done — Save results and exit
```

### Fix Flow

If user chooses to fix:

1. Ask which check to fix
2. Display the suggested fix action from the check catalog
3. Delegate to `hiivmind-pulse-gh:gh-operations` with the fix command
4. After fix completes, offer to re-evaluate that check

### Dismiss Flow

If user chooses to dismiss:

1. Ask which check to dismiss
2. Ask for reason (required): "Why is this check not applicable?"
3. Ask for time-boxing: "Review again in? [never / 1 month / 3 months / 6 months]"
4. Record dismissal:

```yaml
dismissals:
  {repo-name}:
    {check-id}:
      dismissed_at: "2026-02-21T10:00:00Z"
      dismissed_by: {current_user_login}
      reason: "Pre-release project, no formal releases yet"
      review_after: "2026-05-21"  # null for "never"
```

### Clear Dismissals

If invoked with `clear`:

- `/gh healthcheck clear {check-id}` — Clear dismissal for specific check (current repo or specified repo)
- `/gh healthcheck clear all` — Clear all dismissals for repo

Confirm before clearing:

```
Clear dismissal for "{check-id}" on {repo-name}?

Dismissed by: alice
Reason: Pre-release project
Review after: 2026-05-21

This will re-evaluate the check on next healthcheck run. Proceed? [Y/n]
```

---

## Phase 5: PERSIST

**Goal:** Write healthcheck.yaml with results and dismissals.

### What to Do

1. If `.hiivmind/github/healthcheck.yaml` doesn't exist, create from template
2. Update `last_run` section with timestamp, scope, aggregate score/grade
3. Update `repos.{name}` section for each evaluated repo
4. Preserve existing dismissals (merge, don't overwrite)
5. Write file

**See:** `{PLUGIN_ROOT}/templates/healthcheck.yaml.template` for structure

### File Location

```
.hiivmind/github/healthcheck.yaml
```

This file is **committed to git** (team-shared decisions). Dismissals represent team governance decisions that should persist across contributors.

---

## Related Skills

| Skill | Use For |
|-------|---------|
| **gh-operations** | Fix failing checks (delegated from Phase 4) |
| **gh-init** | Offers healthcheck in Phase 5.7 for new workspaces |
| **gh-refresh** | Refresh stale config before healthcheck |

---

## Resources

### Patterns (HOW to do things)

| Pattern | Purpose |
|---------|---------|
| `{PLUGIN_ROOT}/lib/patterns/config-parsing.md` | Read/write YAML config files |
| `{PLUGIN_ROOT}/lib/patterns/healthcheck-evaluation.md` | Evaluation logic per check |
| `{PLUGIN_ROOT}/lib/patterns/tool-detection.md` | Check gh/jq/yq availability |

### References (WHAT exists)

| Reference | Purpose |
|-----------|---------|
| `{PLUGIN_ROOT}/lib/references/healthcheck-checks.md` | Check catalog (extension point) |
| `{PLUGIN_ROOT}/lib/references/api-routing.md` | API routing for fix actions |
