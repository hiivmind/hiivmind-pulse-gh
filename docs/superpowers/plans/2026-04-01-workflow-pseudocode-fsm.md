# Workflow Pseudocode FSM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace flat `actions[]` workflow YAMLs with pseudocode FSM workflows across all templates and deployed instances.

**Architecture:** Each workflow YAML gets its `actions:` block replaced with `state:` and `workflow:` fields. The pseudocode content comes directly from the design spec. Two directories are updated: `templates/workflows/` (canonical templates) and `.hiivmind/github/workflows/` (deployed instances).

**Tech Stack:** YAML files only — no code, no tests, no runtime changes.

**Key difference between directories:** The deployed `.hiivmind/github/workflows/` has user customizations that must be preserved:
- `auto-refresh.yaml`: `auto: true` (template has `auto: false`)
- `project-sync.yaml`: uses assignment-focused operation text
- `.hiivmind/github/workflows/` does NOT have `repo-healthcheck.yaml` (only in templates)

---

### Task 1: Update simple workflow templates

**Files:**
- Modify: `templates/workflows/auto-refresh.yaml`
- Modify: `templates/workflows/repo-healthcheck.yaml`

- [ ] **Step 1: Rewrite `auto-refresh.yaml` template**

Replace the full file content with:

```yaml
# hiivmind-pulse-gh - Auto-Refresh Workflow
# Triggers config refresh when sections become stale
# Copy to: .hiivmind/github/workflows/auto-refresh.yaml

name: "auto-refresh"
description: "Automatically refresh stale config sections on session start"
enabled: true
auto: false  # Set to true to refresh without asking

trigger:
  type: freshness
  condition: threshold_exceeded

state: {}

workflow: |
  EXECUTE:
    INVOKE skill hiivmind-pulse-gh:gh-refresh

cooldown_minutes: 60
```

- [ ] **Step 2: Rewrite `repo-healthcheck.yaml` template**

Replace the full file content with:

```yaml
# hiivmind-pulse-gh - Repository Healthcheck Workflow
# On-demand governance audit for repository maturity
# Copy to: .hiivmind/github/workflows/repo-healthcheck.yaml

name: "repo-healthcheck"
description: "Run governance healthcheck to assess repository maturity"
enabled: true
auto: false  # Must be explicitly requested — never runs automatically

trigger:
  type: on_demand
  condition: user_requested

state: {}

workflow: |
  EXECUTE:
    INVOKE skill hiivmind-pulse-gh:gh-healthcheck

cooldown_minutes: 10080  # 7 days
```

- [ ] **Step 3: Verify YAML validity**

Run: `yq '.' templates/workflows/auto-refresh.yaml && yq '.' templates/workflows/repo-healthcheck.yaml`
Expected: Both files parse without error, output shows `state` and `workflow` fields, no `actions` field.

- [ ] **Step 4: Commit**

```bash
git add templates/workflows/auto-refresh.yaml templates/workflows/repo-healthcheck.yaml
git commit -m "feat(workflows): migrate simple templates to v2 pseudocode format

Replace actions[] with state/workflow fields for auto-refresh
and repo-healthcheck templates."
```

---

### Task 2: Update medium workflow templates

**Files:**
- Modify: `templates/workflows/release-monitor.yaml`
- Modify: `templates/workflows/deploy-monitor.yaml`
- Modify: `templates/workflows/project-sync.yaml`

- [ ] **Step 1: Rewrite `release-monitor.yaml` template**

Replace the full file content with:

```yaml
# hiivmind-pulse-gh - Release Monitor Workflow
# Detects new releases and offers follow-up actions
# Copy to: .hiivmind/github/workflows/release-monitor.yaml

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

- [ ] **Step 2: Rewrite `deploy-monitor.yaml` template**

Replace the full file content with:

```yaml
# hiivmind-pulse-gh - Deploy Monitor Workflow
# Tracks deployment status and offers remediation for failures
# Copy to: .hiivmind/github/workflows/deploy-monitor.yaml

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

