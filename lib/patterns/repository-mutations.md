# Repository-file mutations via Nave pens

Repository-file writes never happen through raw shell commands or a
second checkout mechanism — they route through a Nave pen
(`lib/pulse/scripts/nave_adapter.py`, F6 Task 1), driven by a typed
mutation proposal validated against a strict, committed transformation
registry (`lib/pulse/scripts/mutation_plan.py`, F6 Task 2). Task 3's pen
orchestrator (`pen_orchestrator.py`) consumes a validated `Proposal`, walks
it through `planned -> created -> executed -> validated -> proposed |
blocked | failed`, and is the only caller that actually drives
`nave_adapter.pen_create` / `pen_exec`. This document is the normative
contract those two modules implement; both modules are pure — no
subprocess calls, no filesystem writes, no Nave interaction.

## Global constraints (repeated from the F6 plan)

- `nave pen exec` arbitrary commands are user-gated unless mapped to a
  registered transformation.
- Automatic/scheduled mode permits only registered transformation IDs with
  `allow_scheduled: true`.
- Default mutation policy is propose-only: create/run locally, no push.
- Stale or dirty pens block application.
- Pulse records actor, machine, Nave version, pen name, selection, command
  ID, and per-repo outcome.

## The proposal

`mutation_plan.build_proposal(...)` constructs and validates a `Proposal`:

```text
{id, selection, transformation, expected_shas, mutation_policy, actor}
```

| Field | Shape | Meaning |
|---|---|---|
| `id` | non-empty string | Caller-assigned identifier for this proposal/run. |
| `selection` | list of `owner/name` strings, non-empty, no duplicates | The repositories this proposal targets. Resolving a fleet query (Nave `search`/`match` terms) into this concrete repo list is the caller's job — `mutation_plan` never talks to Nave. |
| `transformation` | string | A registered transformation ID (`TransformationRegistry` key). |
| `expected_shas` | dict `owner/name -> sha` | The expected-base guard: keys must be **exactly** `selection`, no more, no fewer. The orchestrator (Task 3) compares this against each repo's current SHA before executing and blocks on any mismatch — a stale base is never silently mutated. Since no Nave surface exposes a per-repo SHA, this comparison runs through an injectable `read_repo_head` reader `execute` accepts (same seam pattern as `read_repo_file`); with `expected_shas` non-empty and no reader supplied, verification fails closed. |
| `mutation_policy` | one of `propose`, `allow-listed`, `allow` | See below. Default: `propose`. |
| `actor` | `{gh_login, machine, mode}` | Same shape as the headless result contract's `actor:` block (`lib/patterns/headless-contract.md`); `mode` is `interactive` or `scheduled`. |

### `mutation_policy` values

Reused verbatim from the `on_mutation` headless-workflow vocabulary
(`lib/patterns/workflow-execution.md` § Headless Execution) — repository
mutations are not a separate policy dialect from GitHub-object mutations:

- **`propose`** (default) — create the pen, run the transformation locally,
  report the resulting diff/status as a proposed action. Never commits or
  pushes. This is what "default mutation policy is propose-only" means in
  pen terms: `pen_exec` is called with `commit=False, push_changes=False`.
- **`allow-listed`** — commit/push only when the proposal's transformation
  is itself the allow-listed capability (registry membership + a scheduled
  run's `allow_scheduled: true` gate stand in for the workflow-level
  `mutation_allowlist`); otherwise behaves like `propose`.
- **`allow`** — commit and push are permitted outright, subject to every
  other gate below (still requires a registered transformation; still
  blocks on a stale/dirty pen or a validation failure).

## The transformation registry

`mutation_plan.load_registry(path_or_dict)` loads and cross-validates
`templates/transformations.yaml.template`-shaped content into a
`TransformationRegistry`. Each entry:

```text
{id, command_argv, applies_to, validation, allow_scheduled}
```

