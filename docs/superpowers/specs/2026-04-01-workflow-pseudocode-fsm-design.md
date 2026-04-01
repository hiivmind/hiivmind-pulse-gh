# Workflow Pseudocode FSM Design

**Date:** 2026-04-01
**Status:** Draft
**Scope:** Workflow YAML templates (`templates/workflows/`) and deployed workflows (`.hiivmind/github/workflows/`)

## Problem

Current workflow YAMLs are flat action lists — sequential operation strings with no decision logic. They tell the LLM *what to check* but not *how to think about what it finds*. A workflow like `ci-monitor` lists failed runs and shows logs, but can't classify failures, offer targeted remediation, or loop through multiple items.

## Design

### Format: Hybrid structured YAML + embedded pseudocode

Keep YAML for what YAML is good at (metadata, trigger config, state declarations). Use pseudocode for what pseudocode is good at (decision logic, branching, user interaction, loops).

The pseudocode is **LLM-interpreted** — there is no parser. The conventions make it predictable for humans to author and review, but the LLM has latitude in execution. This mirrors the proven fairgo-mcp pattern.

### YAML Format v2

**Unchanged fields:**
- `name` — workflow identifier
- `description` — human-readable purpose
- `enabled` — whether the workflow is active
- `auto` — whether it runs without user approval
- `trigger` — when the workflow fires (session_poll, freshness, on_demand, post_operation)
- `cooldown_minutes` — minimum interval between runs

**New field: `state:`**

Declares the workflow's scratchpad. Initialized fresh each run. Gives the LLM named variables to work with.

```yaml
state:
  failures: []        # gathered data
  selected: null      # current focus
  actions_taken: []   # audit trail for summary
```

**New field: `workflow:`**

Pseudocode FSM replacing `actions[]`. Uses labeled phases with control flow, user interaction, and state management.

**Removed field: `actions[]`**

Replaced entirely by `workflow:`. Simple workflows that were just "run these operations" become simple pseudocode.

### Pseudocode Conventions

**Phase labels** — capitalized, colon-terminated. Named for intent.

| Label | Purpose |
|-------|---------|
| `GATHER:` | Fetch data, compute derived fields |
| `PRESENT:` | Show findings, offer choices |
| `TRIAGE:` | Classify or prioritize |
| `INVESTIGATE:` | Deep-dive on a selected item |
| `ACT:` | Perform actions on a selected item |
| `EXECUTE:` | Perform actions (simple workflows) |
| `SUMMARIZE:` | Wrap up, report what was done |

These are conventions, not reserved words. Authors can use any label that reads clearly.

**Operations** — natural language strings, interpreted via gh-operations:

```
failures = list recent failed workflow runs with conclusions
SHOW failing test output from logs
trigger workflow rerun for selected.run_id
```

**Control flow:**

```
IF / ELIF / ELSE          # branching
FOR EACH item IN list     # iteration
GOTO PHASE_NAME           # loop back (FSM transition)
STOP "reason"             # early exit
```

**User interaction:**

```
ASK "question" (option_a | option_b | option_c)    # multiple choice
ASK "free text question?"                           # open-ended
```

Every `ASK` maps to an AskUserQuestion call at runtime.

**State management:**

```
STORE variable_name           # persist to state
REMOVE item FROM list         # remove processed item
SET variable = value          # direct assignment
RECORD action in list         # append to audit trail
```

**Skill invocation:**

```
INVOKE skill plugin:skill-name
INVOKE skill plugin:skill-name WITH args
```

**Classification/inference:**

```
INFER category from data (option_a | option_b | option_c)
```

Signals the LLM to use judgment. The options are guidance, not constraints.

## Workflows

### auto-refresh (simple)

```yaml
name: "auto-refresh"
description: "Automatically refresh stale config sections on session start"
enabled: true
auto: false

trigger:
  type: freshness
  condition: threshold_exceeded

state: {}

workflow: |
  EXECUTE:
    INVOKE skill hiivmind-pulse-gh:gh-refresh

cooldown_minutes: 60
```

### repo-healthcheck (simple)

