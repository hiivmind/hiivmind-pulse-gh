# Architecture Principles & Design Patterns

> **Document ID:** ARCH-001
> **Created:** 2025-12-10
> **Status:** Canonical Reference

This document establishes the foundational principles for building composable GitHub API tooling. These patterns apply across all domains: Projects, Issues, PRs, Repositories, Milestones, Branch Protection, Actions, and beyond.

---

## Core Philosophy

**Build a complete, composable CRUD system where workflows are composed from predefined primitives. We never guess - every operation uses a known, tested primitive.**

---

## 1. Interaction Priority Chain

When implementing any GitHub operation, follow this priority order:

```
┌─────────────────────────────────────────────────────────────┐
│  PRIORITY 1: Native gh CLI Commands                         │
│  gh issue create, gh pr list, gh project item-add          │
│  Use when: CLI has direct support for the operation         │
│  Why: Battle-tested, handles auth, pagination, errors       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ if not available
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PRIORITY 2: gh api graphql                                 │
│  gh api graphql -f query='...'                             │
│  Use when: Complex queries, relationships, ProjectsV2      │
│  Why: Full API power, single request for related data       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ if not available
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PRIORITY 3: gh api (REST)                                  │
│  gh api /repos/{owner}/{repo}/milestones                   │
│  Use when: Mutations not in GraphQL, legacy endpoints      │
│  Why: Some operations only available via REST               │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ if unclear/undocumented
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PRIORITY 4: Research via github-navigate Skill            │
│  Consult GitHub docs corpus, then construct using config   │
│  Use when: New API features, unclear behavior              │
│  Why: Always current, authoritative source                  │
└─────────────────────────────────────────────────────────────┘
```

### Priority 1: Native gh CLI

The `gh` CLI should be the first choice. It handles:
- Authentication and token management
- Pagination automatically
- Error handling and retries
- Output formatting (--json, --jq)

```bash
# PREFERRED: Native CLI commands
gh issue list -R owner/repo --state open --json number,title
gh pr create --title "Feature" --body "Description"
gh project item-add 2 --owner hiivmind --url "$ISSUE_URL"
gh release create v1.0.0 --notes "Release notes"
```

### Priority 2: GraphQL via gh api

Use GraphQL when:
- CLI doesn't support the operation
- You need related data in a single request
- Working with ProjectsV2 (complex field structures)
- Need precise control over returned fields

```bash
# GraphQL for complex queries
gh api graphql -H X-Github-Next-Global-ID:1 \
    -f query='query($org: String!) {
        organization(login: $org) {
            projectsV2(first: 20) {
                nodes { id number title }
            }
        }
    }' \
    -f org="hiivmind"
```

### Priority 3: REST via gh api

Use REST when:
- GraphQL doesn't support the mutation
- Working with legacy features
- Specific REST-only endpoints (webhooks, some admin operations)

```bash
# REST for operations not in GraphQL
gh api repos/owner/repo/milestones \
    -f title="v1.0" \
    -f due_on="2025-01-01T00:00:00Z"
```

### Priority 4: Research & Construct

When the operation is unclear:
1. Use `github-navigate` skill to consult documentation
2. Check `.hiivmind/github/config.yaml` for cached IDs
3. Construct the appropriate command using known patterns

---