| Field | Shape | Meaning |
|---|---|---|
| `id` | string, must match its registry key | The transformation ID proposals reference. |
| `command_argv` | non-empty list of plain strings | The **exact** argv passed to `nave_adapter.pen_exec` after `--`. No nested structures (lists/dicts as elements are rejected), no booleans. |
| `applies_to` | non-empty list of predicates | OR-matched repository eligibility, in the same grammar `profile_dispatch.py` uses for scorecard-check applicability: `always`, `profile:<id>`, `capability:<id>`, `evidence_path:<glob>`. `mutation_plan.transformation_applies(entry, profiles, capabilities, evidence_paths)` evaluates it. |
| `validation` | `{kind: none \| json_schema, ...}` | Post-execution check the orchestrator runs after `pen_exec` succeeds. `kind: none` takes no extra fields. `kind: json_schema` requires `path` (repo-relative file the transformation is expected to produce/modify) and `schema` (inline JSON Schema mapping the file's parsed content must satisfy). A validation failure is a `blocked`/`failed` outcome, never a silent pass. |
| `allow_scheduled` | boolean | Whether this transformation may run under `actor.mode: scheduled`. Interactive-only transformations (destructive, judgment-requiring, or simply not yet trusted unattended) set this `false`. |

### No shell strings, ever

`command_argv` is a strict argv array. There is no template/command
substitution of any kind — `mutation_plan.resolve_argv(entry)` returns
`entry.command_argv` byte-identical to what was committed, and no proposal
field (repo name, SHA, actor, …) is ever interpolated into it. An argv
element containing shell metacharacters (`` `$(rm -rf /)` ``, `` ; rm -rf / ``,
`` | cat ``, backticks) is passed through as **literal data** to
`subprocess.run(..., shell=False)` (`nave_adapter.NaveRunner.run`) — it is
never parsed or expanded by a shell, because no shell is ever invoked. This
is the same guarantee `nave_adapter.pen_exec`'s docstring makes for its
`command` parameter; the registry is simply the only place argv is allowed
to originate from for anything other than an explicitly user-approved
one-off `pen exec`.

## Gating rules

1. **Unknown transformation ID is a hard error.** `registry.get(id)` /
   `validate_proposal` raise `MutationPlanError` — there is no fallback to
   raw argv.
2. **Scheduled mode requires `allow_scheduled: true`.** A proposal whose
   `actor.mode == "scheduled"` referencing a transformation with
   `allow_scheduled: false` fails validation before anything runs. This is
   the mechanical enforcement of "automatic/scheduled mode permits only
   registered transformation IDs with `allow_scheduled: true`" — unregistered
   or interactive-only commands can never reach an unattended run.
3. **Arbitrary `pen exec` stays user-gated.** `mutation_plan` has no code
   path that turns free-form text into argv; only a registry entry's fixed
   `command_argv` is ever executed by the orchestrator. A human running
   `nave pen exec` directly, outside Pulse, is unaffected — that gate is a
   property of *this* module's proposal path, not of Nave itself.
4. **`expected_shas` must cover the selection exactly.** Every selected
   repo needs a guard SHA; no guard SHA may reference a repo outside the
   selection (that would silently widen the blast radius of a "matched"
   proposal).
5. **Propose-only is the default.** Omitting `mutation_policy` yields
   `propose`; nothing commits or pushes without an explicit, validated
   opt-in.

## Attribution

Every proposal carries the `actor` block Pulse needs to record who/what ran
a mutation: `gh_login`, `machine`, and `mode`. Task 3's orchestrator
combines this with the pen name, the probed Nave version
(`nave_adapter.probe`), the resolved `selection`, the `transformation` ID,
and each repo's exec outcome (from `pen_status --json`) into the
`repo-mutation` result kind (F6 Task 4, `lib/patterns/headless-contract.md`).
Nothing in that attribution record is inferred or reconstructed after the
fact — it is built from the same `Proposal` that gated execution.

## Validation

```text
uv run pytest lib/pulse/scripts/tests/test_mutation_plan.py -q
```

## Related patterns

- `lib/patterns/nave-evidence-contract.md` — read-side Nave fleet evidence.
- `lib/patterns/headless-contract.md` — actor block, mutation-policy
  vocabulary (`on_mutation`), and the `repo-mutation` result kind (F6 Task 4).
- `lib/pulse/scripts/profile_dispatch.py` — the applicability predicate
  grammar `applies_to` reuses.
