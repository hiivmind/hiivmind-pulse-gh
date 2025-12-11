# Automated Bug Reporting & Volume Tracking System

## Requirements Document

**Version:** 1.0
**Date:** 2025-12-11
**Status:** Draft

---

## 1. Executive Summary

This document specifies requirements for an automated error reporting system for hiivmind-pulse-gh that:

1. **Automatically creates GitHub issues** when plugin errors occur (GraphQL schema failures, jq query errors, API failures)
2. **Prevents duplicate issues** through deterministic error signatures
3. **Tracks impact volume** using GitHub-native mechanisms (no external telemetry)
4. **Enables prioritization** by surfacing most-impactful bugs to maintainers

The system operates entirely within the GitHub ecosystem using bot accounts, Projects v2 custom fields, reactions, and labels.

---

## 2. Problem Statement

### Current State
- Plugin errors fail silently or produce cryptic error messages
- Users must manually report bugs (high friction)
- No visibility into which errors affect the most users
- No mechanism to track "me too" reports without creating duplicate issues

### Desired State
- Errors automatically create/update issues in the public repository
- Duplicate reports increment a counter instead of creating new issues
- Maintainers can view bugs sorted by impact
- Zero manual intervention required from users

### Constraints
- Must use GitHub-native features only (no external databases, logs, or analytics)
- Must respect GitHub API rate limits
- Must protect user privacy (no PII in error reports)
- Must work with public open-source repositories

---

## 3. Bot Account Architecture

### 3.1 Bot Account Strategy

Rather than a single monolithic bot, hiivmind uses **purpose-specific bot accounts** for separation of duties:

| Bot Account | Purpose | Permissions Required |
|-------------|---------|---------------------|
| `hiivmind-sentinel` | Automated bug reporting & error tracking | `repo`, `project` |
| `hiivmind-ci` | CI/CD operations, test result reporting | `repo`, `actions` |
| `hiivmind-reviewer` | Automated code review comments | `repo`, `pull_request` |
| `hiivmind-curator` | Project/issue triage, labeling | `repo`, `project` |

### 3.2 Benefits of Multiple Bots

1. **Clear Audit Trail**: Easy to identify which automation performed which action
2. **Granular Permissions**: Each bot has minimal required scopes
3. **Rate Limit Isolation**: Independent rate limit pools per bot
4. **Agent Separation**: Enables future AI agent specialization
5. **Revocation Safety**: Compromised bot affects only its domain

### 3.3 Bot Account Setup

Each bot account requires:

```yaml
# .hiivmind/github/bots.yaml (gitignored - contains tokens)
bots:
  sentinel:
    login: hiivmind-sentinel
    token: ghp_xxxxxxxxxxxx  # Fine-grained PAT
    scopes:
      - repo
      - project
    purpose: "Automated error reporting and bug tracking"

  ci:
    login: hiivmind-ci
    token: ghp_xxxxxxxxxxxx
    scopes:
      - repo
      - actions
      - checks
    purpose: "CI/CD automation and test reporting"

  reviewer:
    login: hiivmind-reviewer
    token: ghp_xxxxxxxxxxxx
    scopes:
      - repo
    purpose: "Automated code review"

  curator:
    login: hiivmind-curator
    token: ghp_xxxxxxxxxxxx
    scopes:
      - repo
      - project
    purpose: "Issue and project triage"
```

### 3.4 Bot Authentication in Functions

```bash
# lib/github/gh-bot-functions.sh

# Get bot token for specific purpose
get_bot_token() {
    local bot_name="$1"
    yq ".bots.${bot_name}.token" .hiivmind/github/bots.yaml
}

# Execute gh command as specific bot
gh_as_bot() {
    local bot_name="$1"
    shift
    GH_TOKEN=$(get_bot_token "$bot_name") gh "$@"
}

# Example usage
gh_as_bot "sentinel" issue create -R "hiivmind/hiivmind-pulse-gh" --title "..."
```