```yaml
name: "repo-healthcheck"
description: "Run governance healthcheck to assess repository maturity"
enabled: true
auto: false

trigger:
  type: on_demand
  condition: user_requested

state: {}

workflow: |
  EXECUTE:
    INVOKE skill hiivmind-pulse-gh:gh-healthcheck

cooldown_minutes: 10080
```

### release-monitor (medium)

```yaml
name: "release-monitor"
description: "Detect new releases, show details, and offer follow-up actions"
enabled: true
auto: false

trigger:
  type: session_poll
  source: releases
  condition: state_changed
  filter: {}

state:
  release: null
  previous_tag: null

workflow: |
  GATHER:
    release = show latest release including tag, author, notes, and assets
    IF release is empty: STOP "No releases found"
    previous_tag = get the release tag before release.tag

  PRESENT:
    SHOW release summary: tag, author, date, release notes excerpt
    IF previous_tag exists:
      ASK "Compare changes since {previous_tag}, view full release notes, or skip?" (compare | notes | skip)
      IF compare: show commit log between previous_tag and release.tag
      IF notes: show full release notes body
    ELSE:
      ASK "View full release notes?" (yes | skip)
      IF yes: show full release notes body

cooldown_minutes: 60
```

### deploy-monitor (medium)

```yaml
name: "deploy-monitor"
description: "Track deployment status, surface failures, and offer rollback discussion"
enabled: true
auto: false

trigger:
  type: session_poll
  source: deployments
  condition: state_changed
  filter: {}

state:
  deployment: null
  previous: null

workflow: |
  GATHER:
    deployment = show latest deployment status including environment, creator, and sha
    IF deployment.status == "success":
      SHOW "Deployment to {deployment.environment} succeeded ({deployment.sha})"
      STOP "No action needed"
    previous = show the deployment before the latest one

  PRESENT:
    IF deployment.status == "failure":
      SHOW deployment failure details: environment, error, creator, time
      ASK "Investigate logs, compare with previous deployment, or skip?" (logs | compare | skip)
      IF logs: show deployment logs and error output
      IF compare: show diff between deployment.sha and previous.sha

    ELIF deployment.status == "pending" OR deployment.status == "in_progress":
      SHOW "Deployment to {deployment.environment} is {deployment.status}"
      ASK "Watch for completion, or skip?" (watch | skip)
      IF watch: check deployment status again after brief wait

    IF deployment.status == "failure":
      ASK "Open an issue for this deployment failure?" (yes | no)
      IF yes: create issue with deployment details labeled "deployment-failure"

cooldown_minutes: 10
```

### project-sync (medium)

```yaml
name: "project-sync"
description: "Detect project board changes and offer status management"
enabled: true
auto: false

trigger:
  type: session_poll
  source: projects
  condition: state_changed
  filter: {}

state:
  assignments: []
  selected: null
  actions_taken: []

workflow: |
  GATHER:
    assignments = show my current project assignments across all projects
    IF assignments is empty: STOP "No project assignments found"
    FOR EACH item IN assignments:
      item.changed = CHECK if status or assignee changed since last session
    STORE assignments

  PRESENT:
    changed = FILTER assignments WHERE changed == true
    IF changed is empty:
      SHOW "No changes to your project assignments since last session"
      STOP "Nothing to act on"
    SHOW changed items as table: [project, item, old_status, new_status, assignee]
    IF count(changed) > 1:
      ASK "Update any of these items?" showing each as a choice, plus "skip all"
    ELIF count(changed) == 1:
      selected = changed[0]
      ASK "Update status for {selected.title}?" (update | skip)

  ACT(selected):
    SHOW current status and available status options for selected
    ASK "Set status to?" showing available statuses as choices, plus "skip"
    IF not skip: update project item status to chosen value
    RECORD action in actions_taken

    REMOVE selected from changed
    IF changed not empty:
      GOTO PRESENT
    ELSE:
      GOTO SUMMARIZE

  SUMMARIZE:
    IF actions_taken not empty:
      SHOW actions_taken as table: [item, old_status, new_status]

cooldown_minutes: 30
```

### ci-monitor (complex)

