# Test Fixtures

> **Single source of truth for test data**
> **Status:** Phase 2 - Infrastructure Complete, Recording In Progress

Test fixtures for hiivmind-pulse-gh, recorded from live GitHub APIs and carefully sanitized.

## Directory Structure

```
fixtures/
├── scripts/                       # Recording and maintenance tools
│   ├── record_fixtures.bash       # Record fixtures from live API
│   ├── sanitize_fixture.bash      # Sanitize sensitive data
│   └── detect_fixture_drift.bash  # Detect API schema changes
│
├── recording_manifest.yaml        # What to record and how
├── SCHEMA_DIFFERENCES.md          # Documented API mismatches
│
├── graphql/                       # GraphQL API responses
│   ├── identity/                  # User, org, viewer
│   ├── repository/                # Repo details, lists
│   ├── project/                   # Projects v2
│   ├── issue/                     # Issues
│   ├── pr/                        # Pull requests
│   └── release/                   # Releases
│
├── rest/                          # REST API responses
│   ├── milestone/                 # Milestones
│   ├── protection/                # Branch protection, rulesets
│   ├── action/                    # Workflows, runs, jobs
│   ├── secret/                    # Secrets
│   ├── variable/                  # Variables
│   └── release/                   # Release REST endpoints
│
└── _synthetic/                    # Hand-crafted edge cases
    ├── errors/                    # Error responses
    ├── empty/                     # Empty states
    ├── null_fields/               # Null value scenarios
    └── README.md                  # Synthetic fixture docs
```

## Why Record From Live APIs?

Hand-crafted fixtures test **assumptions**, not reality.

| Approach | Tests Against | Risk |
|----------|---------------|------|
| Hand-crafted | What we *think* the API returns | Tests pass, production fails |
| Live-recorded | What the API *actually* returns | Catches mismatches early |

**Real example from this project:**
- **Assumed:** `viewer.email` field available with `repo` scope
- **Reality:** Requires `user:email` or `read:user` scope
- **Impact:** Would have written code that fails at runtime

See `SCHEMA_DIFFERENCES.md` for all documented mismatches.

## Recording Fixtures

### Prerequisites

```bash
# Authenticate with GitHub CLI
gh auth login

# Verify scopes (need: repo, read:org, project)
gh auth status

# Install dependencies
npm install  # for yq
```

### Record Single Fixture

```bash
cd tests/fixtures
./scripts/record_fixtures.bash --fixture identity viewer
```

Output:
```
[INFO] Recording fixture: identity/viewer
[INFO] Sanitizing fixture...
Sanitized: .../graphql/identity/viewer.json
[SUCCESS] Recorded: .../graphql/identity/viewer.json
```

### Record Entire Domain

```bash
./scripts/record_fixtures.bash --domain milestone
```

Records all fixtures defined for the milestone domain in `recording_manifest.yaml`.

### Record All Fixtures

```bash
./scripts/record_fixtures.bash --all
```

**Warning:** This makes many API calls. Use sparingly to avoid rate limits.

## Sanitization

All recorded fixtures are automatically sanitized to remove:

- **Usernames** → `test-user`
- **Organizations** → `test-org`
- **Emails** → `test@example.com`
- **Node IDs** → Deterministic fake IDs (`I_SANITIZED_ISSUE`, etc.)
- **Timestamps** → Normalized sequential values (preserves chronological order)
- **Avatar URLs** → Generic test URLs
- **Tokens/Secrets** → `sanitized_token`

### Sanitization Pipeline

```bash
# Manual sanitization (if needed)
./scripts/sanitize_fixture.bash identity viewer path/to/fixture.json
```

The sanitization preserves:
- ✅ Field names
- ✅ Data types
- ✅ Object/array structure
- ✅ Chronological relationships
- ✅ Null values

But removes:
- ❌ Personal data
- ❌ Credentials
- ❌ Actual timestamps
- ❌ Real IDs

## Drift Detection

Detect when GitHub API schema changes by comparing recorded fixtures against fresh API calls.

### Check Single Fixture

```bash
./scripts/detect_fixture_drift.bash --fixture identity viewer
```

### Check Entire Domain

```bash
./scripts/detect_fixture_drift.bash --domain milestone
```

### Check All Fixtures

```bash
./scripts/detect_fixture_drift.bash --all
```

**Exit codes:**
- `0` - No drift detected
- `1` - Drift detected or error

**Example output:**
```
[WARNING] Schema drift detected in: rest/milestone/list.json
  + New fields:
    due_on_timestamp
    updated_by.id
  - Removed fields:
    (none)
```

### CI Integration

Drift detection runs weekly in CI:

```yaml
# .github/workflows/fixture-drift.yml
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  detect-drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Detect fixture drift
        run: ./tests/fixtures/scripts/detect_fixture_drift.bash --all
```

## Fixture Naming Convention

```
{domain}/{operation}[_{variant}].json
```

