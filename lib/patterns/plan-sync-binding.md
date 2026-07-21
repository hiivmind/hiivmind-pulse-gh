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
