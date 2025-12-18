Plan saved to: ~/.claude/plans/serialized-bubbling-hippo.md · /plan to edit
     API Routing Guide Enhancement Plan

     Goal

     Transform api-routing.md from prescriptive (recommending ONE API method) to descriptive (showing support across all 4 methods: gh CLI, REST, GraphQL, Web UI) for each domain and operation.

     Current State Analysis

     What Works Well

     - Single source of truth: All skills reference this one file (ADR-004 architectural decision)
     - Standalone utility: Used directly without corpus lookup for known patterns
     - Fast routing: Skills read the full file once to make all routing decisions
     - Graceful degradation: Corpus lookup for uncertain syntax, REST default for unlisted domains

     Current Limitations

     - Shows only the recommended API method per operation
     - Doesn't expose when multiple methods work (e.g., CLI shortcuts vs direct API)
     - Doesn't document Web UI limitations (only mentioned in Projects v2 views)
     - Doesn't show that gh CLI can wrap both GraphQL AND REST

     Proposed Enhancement

     New Table Format

     Replace single "API" column with 4 support columns:

     | Operation           | gh CLI | REST | GraphQL | Web UI | Notes                |
     |---------------------|--------|------|---------|--------|----------------------|
     | Create issue        | ✓      | ✓    | ✓       | ✓      | CLI: gh issue create |
     | Create milestone    | ✗      | ✓    | ✗       | ✓      | No GraphQL mutation  |
     | Create project view | ✗      | ✗    | ✗       | ✓      | UI-only operation    |
     | Delete repo         | ✗      | ⊗    | ⊗       | ⊗      | Blocked for safety   |

     Legend:
     - ✓ = Supported
     - ✗ = Not available
     - ⊗ = Available but blocked for safety

     Benefits

     1. User empowerment: See all options, choose based on context
     2. Debugging aid: When one method fails, try another
     3. Learning resource: Understand GitHub API landscape
     4. Safety transparency: Show where operations are intentionally blocked
     5. Maintains speed: Still one file read, just more comprehensive data

     Affected Files

     Primary Changes

     lib/examples/operations/api-routing.md (~260 lines)
     - Update Quick Reference table (lines 11-23)
     - Update each domain's detailed table (8 domains × ~10 lines each)
     - Add legend section explaining symbols
     - Add "Method Selection Guidance" section
     - Preserve all Search Keywords columns (used for corpus lookup)

     Documentation Updates

     docs/operation-blocklist.md (~50 lines)
     - Already documents blocked operations
     - Reference from routing guide
     - No changes needed (just cross-reference)

     CLAUDE.md (root, git/hiivmind, git/hiivmind/hiivmind-pulse-gh)
     - Update "Supported Domains" table to mention multi-method visibility
     - No structural changes

     Skills (No Changes Required)

     Skills already read the FULL file, so enhanced tables will be automatically consumed:

     - skills/hiivmind-pulse-gh-operations/SKILL.md - Reads full routing guide in Phase 3
     - commands/hiivmind-pulse-gh.md - References routing guide
     - All skills use See: lib/examples/operations/api-routing.md pattern

     Project Management Approach

     We'll manage this as a structured project with:

     1. ADR (Architecture Decision Record): Document the decision to move from prescriptive to descriptive API routing
     2. Milestone: Group all domain research issues under one milestone
     3. Individual Issues: One issue per domain for systematic tracking (25 issues total)

     This allows:
     - Parallel work on different domains
     - Clear progress tracking
     - Incremental updates to the routing guide
     - Easy resumption if interrupted

     Implementation Steps

     Step 0: Project Setup (Do This First!)

     1. Create ADR documenting the architectural decision:
       - Use /hiivmind-pulse-gh adr for multi-method API routing visibility
       - Link to the planned milestone
       - Document rationale: user empowerment, debugging aid, learning resource
       - Note backwards compatibility (no skill changes needed)
     2. Create Milestone:
       - Title: "API Routing Guide: Multi-Method Visibility"
       - Description: "Transform routing guide to show support across all 4 methods (gh CLI, REST, GraphQL, Web UI) for comprehensive coverage"
       - Due date: (user can set, or leave open-ended)
     3. Create Issues (one per domain):
       - Template title: "Research {Domain}: 4-method API support matrix"
       - Template body:
       ## Goal
     Document support across all 4 methods for {Domain} operations:
     - ✓/✗ gh CLI commands
     - ✓/✗ REST endpoints
     - ✓/✗ GraphQL queries/mutations
     - ✓/✗/⊗ Web UI (including blocked operations)

     ## Research Steps
     1. Run `gh {domain} --help` for CLI coverage
     2. Use GitHub API corpus for REST paths
     3. Use GitHub API corpus for GraphQL schema
     4. Check operation-blocklist.md for safety blocks

     ## Deliverable
     Updated section in `lib/examples/operations/api-routing.md` with comprehensive method support table

     ## Related
     - ADR: (link to ADR)
     - Milestone: (link to milestone)
       - Assign all issues to the milestone
       - Use labels: documentation, enhancement, api-routing

     Step 1: Research Domain Support Matrix (Per Issue)

     Methodology: For each domain, systematically check all 4 methods:

     1. gh CLI commands:
       - Run gh --help to list top-level commands
       - Run gh {domain} --help to see available operations
       - Check gh {domain} {operation} --help for exact syntax
       - If CLI help insufficient: Use GitHub API corpus to fetch CLI docs
           - Invoke: Skill: hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs
         - Query: "gh CLI {domain} commands reference"
         - The corpus includes links to cli.github.com documentation
         - Use WebFetch on those links if needed for full command syntax
       - Document which operations have CLI shortcuts
     2. REST endpoints (use GitHub API corpus):
       - Invoke: Skill: hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs
       - Query: "GitHub REST API {domain} endpoints {operation}"
       - Extract: Full endpoint paths (e.g., /repos/{owner}/{repo}/milestones)
       - Extract: HTTP methods (GET/POST/PATCH/DELETE)
       - Note which CRUD operations are available
     3. GraphQL support (use GitHub API corpus):
       - Invoke: Skill: hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs
       - Query: "GitHub GraphQL {domain} schema mutations queries"
       - Extract: Query types for reads (e.g., issue, pullRequest)
       - Extract: Mutation names for writes (e.g., createIssue, updateIssue)
       - Extract: Search keywords for corpus lookup
       - Distinguish queries (read-only) from mutations (write)
     4. Web UI limitations:
       - Check docs/operation-blocklist.md for blocked operations
       - Review current routing guide for "UI-only" notes (Projects v2 views)
       - Document operations that are UI-exclusive or blocked for safety

     Research approach - For each domain:
     1. Start with current routing guide as baseline (already has some info)
     2. Use gh {domain} --help to discover CLI coverage
     3. Use GitHub API corpus for REST paths and GraphQL keywords
     4. Build a matrix showing ✓/✗/⊗ for each method
     5. Document the exact CLI commands and search keywords
     6. Note which operations are blocked or UI-only

     Domains to research (organized by category):

     Core Operations (currently documented):
     1. Issues
     2. Pull Requests
     3. Milestones
     4. Labels
     5. Projects v2

     Security (currently documented):
     6. Branch Protection (Legacy)
     7. Rulesets (Modern)
     8. Secrets
     9. Variables

     Automation (currently documented):
     10. Actions (Workflows/Runs/Jobs)
     11. Releases

     Additional Domains (to add):
     12. Repository (create, update, delete, archive, transfer, topics, settings)
     13. Collaborators (add, remove, permissions)
     14. Teams (create, add members, permissions)
     15. Webhooks (create, update, delete, test)
     16. Checks (create, update, check runs, check suites)
     17. Deployments (create, update, deployment status)
     18. Environments (create, update, secrets, protection rules)
     19. Dependabot (alerts, security updates, config)
     20. Code Scanning (alerts, analyses, upload SARIF)
     21. Secret Scanning (alerts, locations)
     22. Gists (create, update, delete, star)
     23. Search (repositories, issues, code, users)
     24. Notifications (mark read, thread subscription)
     25. Reactions (add, delete to issues/PRs/comments)

     Step 2: Update Quick Reference Table

     File: lib/examples/operations/api-routing.md (lines 9-23)

     Current format:
     | Domain | Read | Create | Update | Delete | Notes |

     New format:
     | Domain | Read (CLI/REST/GraphQL/UI) | Create (CLI/REST/GraphQL/UI) | Update | Delete | Notes |

     Or split into separate columns (evaluate table width first):
     | Domain | Operation | gh CLI | REST | GraphQL | Web UI | Notes |

     Second format is clearer and follows user's preference for verbose CLI commands in table.

     Step 3: Update Domain Detail Sections

     For each of the 10 domains (lines ~28-218):

     New structure:

     ### Domain Name

     | Operation | gh CLI | REST | GraphQL | Web UI | Notes |
     |-----------|--------|------|---------|--------|-------|
     | List | `gh domain list` | ✓ | ✓ | ✓ | All methods work |
     | Get | `gh domain view` | ✓ | ✓ | ✓ | |
     | Create | `gh domain create` | ✓ | ✗ | ✓ | No GraphQL mutation |
     | Update | ✗ | ✓ | ✗ | ✓ | CLI doesn't support |
     | Delete | ⊗ | ⊗ | ⊗ | ⊗ | Blocked (see operation-blocklist.md) |

     **Legend:**
     - ✓ = Supported
     - ✗ = Not available
     - ⊗ = Blocked for safety
     - CLI commands shown when available (use `gh domain --help` for full syntax)

     **Corpus Lookup Guide** (when you need exact syntax):

     | API | When to Use | Search Keywords |
     |-----|-------------|-----------------|
     | GraphQL | Complex queries, field selection | `query`, `repository`, `mutation`, `createX` |
     | REST | CRUD, admin operations | `POST`, `PATCH`, `DELETE`, `/repos/{owner}/{repo}/...` |

     Preserve existing content where possible (Why sections, Key concepts, CLI alternatives).

     Step 4: Add Method Selection Guide

     Insert new section after line 23 (after Quick Reference, before Domain Details):

     ## How to Choose an API Method

     Use this guide to select the right method for your operation:

     ### 1. gh CLI (Try First)
     **When:** Operation has CLI support (check table)
     **Pros:** Simple syntax, handles auth/pagination automatically
     **Example:** `gh issue create --title "Bug" --body "Description"`

     ### 2. REST API (CRUD Operations)
     **When:** Creating/updating/deleting resources, or CLI not available
     **Pros:** Full CRUD support, well-documented, predictable
     **Example:** `gh api POST /repos/{owner}/{repo}/milestones -f title="v2.0"`

     ### 3. GraphQL (Complex Queries)
     **When:** Reading nested data, need field selection, batch operations
     **Pros:** Get exactly what you need, fewer roundtrips
     **Example:** `gh api graphql -f query='...'` with field selection

     ### 4. Web UI (Fallback)
     **When:** Operation marked ⊗ (blocked) or ✓ only in UI column
     **Why:** Some features are UI-only (e.g., Projects v2 views)
     **Example:** Project view creation, dangerous operations

     **Symbol meanings in tables:**
     - ✓ = Method is supported and available
     - ✗ = Method not available for this operation
     - ⊗ = Method exists but blocked for safety (see docs/operation-blocklist.md)

     Step 5: Update Documentation Cross-References

     Files to update:

     1. CLAUDE.md (repository root, line ~160):
       - Update "Supported Domains" table description
       - Mention multi-method visibility in routing guide
     2. docs/operation-blocklist.md (no changes):
       - Already documents blocked operations
       - Routing guide will reference this with ⊗ symbol

     Step 6: Verification Checklist

     Before marking complete:

     - All 10 core domains updated with 4-column method support
     - Quick Reference table includes method indicators
     - Method Selection Guide added with clear decision tree
     - Corpus Lookup Guide sections added to each domain
     - Legend explains ✓/✗/⊗ symbols consistently
     - CLI commands shown verbosely in table (e.g., gh issue create)
     - Search keywords moved to separate Corpus Lookup subsections
     - No changes required to skills (they read full file already)
     - Cross-references to operation-blocklist.md in place
     - File remains standalone useful (no corpus required for basic routing)

     User Decisions

     ✅ Scope: All domains (comprehensive coverage)
     - Core operations: Issues, PRs, Milestones, Labels, Projects v2
     - Security: Branch Protection, Rulesets, Secrets, Variables
     - Automation: Actions (Workflows/Runs/Jobs), Releases
     - Collaboration: Collaborators, Teams
     - Repository: Settings, Topics, Webhooks
     - CI/CD: Checks, Deployments, Environments
     - Security scanning: Dependabot, Code Scanning, Secret Scanning
     - Other: Gists, Search, Notifications, Reactions

     ✅ Notation: Symbols (✓/✗/⊗)
     - ✓ = Supported
     - ✗ = Not available
     - ⊗ = Available but blocked for safety
     - Visual, compact, scans quickly

     ✅ CLI details: In the table (verbose)
     - Show exact gh CLI commands directly in table
     - Example: gh issue create instead of just ✓
     - More immediate reference for users

     ✅ Keywords: Separate subsection
     - Main table focuses on method support
     - "Corpus Lookup Guide" section below each domain
     - Cleaner tables, keywords grouped by what to search for

     Summary

     This enhancement transforms the API routing guide from prescriptive (recommending one method) to descriptive (showing all options). Users will see at a glance which of the 4 methods (gh CLI,
     REST, GraphQL, Web UI) support each operation, enabling them to choose based on their context and constraints.

     Key design principles maintained:
     - Single source of truth (ADR-004)
     - Standalone utility (no corpus required for basic routing)
     - Fast consumption (skills read full file once)
     - Backward compatible (no skill code changes needed)

     Benefits delivered:
     - User empowerment through visibility of all options
     - Better debugging (try alternative methods when one fails)
     - Learning resource (understand GitHub API landscape)
     - Safety transparency (⊗ symbol shows blocked operations)



