# GitHub Projects Command Standardization Development Plan

## Overview

This plan standardizes all command files in `.claude/commands/` to adopt the exact same architecture as the mature `hv-gh-project-dashboard.md` command, following the system architecture documented in `hv-gh-project-system-architecture.md`.

## Current State Analysis

### ✅ Mature Command (Reference Architecture)
- **`hv-gh-project-dashboard.md`** - Fully implements the standardized architecture

### 🔄 Commands Requiring Standardization
1. **`hv-gh-project-discover.md`** - Discovery operations

## Architecture Gaps Identified

### ❌ Current Issues

1. **Inconsistent Implementation Patterns**
   - Commands use direct `gh api graphql` with complex command substitution
   - Manual jq filter construction instead of YAML templates
   - Shell escaping and quoting issues
   - No standardized pipeline approach

2. **Missing Architecture Components**
   - No "LLM Implementation Reference" section
   - No "Working Examples" with expected JSON output
   - No "Parameter Substitution Reference"
   - No bash function pipeline patterns

3. **Template Integration Issues**
   - Direct YAML queries instead of process substitution
   - Missing `.hiivmind/gh-project-functions.sh` integration
   - No standardized filter pipeline usage

4. **Documentation Structure**
   - Different section organization
   - Missing production notes and benefits
   - No function reference sections

## Standardization Requirements

### ✅ Target Architecture (from `hv-gh-project-dashboard.md`)

Each command file must have these exact sections:

```markdown
# {Command Title}
{Brief description}

## Usage
/command-name <params>

### Parameters
- Parameter documentation

### Examples
Command examples

---

## LLM Implementation Reference

### Core Pattern: Bash Functions with YAML Templates
**✅ PRODUCTION APPROACH**: Use bash functions...

### Command Templates
#### Organization Project Pattern
#### User Project Pattern
#### Discovery Pattern (if applicable)

---

## Working Examples
### Example 1: Basic Usage
### Example 2: Filtered Usage
### Example N: Advanced Usage

---

## Parameter Substitution Reference
### Template Variables
### YAML Template Paths

---

## Benefits of Bash Functions Approach
### ✅ Advantages
### 🔄 Implementation Pattern
### 📊 Output Format

---

## Production Notes
## Available Functions Reference
```

## Development Plan

### Phase 1: Function Extensions (Est: 2-3 hours)

**Goal**: Extend `.hiivmind/gh-project-functions.sh` with functions needed by all commands

#### 1.1 Discovery Functions
Add to `gh-project-functions.sh`:
```bash
# Discovery context functions
discover_user_projects()
discover_org_projects()
discover_repo_projects()
discover_all_projects()

# Field inspection functions
inspect_user_project_fields()
inspect_org_project_fields()

# Enhanced listing functions
list_user_project_items_enhanced()
list_org_project_items_enhanced()
```

#### 1.2 GraphQL Query Extensions
Add to `github-projects-graphql-queries.yaml`:
- Field inspection queries for discovery commands
- Enhanced item listing queries
- Repository context queries

#### 1.3 jq Filter Extensions
Add to `github-projects-jq-filters.yaml`:
- Field summary filters
- Enhanced item formatting filters
- Discovery result formatting filters

### Phase 2: Command File Standardization (Est: 4-5 hours)

Transform each command file to match the reference architecture:

#### 2.1 `hv-gh-project-discover.md`
- **Replace**: Direct `gh api graphql` calls
- **With**: `discover_user_projects | format_discovery_output`
- **Add**: LLM Implementation Reference section
- **Add**: Working Examples with JSON output
- **Add**: Parameter substitution reference

#### 2.2 `hv-gh-project-filter.md`
- **Replace**: Complex jq inline filters
- **With**: Pipeline functions like `fetch_org_project | apply_status_filter | get_items`
- **Standardize**: Universal filter usage patterns
- **Add**: All required architecture sections

#### 2.3 `hv-gh-project-fields.md`
- **Replace**: Direct GraphQL field queries
- **With**: `inspect_org_project_fields | format_field_summary`
- **Add**: Field discovery pipeline examples
- **Add**: Complete architecture sections

#### 2.4 `hv-gh-project-itemlist.md`
- **Replace**: Basic `gh project item-list` commands
- **With**: Enhanced GraphQL pipeline functions
- **Add**: Full field data access via templates
- **Add**: Standardized architecture sections

#### 2.5 `hv-gh-project-items-enhanced.md`
- **Replace**: Direct API calls with manual jq
- **With**: `fetch_org_project | apply_enhanced_formatting`
- **Add**: Configurable field selection
- **Add**: Complete architecture documentation

