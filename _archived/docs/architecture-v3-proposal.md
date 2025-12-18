# Architecture v3: Lean Context Engineering

> Based on [Anthropic's context engineering guidance](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

## The Problem

Current architecture has 7 skills and 10+ function libraries. This creates:
- **Ambiguity**: When do I use `investigate` vs `projects`?
- **Bloat**: Each skill loads context the LLM may not need
- **Duplication**: Bash functions re-implement what's documented in the corpus

The article's key insight: *"Find the smallest set of high-signal tokens that maximize desired outcomes."*

## The Solution

### Core Principle

**One skill to initialize. One reference for routing. The corpus for specifics. Examples for patterns.**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  hiivmind-pulse-gh-init          ← THE skill (validates, discovers, caches)│
│       │                                                                     │
│       ▼                                                                     │
│  config.yaml                     ← Cached context (IDs, fields, options)   │
│       │                                                                     │
│       ▼                                                                     │
│  api-routing.md                  ← Decision tree (which API for what)      │
│       │                                                                     │
│       ▼                                                                     │
│  hiivmind-corpus-github          ← JIT specifics (schema, endpoints, CLI)  │
│       │                                                                     │
│       ▼                                                                     │
│  workflows/                      ← Multi-shot examples (proven patterns)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### What Changes

| Before | After |
|--------|-------|
| 7 skills | 2 skills (init + refresh) |
| 10+ function libraries | Reference docs (optional reading) |
| Skill per domain (projects, milestones, protection) | LLM composes directly with `gh` |
| Functions wrap every operation | LLM uses `gh` + corpus for syntax |

### What Stays

| Component | Why |
|-----------|-----|
| `hiivmind-pulse-gh-init` | Procedural work: validates auth, discovers structure, caches IDs |
| `hiivmind-pulse-gh-refresh` | Keeps cached config in sync |
| `config.yaml` output | Cached IDs are essential - LLM can't discover these without guidance |
| `user.yaml` output | Personal identity and permissions |

### What Goes

| Component | Why |
|-----------|-----|
| `hiivmind-pulse-gh-projects` | LLM can compose GraphQL with corpus + examples |
| `hiivmind-pulse-gh-milestones` | LLM can use REST API with corpus |
| `hiivmind-pulse-gh-investigate` | LLM can query directly with cached IDs |
| `hiivmind-pulse-gh-branch-protection` | LLM can use REST/GraphQL with routing guide |
| Function libraries (as runtime deps) | Become reference docs, not sourced code |

---

## New File Structure

```
hiivmind-pulse-gh/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── hiivmind-pulse-gh-init/           # Consolidated: user + workspace
│   │   └── SKILL.md
│   └── hiivmind-pulse-gh-refresh/        # Maintenance only
│       └── SKILL.md
├── reference/
│   ├── api-routing.md                     # Decision trees: which API for what
│   ├── config-schema.md                   # How to read/use config.yaml
│   └── workflows/                         # Multi-shot examples
│       ├── issue-to-project.md
│       ├── setup-branch-protection.md
│       ├── manage-milestones.md
│       ├── project-status-update.md
│       └── bulk-operations.md
├── templates/
│   ├── config.yaml.template
│   └── user.yaml.template
├── lib/github/                            # DEMOTED: reference only, not sourced
│   ├── README.md                          # "These are reference implementations"
│   └── ... (existing files for reference)
└── CLAUDE.md                              # Points to new architecture
```

---

## The Three Layers

### Layer 1: Initialization (Procedural)

**Skill:** `hiivmind-pulse-gh-init`

This is the only skill that does *procedural work*. It:
1. Validates `gh` CLI, `jq`, `yq`
2. Checks auth scopes
3. Detects workspace from git remote
4. Discovers projects, fields, options
5. Caches everything to `config.yaml`
6. Saves user identity to `user.yaml`

**Why it can't be replaced:** These are multi-step operations with conditional logic. An LLM without guidance would waste tokens discovering this.

### Layer 2: Routing Intelligence (Reference)

**File:** `reference/api-routing.md`

Decision trees extracted from the current index files:

```markdown
## Milestones
| Intent | API | Why |
|--------|-----|-----|
| List/query | GraphQL | Better pagination, field selection |
| Create/update/delete | REST | Not available in GraphQL |
| Set on issue | GraphQL | updateIssue mutation |

## Protection
| Intent | API | Why |
|--------|-----|-----|
| Legacy branch rules | REST | BranchProtectionRule is read-only in GraphQL |
| Modern rulesets | GraphQL | Full CRUD support |
| Check what applies | REST | /repos/{owner}/{repo}/rules/branches/{branch} |

## Projects v2
| Intent | API | Why |
|--------|-----|-----|
| Everything | GraphQL | Designed for GraphQL |
| EXCEPT views | UI only | No createProjectV2View mutation |
| Field options | GraphQL | updateProjectV2Field replaces ALL options |
```

### Layer 3: JIT Specifics (Corpus)

**Plugin:** `hiivmind-corpus-github`

When the LLM knows *which* API to use (from routing), it gets specifics from the corpus:
- GraphQL schema: exact type/mutation/input definitions
- REST endpoints: paths, parameters, response shapes
- CLI syntax: `gh` command options

**Example flow:**
1. User: "Create a milestone for v2.0"
2. LLM reads `api-routing.md`: Milestones → Create → REST
3. LLM invokes `github-navigate` skill, searches for "create milestone REST"
4. Corpus returns: `POST /repos/{owner}/{repo}/milestones`
5. LLM reads config.yaml for owner/repo
6. LLM executes: `gh api /repos/hiivmind/repo/milestones -f title="v2.0"`

### Layer 4: Patterns (Examples)

**Directory:** `reference/workflows/`

Multi-shot examples showing complete flows. Each example:
- States the goal
- Shows prerequisite context loading
- Walks through the API calls
- Includes error handling

---

## Integration with hiivmind-corpus-github

The corpus is the **specifics engine**. The routing guide tells you *what* to look up.

### CLAUDE.md Addition

```markdown
## GitHub API Operations

After running `hiivmind-pulse-gh-init`:

1. **Load context:** Read `.hiivmind/github/config.yaml`
2. **Check routing:** Read `reference/api-routing.md` to choose API
3. **Get specifics:** Use `github-navigate` skill for exact syntax
4. **Follow patterns:** Check `reference/workflows/` for similar operations

### Quick Lookups

| Need | Corpus Path |
|------|-------------|
| GraphQL type definition | `graphql-schema:schema.docs.graphql` (grep) |
| REST endpoint | `sections/rest.md` → find path |
| `gh` command | `sections/github-cli.md` |
| Projects v2 | `sections/issues.md` → Projects subsection |
```

---

## Migration Path

### Phase 1: Create New Structure
1. Create `reference/api-routing.md` (distilled from index files)
2. Create `reference/workflows/` with 3-5 key examples
3. Consolidate init skills into single `hiivmind-pulse-gh-init`

### Phase 2: Update CLAUDE.md
1. Point to new architecture
2. Add corpus integration guidance
3. Deprecate direct function library usage

### Phase 3: Demote Function Libraries
1. Add `lib/github/README.md` explaining these are reference only
2. Update skill descriptions to not reference sourcing functions
3. Keep files for reference but don't require sourcing

### Phase 4: Remove Old Skills
1. Archive `hiivmind-pulse-gh-projects`
2. Archive `hiivmind-pulse-gh-milestones`
3. Archive `hiivmind-pulse-gh-branch-protection`
4. Archive `hiivmind-pulse-gh-investigate`

---

## Expected Outcomes

### Reduced Ambiguity
- Before: "Which of 7 skills handles this?"
- After: "Init once, then compose with routing + corpus"

### Reduced Token Usage
- Before: Load skill SKILL.md + function library for each domain
- After: Load routing guide once, JIT load from corpus

### Improved Composability
- Before: Skill boundaries limit cross-domain operations
- After: LLM freely composes across domains with same context

### Better Maintenance
- Before: Update bash functions when API changes
- After: Corpus auto-updates from upstream docs

---

## Open Questions

1. **Should we keep `investigate` as a lightweight skill?**
   - It provides deep-dive context that might be hard to compose
   - Could become a workflow example instead

2. **How do we handle offline scenarios?**
   - Corpus requires git clone of github/docs
   - Could bundle essential schema snippets in reference/

3. **What about complex multi-step operations?**
   - Workflow examples should cover common patterns
   - LLM can compose novel operations from primitives
