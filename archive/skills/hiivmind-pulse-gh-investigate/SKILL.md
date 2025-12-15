---
name: hiivmind-pulse-gh-investigate
description: >
  Deep-dive investigation of GitHub entities. Starting from an issue, PR, or project item,
  traverse all relationships to build full context: linked issues, pull requests, comments,
  reviewers, commits, and participants. Use when you need to understand the complete picture
  of a work item, prepare for standups, or audit who touched what. Returns rich context
  but does NOT cache (data too volatile). Answers: "What's the full story on issue #42?"
---

# GitHub Entity Investigator

Deep-dive investigation tool that traverses GitHub entity relationships to build complete context.

## Prerequisites

**Required setup (run once):**
1. `hiivmind-pulse-gh-user-init` - Validates environment, creates `user.yaml`
2. `hiivmind-pulse-gh-workspace-init` - Discovers projects/repos, creates `config.yaml`

**Note:** This skill can work without workspace config (explicit params required), but config simplifies commands by providing cached org/repo context.

## Quick Start

```bash
# Source functions (once per session)
source lib/github/gh-investigate-functions.sh

# Quick issue summary
get_issue_summary "owner" "repo" 42

# Full issue analysis
analyze_issue "owner" "repo" 42

# Full PR analysis
analyze_pr "owner" "repo" 87
```

## Function Reference

### Issue Analysis

| Function | Purpose | Example |
|----------|---------|---------|
| `get_issue_summary OWNER REPO NUM` | Quick one-line overview | `get_issue_summary "acme" "api" 42` |
| `analyze_issue OWNER REPO NUM [DEPTH]` | Full analysis | `analyze_issue "acme" "api" 42 standard` |
| `fetch_issue OWNER REPO NUM` | Raw JSON data | `fetch_issue "acme" "api" 42 \| jq .` |

### PR Analysis

| Function | Purpose | Example |
|----------|---------|---------|
| `get_pr_summary OWNER REPO NUM` | Quick one-line overview | `get_pr_summary "acme" "api" 87` |
| `analyze_pr OWNER REPO NUM [DEPTH]` | Full analysis | `analyze_pr "acme" "api" 87 deep` |
| `fetch_pr OWNER REPO NUM` | Raw JSON data | `fetch_pr "acme" "api" 87 \| jq .` |

### Relationship Discovery

| Function | Purpose | Example |
|----------|---------|---------|
| `find_closing_prs OWNER REPO NUM` | Find PRs that close an issue | `find_closing_prs "acme" "api" 42` |
| `find_issue_participants OWNER REPO NUM` | List all users on issue | `find_issue_participants "acme" "api" 42` |
| `find_pr_participants OWNER REPO NUM` | List all users on PR | `find_pr_participants "acme" "api" 87` |

### Activity & Timeline

| Function | Purpose | Example |
|----------|---------|---------|
| `get_issue_activity OWNER REPO NUM [LIMIT]` | Recent activity | `get_issue_activity "acme" "api" 42 10` |

### Batch Operations

| Function | Purpose | Example |
|----------|---------|---------|
| `batch_issue_summary OWNER REPO NUMS...` | Multiple issue summaries | `batch_issue_summary "acme" "api" 1 2 3` |
| `batch_pr_summary OWNER REPO NUMS...` | Multiple PR summaries | `batch_pr_summary "acme" "api" 10 11 12` |

## Analysis Depths

| Depth | Data Retrieved | Use Case |
|-------|----------------|----------|
| `shallow` | Title, state, author, assignees | Quick status check |
| `standard` | + comments, labels, milestone, project status | Normal investigation |
| `deep` | + linked PRs, commits, reviews, all participants | Full audit trail |

## Example Workflows

### Quick Status Check

```bash
source lib/github/gh-investigate-functions.sh

get_issue_summary "hiivmind" "hiivmind-pulse-gh" 1
# Issue #1: User init skill required
# State: OPEN | Author: @discreteds | Assignees: none
# Labels: none | Milestone: none
# Updated: 2025-12-08T20:36:05Z
```

