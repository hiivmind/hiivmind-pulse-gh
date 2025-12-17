# GitHub Actions Operations Examples

Examples of workflow and actions operations using hiivmind-pulse-gh.

**Note:** All Actions operations use REST API.

## Trigger Workflow

**Natural language:**
```
/hiivmind-pulse-gh trigger workflow ci.yml
/hiivmind-pulse-gh run deploy workflow on main
/hiivmind-pulse-gh dispatch workflow "build.yml" with inputs
```

**Prerequisites:** Workflow must have `workflow_dispatch` trigger configured.

**REST endpoint:**
```
POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches
```

**Request body:**
```json
{
  "ref": "main",
  "inputs": {
    "environment": "staging",
    "debug": "true"
  }
}
```

**CLI shortcut (recommended):**
```bash
gh workflow run ci.yml --ref main
gh workflow run deploy.yml -f environment=staging -f debug=true
```

---

## List Workflow Runs

**Natural language:**
```
/hiivmind-pulse-gh list workflow runs
/hiivmind-pulse-gh show recent CI runs
/hiivmind-pulse-gh list failed workflow runs
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/actions/runs?status=failure
```

**CLI shortcut:**
```bash
gh run list
gh run list --status failure
gh run list --workflow ci.yml
```

---

## View Workflow Run Details

**Natural language:**
```
/hiivmind-pulse-gh show run 12345678
/hiivmind-pulse-gh view workflow run details
/hiivmind-pulse-gh check run status for 12345678
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/actions/runs/{run_id}
```

**CLI shortcut:**
```bash
gh run view 12345678
gh run view 12345678 --log
```

---

## Cancel Workflow Run

**Natural language:**
```
/hiivmind-pulse-gh cancel run 12345678
/hiivmind-pulse-gh stop workflow run 12345678
```

**REST endpoint:**
```
POST /repos/{owner}/{repo}/actions/runs/{run_id}/cancel
```

**CLI shortcut:**
```bash
gh run cancel 12345678
```

---

## Re-run Workflow

**Natural language:**
```
/hiivmind-pulse-gh rerun workflow 12345678
/hiivmind-pulse-gh retry failed run 12345678
/hiivmind-pulse-gh rerun failed jobs in 12345678
```

**REST endpoints:**
```
POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun        # Full rerun
POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs  # Failed only
```

**CLI shortcut:**
```bash
gh run rerun 12345678
gh run rerun 12345678 --failed
```

---

## List Workflows

**Natural language:**
```
/hiivmind-pulse-gh list workflows
/hiivmind-pulse-gh show available workflows
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/actions/workflows
```

**CLI shortcut:**
```bash
gh workflow list
```

---

## Set Repository Secret

**Natural language:**
```
/hiivmind-pulse-gh set secret API_KEY
/hiivmind-pulse-gh create secret DATABASE_URL with value
/hiivmind-pulse-gh update secret DEPLOY_TOKEN
```

**What happens:**
1. Get repository public key for encryption
2. Encrypt secret value using libsodium
3. PUT encrypted secret to API

**REST endpoint:**
```
PUT /repos/{owner}/{repo}/actions/secrets/{secret_name}
```

**Request body:**
```json
{
  "encrypted_value": "base64-encoded-encrypted-value",
  "key_id": "repository-public-key-id"
}
```

**CLI shortcut (handles encryption automatically):**
```bash
gh secret set API_KEY
gh secret set API_KEY --body "secret-value"
gh secret set API_KEY < secret-file.txt
```

---

## List Secrets

**Natural language:**
```
/hiivmind-pulse-gh list secrets
/hiivmind-pulse-gh show repository secrets
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/actions/secrets
```

**Note:** Only returns secret names, not values (secrets are write-only).

**CLI shortcut:**
```bash
gh secret list
```

---

## Delete Secret

**Natural language:**
```
/hiivmind-pulse-gh delete secret OLD_API_KEY
/hiivmind-pulse-gh remove secret UNUSED_TOKEN
```

**REST endpoint:**
```
DELETE /repos/{owner}/{repo}/actions/secrets/{secret_name}
```

**CLI shortcut:**
```bash
gh secret delete OLD_API_KEY
```

---

## Set Repository Variable

**Natural language:**
```
/hiivmind-pulse-gh set variable ENVIRONMENT to "production"
/hiivmind-pulse-gh create variable APP_VERSION
/hiivmind-pulse-gh update variable DEBUG_MODE to "false"
```

**REST endpoint (create):**
```
POST /repos/{owner}/{repo}/actions/variables
```

**Request body:**
```json
{
  "name": "ENVIRONMENT",
  "value": "production"
}
```

**REST endpoint (update):**
```
PATCH /repos/{owner}/{repo}/actions/variables/{name}
```

**CLI shortcut:**
```bash
gh variable set ENVIRONMENT --body "production"
```

---

## List Variables

**Natural language:**
```
/hiivmind-pulse-gh list variables
/hiivmind-pulse-gh show repository variables
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/actions/variables
```

**CLI shortcut:**
```bash
gh variable list
```