- [ ] **Step 3: Rewrite `project-sync.yaml` template**

Replace the full file content with:

```yaml
# hiivmind-pulse-gh - Project Sync Workflow
# Detects project board changes and offers status management
# Copy to: .hiivmind/github/workflows/project-sync.yaml
# Note: Requires default project set in config.yaml — skipped if unset

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

- [ ] **Step 4: Verify YAML validity**

Run: `yq '.' templates/workflows/release-monitor.yaml && yq '.' templates/workflows/deploy-monitor.yaml && yq '.' templates/workflows/project-sync.yaml`
Expected: All three parse without error, each shows `state` and `workflow` fields, no `actions` field.

- [ ] **Step 5: Commit**

```bash
git add templates/workflows/release-monitor.yaml templates/workflows/deploy-monitor.yaml templates/workflows/project-sync.yaml
git commit -m "feat(workflows): migrate medium templates to v2 pseudocode format

Replace actions[] with state/workflow FSM for release-monitor,
deploy-monitor, and project-sync templates."
```

---

### Task 3: Update complex workflow templates

**Files:**
- Modify: `templates/workflows/ci-monitor.yaml`
- Modify: `templates/workflows/pr-lifecycle.yaml`
- Modify: `templates/workflows/issue-triage.yaml`
- Modify: `templates/workflows/stale-check.yaml`
- Modify: `templates/workflows/dependabot-alerts.yaml`

- [ ] **Step 1: Rewrite `ci-monitor.yaml` template**

Replace the full file content with:

```yaml
# hiivmind-pulse-gh - CI Monitor Workflow
# Detects failed CI runs, classifies failures, and offers targeted remediation
# Copy to: .hiivmind/github/workflows/ci-monitor.yaml

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

- [ ] **Step 2: Rewrite `pr-lifecycle.yaml` template**

Replace the full file content with:

```yaml
# hiivmind-pulse-gh - PR Lifecycle Workflow
# Summarizes PR activity, triages by urgency, and offers review actions
# Copy to: .hiivmind/github/workflows/pr-lifecycle.yaml

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

- [ ] **Step 3: Rewrite `issue-triage.yaml` template**

Replace the full file content with:

```yaml
# hiivmind-pulse-gh - Issue Triage Workflow
# Detects untriaged issues, suggests labels and milestones, applies with confirmation
# Copy to: .hiivmind/github/workflows/issue-triage.yaml

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

- [ ] **Step 4: Rewrite `stale-check.yaml` template**

Replace the full file content with:

```yaml
# hiivmind-pulse-gh - Stale Check Workflow
# Finds stale PRs and issues, prioritizes by age, and offers actions
# Copy to: .hiivmind/github/workflows/stale-check.yaml

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

- [ ] **Step 5: Rewrite `dependabot-alerts.yaml` template**

Replace the full file content with:

```yaml
# hiivmind-pulse-gh - Dependabot Alerts Workflow
# Surfaces security vulnerabilities, prioritizes by severity, and offers remediation
# Copy to: .hiivmind/github/workflows/dependabot-alerts.yaml
# Note: Requires security_events scope — skipped gracefully if 403

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

- [ ] **Step 6: Verify YAML validity**

Run: `for f in templates/workflows/ci-monitor.yaml templates/workflows/pr-lifecycle.yaml templates/workflows/issue-triage.yaml templates/workflows/stale-check.yaml templates/workflows/dependabot-alerts.yaml; do echo "--- $f ---" && yq '.' "$f"; done`
Expected: All five parse without error, each shows `state` and `workflow` fields, no `actions` field.

- [ ] **Step 7: Commit**

```bash
git add templates/workflows/ci-monitor.yaml templates/workflows/pr-lifecycle.yaml templates/workflows/issue-triage.yaml templates/workflows/stale-check.yaml templates/workflows/dependabot-alerts.yaml
git commit -m "feat(workflows): migrate complex templates to v2 pseudocode format

Replace actions[] with state/workflow FSM for ci-monitor,
pr-lifecycle, issue-triage, stale-check, and dependabot-alerts."
```