---

## 4. Error Signature System

### 4.1 Error Signature Generation

Each error must produce a **deterministic signature** for deduplication:

```bash
# Generate error signature from error context
generate_error_signature() {
    local error_type="$1"      # e.g., "GRAPHQL_SCHEMA_ERROR"
    local error_code="$2"      # e.g., "FIELD_NOT_FOUND"
    local error_location="$3"  # e.g., "gh-issue-functions.sh:fetch_issue"
    local error_detail="$4"    # e.g., "Field 'projectItems' not found on type 'Issue'"

    # Create deterministic hash (excluding timestamps, user info)
    local signature_input="${error_type}|${error_code}|${error_location}|${error_detail}"
    echo "$signature_input" | sha256sum | cut -c1-12
}

# Example output: "a3f8c7d91b2e"
```

### 4.2 Error Categories

| Error Type | Code Pattern | Example |
|------------|--------------|---------|
| `GRAPHQL_SCHEMA_ERROR` | `FIELD_NOT_FOUND`, `TYPE_MISMATCH` | Field deprecated or renamed |
| `GRAPHQL_AUTH_ERROR` | `FORBIDDEN`, `INSUFFICIENT_SCOPES` | Missing permissions |
| `JQ_PARSE_ERROR` | `PARSE_ERROR`, `TYPE_ERROR` | Invalid jq filter syntax |
| `API_ERROR` | `RATE_LIMITED`, `SERVER_ERROR` | GitHub API issues |
| `VALIDATION_ERROR` | `INVALID_INPUT`, `MISSING_REQUIRED` | Bad function parameters |

### 4.3 Error Context Collection

```yaml
# Error report structure (sanitized - no PII)
error_report:
  signature: "a3f8c7d91b2e"
  timestamp: "2025-12-11T10:30:00Z"

  error:
    type: "GRAPHQL_SCHEMA_ERROR"
    code: "FIELD_NOT_FOUND"
    message: "Field 'projectItems' not found on type 'Issue'"

  location:
    file: "gh-issue-functions.sh"
    function: "fetch_issue"
    line: 142

  context:
    toolkit_version: "2.1.0"
    gh_version: "2.40.0"
    os: "linux"  # Generic, not specific distro

  query:
    name: "issue_with_project_items"
    # Query text (public anyway)

  # Explicitly excluded:
  # - User login/name/email
  # - Repository names (unless public)
  # - Issue/PR content
  # - OAuth tokens
```

---

## 5. Issue Creation & Deduplication

### 5.1 Issue Search Strategy

Before creating an issue, search for existing matches:

```bash
# Search for existing issue by signature
find_existing_issue() {
    local signature="$1"
    local repo="hiivmind/hiivmind-pulse-gh"

    # Search by signature label
    gh_as_bot "sentinel" issue list \
        -R "$repo" \
        -l "auto-bug" \
        -l "sig:${signature}" \
        --state all \
        --json number,state,url \
        --jq '.[0] // empty'
}
```

### 5.2 Issue Creation Template

```markdown
## Error: ${ERROR_TYPE}

**Signature:** `${SIGNATURE}`
**First Reported:** ${TIMESTAMP}

### Error Details

- **Code:** ${ERROR_CODE}
- **Message:** ${ERROR_MESSAGE}
- **Location:** `${FILE}:${FUNCTION}:${LINE}`

### Query Context

```graphql
${QUERY_TEXT}
```

### Environment

| Component | Version |
|-----------|---------|
| Toolkit | ${TOOLKIT_VERSION} |
| gh CLI | ${GH_VERSION} |
| OS | ${OS_TYPE} |

---

## Impact Tracking

<!-- AUTO-UPDATED SECTION - DO NOT EDIT MANUALLY -->
| Metric | Value |
|--------|-------|
| Total Reports | 1 |
| Unique Environments | 1 |
| Last Reported | ${TIMESTAMP} |
<!-- END AUTO-UPDATED SECTION -->

---

*This issue was automatically created by hiivmind-sentinel. Add a reaction to help prioritize this bug.*
```

