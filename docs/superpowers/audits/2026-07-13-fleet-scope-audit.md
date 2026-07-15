# Fleet Scope Audit: Plugin Dogfooding vs General GitHub Multi-Repo Management

**Date:** 2026-07-13  
**Scope:** `2026-07-10-lockstep-bindings-and-target-workflows-design.md` and implementation plans W1–W9  
**Question:** Do the design and plans describe a general GitHub multi-repo fleet-management capability, or do they accidentally assume that every repository is a Claude plugin with skills?

## Executive finding

The design has a sound repository-neutral core: bindings, content-addressed state, three-way reconciliation, durable markers, attribution, polling, result contracts, and mutation policy. The scope failure occurs in the catalog overlays and becomes concrete in the plans.

The current plans are primarily a dogfooding program for the `hiivmind` ecosystem, not a general fleet-management implementation. They repeatedly treat plugin concepts as if they were universal repository facts:

- a repository is expected to contain Claude skills;
- `CLAUDE.md` is treated as a fleet-wide documentation authority;
- `plugin.json`/marketplace release identity is treated as a normal dependency/release shape;
- generated downstream files are assumed to be generated skills;
- onboarding classification is biased toward `plugin`, `corpus-data`, `app`, and `test`;
- Python dependency handling is centered on `pyproject.toml`/`uv.lock`, despite the stated goal covering arbitrary third-party dependency coherence;
- the plans’ own validation and close-out steps assume this plugin’s `SKILL.md`, `CLAUDE.md`, `.claude-plugin`, and `skills/` layout.

This is not merely a documentation problem. If implemented as written, a real fleet containing services, libraries, CLIs, front-end applications, infrastructure repositories, data projects, archived repositories, or non-Python code will receive false findings, irrelevant onboarding actions, or skipped coverage. The most serious case is W8: it turns absence of `CLAUDE.md` into a healthcheck failure, making a Claude-specific convention a fleet governance requirement.

The intended correction is not one universal lowest-common-denominator score. A plugin repository should be audited against plugin-specific expectations, a Python repository against Python packaging/runtime expectations, and a Node repository against Node packaging/runtime expectations. Those differentiated audits are valuable; they simply need to be explicit, declared, and comparable at the fleet-reporting layer.

## Scope model that should have been used

The product should distinguish three layers:

1. **Fleet primitives — universal.** Repository identity, default branch, pushed refs, paths, releases, issues, milestones, dependency evidence, relationship edges, result contracts, polling, attribution, and mutation policy.
2. **Repository capabilities — opt-in or detected.** Python packaging, Node packaging, Claude plugin, generated repository, documentation-managed repository, release-managed repository, service, infrastructure, and so on.
3. **Dogfood overlays — this repository family only.** `.claude-plugin/`, `skills/`, `CLAUDE.md`, corpus templates, marketplace manifests, and the hiivmind-specific release/onboarding conventions.

Every check or workflow should declare its applicability predicate and report `not_applicable`/`unknown` when the predicate is not satisfied. It must not convert “capability absent” into “governance failure.”

### Explicit profile-based scoring

The workspace should declare a profile for each repository, either directly or through a reviewed capability-detection proposal:

```yaml
repository_profiles:
  hiivmind-pulse-gh:
    profiles: [claude-plugin, python, control-plane]
    scorecard: plugin-standard-v1
  billing-api:
    profiles: [python, service]
    scorecard: python-service-v1
  web-console:
    profiles: [node, web-application]
    scorecard: node-web-v1
```

A scorecard should define its checks, weights, applicability, and evidence adapters. For example:

```yaml
scorecards:
  python-service-v1:
    checks:
      - id: dependency-lock
        weight: 2
        adapter: python.lockfiles
      - id: ci
        weight: 2
        adapter: github.actions
      - id: documentation
        weight: 1
        adapter: generic.docs
      - id: claude-context
        applicability: capability:claude_context
        weight: 0
  plugin-standard-v1:
    extends: python-service-v1
    checks:
      - id: plugin-manifest
        weight: 2
        adapter: claude.plugin_manifest
      - id: skill-layout
        weight: 1
        adapter: claude.skills
      - id: marketplace-release
        weight: 1
        adapter: hiivmind.marketplace
```

The important distinction is between a repository’s score and the fleet’s coverage view:

- A score is evaluated only against checks applicable to that repository’s declared scorecard.
- `not_applicable` checks do not lower the repository’s score or inflate its denominator.
- `unsupported` checks are excluded from the score but appear as coverage debt.
- Fleet reports compare normalized percentages, profile-specific grades, and coverage gaps; they should not pretend that an `A` on a plugin scorecard is identical to an `A` on a Python-service scorecard.
- A repository may have multiple profiles, but each check has one owner/profile and must not be counted twice.
- Profile changes are durable, reviewable workspace state. Automatic detection can propose a change; it must not silently change the scorecard and thereby change the repository’s grade.