```yaml
name: "ci-monitor"
description: "Detect failed CI runs, classify failures, and offer targeted remediation"
enabled: true
auto: false

trigger:
  type: session_poll
  source: actions
  condition: new_failure
  filter: {}

state:
  failures: []
  selected: null
  actions_taken: []

workflow: |
  GATHER:
    failures = list recent failed workflow runs with conclusions
    IF failures is empty: STOP "No failed runs detected"
    FOR EACH failure IN failures:
      logs = fetch logs for failure
      failure.classify = INFER from logs (test | infra | config | flaky | permissions)
      failure.branch = extract branch name
      failure.user_touched = CHECK git blame on failing files against current user
    STORE failures

  PRESENT:
    SHOW failures as table: [workflow, branch, classify, user_touched, time]
    IF count(failures) > 1:
      ASK "Which failure to investigate?" showing each as a choice
    ELSE:
      selected = failures[0]

  INVESTIGATE(selected):
    IF selected.classify == "flaky":
      SHOW note: "This run failed then passed on a subsequent run, or has a history of intermittent failures"
      ASK "Rerun this workflow, open a flaky-test issue, or skip?" (rerun | issue | skip)
      IF rerun: trigger workflow rerun for selected.run_id
      IF issue: create issue labeled "flaky-test" with failure details

    ELIF selected.classify == "test" AND selected.user_touched:
      SHOW failing test names and relevant log output
      ASK "Debug this failure, open an issue, or skip?" (debug | issue | skip)
      IF debug: analyze test failure against recent changes and suggest fix
      IF issue: create issue with failure details and suggested assignee

    ELIF selected.classify == "test" AND NOT selected.user_touched:
      SHOW failing test names and committer info
      ASK "Open an issue, ping the author, or skip?" (issue | ping | skip)
      IF issue: create issue with failure details
      IF ping: comment on the commit with failure summary

    ELIF selected.classify == "infra":
      SHOW infrastructure error summary (timeout, OOM, network, runner)
      ASK "Open an issue, rerun, or skip?" (issue | rerun | skip)
      IF issue: create issue labeled "infrastructure"
      IF rerun: trigger workflow rerun

    ELIF selected.classify == "config":
      SHOW config-related error (missing secret, bad YAML, version mismatch)
      ASK "Investigate config, open an issue, or skip?" (investigate | issue | skip)
      IF investigate: show relevant config files and suggest fix

    ELIF selected.classify == "permissions":
      SHOW permission error details
      ASK "Check token scopes, open an issue, or skip?" (check | issue | skip)
      IF check: verify gh auth scopes against required permissions

    RECORD action taken for selected in actions_taken
    REMOVE selected from failures
    IF failures not empty:
      GOTO PRESENT
    ELSE:
      GOTO SUMMARIZE

  SUMMARIZE:
    SHOW actions_taken as table: [workflow, action, result]
    IF any issues created: SHOW links

cooldown_minutes: 10
```

### pr-lifecycle (complex)

```yaml
name: "pr-lifecycle"
description: "Summarize PR activity, triage by urgency, and offer review actions"
enabled: true
auto: false

trigger:
  type: session_poll
  source: pull_requests
  condition: state_changed
  filter: {}

state:
  prs: []
  selected: null
  actions_taken: []

workflow: |
  GATHER:
    prs = list open PRs with diff stats, review status, and CI status
    IF prs is empty: STOP "No open PRs"
    FOR EACH pr IN prs:
      pr.urgency = INFER from age, review state, CI status (critical | needs_review | waiting | stale)
      pr.risks = INFER from diff size, files changed, missing tests (high | medium | low)
    SORT prs by urgency descending
    STORE prs

  PRESENT:
    SHOW prs as table: [title, author, urgency, risks, reviews, CI]
    IF count(prs) > 1:
      ASK "Which PR to investigate?" showing each as a choice, plus "skip all"
    ELSE:
      selected = prs[0]

  INVESTIGATE(selected):
    SHOW diff summary: what changed, why (from PR body), file categories
    IF selected.risks == "high":
      SHOW risk factors (large diff, no tests, sensitive files)

    ASK "What would you like to do?" (review | merge | comment | request_reviewer | skip)

    IF review:
      SHOW detailed diff with inline commentary on notable changes
      ASK "Approve, request changes, or comment?" (approve | request_changes | comment)
      IF approve: submit approving review
      IF request_changes: ASK "What changes to request?" then submit review
      IF comment: ASK "What to comment?" then submit review comment

    IF merge:
      IF selected.CI != "passing":
        ASK "CI is not passing. Merge anyway?" (yes | no)
      IF selected.reviews_approved == 0:
        ASK "No approving reviews. Merge anyway?" (yes | no)
      IF proceeding: merge PR with appropriate method (merge | squash | rebase)

    IF comment:
      ASK "What to comment on this PR?"
      add comment to PR

    IF request_reviewer:
      ASK "Who should review?" showing team members as choices
      request review from selected reviewer

    RECORD action in actions_taken
    REMOVE selected from prs
    IF prs not empty:
      GOTO PRESENT
    ELSE:
      GOTO SUMMARIZE

  SUMMARIZE:
    IF actions_taken not empty:
      SHOW actions_taken as table: [PR, action, result]

cooldown_minutes: 15
```

