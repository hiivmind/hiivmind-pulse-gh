# Activity Reporting Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create three new on-demand activity reporting workflow templates using the v2 pseudocode FSM format with the new `params:` extension.

**Architecture:** Three new YAML files in `templates/workflows/`. No deployed instances yet — these are templates only. No runtime changes.

**Tech Stack:** YAML files only.

---

### Task 1: Create commit-summary workflow template

**Files:**
- Create: `templates/workflows/commit-summary.yaml`

- [ ] **Step 1: Write `commit-summary.yaml`**

Create the file with this exact content:

```yaml
# hiivmind-pulse-gh - Commit Summary Workflow
# On-demand summary of commit activity with flexible filtering
# Copy to: .hiivmind/github/workflows/commit-summary.yaml

name: "commit-summary"
description: "Summarize commit activity by time range, branch, or author"
enabled: true
auto: false

trigger:
  type: on_demand
  condition: user_requested

params:
  scope:
    description: "Time range or commit range to summarize"
    type: string
    default: "since last session"
    examples: ["last 3 days", "last 24 hours", "since v4.1.0", "since abc1234"]
  branch:
    description: "Branch to scope to, or 'all' for all branches"
    type: string
    default: "current"
    examples: ["main", "all", "feature/auth"]
  author:
    description: "Filter to a specific git author"
    type: string
    default: null

state:
  commits: []
  selected: null
  scope_description: null

workflow: |
  RESOLVE:
    scope_description = human-readable description of params.scope, params.branch, params.author
    SHOW "Gathering commits: {scope_description}"

  GATHER:
    IF params.branch == "all":
      commits = git log across all branches for params.scope
    ELIF params.branch == "current":
      commits = git log on current branch for params.scope
    ELSE:
      commits = git log on params.branch for params.scope

    IF params.author:
      commits = FILTER commits WHERE author matches params.author

    IF commits is empty: STOP "No commits found for {scope_description}"

    FOR EACH commit IN commits:
      commit.files_changed = count of files changed
      commit.insertions = lines added
      commit.deletions = lines removed
      commit.category = INFER from message and files (feature | fix | refactor | docs | chore | test)
    STORE commits

  PRESENT:
    SHOW summary stats: total commits, authors, date range
    SHOW commits grouped by category as table: [hash, author, message, files_changed, +/-, date]
    IF multiple authors:
      SHOW breakdown by author: [author, commit_count, lines_changed]
    IF params.branch == "all" AND multiple branches:
      SHOW breakdown by branch: [branch, commit_count]

    ASK "Investigate a specific commit, view diff stats, change filters, or done?" (investigate | diff_stats | refilter | done)

    IF investigate:
      ASK "Which commit?" showing recent commits as choices
      SHOW full commit details: message, diff summary, files changed
      ASK "View full diff, open in browser, or back to summary?" (diff | browser | back)
      IF diff: show full diff for selected commit
      IF browser: open commit on GitHub
      GOTO PRESENT

    IF diff_stats:
      SHOW aggregated diff stats: files most frequently changed, hotspots, total lines
      GOTO PRESENT

    IF refilter:
      ASK "New scope?" then update params.scope
      GOTO GATHER

cooldown_minutes: 0
```

- [ ] **Step 2: Verify YAML validity**

Run: `yq '.' templates/workflows/commit-summary.yaml`
Expected: Parses without error, shows `params`, `state`, and `workflow` fields.

- [ ] **Step 3: Commit**

```bash
git add templates/workflows/commit-summary.yaml
git commit -m "feat(workflows): add commit-summary on-demand workflow template

New v2 workflow with params for scope, branch, and author filtering.
Introduces params: extension for parameterized workflows."
```

---

### Task 2: Create user-activity workflow template

**Files:**
- Create: `templates/workflows/user-activity.yaml`

- [ ] **Step 1: Write `user-activity.yaml`**

Create the file with this exact content:

