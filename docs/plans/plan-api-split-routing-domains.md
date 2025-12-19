Plan: API Routing Architecture Evaluation

 Question

 Should we restructure the api-routing guide now that it's grown to 1,052 lines with 25 domains?

 Options to evaluate:
 1. Split api-routing.md into per-domain documents
 2. Create individual skills for each domain
 3. Hybrid approach (references pattern)

 Current State Analysis

 api-routing.md

 - Size: 1,052 lines (~50 KB)
 - Structure: Quick reference table (30 lines) + 25 domain detail sections (~40 lines each)
 - Purpose: Single source of truth for API routing decisions (ADR-004)

 operations skill

 - Size: 361 lines
 - Workflow: 5-phase pattern (CONTEXT → RESOLVE → ROUTE → EXECUTE → REPORT)
 - Critical constraint: Phase 3 requires reading FULL api-routing.md ("Do NOT grep or search")
 - Description: Already at 1024 char limit (cannot add more trigger phrases)

 Evaluation Against Plugin-Dev Best Practices

 Option 1: Split api-routing.md into per-domain files

 lib/references/
 ├── api-routing.md (quick reference only, ~100 lines)
 ├── domains/
 │   ├── issues.md
 │   ├── pull-requests.md
 │   ├── milestones.md
 │   └── ... (25 files)

 Pros:
 - Reduces initial context load
 - Easier per-domain maintenance
 - Follows "domain-specific organization" pattern

 Cons:
 - Breaks current skill logic (requires full file read)
 - Would need 2-step routing: quick reference → domain file
 - Cross-domain operations need multiple files
 - 25 small files vs 1 comprehensive file

 Verdict: ⚠️ Possible but requires skill changes

 Option 2: Create individual skills per domain

 skills/
 ├── hiivmind-pulse-gh-issues/
 ├── hiivmind-pulse-gh-prs/
 ├── hiivmind-pulse-gh-milestones/
 └── ... (25 skills)

 Pros:
 - Focused trigger phrases per skill
 - Smaller skill files (~150 lines each)
 - Better triggering precision

 Cons:
 - 25+ skills is excessive - plugin-dev guidance recommends splitting when "completely different trigger phrases" and "distinct user personas"
 - Users say "create issue" not "use issues skill" - same trigger pattern across domains
 - Massive duplication: Phase 1-2 identical across all skills
 - Gateway would need complex routing logic
 - Violates "don't split if skills share significant code"

 Verdict: ❌ Not recommended - violates plugin-dev anti-patterns

 Option 3: Keep monolithic skill, use references directory

 skills/hiivmind-pulse-gh-operations/
 ├── SKILL.md (lean orchestration, ~300 lines)
 └── references/
     ├── api-routing-quick.md (index table, ~100 lines)
     ├── issues.md (~50 lines)
     ├── prs.md (~50 lines)
     └── ... (domain-specific details)

 Pros:
 - Matches plugin-dev "domain-specific organization" pattern
 - Single skill, single workflow
 - Progressive disclosure: load quick reference first, then domain-specific
 - No trigger phrase changes needed
 - Skill stays lean per guidance (~1500-2000 words)

 Cons:
 - Still need to read quick reference + domain file (2 reads)
 - Need to update skill's Phase 3 logic
 - More files to maintain

 Verdict: ✅ Recommended - follows best practices

 Recommendation: Option 3 (References Pattern)

 Why This Approach

 1. Plugin-dev guidance says: "Move detailed content to references/ - this keeps SKILL.md lean"
 2. Single skill maintained: No 25-skill explosion
 3. Progressive disclosure: Read quick reference (~100 lines), then only relevant domain (~50 lines)
 4. ADR-004 preserved: Quick reference remains single source of truth for routing decisions

 Implementation Plan

 Phase 1: Create references directory structure

 lib/references/
 ├── api-routing.md (NEW: quick reference only)
 │   - Quick Reference table (25 domains, 4-method support)
 │   - Method Selection Guide
 │   - Symbol legend
 │   - ~150 lines total
 │
 └── domains/
     ├── README.md (index of all domains)
     ├── issues.md
     ├── pull-requests.md
     ├── milestones.md
     ├── labels.md
     ├── projects-v2.md
     ├── branch-protection.md
     ├── rulesets.md
     ├── actions.md
     ├── secrets.md
     ├── variables.md
     ├── releases.md
     ├── repository.md
     ├── gists.md
     ├── search.md
     ├── collaborators.md
     ├── teams.md
     ├── webhooks.md
     ├── checks.md
     ├── deployments.md
     ├── environments.md
     ├── dependabot.md
     ├── code-scanning.md
     ├── secret-scanning.md
     ├── notifications.md
     └── reactions.md

 Phase 2: Update operations skill Phase 3

 Current:
 Read the FULL `lib/references/api-routing.md` file.
 Do NOT grep or search - read it completely.

 New:
 1. Read `lib/references/api-routing.md` (quick reference, ~150 lines)
 2. Identify domain from quick reference table
 3. Read `lib/references/domains/{domain}.md` for detailed syntax

 Phase 3: Create ADR-007

 Document the decision to split routing guide into quick reference + domain files.

 Files to Modify

 | File                                         | Change                         |
 |----------------------------------------------|--------------------------------|
 | lib/references/api-routing.md       | Slim to quick reference only   |
 | lib/references/domains/*.md         | NEW: 25 domain-specific files  |
 | skills/hiivmind-pulse-gh-operations/SKILL.md | Update Phase 3 reading pattern |
 | docs/adrs/007-*.md                           | NEW: Document decision         |

 Context Savings

 | Current                 | After Split                                                |
 |-------------------------|------------------------------------------------------------|
 | 1,052 lines (full file) | ~150 lines (quick ref) + ~50 lines (1 domain) = ~200 lines |

 Reduction: ~80% less context per operation

 Alternative Considered: Do Nothing

 Rationale for status quo:
 - 1,052 lines is large but not unmanageable
 - Skills can read ~50KB without issue
 - Current approach works and is battle-tested
 - Splitting adds complexity

 When to split:
 - When file exceeds ~2,000 lines
 - When users report slow skill activation
 - When maintenance becomes difficult

 Verdict: Current size is borderline - splitting is beneficial but not urgent.

 User Decision

 ✅ Approach: Option 3 - Split routing into quick reference + domain files
 ✅ ADR: Create ADR-007 to document decision

 ---
 Final Implementation Plan

 Step 1: Create ADR-007

 File: docs/adrs/007-split-api-routing-domains.md

 Document:
 - Context: api-routing.md grew to 1,052 lines with 25 domains
 - Decision: Split into quick reference + domain-specific files
 - Consequences: ~80% context reduction per operation

 Step 2: Create domains directory

 Directory: lib/references/domains/

 Extract each domain section from api-routing.md into individual files:

 | Domain            | File                 |
 |-------------------|----------------------|
 | Issues            | issues.md            |
 | Pull Requests     | pull-requests.md     |
 | Milestones        | milestones.md        |
 | Labels            | labels.md            |
 | Projects v2       | projects-v2.md       |
 | Branch Protection | branch-protection.md |
 | Rulesets          | rulesets.md          |
 | Actions           | actions.md           |
 | Secrets           | secrets.md           |
 | Variables         | variables.md         |
 | Releases          | releases.md          |
 | Repository        | repository.md        |
 | Gists             | gists.md             |
 | Search            | search.md            |
 | Collaborators     | collaborators.md     |
 | Teams             | teams.md             |
 | Webhooks          | webhooks.md          |
 | Checks            | checks.md            |
 | Deployments       | deployments.md       |
 | Environments      | environments.md      |
 | Dependabot        | dependabot.md        |
 | Code Scanning     | code-scanning.md     |
 | Secret Scanning   | secret-scanning.md   |
 | Notifications     | notifications.md     |
 | Reactions         | reactions.md         |

 Step 3: Slim api-routing.md

 File: lib/references/api-routing.md

 Keep only:
 - Quick Reference table (25 domains × 4 methods)
 - Method Selection Guide
 - Symbol legend (✓/✗/⊗)
 - Link to domains/ directory

 Remove: All 25 domain detail sections (moved to domains/)

 Target size: ~150 lines

 Step 4: Update operations skill Phase 3

 File: skills/hiivmind-pulse-gh-operations/SKILL.md

 Update Phase 3 from:
 Read the FULL lib/references/api-routing.md file.
 Do NOT grep or search - read it completely.

 To:
 1. Read lib/references/api-routing.md (quick reference)
 2. Identify domain from table
 3. Read lib/references/domains/{domain}.md for syntax details

 Step 5: Update CLAUDE.md references

 File: CLAUDE.md (repository root)

 Update any references to api-routing.md structure.

 ---
 Files to Create/Modify

 | Action | File                                            |
 |--------|-------------------------------------------------|
 | CREATE | docs/adrs/007-split-api-routing-domains.md      |
 | CREATE | lib/references/domains/ (directory)    |
 | CREATE | lib/references/domains/*.md (25 files) |
 | MODIFY | lib/references/api-routing.md          |
 | MODIFY | skills/hiivmind-pulse-gh-operations/SKILL.md    |
 | MODIFY | CLAUDE.md (if needed)                           |

 Expected Outcome

 - Before: 1,052 lines loaded per operation
 - After: ~150 lines (quick ref) + ~50 lines (domain) = ~200 lines
 - Savings: ~80% context reduction