### issue-triage (complex)

```yaml
name: "issue-triage"
description: "Detect untriaged issues, suggest labels and milestones, apply with confirmation"
enabled: true
auto: false

trigger:
  type: session_poll
  source: issues
  condition: state_changed
  filter: {}

state:
  issues: []
  selected: null
  actions_taken: []

workflow: |
  GATHER:
    issues = list open issues without labels or milestones
    IF issues is empty: STOP "All issues are triaged"
    FOR EACH issue IN issues:
      issue.suggested_labels = INFER from title and body, matched against repo's existing labels
      issue.suggested_milestone = INFER from title, body, and open milestones
      issue.possible_duplicate = CHECK if title/body closely matches another open issue
    STORE issues

  PRESENT:
    SHOW issues as table: [title, author, age, suggested_labels, suggested_milestone, duplicate?]
    IF count(issues) > 1:
      ASK "Which issue to triage?" showing each as a choice, plus "skip all"
    ELSE:
      selected = issues[0]

  TRIAGE(selected):
    SHOW issue body and suggested triage

    IF selected.possible_duplicate:
      SHOW the potential duplicate issue
      ASK "Close as duplicate, keep both, or investigate?" (close_dup | keep | investigate)
      IF close_dup: close issue with "duplicate of #N" comment
      IF investigate: show both issues side by side for comparison
        ASK "Close as duplicate or keep both?" (close_dup | keep)

    IF NOT closed as duplicate:
      SHOW suggested labels: selected.suggested_labels
      ASK "Apply these labels, choose different ones, or skip?" (apply | choose | skip)
      IF apply: add suggested labels to issue
      IF choose: SHOW all available repo labels as choices, apply selected

      SHOW suggested milestone: selected.suggested_milestone
      ASK "Apply this milestone, choose different one, or skip?" (apply | choose | skip)
      IF apply: set milestone on issue
      IF choose: SHOW open milestones as choices, apply selected

      ASK "Assign this issue?" (assign | skip)
      IF assign: SHOW team members as choices, assign selected

    RECORD actions in actions_taken
    REMOVE selected from issues
    IF issues not empty:
      GOTO PRESENT
    ELSE:
      GOTO SUMMARIZE

  SUMMARIZE:
    SHOW actions_taken as table: [issue, labels_added, milestone, assignee]
    SHOW count of issues triaged vs skipped

cooldown_minutes: 30
```

### stale-check (complex)