### Phase 3: Template Integration (Est: 1-2 hours)

#### 3.1 GraphQL Template Standardization
Ensure all queries use the centralized YAML approach:
```bash
# ❌ Old approach
gh api graphql -f query="$(yq '.discovery.user_projects.query' ...)"

# ✅ New approach
source .hiivmind/gh-project-functions.sh
discover_user_projects | format_discovery_output
```

#### 3.2 Filter Template Integration
Standardize all jq operations through YAML templates:
```bash
# ❌ Old approach
jq -r '.data.viewer.projectV2.items.nodes[] | select(...)'

# ✅ New approach
jq -f <(yq '.discovery_filters.project_summary.filter' github-projects-jq-filters.yaml)
```

### Phase 4: Documentation Validation (Est: 1 hour)

#### 4.1 Architecture Compliance Check
Verify each command file has:
- [ ] Correct section structure
- [ ] LLM Implementation Reference
- [ ] Working Examples with JSON output
- [ ] Parameter Substitution Reference
- [ ] Production notes
- [ ] Function reference

#### 4.2 Pipeline Testing
Test all pipeline patterns work correctly:
- [ ] Function chaining via pipes
- [ ] Process substitution for YAML templates
- [ ] Error handling and parameter validation
- [ ] JSON output consistency

## Implementation Details

### Function Naming Convention
```bash
# Data fetching
fetch_{context}_project
discover_{context}_projects

# Processing
inspect_{context}_project_fields
list_{context}_project_items_enhanced

# Formatting
format_discovery_output
format_field_summary
format_enhanced_items
```

### Template Path Convention
```yaml
# GraphQL queries
discovery:
  {context}_projects_summary:
project_structure:
  {context}_project_fields_detailed:

# jq filters
discovery_filters:
  format_{output_type}:
enhanced_filters:
  {context}_items_detailed:
```

### Pipeline Pattern Standardization
All commands must follow:
```bash
# 1. Source functions (once per session)
source .hiivmind/gh-project-functions.sh

# 2. Fetch data with appropriate function
{fetch_function} PROJECT_NUM ["ORG_NAME"]

# 3. Apply processing through pipeline
| {processing_function} [params]

# 4. Format output
| {formatting_function}
```

## Success Criteria

### ✅ Completion Checklist

1. **Function Library Complete**
   - [ ] All required functions added to `gh-project-functions.sh`
   - [ ] GraphQL templates extended for all use cases
   - [ ] jq filters support all command patterns

2. **Commands Standardized**
   - [ ] All 5 command files match reference architecture
   - [ ] Pipeline patterns consistently implemented
   - [ ] Shell escaping issues eliminated

3. **Documentation Complete**
   - [ ] LLM Implementation Reference in all files
   - [ ] Working Examples with expected JSON
   - [ ] Parameter substitution guides
   - [ ] Production notes and benefits

4. **Integration Tested**
   - [ ] All pipeline patterns work end-to-end
   - [ ] YAML template loading via process substitution
   - [ ] Error handling and validation
   - [ ] Memory efficiency (no temp files)

## Benefits of Standardization

### 🎯 Immediate Benefits
- **Consistent API**: All commands use identical patterns
- **Reduced Complexity**: No more command substitution issues
- **Better Performance**: Streaming pipelines, no temp files
- **Maintainability**: Centralized templates and functions

### 📈 Long-term Benefits
- **Extensibility**: Easy to add new commands following pattern
- **Reliability**: Proven architecture reduces bugs
- **Documentation**: Self-documenting pipeline patterns
- **LLM Optimization**: Consistent structure improves Claude interaction

## Estimated Timeline

- **Phase 1**: Function Extensions - 2-3 hours
- **Phase 2**: Command Standardization - 4-5 hours
- **Phase 3**: Template Integration - 1-2 hours
- **Phase 4**: Documentation Validation - 1 hour

**Total Estimated Time**: 8-11 hours

## Priority Order

1. **High Priority**: `hv-gh-project-filter.md` - Most complex, biggest impact
2. **Medium Priority**: `hv-gh-project-items-enhanced.md` - Heavy usage patterns
3. **Medium Priority**: `hv-gh-project-discover.md` - Foundation command
4. **Low Priority**: `hv-gh-project-fields.md` - Administrative function
5. **Low Priority**: `hv-gh-project-itemlist.md` - Basic functionality

This plan ensures all commands follow the mature, production-tested architecture of `hv-gh-project-dashboard.md` while maintaining backward compatibility and improving reliability.
