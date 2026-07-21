# Pattern: Generation Manifest

Generated artifacts are files in a repository that are produced from a
committed template source and are guarded against drift. This document defines
the manifest that records those bindings and the rules the audit engine uses
to classify them. The companion result kind is `generated-artifact`
(`lib/patterns/headless-contract.md` § generated-artifact-result.yaml), validated
by `lib/pulse/scripts/validate_result.py`.

## Binding shape

Each binding is stored in `templates/generated.yaml.template` and loaded by the
F7 Task 2/3 loaders. A binding is a mapping with these fields:

```text
{id, source, branch, template_path, template_tree, generator, files, generated_at}
```

| Field | Shape | Meaning |
|---|---|---|
| `id` | non-empty string | Stable binding identifier, unique within the workspace manifest. |
| `source` | `owner/repo` string | Repository that owns the template source. |
| `branch` | string | Branch in the source repo where the template is resolved. |
| `template_path` | string | Repo-relative path to the template file within `source`. |
| `template_tree` | tree SHA | Git tree SHA of the source repo at the point the files were generated; used to detect template drift. |
| `generator` | string | Registered generator id that produced the files; unknown ids are a load-time error. |
| `files` | non-empty list of `{path, blob}` | Output files guarded by this binding. `path` is repo-relative in the target repo; `blob` is the blob SHA at generation time. |
| `generated_at` | ISO 8601 timestamp | When the files were last generated. |

## Binding validity rules

The following are manifest errors; the loader rejects a binding that violates
any of them. The result validator does not enforce these — it validates the
`generated-artifact` result shape, not the committed manifest.

1. **No duplicate `files[].path` within a binding.** A path may appear only once
   per binding; a duplicate path makes the binding ambiguous.
2. **No empty `files` list.** A binding with nothing to guard is invalid.
3. **`template_tree` must be present.** Drift detection needs a known source tree
   SHA.
4. **Every `files[].blob` must be present.** Customization detection needs the
   blob SHA recorded at generation time.

Validity is computed per binding, so one repository may have multiple bindings
(e.g. one per generator or template source).

## Audit states

For each binding, the audit engine computes one of these states:

| State | Meaning |
|---|---|
| `current` | The generated files match the recorded blobs and the source template tree has not changed. |
| `template-drift` | The source template tree or template path content changed since `generated_at`; the generated files need to be regenerated. |
| `local-customization` | The target file blobs differ from the recorded blobs but the source template did not change; a local edit was made. |
| `conflict` | Both template drift and local customization are present; the generated files cannot be safely regenerated without reconciling the local changes. |
| `error` | The audit could not determine the state (e.g. missing source or target blob, unreachable ref). |

## Findings and proposals

The `generated-artifact` result kind records:

- `bindings_audited`: total number of bindings audited.
- `states`: mapping from binding id to one of the five states above.
- `findings`: typed findings with the same shape as the `impact` kind
  (`{kind, repo, severity, detail}` plus optional `ref` and `inferred`).
- `proposals`: list of `{binding, transformation, proposal_id}` entries. A
  proposal is emitted only when a binding is in `template-drift` state, because
  only template drift can be resolved by re-running a registered generator.
  `local-customization` and `conflict` findings are surfaced without a proposal.

## Result validation

```text
uv run lib/pulse/scripts/validate_result.py generated-artifact-result.yaml --kind generated-artifact
```

## Related patterns

- `lib/patterns/headless-contract.md` — the `generated-artifact` result kind.
- `lib/pulse/scripts/validate_result.py` — result-kind validator.
- `templates/generated.yaml.template` — manifest template with commented examples.
