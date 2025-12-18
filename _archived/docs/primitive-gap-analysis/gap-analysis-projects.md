# Primitive Gap Analysis

> **Document ID:** KB-002
> **Created:** 2025-12-10
> **Status:** Active
> **Related Issue:** #8

## Executive Summary

The `gh-workspace-functions.sh` file contains goal-oriented composite functions that should instead be composed from primitives. This analysis identifies what primitives exist, what's missing, and what needs to be added to the core library.

## Existing Primitives in `gh-project-functions.sh`

### Query Primitives (stdin→stdout)

| Category | Primitive | Exists | Notes |
|----------|-----------|--------|-------|
| **User Discovery** | `discover_user_projects` | ✅ | Returns full project metadata |
| **Org Discovery** | `discover_org_projects` | ✅ | Requires org login |
| **Repo Discovery** | `discover_repo_projects` | ✅ | Requires owner + repo |
| **Project Fields** | `fetch_user_project_fields` | ✅ | Full field structure |
| **Project Fields** | `fetch_org_project_fields` | ✅ | Full field structure |
| **Project Items** | `fetch_user_project` | ✅ | Full item data |
| **Project Items** | `fetch_org_project` | ✅ | Full item data |
| **ID Lookups** | `get_user_project_id` | ✅ | Number → ID |
| **ID Lookups** | `get_org_project_id` | ✅ | Number + org → ID |
| **ID Lookups** | `get_user_id` | ✅ | Viewer ID |
| **ID Lookups** | `get_org_id` | ✅ | Org login → ID |
| **ID Lookups** | `get_repo_id` | ✅ | Owner + repo → ID |

### Filter Primitives (stdin→stdout)

| Filter | Exists | Notes |
|--------|--------|-------|
| `apply_universal_filter` | ✅ | Multi-criteria |
| `apply_assignee_filter` | ✅ | By assignee |
| `apply_repo_filter` | ✅ | By repository |
| `apply_status_filter` | ✅ | By status field |
| `list_repositories` | ✅ | Extract repos |
| `list_assignees` | ✅ | Extract assignees |
| `list_statuses` | ✅ | Extract statuses |

### Format Primitives (stdin→stdout)

| Formatter | Exists | Notes |
|-----------|--------|-------|
| `format_user_projects` | ✅ | For user project lists |
| `format_org_projects` | ✅ | For org project lists |
| `format_repo_projects` | ✅ | For repo project lists |
| `format_all_projects` | ✅ | Universal formatter |

## Missing Primitives (from workspace-functions analysis)

### Identity & Workspace Primitives

| Primitive | Status | Description |
|-----------|--------|-------------|
| `fetch_viewer` | ❌ MISSING | Get current authenticated user info |
| `fetch_organization` | ❌ MISSING | Get organization info by login |
| `detect_owner_type` | ❌ MISSING | Determine if login is org or user |

### Repository Primitives

| Primitive | Status | Description |
|-----------|--------|-------------|
| `fetch_user_repositories` | ❌ MISSING | List repos for a user |
| `fetch_org_repositories` | ❌ MISSING | List repos for an org |
| `fetch_repository` | ❌ MISSING | Get single repo by owner/name |
| `format_repositories` | ❌ MISSING | Format repo list for display |

### Project List Formatting

| Primitive | Status | Description |
|-----------|--------|-------------|
| `format_projects_simple` | ❌ MISSING | Simple `#N - Title [status]` format |
| `extract_project_numbers` | ❌ MISSING | Extract just numbers from project list |
| `filter_open_projects` | ❌ MISSING | Filter to only open projects |

### Field Structure Primitives

| Primitive | Status | Description |
|-----------|--------|-------------|
| `extract_fields_structure` | ❌ MISSING | Transform fields JSON to config format |
| `extract_single_select_options` | ❌ MISSING | Get options from single-select field |
| `extract_iteration_config` | ❌ MISSING | Get iteration configuration |

## What `gh-workspace-functions.sh` Does That Should Be Composed

### Current: `discover_projects(login, type)`
**Problem:** Dual-mode function (org vs user) with embedded GraphQL

**Should be:**
```bash
# For organization
discover_org_projects "hiivmind" | format_projects_simple

# For user
discover_user_projects | format_projects_simple
```

### Current: `get_workspace_type(login)`
**Problem:** Goal-specific, uses REST API probe

**Should be:**
```bash
# New primitive
detect_owner_type "hiivmind"  # → "organization" or "user"
```

### Current: `get_workspace_id(login, type)`
**Problem:** Dual-mode, mixes concerns