### 5.3 Issue Labels

| Label | Purpose | Color |
|-------|---------|-------|
| `auto-bug` | Identifies auto-created issues | Red |
| `sig:XXXXXX` | Error signature for dedup | Gray |
| `error:graphql` | Error category | Orange |
| `error:jq` | Error category | Orange |
| `error:api` | Error category | Orange |
| `impact-critical` | 50+ reports | Dark Red |
| `impact-high` | 20-49 reports | Red |
| `impact-medium` | 5-19 reports | Yellow |
| `impact-low` | 1-4 reports | Blue |

---

## 6. Volume Tracking Mechanisms

### 6.1 Primary: Projects v2 Custom Number Field

The most structured approach using GitHub Projects v2:

```yaml
# Project field configuration
bug_tracking_project:
  number: 3  # Dedicated bug tracking project
  fields:
    Report Count:
      type: number
      description: "Total times this error has been reported"

    Unique Environments:
      type: number
      description: "Distinct environment configurations affected"

    Impact Score:
      type: number
      description: "Calculated as: reports * env_multiplier"

    Impact Tier:
      type: single_select
      options:
        - Critical  # 50+ reports
        - High      # 20-49 reports
        - Medium    # 5-19 reports
        - Low       # 1-4 reports

    Last Reported:
      type: date
      description: "Most recent occurrence"
```

**Update Flow:**

```bash
# Increment report count for project item
increment_report_count() {
    local item_id="$1"
    local field_id="$2"  # Report Count field ID
    local current_count="$3"

    local new_count=$((current_count + 1))

    gh_as_bot "sentinel" api graphql -f query='
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: Float!) {
            updateProjectV2ItemFieldValue(input: {
                projectId: $projectId
                itemId: $itemId
                fieldId: $fieldId
                value: { number: $value }
            }) {
                projectV2Item { id }
            }
        }
    ' -f projectId="$PROJECT_ID" \
      -f itemId="$item_id" \
      -f fieldId="$field_id" \
      -F value="$new_count"
}
```

### 6.2 Secondary: Reactions as Voting

For public visibility and user engagement:

```bash
# Add thumbs-up reaction (one per bot, but tracks visibility)
add_impact_reaction() {
    local issue_number="$1"
    local repo="hiivmind/hiivmind-pulse-gh"

    gh_as_bot "sentinel" api \
        -X POST \
        "/repos/${repo}/issues/${issue_number}/reactions" \
        -f content='+1'
}

# Users can also add reactions manually
# Query reaction count for display
get_reaction_count() {
    local issue_number="$1"
    local repo="hiivmind/hiivmind-pulse-gh"

    gh api "/repos/${repo}/issues/${issue_number}/reactions" \
        --jq '[.[] | select(.content == "+1")] | length'
}
```

### 6.3 Tertiary: Issue Body Updates

Maintain a human-readable summary in the issue body:

```bash
# Update impact summary section in issue body
update_impact_summary() {
    local issue_number="$1"
    local report_count="$2"
    local unique_envs="$3"
    local last_reported="$4"
    local repo="hiivmind/hiivmind-pulse-gh"

    # Get current body
    local current_body=$(gh_as_bot "sentinel" issue view "$issue_number" \
        -R "$repo" --json body --jq '.body')

    # Generate new summary section
    local new_summary="<!-- AUTO-UPDATED SECTION - DO NOT EDIT MANUALLY -->
| Metric | Value |
|--------|-------|
| Total Reports | ${report_count} |
| Unique Environments | ${unique_envs} |
| Last Reported | ${last_reported} |
<!-- END AUTO-UPDATED SECTION -->"

    # Replace section using sed
    local updated_body=$(echo "$current_body" | sed \
        '/<!-- AUTO-UPDATED SECTION/,/<!-- END AUTO-UPDATED SECTION -->/c\'"$new_summary")

    # Update issue
    gh_as_bot "sentinel" issue edit "$issue_number" \
        -R "$repo" \
        --body "$updated_body"
}
```