## 2. The Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 3: SKILLS                          │
│  Workflow orchestration via SKILL.md instructions           │
│  Composes primitives using pipe patterns                    │
│  Human-readable, goal-oriented                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ composes
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  LAYER 2: FUNCTIONS                         │
│  Shell functions in lib/github/gh-{domain}-functions.sh    │
│  Single-responsibility, stdin→stdout                        │
│  Uses Priority Chain internally                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ references
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  LAYER 1: TEMPLATES                         │
│  GraphQL queries: gh-{domain}-graphql-queries.yaml         │
│  jq filters: gh-{domain}-jq-filters.yaml                   │
│  Index docs: gh-{domain}-index.md                          │
└─────────────────────────────────────────────────────────────┘
```

### Layer 1: Templates & Documentation

**Templates (YAML)**
- Externalized, versionable, testable query/filter definitions
- GraphQL queries with parameters and extraction paths
- jq filters for data transformation
- No logic, only data

**Index Documentation (Markdown)**
- `gh-{domain}-index.md` for each domain
- Documents every function and filter
- Includes examples and composition patterns
- Single source of truth for available primitives

### Layer 2: Functions

- Thin wrappers that select appropriate interaction method
- Follow Priority Chain internally
- Single responsibility, composable via pipes
- Located in `lib/github/gh-{domain}-functions.sh`

### Layer 3: Skills

- Human-readable workflows in SKILL.md
- Compose primitives - no new logic
- Reference index.md for available operations
- Located in `skills/{skill-name}/SKILL.md`

---

## 3. File Organization

### 3.1 Directory Structure

```
lib/github/
├── index.md                           # Master index of all domains
├── gh-{domain}-functions.sh           # Shell function primitives
├── gh-{domain}-graphql-queries.yaml   # GraphQL query templates
├── gh-{domain}-jq-filters.yaml        # jq filter templates
└── gh-{domain}-index.md               # Domain-specific function index
```

### 3.2 Domain Coverage

| Domain | Functions | Queries | Filters | Index |
|--------|-----------|---------|---------|-------|
| Projects | `gh-project-functions.sh` | `gh-project-graphql-queries.yaml` | `gh-project-jq-filters.yaml` | `gh-project-index.md` |
| Issues | `gh-issue-functions.sh` | `gh-issue-graphql-queries.yaml` | `gh-issue-jq-filters.yaml` | `gh-issue-index.md` |
| Repositories | `gh-repo-functions.sh` | `gh-repo-graphql-queries.yaml` | `gh-repo-jq-filters.yaml` | `gh-repo-index.md` |
| Identity | `gh-identity-functions.sh` | `gh-identity-graphql-queries.yaml` | - | `gh-identity-index.md` |
| Milestones | `gh-milestone-functions.sh` | (shared) | `gh-milestone-jq-filters.yaml` | `gh-milestone-index.md` |

---

## 4. Index Documentation Standard

Each domain must have an `index.md` documenting all available primitives.

### 4.1 Index File Structure

```markdown
# {Domain} Functions Index

> Auto-generated from gh-{domain}-functions.sh
> Last updated: {date}

## Quick Reference

| Function | Type | Description |
|----------|------|-------------|
| `discover_org_projects` | FETCH | List projects for an organization |
| `filter_open` | FILTER | Keep only open items |
| ...

## Functions

### FETCH Primitives

#### `discover_org_projects`
List all projects for an organization.

**Args:**
- `org_login` - Organization login name

**Output:** JSON array of projects

**Example:**
\`\`\`bash
discover_org_projects "hiivmind"
\`\`\`

**Composition:**
\`\`\`bash
discover_org_projects "hiivmind" | filter_open | format_projects
\`\`\`

---

### FILTER Primitives

#### `filter_open`
Keep only open items from a JSON array.

**Input:** JSON array from stdin
**Output:** Filtered JSON array

**Example:**
\`\`\`bash
echo "$DATA" | filter_open
\`\`\`

---

## jq Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `.filters.open_only` | Keep open items | `jq 'map(select(.closed == false))'` |

## GraphQL Queries

| Query | Category | Parameters |
|-------|----------|------------|
| `discovery.org_projects` | Discovery | orgLogin: String! |

## Composition Examples

### List open organization projects
\`\`\`bash
discover_org_projects "hiivmind" | filter_open | format_projects
\`\`\`

### Get project field structure
\`\`\`bash
fetch_org_project_fields 2 "hiivmind" | extract_field_ids
\`\`\`
```

### 4.2 Master Index

`lib/github/index.md` aggregates all domains:

```markdown
# GitHub Functions Library Index

## Domains

| Domain | Functions | Description |
|--------|-----------|-------------|
| [Projects](gh-project-index.md) | 24 | ProjectsV2 CRUD, fields, items, views |
| [Issues](gh-issue-index.md) | 12 | Issue CRUD, labels, assignees |
| [Repositories](gh-repo-index.md) | 8 | Repository discovery and metadata |
| [Identity](gh-identity-index.md) | 6 | User/org detection and lookup |
| [Milestones](gh-milestone-index.md) | 8 | Milestone CRUD operations |

## Function Types

- **FETCH** - Retrieve data (`discover_*`, `fetch_*`)
- **LOOKUP** - Resolve IDs (`get_*_id`)
- **FILTER** - Transform data (`filter_*`, `apply_*_filter`)
- **EXTRACT** - Pull specific fields (`extract_*`)
- **FORMAT** - Human-readable output (`format_*`)
- **MUTATE** - Create/update/delete (`create_*`, `update_*`, `delete_*`)
- **DETECT** - Determine types (`detect_*`)

## Interaction Priority

1. Native `gh` CLI commands
2. `gh api graphql` for complex queries
3. `gh api` REST for mutations not in GraphQL
4. Research via `github-navigate` skill
```

---

## 5. Primitive Classification

Every primitive falls into exactly one category:

### 5.1 FETCH Primitives
**Purpose:** Retrieve data from GitHub API
**Pattern:** `fetch_{scope}_{entity}` or `discover_{scope}_{entities}`
**Output:** JSON to stdout
**Input:** Arguments only (no stdin)

```bash
fetch_viewer                          # Current user
fetch_organization "hiivmind"         # Specific org
discover_org_projects "hiivmind"      # List org's projects
fetch_org_project 2 "hiivmind"        # Specific project with items
```

### 5.2 LOOKUP Primitives
**Purpose:** Resolve identifiers (number→ID, name→ID)
**Pattern:** `get_{entity}_id`
**Output:** Single value (ID string) to stdout
**Input:** Arguments only

```bash
get_user_id                           # Viewer's node ID
get_org_id "hiivmind"                 # Org's node ID
get_org_project_id 2 "hiivmind"       # Project's node ID
```

### 5.3 FILTER Primitives
**Purpose:** Transform/filter JSON data
**Pattern:** `filter_{criteria}` or `apply_{criteria}_filter`
**Output:** Filtered JSON to stdout
**Input:** JSON from stdin

```bash
echo "$DATA" | filter_open              # Keep only open items
echo "$DATA" | filter_by_assignee "bob" # Filter by assignee
```

### 5.4 EXTRACT Primitives
**Purpose:** Pull specific data out of JSON structures
**Pattern:** `extract_{what}`
**Output:** Extracted data (JSON or text) to stdout
**Input:** JSON from stdin

```bash
echo "$DATA" | extract_repositories     # Get unique repos
echo "$DATA" | extract_field_ids        # Get field ID mappings
```

### 5.5 FORMAT Primitives
**Purpose:** Transform JSON to human-readable output
**Pattern:** `format_{entity}` or `format_{entity}_list`
**Output:** Formatted text to stdout
**Input:** JSON from stdin

```bash
echo "$DATA" | format_projects          # Tabular project list
echo "$DATA" | format_issues            # Issue summary
```

### 5.6 MUTATE Primitives
**Purpose:** Create, update, or delete entities
**Pattern:** `create_{entity}`, `update_{entity}`, `delete_{entity}`, `set_{property}`
**Output:** Result JSON to stdout
**Input:** Arguments only (entity IDs, values)

```bash
create_issue "hiivmind" "repo" "Title" "Body"
set_issue_milestone "$issue_id" "$milestone_id"
add_item_to_project "$project_id" "$issue_id"
```

### 5.7 DETECT Primitives
**Purpose:** Determine type/state of an entity
**Pattern:** `detect_{what}`
**Output:** Type string to stdout
**Input:** Arguments only

```bash
detect_owner_type "hiivmind"            # → "organization" or "user"
detect_default_branch "owner" "repo"    # → "main" or "master"
```

---

## 6. Naming Conventions

### 6.1 Scope Prefixes

Always specify the scope explicitly. Never create "dual-mode" functions.

| Scope | Meaning | Example |
|-------|---------|---------|
| `viewer_` | Authenticated user (implicit) | `fetch_viewer` |
| `user_` | Specific user by login | `fetch_user_repositories "bob"` |
| `org_` | Organization by login | `fetch_org_projects "hiivmind"` |
| `repo_` | Repository by owner/name | `fetch_repo_issues "owner" "repo"` |

### 6.2 Entity Naming

