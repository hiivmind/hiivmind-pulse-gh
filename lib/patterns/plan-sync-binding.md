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
path as a Pulse proposed action, and **neither is ever applied**.

- **Bound-path enforcement (closed in F11 Task 2).** `plan-sync-doc-patch`
  proposals carry `bound_paths: {repo: [doc_path]}` as immutable proposal
  metadata, enforced by `pen_orchestrator.py` via `validation: {kind: paths_changed}`.
  `apply_doc_patch.py` also verifies base-blob match and rejects path escapes.