### 6.4 Impact Label Auto-Update

Automatically adjust impact labels based on report count:

```bash
# Update impact label based on current count
update_impact_label() {
    local issue_number="$1"
    local report_count="$2"
    local repo="hiivmind/hiivmind-pulse-gh"

    # Remove existing impact labels
    for label in "impact-critical" "impact-high" "impact-medium" "impact-low"; do
        gh_as_bot "sentinel" issue edit "$issue_number" \
            -R "$repo" \
            --remove-label "$label" 2>/dev/null || true
    done

    # Add appropriate label
    local new_label
    if [[ $report_count -ge 50 ]]; then
        new_label="impact-critical"
    elif [[ $report_count -ge 20 ]]; then
        new_label="impact-high"
    elif [[ $report_count -ge 5 ]]; then
        new_label="impact-medium"
    else
        new_label="impact-low"
    fi

    gh_as_bot "sentinel" issue edit "$issue_number" \
        -R "$repo" \
        --add-label "$new_label"
}
```

---

## 7. Full Error Reporting Flow

### 7.1 Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Error Occurs in Plugin Function                                            │
│  (GraphQL failure, jq error, validation error)                              │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. Capture Error Context                                                    │
│     - Error type, code, message                                             │
│     - Location (file, function, line)                                       │
│     - Environment (versions, OS type)                                       │
│     - Query text (if applicable)                                            │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. Generate Error Signature                                                 │
│     SHA256(type|code|location|detail)[0:12]                                 │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. Check for Existing Issue                                                 │
│     gh issue list -l "sig:SIGNATURE" --state all                            │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
         Issue Exists                    No Existing Issue
              │                               │
              ▼                               ▼
┌─────────────────────────────┐  ┌─────────────────────────────────────────────┐
│  4a. Update Existing Issue  │  │  4b. Create New Issue                       │
│  - Increment report count   │  │  - Apply labels: auto-bug, sig:XXX, error:Y │
│  - Update impact label      │  │  - Add to bug tracking project              │
│  - Update issue body        │  │  - Initialize report count = 1              │
│  - Add tracking comment     │  │  - Set initial impact label                 │
│    (optional, rate-limited) │  │                                             │
└─────────────────────────────┘  └─────────────────────────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. Update Projects v2 Fields                                                │
│     - Report Count (increment)                                              │
│     - Unique Environments (if new)                                          │
│     - Impact Score (recalculate)                                            │
│     - Impact Tier (auto-update)                                             │
│     - Last Reported (timestamp)                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  6. Return Issue URL to User                                                 │
│     "Error reported: https://github.com/hiivmind/hiivmind-pulse-gh/issues/X" │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Implementation: Main Error Handler