**Examples:**
```
identity/viewer.json              # Current user (GraphQL)
identity/organization.json        # Org details (GraphQL)
milestone/list_all.json           # All milestones (REST)
milestone/list_open.json          # Open only (REST)
project/org_project.json          # Org project with items (GraphQL)
_synthetic/errors/404_not_found.json  # Hand-crafted error
```

## Recording Manifest

The `recording_manifest.yaml` defines:
- Which fixtures to record
- API calls to make
- Sanitization rules
- Last recorded timestamp

**Example entry:**
```yaml
fixtures:
  identity:
    viewer:
      type: graphql
      description: "Current authenticated user"
      query: |
        query {
          viewer {
            id
            login
            name
          }
        }
      sanitize:
        - path: ".data.viewer.name"
          value: "Test User"
      last_recorded: "2024-12-11T10:30:00Z"
```

## Adding New Fixtures

1. **Update manifest:**
   ```yaml
   fixtures:
     my_domain:
       new_fixture:
         type: rest
         description: "What this fixture captures"
         endpoint: "/path/to/endpoint"
         method: "GET"
   ```

2. **Record it:**
   ```bash
   ./scripts/record_fixtures.bash --fixture my_domain new_fixture
   ```

3. **Verify sanitization:**
   ```bash
   cat graphql/my_domain/new_fixture.json | jq '.'
   # Check for any leaked personal data
   ```

4. **Use in tests:**
   ```bash
   local fixture=$(load_rest_fixture "my_domain" "new_fixture")
   ```

## Synthetic Fixtures

Some edge cases can't be recorded naturally:
- Error responses (404, 401, 403, 422)
- Empty states
- Null field scenarios

These are hand-crafted in `_synthetic/` with clear documentation.

See `_synthetic/README.md` for details.

## Schema Differences Log

All discovered mismatches between our assumptions and reality are documented in `SCHEMA_DIFFERENCES.md`.

**Current findings:**
- Identity domain email field requires extra scopes
- Milestone domain can return empty arrays
- Sanitization script needs error response handling

This log guides code improvements and prevents future assumptions.

## Troubleshooting

### "Fixture not found in manifest"

Add the fixture definition to `recording_manifest.yaml` first.

### "Authentication required"

```bash
gh auth login
gh auth refresh -s repo,read:org,project
```

### "Rate limit exceeded"

Wait for rate limit reset or use authenticated requests (they have higher limits).

```bash
# Check rate limit status
gh api rate_limit
```

### "Invalid JSON after sanitization"

The sanitization script has a bug. Check `SCHEMA_DIFFERENCES.md` for known issues.

Restore from backup:
```bash
mv fixture.json.backup fixture.json
```

## Best Practices

1. **Record regularly** - APIs change, keep fixtures fresh
2. **Run drift detection** - Catch schema changes early
3. **Document mismatches** - Update `SCHEMA_DIFFERENCES.md`
4. **Use real data for recording** - Record from repos with actual content
5. **Create synthetics for edges** - Hand-craft scenarios that don't occur naturally
6. **Verify sanitization** - Always check fixtures for leaked data
7. **Version control** - Commit fixtures to track changes over time

## Related Documentation

- **Phase 2 Plan:** `../../docs/testing-framework-refactor-plan.md` (Phase 2)
- **Test README:** `../README.md`
- **Helper Functions:** `../bats-helpers/fixtures.bash`

## Status

**Completed:**
- ✅ Recording infrastructure (`record_fixtures.bash`)
- ✅ Sanitization pipeline (`sanitize_fixture.bash`)
- ✅ Drift detection (`detect_fixture_drift.bash`)
- ✅ Recording manifest with 10+ domains defined
- ✅ Synthetic edge case fixtures
- ✅ Schema differences documentation

**In Progress:**
- 🔄 Recording fixtures for all domains
- 🔄 Fixing sanitization edge cases
- 🔄 Adding more synthetic fixtures

**Pending:**
- ⏳ CI workflow for drift detection
- ⏳ Complete fixture coverage for all 11 domains
- ⏳ Migration of existing test fixtures

## Quick Reference

```bash
# Record
./scripts/record_fixtures.bash --fixture DOMAIN NAME
./scripts/record_fixtures.bash --domain DOMAIN
./scripts/record_fixtures.bash --all

# Sanitize (automatic, but can run manually)
./scripts/sanitize_fixture.bash DOMAIN NAME path/to/fixture.json

# Detect drift
./scripts/detect_fixture_drift.bash --fixture DOMAIN NAME
./scripts/detect_fixture_drift.bash --domain DOMAIN
./scripts/detect_fixture_drift.bash --all

# Load in tests
load_fixture DOMAIN NAME [TYPE]           # graphql (default) or rest
load_graphql_fixture DOMAIN NAME
load_rest_fixture DOMAIN NAME
load_synthetic_fixture CATEGORY NAME
```