● Perfect! Project Setup Complete! Here's what we've accomplished:

  ✅ Project Initialized

  1. ADR-006 Created: Architecture Decision Record documenting the decision to show multi-method API support
    - File: /home/nathanielramm/git/hiivmind/hiivmind-pulse-gh/docs/adrs/006-descriptive-multi-method-routing.md
    - Status: Proposed
    - Linked to milestone
  2. Milestone #14 Created: "API Routing Guide: Multi-Method Visibility"
    - URL: https://github.com/hiivmind/hiivmind-pulse-gh/milestone/14
    - Description: Transform routing guide to show support across all 4 methods
  3. 29 Domain Research Issues Created:
    - Core Operations (7): Issues, PRs, Milestones, Labels, Projects v2, Discussions, PR Reviews
    - Security (6): Branch Protection, Rulesets, Secrets, Variables, Dependabot, Code Scanning, Secret Scanning
    - Automation (3): Actions, Releases, Deployments
    - Collaboration (4): Collaborators, Teams, Invitations, Reactions
    - Repository (3): Settings, Topics, Webhooks
    - CI/CD (2): Checks, Environments
    - Other (2): Gists, Search, Notifications
    - All linked to milestone #14 with documentation labels

  ---
  🎯 Next Steps: Domain Research

  Now we systematically research each domain using:
  1. gh CLI: gh {domain} --help
  2. GitHub API Corpus: Query for REST endpoints and GraphQL schema
  3. Operation Blocklist: Check docs/operation-blocklist.md
  4. Current Routing Guide: Reference lib/examples/operations/api-routing.md

  Would you like me to start researching the first domain (Issues)? I'll use the corpus to get comprehensive 4-method support data.