This allows a plugin repository to fail a missing marketplace manifest while a normal Python library is correctly marked `not_applicable`, and allows a Node repository to be assessed using `package.json`/lockfile and Node CI adapters without pretending it is Python.

## Findings

### F1 — Critical: W8 makes Claude-specific documentation mandatory

**Evidence:** W8 states “Missing `CLAUDE.md` is a deterministic fail” and defines a `claude_md_currency` fleet check. Its facts extractor is explicitly built around `skills`, and its dogfood case says “CLAUDE omits three skills.” The design’s shortlist entry 3.6.7 is similarly framed as a repo’s `CLAUDE.md` claims versus “skills, directories, commands.”

**Why this is wrong:** Most GitHub repositories do not use Claude Code, do not have `CLAUDE.md`, and have no `skills/` directory. A missing file is not stale documentation; it is non-applicability. A general fleet manager cannot assign a failing healthcheck score because a repository does not participate in one assistant’s instruction format.

**Required correction:** Recast this as an optional capability check, e.g. `assistant_context_currency`, enabled only by repository policy (`capabilities.claude_context: true`) or an explicit file/profile declaration. For generic fleets, provide separate checks for README/CONTRIBUTING/API docs and command inventory. The default for absent capability must be `not_applicable`, excluded from totals.

### F2 — High: W2 onboarding classification assumes a narrow repository universe

**Evidence:** W2 requires LLM classification of new repositories into `plugin | corpus-data | app | library | test | unknown`; the architecture says classification selects an “onboarding overlay.” The design 3.4 says the cascade applies a governance baseline, labels/milestones, scheduler stub, and class-specific overlay.

**Why this is wrong:** The class list is an internal hiivmind taxonomy, not a general GitHub taxonomy. It omits common fleet classes such as service/API, CLI, web application, mobile, infrastructure/IaC, deployment/configuration, documentation-only, SDK, data pipeline, research/notebook, monorepo, mirror, and archived/read-only. More importantly, it makes classification precede evidence collection and implies that every class deserves a scheduler and the same governance cascade.

**Required correction:** Separate stable facts from policy classification. First collect repository metadata and capability evidence (languages, manifests, workflows, topics, visibility, archived state, owner/team). Then match against workspace-declared profiles and scorecards. Profiles should define which checks, weights, labels, milestones, workflows, and onboarding actions apply. Unknown profiles must produce a review request, not a guessed overlay or automatic mutations. The LLM may suggest a profile, but it must not select mutation scope or silently change a scorecard without confirmation.

### F3 — High: W3 marketplace-sync is a product-specific workflow presented as a catalog phase

**Evidence:** W3’s goal is specifically “a plugin repository’s latest stable release” versus a `hiivmind-marketplace` entry. Its data model requires `plugin_id`; its skill fetches plugin releases; its close-out asks to access “live plugin releases or a marketplace checkout.”

**Why this is wrong:** This is a valid hiivmind dogfood workflow, but it is not a general fleet-management capability and should not be presented as a generic phase after fleet membership. Many repositories have no marketplace entry, no plugin ID, no release tags, or release artifacts managed elsewhere. The plan’s `plugins_checked` and `entries_stale` counters encode the wrong abstraction.

**Required correction:** Move W3 into a named `hiivmind-plugin` overlay or a separate dogfood specification. The general primitive should be `release_artifact_sync` with a configurable artifact registry/manifest binding. Applicability must be explicit; non-plugin repositories should be skipped, not counted as stale.

### F4 — High: W5 scaffold-drift equates generated outputs with generated skills

**Evidence:** The design’s 3.5 examples are `hiivmind-blueprint`, corpus `templates/`, and generated navigate skills. W5’s task is “Dogfood corpus navigate-skill generation”; it invokes an “existing generator/init skill”; the generated manifest examples use `skills/hiivmind-corpus-{name}-navigate/SKILL.md`.

**Why this is wrong:** The manifest mechanism is generalizable, but the plan’s discovery, regeneration, and validation path is not. A general fleet includes generated OpenAPI clients, Terraform modules, protobuf code, SDKs, Helm charts, documentation sites, and codegen outputs. Regenerating a file via a Claude skill is not a safe generic action and can be actively destructive for generated code with language-specific toolchains.

**Required correction:** Keep the content-addressed manifest/audit primitive, but make regeneration an explicitly configured command or workflow per generator profile. A binding must record generator identity, command, toolchain constraints, source paths, output paths, and whether regeneration is automatic or proposal-only. The default action is “report drift”; never infer a generator from a path named `skills/`.

### F5 — High: W1 claims fleet-wide dependency coherence while implementing a narrow ecosystem slice