### Full Issue Investigation

```bash
source lib/github/gh-investigate-functions.sh

analyze_issue "hiivmind" "hiivmind-pulse-gh" 1
# === Issue #1 Analysis ===
#
# Title: User init skill required
# URL: https://github.com/hiivmind/hiivmind-pulse-gh/issues/1
# State: OPEN (N/A)
# Created: 2025-12-08T20:36:05Z
# Updated: 2025-12-08T20:36:05Z
#
# --- Attribution ---
# Author: @discreteds
# Assignees: none
#
# --- Labels ---
#
# --- Project Board ---
# Project: Hiivmind Pulse Bug Tracker (#1)
#   Status: To triage
#
# --- Comments (0) ---
#
# === End Analysis ===
```

### PR Analysis with Reviews

```bash
source lib/github/gh-investigate-functions.sh

analyze_pr "owner" "repo" 87
# === PR #87 Analysis ===
#
# Title: Add retry logic for auth timeouts
# URL: https://github.com/owner/repo/pull/87
# State: OPEN (draft)
# ...
#
# --- Reviews ---
# Requested: @reviewer1, @reviewer2
#   @reviewer1: APPROVED
#
# --- Commits (3) ---
#   abc1234 Initial implementation
#   def5678 Add tests
#   ghi9012 Fix edge case
#
# --- CI Status ---
# Overall: SUCCESS
#
# --- Closes Issues ---
#   #42: Fix authentication timeout (OPEN)
```

### Find Who's Involved

```bash
source lib/github/gh-investigate-functions.sh

find_issue_participants "owner" "repo" 42
# alice
# bob
# carol

find_pr_participants "owner" "repo" 87
# alice
# bob
# reviewer1
```

### Batch Analysis for Standup

```bash
source lib/github/gh-investigate-functions.sh

# Quickly check multiple items
batch_issue_summary "owner" "repo" 42 43 44
# Issue #42: Fix authentication timeout
# State: OPEN | Author: @alice | Assignees: @bob
# ...
# ---
# Issue #43: Add retry logic
# ...
```

## Output Structure

### Issue Analysis Output

```yaml
entity:
  type: issue
  number: 42
  title: "Fix authentication timeout"
  url: https://github.com/owner/repo/issues/42
  state: open
  created: 2025-12-01T10:00:00Z
  updated: 2025-12-08T14:30:00Z

attribution:
  author: "@alice"
  assignees: ["@alice", "@bob"]

labels:
  - bug
  - priority:high

milestone:
  title: "v2.1.0"
  due: 2025-01-15
  state: OPEN

project:
  name: "Product Roadmap"
  status: "In Progress"

comments:
  count: 5
  participants: ["@alice", "@bob", "@carol"]
```

## Key Principles

1. **No caching** - Entity data changes rapidly; always fetch fresh
2. **Relationship traversal** - Follow links between entities
3. **Rich context** - Return everything needed to understand/act
4. **Starting point agnostic** - Can start from issue, PR, or project item

## Entity Relationship Map

```
                              ┌─────────────┐
                              │   Project   │
                              │    Item     │
                              └──────┬──────┘
                                     │ links to
                              ┌──────▼──────┐
                         ┌────┤    Issue    ├────┐
                         │    └──────┬──────┘    │
                    mentions         │         linked to
                         │           │           │
              ┌──────────▼───┐ ┌─────▼─────┐ ┌───▼──────────┐
              │    Issues    │ │  Comments │ │     PRs      │
              │  (related)   │ │           │ │  (closing)   │
              └──────────────┘ └─────┬─────┘ └───┬──────────┘
                                     │           │
                              ┌──────▼───┐ ┌─────▼─────┐
                              │  Authors │ │  Commits  │
                              │          │ │  Reviews  │
                              └──────────┘ └───────────┘
```

## Reference

- Functions library: `lib/github/gh-investigate-functions.sh`
- Projects operations: `skills/hiivmind-pulse-gh-projects/SKILL.md`
- Workspace refresh: `skills/hiivmind-pulse-gh-workspace-refresh/SKILL.md`
