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

## Applying F8 changes (apply-mode landed in F11)

F8 **defaults to propose** (see the plan's Global Constraints): the doc path is a
proposed F6 `plan-sync-doc-patch` repo mutation and the GitHub path a Pulse
proposed action. Both **now have a landing path** — **F11 apply-mode** (merged to
`develop` 2026-07-29, PR #138). Under an explicit, gated `allow-listed`
`mutation_policy` the doc path lands via `pen_orchestrator.execute`
(provision `pulse/apply/{id}` → exec → validate → commit-all → push-all → open PR →
merge-detect → base-advance), and the GitHub path lands via `object_apply` under
`on_mutation`. Propose remains the default; landing is always opt-in and PR-gated.
The two V1 blockers this section previously named are both closed:

- **Executor path (closed in F11 Task 1).** `plan-sync-doc-patch` argv now references
  the installed `pulse-apply-doc-patch` console entry point (on `PATH` in any pen
  checkout), not a plugin-repo-relative script.
- **Bound-path enforcement (closed in F11 Task 2).** `plan-sync-doc-patch`
  proposals carry `bound_paths: {repo: [doc_path]}` as immutable proposal
  metadata, enforced by `pen_orchestrator.py` via `validation: {kind: paths_changed}`.
  `apply_doc_patch.py` also verifies base-blob match and rejects path escapes.