```bash
# lib/github/gh-error-handler.sh

# Main entry point for error reporting
report_error() {
    local error_type="$1"
    local error_code="$2"
    local error_message="$3"
    local error_location="$4"
    local query_name="${5:-}"
    local query_text="${6:-}"

    # Check if auto-reporting is enabled
    if [[ "${HIIVMIND_AUTO_REPORT:-false}" != "true" ]]; then
        return 0
    fi

    # Check for bot configuration
    if [[ ! -f ".hiivmind/github/bots.yaml" ]]; then
        echo "Warning: Bot configuration not found, skipping auto-report" >&2
        return 0
    fi

    # Generate signature
    local signature=$(generate_error_signature \
        "$error_type" "$error_code" "$error_location" "$error_message")

    # Collect environment context (sanitized)
    local toolkit_version=$(get_toolkit_version)
    local gh_version=$(gh --version | head -1 | awk '{print $3}')
    local os_type=$(uname -s | tr '[:upper:]' '[:lower:]')

    # Search for existing issue
    local existing_issue=$(find_existing_issue "$signature")

    if [[ -n "$existing_issue" ]]; then
        # Update existing issue
        local issue_number=$(echo "$existing_issue" | jq -r '.number')
        local issue_state=$(echo "$existing_issue" | jq -r '.state')

        # Reopen if closed (bug has recurred)
        if [[ "$issue_state" == "closed" ]]; then
            gh_as_bot "sentinel" issue reopen "$issue_number" \
                -R "hiivmind/hiivmind-pulse-gh"
        fi

        # Get current report count from project
        local current_count=$(get_project_field_value "$issue_number" "Report Count")
        local new_count=$((current_count + 1))

        # Update all tracking mechanisms
        update_project_report_count "$issue_number" "$new_count"
        update_impact_label "$issue_number" "$new_count"
        update_impact_summary "$issue_number" "$new_count" \
            "$(get_unique_env_count "$issue_number")" "$(date -Iseconds)"

        echo "Error reported (existing issue updated): $(echo "$existing_issue" | jq -r '.url')" >&2
    else
        # Create new issue
        local issue_url=$(create_error_issue \
            "$signature" \
            "$error_type" \
            "$error_code" \
            "$error_message" \
            "$error_location" \
            "$query_name" \
            "$query_text" \
            "$toolkit_version" \
            "$gh_version" \
            "$os_type")

        echo "Error reported (new issue created): $issue_url" >&2
    fi
}
```

---

## 8. Maintainer Dashboard

### 8.1 Project View Configuration

Create a dedicated view in the bug tracking project:

```yaml
# Bug Triage view configuration
views:
  - name: "Bug Triage - By Impact"
    layout: table
    sort:
      - field: "Report Count"
        direction: desc
    filter:
      state: open
    columns:
      - Title
      - Report Count
      - Impact Tier
      - Unique Environments
      - Last Reported
      - Labels

  - name: "Bug Triage - Recent"
    layout: table
    sort:
      - field: "Last Reported"
        direction: desc
    filter:
      state: open
    columns:
      - Title
      - Report Count
      - Impact Tier
      - Last Reported

  - name: "Impact Board"
    layout: board
    group_by: "Impact Tier"
    card_fields:
      - Report Count
      - Last Reported
```

### 8.2 CLI Dashboard Commands

```bash
# List bugs by impact
list_bugs_by_impact() {
    source lib/github/gh-project-functions.sh

    fetch_org_project 3 "hiivmind" \
        | jq -r '.data.organization.projectV2.items.nodes
            | sort_by(.fieldValues.nodes[] | select(.field.name == "Report Count") | .number)
            | reverse
            | .[:10]
            | .[] | "\(.content.title) - \(.fieldValues.nodes[] | select(.field.name == "Report Count") | .number) reports"'
}

# Get impact summary
get_impact_summary() {
    local repo="hiivmind/hiivmind-pulse-gh"

    echo "=== Bug Impact Summary ==="
    echo ""
    echo "Critical (50+ reports):"
    gh issue list -R "$repo" -l "impact-critical" -l "auto-bug" --json number,title \
        --jq '.[] | "  #\(.number): \(.title)"'
    echo ""
    echo "High (20-49 reports):"
    gh issue list -R "$repo" -l "impact-high" -l "auto-bug" --json number,title \
        --jq '.[] | "  #\(.number): \(.title)"'
}
```

---

## 9. Privacy & Security Considerations

### 9.1 Data Sanitization Rules

| Data Type | Handling |
|-----------|----------|
| User login/name/email | **Never collected** |
| Private repository names | **Never collected** |
| Issue/PR content | **Never collected** |
| OAuth tokens | **Never collected** |
| Error messages | Collected (public API responses) |
| Query text | Collected (public in codebase) |
| Toolkit version | Collected |
| gh CLI version | Collected |
| OS type | Collected (generic: linux/darwin/windows) |