```yaml
# hiivmind-pulse-gh - User Activity Workflow
# On-demand summary of a user's activity across commits, PRs, issues, and reviews
# Copy to: .hiivmind/github/workflows/user-activity.yaml

name: "user-activity"
description: "Summarize a user's activity across commits, PRs, issues, and reviews"
enabled: true
auto: false

trigger:
  type: on_demand
  condition: user_requested

params:
  user:
    description: "GitHub username to report on"
    type: string
    default: null
    examples: ["octocat", "nathanielramm"]
  scope:
    description: "Time range to summarize"
    type: string
    default: "last 7 days"
    examples: ["last 3 days", "last 24 hours", "last month", "since 2026-03-01"]

state:
  commits: []
  prs: []
  issues: []
  reviews: []
  comments: []
  selected: null

workflow: |
  RESOLVE:
    IF params.user is null:
      params.user = current authenticated GitHub user
    SHOW "Gathering activity for @{params.user} ({params.scope})"

  GATHER:
    commits = git log filtered to params.user for params.scope
    prs = list PRs authored by params.user within params.scope (open and merged)
    issues = list issues authored by params.user within params.scope (open and closed)
    reviews = list PR reviews submitted by params.user within params.scope
    comments = list issue and PR comments by params.user within params.scope

    IF all empty: STOP "No activity found for @{params.user} in {params.scope}"

    FOR EACH pr IN prs:
      pr.status = INFER (open | merged | closed)
      pr.review_state = summarize review status
    FOR EACH issue IN issues:
      issue.status = open or closed

  PRESENT:
    SHOW activity summary header: user, date range, avatar
    SHOW stats bar: [commits, PRs, issues, reviews, comments]

    IF commits not empty:
      SHOW "Commits ({count}):" as table: [hash, message, files_changed, date]
    IF prs not empty:
      SHOW "Pull Requests ({count}):" as table: [title, status, reviews, date]
    IF issues not empty:
      SHOW "Issues ({count}):" as table: [title, status, labels, date]
    IF reviews not empty:
      SHOW "Reviews Given ({count}):" as table: [PR title, verdict, date]
    IF comments not empty:
      SHOW "Comments ({count}):" as table: [target, excerpt, date]

    ASK "Drill into a section, change time range, or done?" (commits | prs | issues | reviews | comments | refilter | done)

    IF commits:
      SHOW detailed commit list with diff stats
      ASK "Investigate a commit or back?" showing commits as choices, plus "back"
      IF selected: SHOW full commit details and diff summary
      GOTO PRESENT

    IF prs:
      SHOW detailed PR list with diffs and review status
      ASK "Investigate a PR or back?" showing PRs as choices, plus "back"
      IF selected: SHOW PR diff summary, reviewers, CI status
      GOTO PRESENT

    IF issues:
      SHOW detailed issue list with bodies
      ASK "Investigate an issue or back?" showing issues as choices, plus "back"
      IF selected: SHOW issue body, comments, labels, milestone
      GOTO PRESENT

    IF reviews:
      SHOW detailed review list with comments
      GOTO PRESENT

    IF comments:
      SHOW full comment bodies with context
      GOTO PRESENT

    IF refilter:
      ASK "New time range?" then update params.scope
      GOTO GATHER

cooldown_minutes: 0
```

- [ ] **Step 2: Verify YAML validity**

Run: `yq '.' templates/workflows/user-activity.yaml`
Expected: Parses without error, shows `params`, `state`, and `workflow` fields.

- [ ] **Step 3: Commit**

```bash
git add templates/workflows/user-activity.yaml
git commit -m "feat(workflows): add user-activity on-demand workflow template

Summarizes a user's commits, PRs, issues, reviews, and comments
with configurable time range."
```

---

### Task 3: Create community-activity workflow template

**Files:**
- Create: `templates/workflows/community-activity.yaml`

- [ ] **Step 1: Write `community-activity.yaml`**

Create the file with this exact content:

```yaml
# hiivmind-pulse-gh - Community Activity Workflow
# On-demand summary of repo-wide activity across issues, PRs, comments, and discussions
# Copy to: .hiivmind/github/workflows/community-activity.yaml

name: "community-activity"
description: "Summarize repo-wide activity across issues, PRs, comments, and discussions"
enabled: true
auto: false

trigger:
  type: on_demand
  condition: user_requested

params:
  scope:
    description: "Time range to summarize"
    type: string
    default: "last 7 days"
    examples: ["last 3 days", "last 24 hours", "last month", "since 2026-03-01"]
  focus:
    description: "Activity type to focus on, or 'all' for everything"
    type: string
    default: "all"
    examples: ["issues", "prs", "comments", "discussions", "all"]

state:
  new_issues: []
  closed_issues: []
  new_prs: []
  merged_prs: []
  issue_comments: []
  pr_comments: []
  discussions: []
  selected: null
  contributors: []

workflow: |
  RESOLVE:
    SHOW "Gathering community activity ({params.scope}, focus: {params.focus})"

  GATHER:
    IF params.focus == "all" OR params.focus == "issues":
      new_issues = list issues created within params.scope
      closed_issues = list issues closed within params.scope

    IF params.focus == "all" OR params.focus == "prs":
      new_prs = list PRs opened within params.scope
      merged_prs = list PRs merged within params.scope

    IF params.focus == "all" OR params.focus == "comments":
      issue_comments = list issue comments within params.scope
      pr_comments = list PR review comments within params.scope

    IF params.focus == "all" OR params.focus == "discussions":
      discussions = list discussion activity within params.scope

    IF all empty: STOP "No community activity found in {params.scope}"

    contributors = EXTRACT unique users across all activity
    FOR EACH contributor IN contributors:
      contributor.actions = count of their activities across all categories

  PRESENT:
    SHOW activity summary header: repo, date range
    SHOW stats bar: [new_issues, closed_issues, new_prs, merged_prs, comments, discussions]
    SHOW top contributors: [user, action_count] (top 5 by activity)

    IF new_issues not empty:
      SHOW "New Issues ({count}):" as table: [title, author, labels, date]
    IF closed_issues not empty:
      SHOW "Closed Issues ({count}):" as table: [title, closed_by, resolution, date]
    IF new_prs not empty:
      SHOW "New PRs ({count}):" as table: [title, author, diff_size, date]
    IF merged_prs not empty:
      SHOW "Merged PRs ({count}):" as table: [title, author, reviewers, date]
    IF issue_comments not empty OR pr_comments not empty:
      SHOW "Comments ({count}):" as table: [target, author, excerpt, date]
    IF discussions not empty:
      SHOW "Discussions ({count}):" as table: [title, author, replies, date]

    ASK "Drill into a section, view a contributor's activity, change filters, or done?" (issues | prs | comments | discussions | contributor | refilter | done)

    IF issues:
      SHOW all issues (new + closed) with bodies
      ASK "Investigate an issue or back?" showing issues as choices, plus "back"
      IF selected: SHOW issue body, comments, timeline
      GOTO PRESENT

    IF prs:
      SHOW all PRs (new + merged) with summaries
      ASK "Investigate a PR or back?" showing PRs as choices, plus "back"
      IF selected: SHOW PR diff summary, review comments, CI status
      GOTO PRESENT

    IF comments:
      SHOW all comments with full context
      GOTO PRESENT

    IF discussions:
      SHOW discussion threads with replies
      ASK "Investigate a discussion or back?" showing discussions as choices, plus "back"
      IF selected: SHOW full discussion thread
      GOTO PRESENT

    IF contributor:
      ASK "Which contributor?" showing contributors as choices
      SHOW selected contributor's full activity breakdown
      ASK "Switch to user-activity workflow for deeper analysis?" (yes | no)
      IF yes: INVOKE workflow user-activity WITH user=selected, scope=params.scope
      GOTO PRESENT

    IF refilter:
      ASK "New time range or focus?" then update params
      GOTO GATHER

cooldown_minutes: 0
```

- [ ] **Step 2: Verify YAML validity**

Run: `yq '.' templates/workflows/community-activity.yaml`
Expected: Parses without error, shows `params`, `state`, and `workflow` fields.

- [ ] **Step 3: Commit**

```bash
git add templates/workflows/community-activity.yaml
git commit -m "feat(workflows): add community-activity on-demand workflow template

Summarizes repo-wide activity across issues, PRs, comments,
and discussions with cross-workflow handoff to user-activity."
```

---

### Task 4: Final verification

- [ ] **Step 1: Verify all three new files exist and parse**

Run: `for f in templates/workflows/commit-summary.yaml templates/workflows/user-activity.yaml templates/workflows/community-activity.yaml; do echo -n "$f: " && yq 'has("params")' "$f"; done`
Expected: All three output `true`.

- [ ] **Step 2: Verify total template count**

Run: `echo "Templates: $(ls templates/workflows/*.yaml | wc -l)"`
Expected: `Templates: 13` (10 existing + 3 new).

- [ ] **Step 3: List all workflow names**

Run: `for f in templates/workflows/*.yaml; do yq '.name' "$f"; done | sort`
Expected: 13 workflow names in alphabetical order.