---

### Task 4: Update deployed workflow instances

**Files:**
- Modify: `.hiivmind/github/workflows/auto-refresh.yaml`
- Modify: `.hiivmind/github/workflows/release-monitor.yaml`
- Modify: `.hiivmind/github/workflows/deploy-monitor.yaml`
- Modify: `.hiivmind/github/workflows/project-sync.yaml`
- Modify: `.hiivmind/github/workflows/ci-monitor.yaml`
- Modify: `.hiivmind/github/workflows/pr-lifecycle.yaml`
- Modify: `.hiivmind/github/workflows/issue-triage.yaml`
- Modify: `.hiivmind/github/workflows/stale-check.yaml`
- Modify: `.hiivmind/github/workflows/dependabot-alerts.yaml`

**Important:** The deployed `auto-refresh.yaml` has `auto: true` — preserve this customization.

- [ ] **Step 1: Rewrite deployed `auto-refresh.yaml`**

Same as template but with `auto: true`:

```yaml
# hiivmind-pulse-gh - Auto-Refresh Workflow
# Triggers config refresh when sections become stale
# Copy to: .hiivmind/github/workflows/auto-refresh.yaml

name: "auto-refresh"
description: "Automatically refresh stale config sections on session start"
enabled: true
auto: true  # Set to true to refresh without asking

trigger:
  type: freshness
  condition: threshold_exceeded

state: {}

workflow: |
  EXECUTE:
    INVOKE skill hiivmind-pulse-gh:gh-refresh

cooldown_minutes: 60
```

- [ ] **Step 2: Copy remaining 8 templates to deployed directory**

Copy each template file to `.hiivmind/github/workflows/`, overwriting the v1 versions:

```bash
for f in release-monitor deploy-monitor project-sync ci-monitor pr-lifecycle issue-triage stale-check dependabot-alerts; do
  cp templates/workflows/${f}.yaml .hiivmind/github/workflows/${f}.yaml
done
```

- [ ] **Step 3: Verify YAML validity for all deployed workflows**

Run: `for f in .hiivmind/github/workflows/*.yaml; do echo "--- $f ---" && yq '.workflow' "$f" | head -3; done`
Expected: All 9 files show the first 3 lines of their `workflow:` field. No file shows an `actions` field.

- [ ] **Step 4: Verify `auto-refresh.yaml` customization preserved**

Run: `yq '.auto' .hiivmind/github/workflows/auto-refresh.yaml`
Expected: `true`

- [ ] **Step 5: Commit**

```bash
git add .hiivmind/github/workflows/
git commit -m "feat(workflows): migrate deployed instances to v2 pseudocode format

Update all 9 deployed workflow YAMLs to v2 format.
Preserves auto: true customization on auto-refresh."
```

---

### Task 5: Final verification

- [ ] **Step 1: Verify no `actions:` fields remain in any workflow**

Run: `grep -r "^actions:" templates/workflows/ .hiivmind/github/workflows/ || echo "PASS: no actions: fields found"`
Expected: `PASS: no actions: fields found`

- [ ] **Step 2: Verify all workflows have `workflow:` field**

Run: `for f in templates/workflows/*.yaml .hiivmind/github/workflows/*.yaml; do echo -n "$f: " && yq 'has("workflow")' "$f"; done`
Expected: Every file outputs `true`.

- [ ] **Step 3: Verify all workflows have `state:` field**

Run: `for f in templates/workflows/*.yaml .hiivmind/github/workflows/*.yaml; do echo -n "$f: " && yq 'has("state")' "$f"; done`
Expected: Every file outputs `true`.

- [ ] **Step 4: Count files**

Run: `echo "Templates: $(ls templates/workflows/*.yaml | wc -l)" && echo "Deployed: $(ls .hiivmind/github/workflows/*.yaml | wc -l)"`
Expected: `Templates: 10`, `Deployed: 9` (repo-healthcheck is template-only).
