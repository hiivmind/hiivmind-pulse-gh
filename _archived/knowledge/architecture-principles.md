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

## 2. The Four-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   LAYER 4: SKILLS                           │
│  Workflow orchestration via SKILL.md instructions           │
│  Multi-step workflows, error handling, documentation        │
│  Human-readable, goal-oriented, composes all lower layers   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ composes
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              LAYER 3: SMART APPLICATION                     │
│  High-level functions: apply_{outcome}()                    │
│  Auto-detect context, compose primitives + templates        │
│  Handle schema variations transparently                     │
│  Example: apply_main_branch_protection()                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ uses
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              LAYER 2: PRIMITIVE FUNCTIONS                   │
│  Shell functions in lib/github/gh-{domain}-functions.sh    │
│  Single-responsibility: FETCH, DETECT, MUTATE, etc.         │
│  Stdin→stdout pipes, uses Priority Chain internally         │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ references
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         LAYER 1: TEMPLATES & DOCUMENTATION                  │
│  GraphQL queries: gh-{domain}-graphql-queries.yaml         │
│  jq filters: gh-{domain}-jq-filters.yaml                   │
│  Config templates: gh-{domain}-templates.yaml (optional)   │
│  Index docs: gh-{domain}-index.md                          │
└─────────────────────────────────────────────────────────────┘
```

### Layer 1: Templates & Documentation

**Query/Filter Templates (YAML) - Required**
- Externalized, versionable, testable query/filter definitions
- GraphQL queries with parameters and extraction paths
- jq filters for data transformation
- No logic, only data

**Configuration Templates (YAML) - Optional**

Configuration templates (`gh-{domain}-templates.yaml`) should only be added when:

1. **High complexity** - API configurations have 10+ fields with nested structures
2. **Non-obvious best practices** - Users need expert knowledge to configure correctly
3. **Schema variations** - API behavior differs based on context (org vs personal repos)
4. **Common use cases** - Clear, reusable patterns exist

**When NOT to use configuration templates:**
- Simple mutations with <5 parameters
- Highly variable configurations with no clear patterns
- Domain where every use case is unique

**Template access functions:**
```bash
get_{domain}_template "NAME"    # Returns JSON config from template
list_{domain}_templates         # Lists available template names
```

**Example - Protection domain has templates:**
- 40+ field configurations (required_status_checks, required_pull_request_reviews, etc.)
- Schema variations (org repos support `restrictions` object, personal repos require `null`)
- 29 different ruleset types with varying parameters
- Clear best practices (main branch needs 2 approvals, signed commits, etc.)

**Example - Issue domain doesn't need templates:**
- Simple CRUD operations (3-5 field mutations)
- No schema variations
- Configurations are highly variable per use case

**Index Documentation (Markdown) - Required**
- `gh-{domain}-index.md` for each domain
- Documents every function at all layers
- Includes examples and composition patterns
- Single source of truth for available operations

### Layer 2: Primitive Functions

**Seven primitive types:**
- FETCH, LOOKUP, FILTER, EXTRACT, FORMAT, MUTATE, DETECT
- Single responsibility, composable via pipes
- Follow Priority Chain internally (gh CLI → GraphQL → REST)
- Located in `lib/github/gh-{domain}-functions.sh`

**Characteristics:**
- Pure operations - no context detection
- Explicit parameters (owner, repo, branch, etc.)
- Stdin→stdout for data flow
- Examples: `fetch_branch_protection`, `detect_owner_type`, `format_issues`

### Layer 3: Smart Application Functions

**Purpose:** Compose primitives with context awareness to achieve complete outcomes.

**When to add Layer 3 functions:**
- Multiple primitives must be composed in a specific sequence
- Context detection is needed (org vs personal, current state, etc.)
- Schema variations must be handled transparently
- Common outcome can be parameterized simply

**Naming pattern:** `apply_{outcome}`, `get_{aggregate}_summary`, `upsert_{entity}`

**Example:** `apply_main_branch_protection()`

This function demonstrates all Layer 3 characteristics:

```bash
apply_main_branch_protection() {
    local owner="$1"
    local repo="$2"

    # 1. CONTEXT DETECTION - Determine repository type
    local repo_type
    repo_type=$(_detect_repo_type "$owner" "$repo")  # Internal API call
    # Returns: "organization" or "personal"

    # 2. SCHEMA VARIATION HANDLING - Select appropriate template
    local template_name
    if [[ "$repo_type" == "organization" ]]; then
        template_name="main_org"      # Can use: restrictions object,
                                      # required_signatures, bypass_pull_request_allowances
    else
        template_name="main_personal" # Must use: restrictions=null,
                                      # no required_signatures
    fi

    # 3. COMPOSITION - Layer 2 primitives + Layer 1 template
    get_protection_template "$template_name" | \
        set_branch_protection_rest "$owner" "$repo" "main"
}
```

**What this achieves:**
- User calls simple function: `apply_main_branch_protection "owner" "repo"`
- Function handles complexity: detects context, selects template, applies protection
- Avoids errors: org-only fields automatically excluded for personal repos
- Encodes best practices: org repos get 2 approvals + code owners, personal get 1 approval

**Other Layer 3 examples:**
- `upsert_repo_ruleset()` - Detects if ruleset exists, then creates or updates
- `get_protection_summary()` - Fetches branch protection + rulesets, formats into single summary
- `apply_branch_naming_ruleset()` - Gets template, applies to repository

**Not all domains need Layer 3:**
- Issue domain: primitives are sufficient (`create_issue`, `set_issue_milestone`)
- Milestone domain: simple CRUD, no context detection needed
- Protection domain: essential (40+ fields, org/personal variations)

### Layer 4: Skills

**Purpose:** Multi-step workflows combining all lower layers with error handling and user guidance.

**Characteristics:**
- Workflow orchestration (multiple operations in sequence)
- Conceptual documentation (when to use X vs Y)
- Error handling guidance (403 = permissions, 404 = missing entity)
- Workspace configuration integration
- Located in `skills/{skill-name}/SKILL.md`

**Skills are NOT code** - they are documentation that guides Claude Code to compose the layers below.

**Example workflow from Protection skill:**
```bash
# Full repository protection setup - composes Layer 3 functions
apply_main_branch_protection "$ORG" "$REPO"
apply_develop_branch_protection "$ORG" "$REPO"
apply_branch_naming_ruleset "$ORG" "$REPO"
apply_release_branch_ruleset "$ORG" "$REPO"
apply_tag_protection_ruleset "$ORG" "$REPO"
```

**Skills provide:**
- Decision trees (Branch Protection vs Rulesets - when to use each)
- Complete outcomes ("Protect Main Branch", "Set Up Full Repository Protection")
- Error scenarios (personal repo + restrictions object = 404 error)
- Workspace integration (loading org/repo from `.hiivmind/github/config.yaml`)
- Human-readable documentation for Claude Code to follow

---

## 3. File Organization

### 3.1 Directory Structure

```
lib/github/
├── index.md                           # Master index of all domains
├── gh-{domain}-functions.sh           # Shell functions (Layer 2 + Layer 3)
├── gh-{domain}-graphql-queries.yaml   # GraphQL query templates (Layer 1)
├── gh-{domain}-jq-filters.yaml        # jq filter templates (Layer 1)
├── gh-{domain}-templates.yaml         # Config templates (Layer 1, optional)
└── gh-{domain}-index.md               # Domain-specific function index (Layer 1)
```

**When to include `gh-{domain}-templates.yaml`:**
- Domain has complex API payloads (10+ fields, nested structures)
- Schema variations exist (org vs personal, different entity types)
- Best practices can be encoded as reusable configs
- Examples: Protection domain (has templates), Issue domain (no templates needed)
```

