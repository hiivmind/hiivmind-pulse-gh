# Healthcheck Check Catalog

> **Purpose:** Extensible catalog of all governance checks. Add new checks here — no skill changes needed.

---

## How to Read This Catalog

Each check defines:

| Field | Description |
|-------|-------------|
| **ID** | Unique identifier used in healthcheck.yaml |
| **Category** | `security`, `governance`, `automation`, `documentation` |
| **Severity** | `high` (blocks maturity grade A/B), `medium` (informational) |
| **Pass** | Condition for passing |
| **Warn** | Condition for warning (partial compliance) |
| **Fail** | Condition for failure |
| **Data Source** | Where to get evaluation data (cache or API) |
| **Fix Action** | What to suggest when failing |

---

## Checks

### `branch_protection`

| Field | Value |
|-------|-------|
| Category | security |
| Severity | high |
| Pass | Default branch has protection rules OR rulesets with `enforcement: active` |
| Warn | Protection exists but `enforce_admins: false` or no required reviews |
| Fail | No protection rules and no active rulesets on default branch |
| Local Data | `.hiivmind/github/repos/{name}.yaml` → `.branch_protection.{default_branch}.enabled`, `.rulesets[]` |
| API Fallback | `GET /repos/{owner}/{repo}/branches/{default_branch}/protection` (404 = no protection) |
| Fix Action | `/gh protect branch {default_branch}` via gh-operations |

---

### `project_linkage`

| Field | Value |
|-------|-------|
| Category | governance |
| Severity | medium |
| Pass | Repo appears in at least one project's linked repos |
| Warn | — |
| Fail | Repo not linked to any project |
| Local Data | `.hiivmind/github/config.yaml` → `.projects.catalog[]`, `.hiivmind/github/relationships.yaml` → `.project_repo_links` |
| API Fallback | GraphQL: `repository(name:) { projectsV2(first:1) { totalCount } }` |
| Fix Action | `/gh add repo to project` via gh-operations |

---

### `issue_triage`

| Field | Value |
|-------|-------|
| Category | governance |
| Severity | medium |
| Pass | Labels include at least: one bug-type label (`bug`, `defect`) AND one priority label (`priority`, `P0`-`P4`, `critical`, `high`, `medium`, `low`) |
| Warn | Has bug-type label but no priority labels (or vice versa) |
| Fail | Missing both bug-type and priority labels |
| Local Data | `.hiivmind/github/repos/{name}.yaml` → `.labels[].name` |
| API Fallback | `GET /repos/{owner}/{repo}/labels` |
| Fix Action | `/gh create label` via gh-operations (suggest standard set) |

**Label matching (case-insensitive):**
- Bug-type: `bug`, `defect`, `error`, `incident`
- Priority: any label containing `priority`, `P0`, `P1`, `P2`, `P3`, `P4`, `critical`, `urgent`

---

### `ci_cd`

| Field | Value |
|-------|-------|
| Category | automation |
| Severity | high |
| Pass | At least one workflow file exists in `.github/workflows/` |
| Warn | — |
| Fail | No workflow files found |
| Local Data | Filesystem: `ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null` (current repo only) |
| API Fallback | `GET /repos/{owner}/{repo}/actions/workflows` → check `total_count > 0` |
| Fix Action | Suggest creating a basic CI workflow |

---

### `releases`

| Field | Value |
|-------|-------|
| Category | automation |
| Severity | medium |
| Pass | At least one release exists OR a release workflow is present |
| Warn | Tags exist but no formal releases |
| Fail | No releases, no tags, no release workflow |
| Local Data | API only (always live) |
| API Fallback | `GET /repos/{owner}/{repo}/releases?per_page=1` + `GET /repos/{owner}/{repo}/tags?per_page=1` |
| Fix Action | `/gh create release` via gh-operations |

---

### `documentation`

| Field | Value |
|-------|-------|
| Category | documentation |
| Severity | medium |
| Pass | `README.md` exists AND (`CONTRIBUTING.md` exists OR `docs/` directory exists) |
| Warn | `README.md` exists but no `CONTRIBUTING.md` and no `docs/` |
| Fail | No `README.md` |
| Local Data | Filesystem: check file existence (current repo only) |
| API Fallback | `GET /repos/{owner}/{repo}/readme` (404 = no README), `GET /repos/{owner}/{repo}/contents/CONTRIBUTING.md`, `GET /repos/{owner}/{repo}/contents/docs` |
| Fix Action | Suggest creating missing documentation files |

