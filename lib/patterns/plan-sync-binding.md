# Pattern: Plan Synchronization Binding

A plan document can opt into GitHub issue reconciliation with a `sync:` block
in its YAML frontmatter. Frontmatter fields outside `sync:` are preserved by
the parser and are not part of this binding contract.

```yaml
sync:
  issue: {repo: owner/name, number: 42}
  policy:
    title: conflict
    state: conflict
    assignees: conflict
    milestone: conflict
    body: conflict
  base:
    blob: <git blob SHA of the doc at last reconciliation>
    title: "..."
    state: open
    assignees: [a, b]
    milestone: "v2.0"
```

`base.blob` is required and must be a non-empty string. It identifies the
document version used for the last reconciliation. `policy` values are one of
`conflict` (the default), `prefer-doc`, or `prefer-github`. Unknown keys under
`sync:` are invalid.

## V1 synchronized fields

V1 reconciles only these issue fields:

- `title`
- `state`
- `assignees`
- `milestone`
- `body`

`assignees` are recorded as a sorted, deduplicated list. `milestone` is a
milestone title or `null`.

## V1 exclusions

V1 does not synchronize GitHub Projects custom fields, labels, or comments.

## V1 limitation: propose-only, apply-mode deferred

F8 is **propose-only** end to end (see the plan's Global Constraints): the doc
path is proposed as an F6 `plan-sync-doc-patch` repo mutation and the GitHub
path as a Pulse proposed action, and **neither is ever applied**. One aspect of
the doc transformation is defined but not yet execution-safe, and
must be closed before any apply-mode consumer runs `plan-sync-doc-patch`:

- **Bound-path enforcement.** The transformation's output allowlist is the
  *per-binding dynamic* document path, but the F6 registry allowlist and
  `validation` are static — the entry carries `validation: {kind: none}`, and
  the bound path is currently self-attested by the (caller-authored) patch
  descriptor. Apply mode needs the bound path carried as immutable proposal
  metadata that the F6 orchestrator enforces, plus a "this exact path changed"
  validation kind. `apply_doc_patch.py` already verifies the base-blob match and
  rejects path escapes, but that is script-level, not orchestrator-level.

These are backlogged as an F6/apply-mode enhancement; they do not affect
propose-mode correctness (the argv is recorded, never executed; no validation
runs).