```yaml
name: "stale-check"
description: "Find stale PRs and issues, prioritize by age, and offer actions"
enabled: true
auto: false

trigger:
  type: session_poll
  source: pull_requests
  condition: state_changed
  filter: {}

state:
  stale_prs: []
  stale_issues: []
  items: []
  selected: null
  actions_taken: []

workflow: |
  GATHER:
    stale_prs = list open PRs not updated in the last 7 days
    stale_issues = list open issues not updated in the last 14 days
    items = MERGE stale_prs and stale_issues
    IF items is empty: STOP "Nothing stale"
    FOR EACH item IN items:
      item.days_stale = calculate days since last update
      item.last_actor = who last commented or reviewed
      item.type = "PR" or "issue"
    SORT items by days_stale descending
    STORE items

  PRESENT:
    SHOW items as table: [type, title, days_stale, last_actor, status]
    IF count(items) > 1:
      ASK "Which item to address?" showing each as a choice, plus "skip all"
    ELSE:
      selected = items[0]

  ACT(selected):
    IF selected.type == "PR":
      ASK "Ping author, request review, close, or skip?" (ping | review | close | skip)
      IF ping: comment on PR asking for update
      IF review: request review from appropriate reviewer
      IF close: close PR with stale comment

    ELIF selected.type == "issue":
      ASK "Ping assignee, add stale label, close, or skip?" (ping | label | close | skip)
      IF ping: comment on issue asking for update
      IF label: add "stale" label to issue
      IF close: close issue with stale comment

    RECORD action in actions_taken
    REMOVE selected from items
    IF items not empty:
      GOTO PRESENT
    ELSE:
      GOTO SUMMARIZE

  SUMMARIZE:
    SHOW actions_taken as table: [type, item, action]
    SHOW count addressed vs skipped

cooldown_minutes: 60
```

### dependabot-alerts (complex)

```yaml
name: "dependabot-alerts"
description: "Surface security vulnerabilities, prioritize by severity, and offer remediation"
enabled: true
auto: false

trigger:
  type: session_poll
  source: dependabot
  condition: state_changed
  filter: {}

state:
  alerts: []
  selected: null
  actions_taken: []

workflow: |
  GATHER:
    alerts = list open dependabot alerts with severity, package, and ecosystem
    IF alerts is empty: STOP "No open Dependabot alerts"
    FOR EACH alert IN alerts:
      alert.has_patch = CHECK if a patched version is available
      alert.pr_exists = CHECK if dependabot has already opened a PR for this
      alert.breaking = INFER if upgrade is likely breaking (major version bump)
    SORT alerts by severity descending (critical > high > medium > low)
    STORE alerts

  PRESENT:
    SHOW alerts grouped by severity as table: [severity, package, ecosystem, has_patch, pr_exists]
    SHOW counts: critical, high, medium, low
    IF count(alerts) > 1:
      ASK "Which alert to address?" showing each as a choice, plus "skip all"
    ELSE:
      selected = alerts[0]

  INVESTIGATE(selected):
    SHOW vulnerability details: CVE, description, affected versions, patched version

    IF selected.pr_exists:
      SHOW existing dependabot PR details
      ASK "Review the PR, merge it, or skip?" (review | merge | skip)
      IF review: show PR diff and summarize changes
      IF merge: merge the dependabot PR

    ELIF selected.has_patch AND NOT selected.breaking:
      ASK "Open a PR to bump this dependency, dismiss alert, or skip?" (bump | dismiss | skip)
      IF bump: create branch and PR updating the dependency
      IF dismiss: dismiss alert with reason

    ELIF selected.has_patch AND selected.breaking:
      SHOW breaking change warning with major version diff
      ASK "Open a PR anyway, open an issue to track, dismiss, or skip?" (bump | issue | dismiss | skip)
      IF bump: create branch and PR with upgrade
      IF issue: create issue to track breaking upgrade
      IF dismiss: dismiss alert with reason

    ELIF NOT selected.has_patch:
      SHOW "No patched version available"
      ASK "Open an issue to track, dismiss as acceptable risk, or skip?" (issue | dismiss | skip)
      IF issue: create issue labeled "security" with vulnerability details
      IF dismiss: dismiss alert with "no fix available" reason

    RECORD action in actions_taken
    REMOVE selected from alerts
    IF alerts not empty:
      GOTO PRESENT
    ELSE:
      GOTO SUMMARIZE

  SUMMARIZE:
    SHOW actions_taken as table: [package, severity, action, result]
    SHOW remaining unaddressed alert count if any skipped

cooldown_minutes: 60
```

## Migration

The `actions[]` field is removed in all workflows. Simple workflows that were flat action lists become trivial pseudocode under `workflow:`. No changes to the heartbeat hook or skill are in scope — those will need to be updated separately to interpret the `workflow:` field.

## Out of Scope

- Changes to `heartbeat.sh` (SessionStart hook)
- Changes to `gh-heartbeat` skill (workflow executor)
- Changes to `workflow-execution.md` pattern
- Cross-workflow chaining
- Persistent state across sessions