**Should be:**
```bash
# For organization
get_org_id "hiivmind"

# For user (already exists)
get_user_id
```

### Current: `fetch_project_with_fields(num, login, type)`
**Problem:** Dual-mode, embeds full GraphQL

**Should be:**
```bash
# Already exists!
fetch_org_project_fields 2 "hiivmind" | extract_fields_structure
fetch_user_project_fields 2 | extract_fields_structure
```

### Current: `discover_repositories(login, type)`
**Problem:** Dual-mode, uses REST API

**Should be:**
```bash
# New primitives needed
fetch_org_repositories "hiivmind" | format_repositories
fetch_user_repositories "discreteds" | format_repositories
```

### Current: `format_projects_list()`
**Problem:** Reads stdin JSON, outputs formatted text

**Status:** This IS a valid primitive pattern, but should be in core library

### Current: Composite functions like `generate_config_yaml`, `initialize_workspace`
**Problem:** These are workflow orchestration, not primitives

**Status:** These belong in SKILL.md instructions or a separate orchestration layer, not in the primitive library

## Recommended Actions

### 1. Add Missing Query Primitives to `gh-project-graphql-queries.yaml`

```yaml
identity:
  viewer_info:
    query: |
      query {
        viewer {
          id
          login
          name
        }
      }

  organization_info:
    query: |
      query($login: String!) {
        organization(login: $login) {
          id
          login
          name
        }
      }

repositories:
  user_repositories:
    query: |
      query($login: String!) {
        user(login: $login) {
          repositories(first: 100) {
            nodes {
              id
              name
              nameWithOwner
              defaultBranchRef { name }
              visibility
            }
          }
        }
      }

  organization_repositories:
    query: |
      query($login: String!) {
        organization(login: $login) {
          repositories(first: 100) {
            nodes {
              id
              name
              nameWithOwner
              defaultBranchRef { name }
              visibility
            }
          }
        }
      }
```

### 2. Add Missing Function Primitives to `gh-project-functions.sh`

```bash
# Identity primitives
fetch_viewer() { ... }
fetch_organization() { ... }
detect_owner_type() { ... }

# Repository primitives
fetch_user_repositories() { ... }
fetch_org_repositories() { ... }
fetch_repository() { ... }

# Format primitives
format_repositories() { ... }
format_projects_simple() { ... }

# Transform primitives
extract_fields_structure() { ... }
```

### 3. Add Missing Filter/Transform to `gh-project-jq-filters.yaml`

```yaml
project_transforms:
  fields_to_config:
    description: "Transform project fields to config.yaml format"
    filter: |
      .fields.nodes | map(
        if .dataType == "SINGLE_SELECT" then
          { key: .name, value: { id: .id, type: "single_select", options: (.options | map({(.name): .id}) | add) } }
        elif .dataType == "ITERATION" then
          { key: .name, value: { id: .id, type: "iteration", iterations: (.configuration.iterations | map({(.title): .id}) | add) } }
        else
          { key: .name, value: { id: .id, type: (.dataType | ascii_downcase) } }
        end
      ) | from_entries

  projects_simple:
    description: "Simple project list format"
    filter: |
      .[] | "  #\(.number) - \(.title) [\(if .closed then "closed" else "open" end)]"
```

### 4. Deprecate `gh-workspace-functions.sh`

Once primitives are complete, the workspace-init workflow becomes pure composition in SKILL.md:

```bash
# In SKILL.md instructions:
source lib/github/gh-project-functions.sh

# Detect workspace
detect_owner_type "hiivmind"  # → organization

# List projects (pipe-first pattern)
discover_org_projects "hiivmind" | format_projects_simple

# Get field structure
fetch_org_project_fields 2 "hiivmind" | extract_fields_structure

# List repositories
fetch_org_repositories "hiivmind" | format_repositories
```

## Architectural Principles

1. **Single-responsibility primitives** - Each function does ONE thing
2. **Stdin→stdout pattern** - All primitives read stdin or return stdout
3. **No dual-mode functions** - Separate `_user_` and `_org_` variants
4. **Queries in YAML** - GraphQL templates externalized
5. **Filters in YAML** - jq filters externalized
6. **Composition in skills** - Workflows composed from primitives in SKILL.md
7. **No intermediate variables** - Use pipes, not `VAR=$(...)` patterns

## References

- `lib/github/gh-project-functions.sh` - Core primitives
- `lib/github/gh-project-graphql-queries.yaml` - Query templates
- `lib/github/gh-project-jq-filters.yaml` - Filter templates
- `lib/github/gh-workspace-functions.sh` - To be deprecated
- `knowledge/claude-code-bash-escaping.md` - Why pipes matter
