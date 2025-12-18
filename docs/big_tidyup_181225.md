Ready to code?

 Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Refactoring Plan: External Corpus Migration & Examples Consolidation

 Summary

 Migrate hiivmind-pulse-gh from embedded local corpus to external dependency, consolidate examples into centralized lib/examples/ with skill-local references, and reorganize for
 clear introspection vs operations separation.

 Key Principle: Introspection examples = HEAVY (very repeatable). Operation examples = LIGHT (just API routing, corpus handles syntax).

 ---
 ADR Documents (Create First)

 ADR-003: External Corpus Dependency

 File: docs/adr/003-external-corpus-dependency.md

 Context: Embedded corpus at skills/hiivmind-corpus-github/ (692MB, 9 sections) vs external hiivmind-corpus-github-docs (4.8GB, 36 sections, 165 gh CLI commands).

 Decision: Declare dependency on external corpus. Remove embedded corpus.

 Consequences:
 - Corpus invocation changes: hiivmind-pulse-gh:hiivmind-corpus-github → hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs
 - Plugin size: 700MB → ~2MB
 - Users must have external corpus installed
 - Better coverage (36 sections, gh CLI docs)

 ---
 ADR-004: Single Source of Truth for API Routing

 File: docs/adr/004-single-source-of-truth-routing.md

 Context: Domain→API routing decisions appear in 10+ files (README, CLAUDE.md, operations skill, corpus-lookup pattern, workflow examples).

 Decision: lib/examples/operations/api-routing.md is THE canonical source. All others reference it.

 Consequences:
 - CLAUDE.md: Remove "Supported Domains" table (dev guidance only)
 - README.md: Link to api-routing.md
 - Skills: Use See: lib/examples/operations/api-routing.md
 - One place to update when APIs change

 ---
 ADR-005: Examples Library Architecture

 File: docs/adr/005-examples-library-architecture.md

 Context: Confusion between lib/github/patterns/ (algorithms) and reference/ (documentation). Some content serves dual purposes (introspection AND operation).

 Decision: Unified lib/examples/ structure with explicit separation:
 - lib/examples/introspection/ - HEAVY examples for repeatable checking operations
 - lib/examples/operations/ - LIGHT examples, just API routing (corpus handles syntax)
 - Individual skills have local examples/ files that REFER to central examples + add clarifications

 Principle: Introspection needs repeatability (detailed examples). Operations just need routing (corpus provides syntax JIT).

 ---
 New Directory Structure

 hiivmind-pulse-gh/
 ├── .claude-plugin/
 │   └── plugin.json              # ADD: dependency on hiivmind-corpus-github
 │
 ├── commands/
 │   └── hiivmind-pulse-gh.md     # Keep domain keywords (intent detection)
 │
 ├── skills/
 │   ├── hiivmind-pulse-gh-init/
 │   │   ├── SKILL.md
 │   │   └── examples/            # LOCAL: refers to lib/examples/ + init-specific notes
 │   │       └── examples.md
 │   │
 │   ├── hiivmind-pulse-gh-refresh/
 │   │   ├── SKILL.md
 │   │   └── examples/
 │   │       └── examples.md
 │   │
 │   ├── hiivmind-pulse-gh-operations/
 │   │   ├── SKILL.md             # SIMPLIFIED: remove Domain Quick Reference
 │   │   └── examples/            # EXISTING: domain files become references
 │   │       └── examples.md      # Points to lib/examples/operations/
 │   │
 │   ├── hiivmind-pulse-gh-adr/
 │   │   ├── SKILL.md
 │   │   └── examples/
 │   │       └── examples.md
 │   │
 │   └── hiivmind-pulse-gh-awareness/
 │       ├── SKILL.md
 │       └── examples/
 │           └── examples.md
 │   # DELETED: hiivmind-corpus-github/
 │
 ├── lib/
 │   └── examples/                 # CENTRALIZED EXAMPLES
 │       │
 │       ├── introspection/        # HEAVY - very repeatable
 │       │   ├── README.md         # Index with section groupings
 │       │   ├── config-parsing.md       # FROM: lib/github/patterns/
 │       │   ├── workspace-detection.md
 │       │   ├── authentication.md
 │       │   ├── tool-detection.md
 │       │   ├── id-resolution.md
 │       │   ├── graphql-execution.md
 │       │   ├── graphql-queries.md
 │       │   ├── error-handling.md
 │       │   └── freshness-checking.md   # NEW: extracted from refresh
 │       │
 │       └── operations/           # LIGHT - just routing
 │           ├── README.md         # Explains corpus-first approach
 │           ├── api-routing.md    # FROM: reference/api-routing.md (THE source)
 │           └── corpus-lookup.md  # How to use corpus for syntax
 │
 ├── docs/
 │   ├── adr/                      # Architecture Decision Records
 │   │   ├── 001-corpus-lookup-pattern.md
 │   │   ├── 002-open-ended-domain-support.md
 │   │   ├── 003-external-corpus-dependency.md     # NEW
 │   │   ├── 004-single-source-of-truth-routing.md # NEW
 │   │   └── 005-examples-library-architecture.md  # NEW
 │   │
 │   ├── config-schema.md          # FROM: reference/
 │   └── operation-blocklist.md    # FROM: reference/
 │
 ├── CLAUDE.md                     # REMOVE domain table, keep dev guidance
 ├── README.md                     # LINK to api-routing.md instead of embed
 │
 ├── # CLEANUP
 ├── reference/                    # DELETE after moving
 │   └── workflows/                # ARCHIVE: historical examples
 └── knowledge/                    # ARCHIVE to _archived/

 ---
 Key Architectural Changes

 1. Introspection Examples (HEAVY)

 These need detailed, repeatable examples because they're checking state:

 | Example                | Purpose                  | Referenced By                             |
 |------------------------|--------------------------|-------------------------------------------|
 | config-parsing.md      | YAML config read/write   | init, refresh, operations, adr, awareness |
 | workspace-detection.md | Git remote → owner/repo  | init                                      |
 | authentication.md      | gh auth + scope checking | init, operations                          |
 | tool-detection.md      | gh, jq, yq availability  | init                                      |
 | id-resolution.md       | Name → ID with cache     | operations, adr                           |
 | error-handling.md      | API error patterns       | refresh, operations                       |
 | graphql-execution.md   | Temp file method         | operations                                |
 | freshness-checking.md  | Config staleness         | refresh, gateway                          |

 2. Operations Examples (LIGHT)

 Operations just need routing to API type. Corpus handles exact syntax:

 | Example          | Purpose                                              |
 |------------------|------------------------------------------------------|
 | api-routing.md   | Domain → GraphQL/REST decision (THE source of truth) |
 | corpus-lookup.md | How to invoke corpus for syntax when uncertain       |

 Removed: Domain-specific operation examples (issues.md, projects.md, etc.)
 Reason: Corpus provides JIT syntax. Operations skill just routes, then calls corpus.

 3. Skill-Local Examples

 Each skill gets a local examples/examples.md that:
 1. Lists which central examples it uses
 2. Adds skill-specific clarifications
 3. Groups by introspection vs operation sections

 ---
 Execution Phases

 Phase 1: Create ADRs (Non-Breaking)

 1. Create docs/adr/003-external-corpus-dependency.md
 2. Create docs/adr/004-single-source-of-truth-routing.md
 3. Create docs/adr/005-examples-library-architecture.md

 Commit: docs(adr): document external corpus and examples architecture decisions

 ---
 Phase 2: External Corpus Migration (Breaking)

 2.1 Update plugin.json

 Add to .claude-plugin/plugin.json:
 "dependencies": {
   "plugins": ["hiivmind-corpus-github-docs@hiivmind-corpus-github"]
 }

 2.2 Update corpus invocations (11 files)

 Change: hiivmind-pulse-gh:hiivmind-corpus-github
 To: hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs

 Files:
 - All 5 skill SKILL.md files
 - lib/github/patterns/corpus-lookup.md
 - lib/github/patterns/id-resolution.md
 - lib/github/patterns/capability-awareness.md
 - reference/api-routing.md
 - CLAUDE.md, README.md

 2.3 Delete embedded corpus

 rm -rf skills/hiivmind-corpus-github/

 Commit: feat(corpus): migrate to external hiivmind-corpus-github-docs dependency

 ---
 Phase 3: Examples Library Reorganization (Breaking Paths)

 3.1 Create new structure

 mkdir -p lib/examples/introspection lib/examples/operations docs/adr

 3.2 Move introspection examples (HEAVY)

 mv lib/github/patterns/config-parsing.md lib/examples/introspection/
 mv lib/github/patterns/workspace-detection.md lib/examples/introspection/
 mv lib/github/patterns/authentication.md lib/examples/introspection/
 mv lib/github/patterns/tool-detection.md lib/examples/introspection/
 mv lib/github/patterns/id-resolution.md lib/examples/introspection/
 mv lib/github/patterns/graphql-execution.md lib/examples/introspection/
 mv lib/github/patterns/graphql-queries.md lib/examples/introspection/
 mv lib/github/patterns/error-handling.md lib/examples/introspection/

 3.3 Move operations examples (LIGHT)

 mv reference/api-routing.md lib/examples/operations/
 mv lib/github/patterns/corpus-lookup.md lib/examples/operations/

 3.4 Move reference docs

 mv reference/config-schema.md docs/
 mv reference/operation-blocklist.md docs/

 3.5 Create README files

 - lib/examples/introspection/README.md - Index of heavy introspection examples
 - lib/examples/operations/README.md - Explains corpus-first approach

 3.6 Delete old operations domain examples

 rm skills/hiivmind-pulse-gh-operations/examples/*.md

 Commit: refactor(examples): reorganize into introspection (heavy) and operations (light)

 ---
 Phase 4: Update Path References

 4.1 Update See: references

 Change lib/github/patterns/X.md → lib/examples/introspection/X.md or lib/examples/operations/X.md

 Files to update (~30 references):
 - All 5 skill SKILL.md files
 - commands/hiivmind-pulse-gh.md
 - Cross-references within example files

 4.2 Update CLAUDE.md

 Remove "Supported Domains" table. Replace with:
 ## API Routing

 For domain-to-API routing, see `lib/examples/operations/api-routing.md`.

 4.3 Update README.md

 Link to lib/examples/operations/api-routing.md instead of embedding table.

 4.4 Update operations skill

 Remove "Domain Quick Reference" table, add:
 **See:** `lib/examples/operations/api-routing.md` (canonical source)

 Commit: refactor(paths): update all See: references to new examples structure

 ---
 Phase 5: Create Skill-Local Examples

 Create examples/examples.md for each skill with:
 - References to relevant central examples
 - Skill-specific clarifications
 - ## Introspection / ## Operations sections

 Example structure:
 # {Skill} Examples

 ## Introspection Examples
 | Example | Location | Notes |
 |---------|----------|-------|
 | Config Parsing | `lib/examples/introspection/config-parsing.md` | ... |

 ## Operations Examples
 | Example | Location | Notes |
 |---------|----------|-------|
 | API Routing | `lib/examples/operations/api-routing.md` | ... |

 Commit: feat(skills): add local examples/ files referencing central examples

 ---
 Phase 6: Cleanup

 6.1 Remove old directories

 rm -rf lib/github/
 rm -rf reference/

 6.2 Archive historical files

 mv reference/workflows/ _archived/
 mv knowledge/ _archived/

 6.3 Handle awareness patterns

 Move capability-awareness.md, adr-awareness.md, adr-management.md to skill-local examples or inline.

 Commit: chore: archive historical docs and clean up directory structure

 ---
 Critical Files Summary

 | File                                              | Action                                      |
 |---------------------------------------------------|---------------------------------------------|
 | .claude-plugin/plugin.json                        | Add external corpus dependency              |
 | skills/hiivmind-corpus-github/                    | DELETE (692MB)                              |
 | reference/api-routing.md                          | MOVE to lib/examples/operations/            |
 | lib/github/patterns/corpus-lookup.md              | MOVE to lib/examples/operations/            |
 | lib/github/patterns/*.md (8 files)                | MOVE to lib/examples/introspection/         |
 | skills/*/examples/examples.md                     | CREATE for each skill (local references)    |
 | CLAUDE.md                                         | Remove domain table, link to api-routing.md |
 | README.md                                         | Link to api-routing.md instead of embed     |
 | skills/hiivmind-pulse-gh-operations/SKILL.md      | Remove Domain Quick Reference               |
 | skills/hiivmind-pulse-gh-operations/examples/*.md | DELETE (corpus replaces domain examples)    |
 | 11 files                                          | Update corpus invocation syntax             |
 | ~30 files                                         | Update See: path references                 |

 ---
 Testing Checklist

 - External corpus invocation works: hiivmind-corpus-github-docs:hiivmind-corpus-navigate-github-docs
 - Operations skill routes correctly via lib/examples/operations/api-routing.md
 - All See: references resolve to valid paths in lib/examples/
 - Init skill works with external corpus
 - Refresh skill works with external corpus
 - Gateway command routes correctly
 - Skill-local examples/examples.md files reference central examples correctly

 ---
 Risks & Mitigations

 | Risk                                        | Mitigation                                                |
 |---------------------------------------------|-----------------------------------------------------------|
 | External corpus not installed               | Plugin manifest declares dependency; init skill checks    |
 | Broken path references                      | Grep for old lib/github/patterns/ and reference/ paths    |
 | Missing corpus invocations                  | Search for hiivmind-pulse-gh:hiivmind-corpus-github       |
 | Confusion about introspection vs operations | README files in each lib/examples/ folder explain purpose |

 ---
 Post-Implementation Verification

 After each phase, verify:

 # Check no old paths remain
 grep -r "lib/github/patterns" skills/ commands/ CLAUDE.md README.md
 grep -r "reference/api-routing" skills/ commands/ CLAUDE.md README.md

 # Check corpus invocation updated
 grep -r "hiivmind-pulse-gh:hiivmind-corpus-github" .

 # Check new paths exist
 ls lib/examples/introspection/
 ls lib/examples/operations/