### 3.2 Domain Coverage

| Domain | Functions | Queries | Filters | Templates | Index |
|--------|-----------|---------|---------|-----------|-------|
| Protection | `gh-protection-functions.sh` | `gh-protection-graphql-queries.yaml` | `gh-protection-jq-filters.yaml` | `gh-protection-templates.yaml` | `gh-protection-index.md` |
| Projects | `gh-project-functions.sh` | `gh-project-graphql-queries.yaml` | `gh-project-jq-filters.yaml` | - | `gh-project-index.md` |
| Issues | `gh-issue-functions.sh` | `gh-issue-graphql-queries.yaml` | `gh-issue-jq-filters.yaml` | - | `gh-issue-index.md` |
| Repositories | `gh-repo-functions.sh` | `gh-repo-graphql-queries.yaml` | `gh-repo-jq-filters.yaml` | - | `gh-repo-index.md` |
| Identity | `gh-identity-functions.sh` | `gh-identity-graphql-queries.yaml` | - | - | `gh-identity-index.md` |
| Milestones | `gh-milestone-functions.sh` | (shared) | `gh-milestone-jq-filters.yaml` | - | `gh-milestone-index.md` |
| PRs | `gh-pr-functions.sh` | `gh-pr-graphql-queries.yaml` | `gh-pr-jq-filters.yaml` | - | `gh-pr-index.md` |

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

| Domain | Layer 2 | Layer 3 | Templates | Description |
|--------|---------|---------|-----------|-------------|
| [Protection](gh-protection-index.md) | 32 | 7 | ✅ | Branch protection + rulesets, schema variations |
| [Projects](gh-project-index.md) | 20 | 4 | - | ProjectsV2 CRUD, fields, items, views |
| [Issues](gh-issue-index.md) | 12 | - | - | Issue CRUD, labels, assignees |
| [PRs](gh-pr-index.md) | 12 | - | - | Pull request CRUD, reviews, status |
| [Repositories](gh-repo-index.md) | 8 | - | - | Repository discovery and metadata |
| [Identity](gh-identity-index.md) | 6 | - | - | User/org detection and lookup |
| [Milestones](gh-milestone-index.md) | 8 | - | - | Milestone CRUD operations |

