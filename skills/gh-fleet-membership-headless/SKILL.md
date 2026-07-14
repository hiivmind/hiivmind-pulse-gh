---
name: gh-fleet-membership-headless
description: >
  Reconcile an organization's live GitHub repository set with the workspace catalog and
  create evidence-backed, non-authoritative profile proposals. Zero prompts; use for scheduled
  fleet-watch runs, new repository detection, rename/transfer reconciliation, and catalog drift.
inputs:
  workspace_path: "required — absolute workspace root containing .hiivmind/github/"
  apply_catalog: "optional boolean — patch stable repository facts in config.yaml (default false)"
  mode: "optional — actor mode recorded in the result: interactive | scheduled (default scheduled)"
outputs:
  result_file: "fleet-membership-result.yaml conforming to lib/patterns/headless-contract.md"
author: hiivmind
---

# Headless Fleet Membership

Reconcile live organization membership, then propose repository profiles from
F0 evidence. Registration and onboarding are deliberately separate: the only
optional mutation is an atomic workspace catalog patch containing stable
repository facts only.

## Contract and boundaries

- Zero prompts and no workspace discovery. `workspace_path` is explicit.
- `apply_catalog=false` by default. True may update only `repositories` in
  `.hiivmind/github/config.yaml` through `fleet_membership.py --apply-catalog`.
- Profile proposals remain `asks_recorded` until a separate confirmation patch.
- This skill never seeds labels, milestones, scheduler files, governance,
  checklists, or any other profile-dependent onboarding action.
- It never mutates a repository or GitHub. It never commits or pushes workspace
  metadata; an orchestrator owns the PR boundary.
- Every exit writes and validates the result file.

`{PLUGIN_ROOT}` is the plugin root. Compute:

```text
CONFIG_DIR = {workspace_path}/.hiivmind/github
CONFIG = CONFIG_DIR/config.yaml
PROFILES = CONFIG_DIR/profiles.yaml
EVIDENCE = CONFIG_DIR/fleet-evidence.yaml
RESULT = CONFIG_DIR/fleet-membership-result.yaml
APPLY = {apply_catalog input, default false}
MODE = {mode input, default scheduled}
RUN_AT = one quoted UTC ISO-8601 timestamp
TMP = a fresh temporary directory outside the workspace
ERRORS = []
```

## Phase 1: FETCH

Validate that `workspace_path`, `CONFIG`, `workspace.type: organization`, `gh`,
and `jq` exist. Resolve `LOGIN` from `workspace.login`, `GH_LOGIN` from the
authenticated GitHub identity (or `unknown` plus an error), and `MACHINE` from
the hostname. Reject modes other than `interactive | scheduled`.

Fetch every live repository page as JSON and flatten the pages:

```bash
gh api --paginate --slurp \
  "/orgs/${LOGIN}/repos?per_page=100&type=all&sort=full_name&direction=asc" \
  | jq '[.[][]]' > "$TMP/org-repos.json"
```

A fetch failure is an ABORT. Never treat an empty or failed response as proof
that every catalog repository was transferred.

## Phase 2: DIFF

Run the identity-safe pure diff without mutation:

```bash
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/fleet_membership.py" \
  --org-repos "$TMP/org-repos.json" \
  --config "$CONFIG" > "$TMP/membership.json"
```

Node ID is rename/transfer identity. The diff applies
`fleet_membership.discovery`, reports exclusions and missing entries, and emits
a complete `catalog_patch` containing only `name`, `id`, `full_name`,
`default_branch`, `is_public`, `archived`, `fork`, and `mirror_url`.

## Phase 3: LOAD F0 EVIDENCE

Invoke `hiivmind-pulse-gh:gh-fleet-evidence-headless` with the same
`workspace_path` and `mode=refresh`. Consume only the validated `EVIDENCE`
artifact it writes. Nave unavailable or a repository absent from evidence is a
degraded observation, not a negative profile signal and not a membership fact.

If no valid evidence artifact is available, write an empty normalized evidence
snapshot to `$TMP/evidence.yaml`, append an error, and continue with empty
candidate lists. Membership reconciliation must not depend on Nave coverage.

## Phase 4: PROPOSE PROFILES

If `PROFILES` exists, run deterministic proposal rules for the policy-included
repositories:

```bash
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/profile_proposals.py" \
  --evidence "$EVIDENCE" \
  --profiles "$PROFILES" \
  --repos "$TMP/membership.json" > "$TMP/proposals.json"
```

On failure, append the error and use `profile_proposals: []`. Do not invent a
fallback profile. Optional inferred explanations may annotate the completed
candidate list only; they cannot add, remove, or reorder candidates.

## Phase 5: APPLY CATALOG

When `APPLY=false`, do not edit `CONFIG`; set `catalog_updated: false` and add a
catalog-review entry to `proposed_actions` when the emitted patch differs.

When `APPLY=true`, rerun the same diff against the same fetched snapshot with
the explicit mutation flag:

```bash
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/fleet_membership.py" \
  --org-repos "$TMP/org-repos.json" \
  --config "$CONFIG" \
  --apply-catalog > "$TMP/membership-applied.json"
```

Use the applied output as membership state. The script atomically replaces
only the `repositories` value and reports whether bytes needed changing. Never
commit or push the workspace; the orchestrator opens the metadata PR.

## Phase 6: WRITE + VALIDATE

Write `RESULT` with:

```yaml
contract_version: 1
kind: fleet-membership
workspace: "{LOGIN}"
run_at: "{RUN_AT}"
actor: {gh_login: "{GH_LOGIN}", machine: "{MACHINE}", mode: "{MODE}"}
org_repos: []                 # membership.org_repos
catalog_repos: []             # membership.catalog_repos
catalog_updated: false        # membership.catalog_updated
profile_proposals: []         # proposals.profile_proposals
findings: []                  # membership.findings
proposed_actions: []          # unapplied catalog patch/review actions only
asks_recorded: []             # one profile-confirmation ask per non-empty proposal
errors: []
```

Validate before reporting success:

```bash
uv run "{PLUGIN_ROOT}/lib/pulse/scripts/validate_result.py" \
  "$RESULT" --kind fleet-membership
```

Profile-dependent governance, labels, milestones, schedulers, and checklists
may be proposed only by later onboarding workflows after profile confirmation.

## ABORT semantics

On ABORT, write the same contract with empty repository/proposal/finding/action
lists, `catalog_updated: false`, and the reason in `errors`; validate it and
stop. If the requested result location is unavailable, write to a temporary
path and report that path.