**Evidence:** W1 says it checks “third-party dependency pin divergence across the fleet,” but its parser set is `pyproject.toml`, `uv.lock`, `package.json`, and `package-lock.json`; the plan’s global constraints and tests center on Python/Node. The design mentions `plugin.json dependencies` but does not define a general manifest adapter model.

**Why this is wrong:** Real Python repositories may use Poetry (`poetry.lock`), PDM (`pdm.lock`), pip-tools (`requirements*.txt`), Conda/environment files, Hatch, or no lockfile. Other fleet members may be Rust, Go, Java, .NET, Ruby, PHP, Swift, or infrastructure repositories. A “fleet” result that silently skips unsupported ecosystems gives false confidence. Conversely, treating an absent supported file as drift can produce false failures.

**Required correction:** Introduce an ecosystem adapter interface and explicit evidence states: `supported`, `unsupported`, `not_applicable`, `unresolved`. Start with a clearly scoped Python adapter family (PEP 621, Poetry, PDM, pip-tools, Conda as separate adapters) and Node adapter family, while preserving unknown ecosystems as visible coverage gaps. Rename the workflow to make its supported scope clear until coverage expands.

### F6 — Medium: W8’s facts model and plan language overfit this repository’s layout

**Evidence:** W8’s facts output is `{skills, directories, commands, files}`; tests create `skills/a/SKILL.md`; the skill fetches and reasons about `CLAUDE.md`; the implementation plan modifies this plugin’s root `SKILL.md`, `README.md`, and workspace gitignore. W2’s close-out likewise requires edits to `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CLAUDE.md`, and skill listings.

**Why this is wrong:** A fleet manager should inspect repository structure, not prescribe one structure. The root `SKILL.md` and `.claude-plugin` are artifacts of the managed tool, not evidence that downstream repositories should have them.

**Required correction:** Move plugin self-description into a dogfood-only validation suite. Generic repository facts should be typed and extensible: files, directories, package manifests, CI workflows, deployment descriptors, docs, language/toolchain signals, and declared ownership metadata. Each check consumes only the facts it needs.

### F7 — Medium: The design’s onboarding cascade conflates fleet registration with repository governance

**Evidence:** Design 3.4 says a new repo triggers catalog registration, governance baseline, labels/milestones, scheduler stub, and a checklist issue. W2 repeats these as default proposed actions for every new repo, regardless of classification confidence.

**Why this is wrong:** Registration is universal; governance and automation are policy-specific. A mirror, archived repository, external vendor mirror, fork, security-sensitive private repo, or intentionally unmanaged experiment may not want labels, milestones, scheduled workflows, or issues. A transferred repository may require ownership review rather than onboarding.

**Required correction:** Split the cascade into independent policy actions with per-action applicability and authorization. The first run should only register metadata and create an `asks_recorded` review. Governance baseline, labels, milestones, scheduler, and checklist issue must each be opt-in by profile and permission policy.

### F8 — Medium: The “general” catalog language hides dogfood examples as normative defaults

**Evidence:** The design says new workflow ideas are bindings, but its live examples repeatedly use hiivmind repositories, corpus repos, plugin marketplace state, generated navigate skills, `CLAUDE.md`, and `plugin.json`. The plans inherit these examples as concrete file paths and expected test fixtures.

**Why this is wrong:** Examples are functioning as architecture. Implementers will copy them into defaults, schemas, and tests, causing the dogfood shape to become the product contract.

**Required correction:** Label examples as `dogfood overlay` or `illustrative instance`; provide neutral examples in the binding spec (e.g. service API, Go library, Terraform module, documentation repository). Add a “scope and applicability” section to every catalog entry and plan header.

### F9 — Medium: Universal workspace assumptions are mixed with local plugin execution assumptions

**Evidence:** Several plans require modifying this repository’s root `SKILL.md`, `README.md`, plugin manifests, and skill structure as part of workflow close-out. W2’s headless skill defines `{PLUGIN_ROOT}` as the location “where plugin.json lives.” W3–W9 continue this convention.

**Why this is wrong:** A fleet-management skill may run from a plugin, a standalone CLI, CI, a scheduler, or another automation host. Requiring a plugin root and `plugin.json` makes the manager unusable outside Claude plugin distribution and confuses the control plane with the managed repositories.

**Required correction:** Define a neutral runtime root and workspace root. Treat plugin packaging as one distribution adapter. Plans should update plugin metadata only in a separate packaging/dogfood task, never as part of fleet workflow correctness.

### F10 — Low: The plans’ test and verification language reinforces dogfooding as correctness

**Evidence:** Tests repeatedly validate `skills/...`, `CLAUDE.md`, plugin assets, corpus navigate skills, and this plugin’s documentation tables. W5’s final dogfood task is explicitly corpus skill generation; W8’s final fixture is missing skills in CLAUDE.md.