---

### `codeowners`

| Field | Value |
|-------|-------|
| Category | governance |
| Severity | medium |
| Pass | CODEOWNERS file exists in any standard location |
| Warn | — |
| Fail | No CODEOWNERS file found |
| Local Data | Filesystem: check `CODEOWNERS`, `.github/CODEOWNERS`, `docs/CODEOWNERS` (current repo only) |
| API Fallback | `GET /repos/{owner}/{repo}/contents/CODEOWNERS`, `.github/CODEOWNERS`, `docs/CODEOWNERS` (first 200 status wins) |
| Fix Action | Suggest creating CODEOWNERS file |

---

### `security_policy`

| Field | Value |
|-------|-------|
| Category | security |
| Severity | high |
| Pass | `SECURITY.md` exists in repo root or `.github/` |
| Warn | — |
| Fail | No SECURITY.md found |
| Local Data | Filesystem: check `SECURITY.md`, `.github/SECURITY.md` (current repo only) |
| API Fallback | `GET /repos/{owner}/{repo}/contents/SECURITY.md`, `GET /repos/{owner}/{repo}/contents/.github/SECURITY.md` |
| Fix Action | Suggest creating SECURITY.md with responsible disclosure template |

---

### `license`

| Field | Value |
|-------|-------|
| Category | documentation |
| Severity | medium |
| Pass | LICENSE file exists (any variant: `LICENSE`, `LICENSE.md`, `LICENSE.txt`) |
| Warn | — |
| Fail | No LICENSE file found |
| Local Data | Filesystem: `ls LICENSE* 2>/dev/null` (current repo only) |
| API Fallback | `GET /repos/{owner}/{repo}/license` (404 = no license) |
| Fix Action | Suggest adding a LICENSE file via GitHub UI (license picker) |

---

### `dependency_management`

| Field | Value |
|-------|-------|
| Category | security |
| Severity | high |
| Pass | Dependabot config (`.github/dependabot.yml` or `.github/dependabot.yaml`) OR Renovate config (`renovate.json`, `.github/renovate.json`, `.renovaterc`, `.renovaterc.json`) exists |
| Warn | — |
| Fail | No dependency management tool configured |
| Local Data | Filesystem: check all config file paths (current repo only) |
| API Fallback | `GET /repos/{owner}/{repo}/contents/.github/dependabot.yml`, then Renovate paths |
| Fix Action | Suggest creating `.github/dependabot.yml` or `renovate.json` with ecosystem detection |

---

### `secrets_scanning`

| Field | Value |
|-------|-------|
| Category | security |
| Severity | high |
| Pass | `security_and_analysis.secret_scanning.status == "enabled"` AND `secret_scanning_push_protection.status == "enabled"` |
| Warn | Secret scanning enabled but push protection disabled |
| Fail | Secret scanning not enabled |
| Local Data | API only (always live — not cached) |
| API Fallback | `GET /repos/{owner}/{repo}` → `.security_and_analysis.secret_scanning.status`, `.security_and_analysis.secret_scanning_push_protection.status` |
| Fix Action | Enable via repository settings UI (requires admin access) |

**Note:** This check may return limited data for repos where the authenticated user lacks admin access. In that case, mark as `unknown` rather than `fail`.

---

## Grading Scale

| Grade | Score Range | Meaning |
|-------|-------------|---------|
| A | 10-11 / 11 | Excellent governance |
| B | 8-9 / 11 | Good, minor gaps |
| C | 6-7 / 11 | Moderate, attention needed |
| D | 4-5 / 11 | Significant gaps |
| F | 0-3 / 11 | Critical governance gaps |

**Scoring:** Each scorecard supplies the check weight. `pass` earns the full
weight, `warn` half, and `fail` zero. `unknown`, `not_applicable`,
`unsupported`, and `error` are excluded from the score denominator. Only
`unsupported` reduces adapter coverage. Use `evaluate_checks.py::score_checks`
for arithmetic; do not reimplement scoring in a skill.

---

## Adding a New Check

1. Add entry to this file following the format above
2. Add evaluation logic to `lib/patterns/healthcheck-evaluation.md`
3. Update the total count in grading scale if applicable
4. No skill changes required — the skill reads this catalog dynamically