### 9.2 Bot Token Security

```yaml
# Fine-grained PAT requirements for hiivmind-sentinel
token_permissions:
  repository_permissions:
    issues: write          # Create/update issues
    pull_requests: read    # Check if error relates to PR
    metadata: read         # Repository metadata

  organization_permissions:
    projects: write        # Update project fields

  # NOT required (minimized scope):
  # - contents: no code access needed
  # - actions: no workflow access needed
  # - secrets: no secrets access needed
```

### 9.3 Rate Limit Handling

```bash
# Rate limit aware execution
gh_with_rate_limit() {
    local response
    response=$(gh "$@" 2>&1)
    local exit_code=$?

    if echo "$response" | grep -q "rate limit"; then
        echo "Rate limited, backing off..." >&2
        sleep 60
        gh "$@"
    else
        echo "$response"
        return $exit_code
    fi
}
```

---

## 10. Configuration Options

### 10.1 User Opt-In/Opt-Out

```yaml
# .hiivmind/github/user.yaml
preferences:
  auto_error_reporting:
    enabled: true           # Master toggle
    include_environment: true  # Include version info
    silent_mode: false      # Suppress console messages
```

### 10.2 Environment Variables

```bash
# Enable auto-reporting
export HIIVMIND_AUTO_REPORT=true

# Disable for CI environments
export HIIVMIND_AUTO_REPORT=false

# Custom target repository (for forks)
export HIIVMIND_ERROR_REPO="myorg/hiivmind-pulse-gh"
```

---

## 11. Implementation Phases

### Phase 1: Foundation
- [ ] Create `hiivmind-sentinel` bot account
- [ ] Set up fine-grained PAT with minimal scopes
- [ ] Create `lib/github/gh-error-handler.sh`
- [ ] Implement error signature generation
- [ ] Implement issue search by signature label

### Phase 2: Issue Management
- [ ] Implement issue creation with template
- [ ] Implement duplicate detection and counter increment
- [ ] Create bug tracking project with custom fields
- [ ] Implement impact label auto-update

### Phase 3: Volume Tracking
- [ ] Implement Projects v2 field updates (Report Count, etc.)
- [ ] Implement issue body auto-update
- [ ] Create maintainer dashboard views

### Phase 4: Integration
- [ ] Add error handlers to all function libraries
- [ ] Add user opt-in/opt-out configuration
- [ ] Create documentation for contributors
- [ ] Add rate limit handling

### Phase 5: Additional Bots
- [ ] Create `hiivmind-ci` bot for test reporting
- [ ] Create `hiivmind-reviewer` bot for code review
- [ ] Create `hiivmind-curator` bot for triage automation
- [ ] Document bot account management procedures

---

## 12. Success Metrics

| Metric | Target |
|--------|--------|
| Auto-reported bugs | 100% of qualifying errors |
| Duplicate issue rate | < 1% (signatures working) |
| Time to triage (critical) | < 24 hours |
| False positive rate | < 5% |
| User opt-out rate | < 10% |

---

## 13. Open Questions

1. **Comment tracking**: Should we add a comment on each duplicate report, or just update the count? Comments create better audit trail but may cause notification noise.

2. **Closed issue handling**: When a bug recurs after being closed, should we reopen or create a new linked issue?

3. **Environment fingerprinting**: How much environment detail is useful without becoming PII?

4. **Cross-repository errors**: If errors occur in consuming repositories, how do we handle that context?

5. **Bot account naming**: Should bots use `hiivmind-` prefix or a different convention?

---

## 14. Related Documentation

- [meta-skill-architecture.md](./meta-skill-architecture.md) - Workspace configuration system
- [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) - Overall toolkit architecture
- [GitHub Reactions API](https://docs.github.com/en/rest/reactions)
- [GitHub Projects v2 API](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects)