**Why this is wrong:** These tests can prove the overlay works, but they cannot prove general fleet behavior. They create a misleading green suite: the product passes its own shape while lacking coverage for common repository variants.

**Required correction:** Maintain two suites:

- `tests/fleet/`: neutral fixtures for services, libraries, CLIs, mixed-language repos, no-lockfile repos, archived repos, mirrors, and unknown profiles;
- `tests/overlays/hiivmind/`: plugin, corpus, marketplace, generated-skill, and CLAUDE.md dogfood fixtures.

Coverage reports should distinguish “not applicable” from “not tested.”

## Workflow-by-workflow scope assessment

| Workflow/plan | General fleet value | Scope risk | Assessment |
|---|---:|---:|---|
| W1 dep-coherence | High | High | Good primitive, underspecified ecosystem coverage and applicability |
| W2 fleet-membership | High | High | Universal diff, but onboarding/classification cascade is hiivmind-biased |
| W3 marketplace-sync | Low outside plugin ecosystems | Critical | Dogfood overlay, not a general fleet phase |
| W4 impact-audit | High | Medium | Strongest general workflow; edge configuration still needs profiles and neutral examples |
| W5 scaffold-drift | High in principle | Critical | General manifest idea, plugin/skill-specific regeneration plan |
| W6 split-repo-currency | Medium | Low | Valid concrete W4 edge; should be an instance configuration, not core product scope |
| W7 contract-propagation | High in principle | Medium | General interface versioning, but current contract examples are plugin-platform contracts |
| W8 claude-md-currency | Low outside Claude users | Critical | Optional dogfood check incorrectly elevated to fleet healthcheck |
| W9 plan-sync | High | Low/Medium | Broadly general; central-repo assumptions and project-specific fields need profile/config boundaries |

## Recommended remediation sequence

### 1. Correct the product boundary before implementing more workflows

Add a short scope contract to the platform design:

```yaml
repository_profile:
  id: service-python
  capabilities: [python, ci, release]
  checks: [dependency-coherence, ci-presence, release-currency]
  onboarding: [catalog-registration, governance-baseline]
  mutation_policy: propose
```

The same workspace may contain multiple profiles. A repository can have zero, one, or several capabilities. Profile assignment is configuration with optional inference, not a universal LLM classification.

### 2. Make applicability first-class in result contracts

For checks and workflow findings, distinguish:

- `pass`, `warn`, `fail`, `unknown` — applicable check outcomes;
- `not_applicable` — capability/profile does not include the check;
- `unsupported` — the repository is in scope but no adapter exists;
- `error` — collection or execution failed.

Do not score `not_applicable` as a failure. Do count `unsupported` in fleet coverage reporting so skipped ecosystems are visible.

### 3. Split the plans into core, adapters, scorecards, and dogfood overlays

- **Core:** W2 membership diff, W4 impact binding, generic polling, result contracts, attribution, mutation policy.
- **Adapters:** dependency ecosystems, release registries, generator commands, documentation formats, contract parsers.
- **Scorecards:** explicit plugin, Python, Node, service, library, and other repository standards, each with its own applicable checks and weights.
- **Dogfood overlays:** W3 marketplace, W5 generated navigate skills, W8 CLAUDE.md currency, this repository’s plugin metadata and skill inventory.

W3 and W8 should be renamed or moved under a `hiivmind`/`claude-plugin` overlay directory. W5 should retain the generic manifest work but remove skill regeneration as its default implementation.

### 4. Add neutral acceptance fixtures before claiming fleet readiness

At minimum, test:

- Python Poetry, PDM, pip-tools, PEP 621, and `uv` repositories;
- a Go service, Rust library, Node application, Terraform repository, and documentation-only repository;
- repositories without `CLAUDE.md`, `skills/`, `plugin.json`, or releases;
- archived, forked, mirrored, transferred, and private repositories;
- a monorepo with multiple package managers;
- an intentionally unmanaged repository that opts out of onboarding actions.

### 5. Keep dogfood checks, but label them honestly

There is real value in dogfooding this plugin’s own structure. It should remain as a separate overlay with explicit enablement and a separate report. That makes the finding actionable without pretending that `CLAUDE.md` and `skills/` are universal GitHub governance primitives.

## Final assessment

The binding architecture is worth keeping. The scope correction is to stop treating the current hiivmind repository family as the ontology of “a repository.” The implementation should first establish a neutral fleet control plane, then attach ecosystem and organization profiles, and finally run the existing plugin/corpus workflows as one dogfood profile. Until that separation is made, the plans should be considered **dogfood implementation plans**, not plans for a general GitHub multi-repo fleet-management skill.