## Layer 2: Primitive Types

- **FETCH** - Retrieve data (`discover_*`, `fetch_*`)
- **LOOKUP** - Resolve IDs (`get_*_id`)
- **FILTER** - Transform data (`filter_*`, `apply_*_filter`)
- **EXTRACT** - Pull specific fields (`extract_*`)
- **FORMAT** - Human-readable output (`format_*`)
- **MUTATE** - Create/update/delete (`create_*`, `update_*`, `delete_*`, `set_*`)
- **DETECT** - Determine types/states (`detect_*`, `check_*`)

## Layer 3: Smart Application

- **apply_*** - Apply configurations with context detection
- **upsert_*** - Idempotent create/update operations
- **get_*_summary** - Aggregate multiple fetches

## Interaction Priority

1. Native `gh` CLI commands
2. `gh api graphql` for complex queries
3. `gh api` REST for mutations not in GraphQL
4. Research via `github-navigate` skill
```

---

## 5. Primitive Classification (Layer 2)

Every Layer 2 primitive falls into exactly one category:

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

### 6.1 Layer 2 Scope Prefixes

Always specify the scope explicitly. Never create "dual-mode" functions.

| Scope | Meaning | Example |
|-------|---------|---------|
| `viewer_` | Authenticated user (implicit) | `fetch_viewer` |
| `user_` | Specific user by login | `fetch_user_repositories "bob"` |
| `org_` | Organization by login | `fetch_org_projects "hiivmind"` |
| `repo_` | Repository by owner/name | `fetch_repo_issues "owner" "repo"` |

### 6.2 Layer 3 Outcome Prefixes

Layer 3 functions focus on outcomes, not operations:

| Prefix | Meaning | Example |
|--------|---------|---------|
| `apply_` | Apply configuration/policy | `apply_main_branch_protection "owner" "repo"` |
| `upsert_` | Create or update (idempotent) | `upsert_repo_ruleset "owner" "repo" "name"` |
| `get_{x}_summary` | Aggregate multiple fetches | `get_protection_summary "owner" "repo"` |

**Key difference from Layer 2:**
- Layer 2: Explicit scope, explicit operation (`fetch_branch_protection "owner" "repo" "main"`)
- Layer 3: Outcome-focused, handles context (`apply_main_branch_protection "owner" "repo"`)

### 6.3 Entity Naming

| Entity | Singular | Plural |
|--------|----------|--------|
| Project | `project` | `projects` |
| Issue | `issue` | `issues` |
| Pull Request | `pr` | `prs` |
| Repository | `repo` or `repository` | `repos` or `repositories` |
| Milestone | `milestone` | `milestones` |
| Protection | `protection` | `protections` |
| Ruleset | `ruleset` | `rulesets` |

### 6.4 Anti-Patterns

**NEVER do this:**

```bash
# BAD: Dual-mode function (Layer 2 should be explicit)
get_projects() {
    local login="$1"
    local type="$2"  # "organization" or "user"
    if [[ "$type" == "organization" ]]; then
        # org logic
    else
        # user logic
    fi
}

# BAD: Ambiguous scope (Layer 2)
fetch_projects "hiivmind"  # Is this user or org?

# BAD: Context detection in Layer 2 primitive
fetch_issues() {
    local owner="$1"
    local repo="$2"
    # BAD: Primitives shouldn't detect context
    if [[ $(detect_owner_type "$owner") == "org" ]]; then
        # Different behavior based on context
    fi
}
```

**ALWAYS do this:**

```bash
# GOOD: Explicit scope (Layer 2)
discover_org_projects "hiivmind"
discover_user_projects

# GOOD: Context detection in Layer 3
apply_main_branch_protection() {
    local owner="$1"
    local repo="$2"
    local repo_type=$(_detect_repo_type "$owner" "$repo")  # Internal helper
    # ... select template based on repo_type
}
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
2. **Four layers:** Templates/Docs → Primitives → Smart Application → Skills
3. **Seven primitive types (Layer 2):** Fetch, Lookup, Filter, Extract, Format, Mutate, Detect
4. **Smart Application (Layer 3):** Context-aware composition (`apply_*`, `upsert_*`, `get_*_summary`)
5. **Configuration templates (optional):** Only for complex domains (10+ fields, schema variations)
6. **Explicit scope:** Always `_user_`, `_org_`, or `_repo_` - never dual-mode
7. **Pipe-first:** Compose via pipes, avoid intermediate variable capture
8. **Complete CRUD:** Every domain has full coverage matrix
9. **Index documentation:** Every function (all layers) documented in `{domain}-index.md`
10. **Config-driven:** Leverage cached IDs from `.hiivmind/github/config.yaml`