| Entity | Singular | Plural |
|--------|----------|--------|
| Project | `project` | `projects` |
| Issue | `issue` | `issues` |
| Pull Request | `pr` | `prs` |
| Repository | `repo` or `repository` | `repos` or `repositories` |
| Milestone | `milestone` | `milestones` |

### 6.3 Anti-Patterns

**NEVER do this:**

```bash
# BAD: Dual-mode function
get_projects() {
    local login="$1"
    local type="$2"  # "organization" or "user"
    if [[ "$type" == "organization" ]]; then
        # org logic
    else
        # user logic
    fi
}

# BAD: Ambiguous scope
fetch_projects "hiivmind"  # Is this user or org?
```

**ALWAYS do this:**

```bash
# GOOD: Explicit scope
discover_org_projects "hiivmind"
discover_user_projects
```

---

## 7. Composition Patterns

### 7.1 Pipe-First Pattern (REQUIRED)

All workflows must use pipes. Never capture to intermediate variables when piping.

```bash
# CORRECT: Pipe-first
discover_org_projects "hiivmind" | filter_open | format_projects

# INCORRECT: Variable capture with pipe (triggers Claude Code bug)
PROJECTS=$(discover_org_projects "hiivmind")
echo "$PROJECTS" | format_projects
```

### 7.2 Branching Pattern

When workflows need conditional logic:

```bash
# Determine scope first (single value lookup is OK)
OWNER_TYPE=$(detect_owner_type "hiivmind")

# Then use appropriate primitive with pipes
if [[ "$OWNER_TYPE" == "organization" ]]; then
    discover_org_projects "hiivmind" | format_projects
else
    discover_user_projects | format_projects
fi
```

### 7.3 Lookup-Then-Mutate Pattern

When mutations require IDs:

```bash
# Lookups can use variable capture (single values, no pipe after)
PROJECT_ID=$(get_org_project_id 2 "hiivmind")

# Then mutate directly
gh project item-add "$PROJECT_ID" --owner hiivmind --url "$ISSUE_URL"
```

---

## 8. CRUD Coverage Matrix

For each domain, ensure complete CRUD coverage:

| Operation | User Scope | Org Scope | Repo Scope |
|-----------|------------|-----------|------------|
| **Create** | | | |
| **Read (single)** | | | |
| **Read (list/discover)** | | | |
| **Update** | | | |
| **Delete** | | | |
| **Filters** | | | |
| **Formatters** | | | |

---

## 9. Config-Driven Operations

Skills should leverage `.hiivmind/github/config.yaml` for cached IDs and context:

```bash
# Load config context
CONFIG=".hiivmind/github/config.yaml"
OWNER=$(yq '.workspace.login' "$CONFIG")
PROJECT_ID=$(yq '.projects.items[0].id' "$CONFIG")

# Use cached IDs with native gh commands
gh project item-add "$PROJECT_ID" --owner "$OWNER" --url "$ISSUE_URL"
```

This avoids repeated API calls for stable identifiers.

---

## 10. Error Handling

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | API error |
| 4 | Not found |

### Error Output

All errors go to stderr. Functions should be silent on success:

```bash
fetch_org_project() {
    if [[ -z "$1" || -z "$2" ]]; then
        echo "ERROR: fetch_org_project requires project_number and org_login" >&2
        return 2
    fi
    # ...
}
```

### Graceful Degradation

Filters should handle empty/null input:

```bash
filter_open() {
    jq 'if . == null then [] else map(select(.closed == false)) end'
}
```

---

## Summary

1. **Priority Chain:** gh CLI → GraphQL → REST → Research
2. **Three layers:** Templates/Indexes → Functions → Skills
3. **Seven primitive types:** Fetch, Lookup, Filter, Extract, Format, Mutate, Detect
4. **Explicit scope:** Always `_user_`, `_org_`, or `_repo_` - never dual-mode
5. **Pipe-first:** Compose via pipes, avoid intermediate variable capture
6. **Complete CRUD:** Every domain has full coverage matrix
7. **Index documentation:** Every function documented in `{domain}-index.md`
8. **Config-driven:** Leverage cached IDs from `.hiivmind/github/config.yaml`
