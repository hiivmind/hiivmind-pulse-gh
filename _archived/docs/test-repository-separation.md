# Test Repository Separation Requirements

## Document Info

| Field | Value |
|-------|-------|
| Status | Draft |
| Created | 2024-12-12 |
| Author | Claude Code |
| Related Issue | TBD |

---

## 1. Problem Statement

### 1.1 Current State

The `hiivmind-pulse-gh` repository contains both the plugin code and extensive test infrastructure:

```
hiivmind-pulse-gh/
├── lib/github/              # Plugin library code (~50 files)
├── skills/                  # Plugin skills
├── templates/               # Config templates
├── .claude-plugin/          # Plugin manifest
└── tests/                   # Test infrastructure (~100+ files)
    ├── fixtures/            # ~500KB+ recorded API responses
    ├── mocks/               # Mock gh CLI system
    ├── unit/                # 178 unit tests
    ├── integration/         # 173 integration tests
    ├── e2e/                 # 17 smoke tests
    ├── bats-helpers/        # Test utilities
    └── lib/resources/       # Fixture recording infrastructure
```

### 1.2 The Problem

Unlike Python packages where only the wheel is distributed, **Claude Code plugins distribute the entire repository**. Users who install this plugin receive:

- All test fixtures (500KB+ of API responses)
- Mock infrastructure they'll never use
- 368 test files
- Test dependencies in package.json

This creates unnecessary bloat for end users who only need the plugin functionality.

### 1.3 Goals

1. **Lean main repository** - Plugin users get only what they need
2. **Preserved test coverage** - All 368 tests continue to work
3. **Maintainable separation** - Clear boundaries between plugin and tests
4. **Practical CI/CD** - Tests run on schedule, not blocking PRs

---

## 2. Proposed Architecture

### 2.1 Repository Structure

```
┌─────────────────────────────────┐      ┌─────────────────────────────────┐
│  hiivmind-pulse-gh              │      │  hiivmind-pulse-gh-tests        │
│  (Plugin Repository - LEAN)     │      │  (Test Repository)              │
├─────────────────────────────────┤      ├─────────────────────────────────┤
│                                 │      │                                 │
│  lib/github/                    │◄────┐│  fixtures/                      │
│    ├── gh-*-functions.sh        │     ││    ├── graphql/                 │
│    ├── gh-*-graphql-queries.yaml│     ││    ├── rest/                    │
│    └── gh-*-jq-filters.yaml     │     ││    └── _synthetic/              │
│                                 │     ││                                 │
│  skills/                        │     ││  mocks/                         │
│    └── hiivmind-pulse-gh-*/     │     ││    ├── gh                       │
│                                 │     ││    ├── registry.bash            │
│  templates/                     │     ││    └── defaults/                │
│    ├── config.yaml.template     │     ││                                 │
│    └── user.yaml.template       │     ││  unit/                          │
│                                 │     ││    └── test_*_functions.bats    │
│  .claude-plugin/                │     ││                                 │
│    └── plugin.json              │     ││  integration/                   │
│                                 │     ││    └── test_*_functions.bats    │
│  docs/                          │     ││                                 │
│                                 │     ││  e2e/smoke/                     │
│  NO tests/ directory            │     ││    ├── test_connectivity.bats   │
│                                 │     ││    └── test_auth.bats           │
└─────────────────────────────────┘     ││                                 │
                                        ││  bats-helpers/                  │
                                        ││  lib/resources/                 │
                                        ││  scripts/                       │
                                        │└── target/ (.gitignore'd)        │
                                        │      └── hiivmind-pulse-gh/      │
                                        │          (cloned at test time)   │
                                        └─────────────────────────────────┘
```

### 2.2 Dependency Direction

```
Test Repository ──depends on──► Main Repository

Tests clone main repo at runtime, NOT the other way around.
Main repo has NO knowledge of test repo.
```

---

## 3. Technical Requirements

### 3.1 Test Repository Setup

#### 3.1.1 Setup Script

The test repository SHALL include a setup script that clones the main repository:

```bash
# scripts/setup.sh
#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-target/hiivmind-pulse-gh}"
MAIN_REPO="https://github.com/hiivmind/hiivmind-pulse-gh.git"
REF="${MAIN_REPO_REF:-main}"

if [[ -d "$TARGET_DIR" ]]; then
    echo "Updating existing clone..."
    cd "$TARGET_DIR"
    git fetch origin
    git checkout "$REF"
    git pull origin "$REF" 2>/dev/null || true
else
    echo "Cloning main repository..."
    git clone "$MAIN_REPO" "$TARGET_DIR"
    cd "$TARGET_DIR"
    git checkout "$REF"
fi

echo "Main repo ready at $TARGET_DIR (ref: $REF)"
```

#### 3.1.2 Test Helper Updates

The `test_helper.bash` SHALL support both CI and local development modes:

```bash
# test_helper.bash

# Allow override for local development
MAIN_REPO="${MAIN_REPO_PATH:-${BATS_TEST_DIRNAME}/../target/hiivmind-pulse-gh}"

# Verify main repo exists
if [[ ! -d "$MAIN_REPO/lib/github" ]]; then
    echo "ERROR: Main repo not found at $MAIN_REPO" >&2
    echo "Run: ./scripts/setup.sh" >&2
    exit 1
fi

# Source library from main repo
source_lib() {
    local lib_name="$1"
    local lib_path="${MAIN_REPO}/lib/github/${lib_name}"

    if [[ ! -f "$lib_path" ]]; then
        echo "ERROR: Library not found: $lib_path" >&2
        return 1
    fi

    source "$lib_path"
}

# Export for child processes
export MAIN_REPO
export LIB_DIR="${MAIN_REPO}/lib/github"
```

#### 3.1.3 Local Development Override

Developers SHALL be able to test against a local main repo checkout:

```bash
# Point to local checkout instead of cloned copy
export MAIN_REPO_PATH="/home/user/git/hiivmind-pulse-gh"

# Run tests against local changes
./node_modules/.bin/bats unit/
```

### 3.2 CI/CD Requirements

#### 3.2.1 No PR-Blocking CI in Main Repo

The main repository SHALL NOT have CI workflows that block PRs on test results because:

1. Tests take too long for real-time feedback
2. Test repo is separate, can't be triggered synchronously
3. Manual review is the approval mechanism

#### 3.2.2 Test Repository CI Workflow

The test repository SHALL have a GitHub Actions workflow with:

| Trigger | Behavior |
|---------|----------|
| Schedule (daily) | Full test suite against `main` |
| Manual dispatch | Full test suite against specified ref |
| Push to test repo | Smoke tests only (fast feedback) |

```yaml
# .github/workflows/test.yaml
name: Test Suite

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
  workflow_dispatch:
    inputs:
      main_repo_ref:
        description: 'Branch/tag of main repo to test against'
        required: false
        default: 'main'
  push:
    branches: [main]

env:
  MAIN_REPO_REF: ${{ github.event.inputs.main_repo_ref || 'main' }}

jobs:
  setup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Clone main repository
        run: ./scripts/setup.sh
        env:
          MAIN_REPO_REF: ${{ env.MAIN_REPO_REF }}

      - name: Run smoke tests
        run: ./node_modules/.bin/bats e2e/smoke/

      - name: Run unit tests
        if: github.event_name != 'push'  # Skip on push, run on schedule/dispatch
        run: ./node_modules/.bin/bats unit/

      - name: Run integration tests
        if: github.event_name != 'push'
        run: ./node_modules/.bin/bats integration/
```

### 3.3 File Migration Requirements

#### 3.3.1 Files to Move

| Source (main repo) | Destination (test repo) |
|--------------------|-------------------------|
| `tests/fixtures/` | `fixtures/` |
| `tests/mocks/` | `mocks/` |
| `tests/unit/` | `unit/` |
| `tests/integration/` | `integration/` |
| `tests/e2e/` | `e2e/` |
| `tests/bats-helpers/` | `bats-helpers/` |
| `tests/lib/resources/` | `lib/resources/` |
| `tests/test_helper.bash` | `test_helper.bash` |
| `tests/package.json` | `package.json` |
| `tests/package-lock.json` | `package-lock.json` |

#### 3.3.2 Files to Update

| File | Changes Required |
|------|------------------|
| `test_helper.bash` | Update paths to reference `target/hiivmind-pulse-gh/` |
| `bats-helpers/fixtures.bash` | Update `FIXTURES_BASE` path |
| `bats-helpers/mocks.bash` | Update mock directory detection |
| `lib/resources/*.bash` | Update library source paths |
| `mocks/registry.bash` | Update `MOCK_DEFAULTS_DIR` path |
| `fixtures/scripts/*.bash` | Update paths for fixture recording |

#### 3.3.3 Files to Delete from Main Repo

After successful migration verification:
- Entire `tests/` directory
- Test-related entries in `.gitignore`

### 3.4 Test Repository Structure

```
hiivmind-pulse-gh-tests/
├── .github/
│   └── workflows/
│       └── test.yaml
├── .gitignore                    # Includes target/
├── README.md
├── package.json
├── package-lock.json
├── test_helper.bash
│
├── scripts/
│   ├── setup.sh                  # Clone main repo
│   ├── record-fixtures.sh        # Fixture recording wrapper
│   └── detect-drift.sh           # Drift detection wrapper
│
├── fixtures/
│   ├── graphql/
│   │   ├── identity/
│   │   ├── repository/
│   │   ├── milestone/
│   │   ├── issue/
│   │   ├── pr/
│   │   ├── project/
│   │   └── release/
│   ├── rest/
│   │   ├── milestone/
│   │   ├── protection/
│   │   ├── action/
│   │   ├── secret/
│   │   ├── variable/
│   │   └── release/
│   ├── _synthetic/
│   └── scripts/
│       ├── record_fixtures.bash
│       └── detect_drift.bash
│
├── mocks/
│   ├── gh                        # Mock executable
│   ├── registry.bash
│   └── defaults/
│       ├── identity.yaml
│       ├── repository.yaml
│       └── ... (domain configs)
│
├── unit/
│   ├── test_identity_functions.bats
│   ├── test_repo_functions.bats
│   └── ... (11 domain test files)
│
├── integration/
│   ├── test_identity_functions.bats
│   ├── test_fetch_functions.bats
│   └── ... (13 test files)
│
├── e2e/
│   └── smoke/
│       ├── test_connectivity.bats
│       └── test_auth.bats
│
├── bats-helpers/
│   ├── assertions.bash
│   ├── fixtures.bash
│   └── mocks.bash
│
├── lib/
│   └── resources/
│       ├── core.bash
│       ├── milestone.bash
│       └── ... (resource management)
│
└── target/                       # .gitignore'd
    └── hiivmind-pulse-gh/        # Cloned at test time
```

---

## 4. Migration Plan

### 4.1 Phase 1: Create Test Repository

1. Create new repository `hiivmind/hiivmind-pulse-gh-tests`
2. Initialize with README and .gitignore
3. Set up repository settings (branch protection, etc.)

### 4.2 Phase 2: Copy Test Infrastructure

1. Copy all files from `tests/` to test repo (maintaining structure)
2. Copy `package.json` and `package-lock.json`
3. Commit with message referencing migration

### 4.3 Phase 3: Update Path References

1. Update `test_helper.bash` with new path logic
2. Update `bats-helpers/*.bash` path references
3. Update `mocks/registry.bash` paths
4. Update `lib/resources/*.bash` paths
5. Update fixture recording scripts

### 4.4 Phase 4: Add CI and Setup Scripts

1. Create `scripts/setup.sh`
2. Create `.github/workflows/test.yaml`
3. Test CI workflow manually

### 4.5 Phase 5: Verify All Tests Pass

1. Run `scripts/setup.sh` to clone main repo
2. Run all 368 tests
3. Verify fixture recording still works
4. Verify drift detection still works

### 4.6 Phase 6: Remove Tests from Main Repo

1. Delete `tests/` directory from main repo
2. Update main repo `.gitignore`
3. Update main repo `README.md` to reference test repo
4. Commit and push

### 4.7 Phase 7: Documentation

1. Update main repo docs to reference test repo
2. Create test repo README with:
   - How to run tests locally
   - How to record new fixtures
   - CI/CD explanation
   - Contributing guidelines

---

## 5. Development Workflow

### 5.1 Making Library Changes (Main Repo)

```
1. Clone both repositories locally
2. Make changes in main repo (lib/github/*.sh)
3. In test repo, set MAIN_REPO_PATH to local main repo
4. Run affected tests locally
5. Create PR in main repo
6. Manual review and merge
7. Daily CI in test repo validates against new main
```

### 5.2 Making Test Changes (Test Repo)

```
1. Clone test repo
2. Run scripts/setup.sh to get current main repo
3. Make test changes
4. Run tests locally
5. Create PR in test repo
6. Smoke tests run on PR (fast)
7. Merge
```

### 5.3 Adding New Domain Tests

```
1. In main repo: Add new lib/github/gh-newdomain-functions.sh
2. In test repo:
   a. Add fixtures/graphql/newdomain/ or fixtures/rest/newdomain/
   b. Add mocks/defaults/newdomain.yaml
   c. Add unit/test_newdomain_functions.bats
   d. Add integration/test_newdomain_functions.bats
3. Run tests locally
4. PR to both repos
```

### 5.4 Recording New Fixtures

```
1. In test repo, ensure main repo is cloned
2. Set required environment variables (GH_TOKEN, etc.)
3. Run: ./scripts/record-fixtures.sh [domain]
4. Review recorded fixtures
5. Commit to test repo
```

---

## 6. Acceptance Criteria

### 6.1 Main Repository

- [ ] No `tests/` directory
- [ ] No test-related dependencies in any manifest
- [ ] README references test repository
- [ ] Plugin functionality unchanged

### 6.2 Test Repository

- [ ] All 368 tests pass
- [ ] Setup script clones main repo correctly
- [ ] Local development override works (`MAIN_REPO_PATH`)
- [ ] CI workflow runs on schedule
- [ ] CI workflow supports manual dispatch with ref selection
- [ ] Fixture recording works
- [ ] Drift detection works
- [ ] README documents all workflows

### 6.3 CI/CD

- [ ] Daily scheduled runs execute successfully
- [ ] Manual dispatch works with custom refs
- [ ] Push triggers smoke tests only
- [ ] No test CI in main repository

---

## 7. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tests drift from main repo | Tests pass but don't reflect reality | Daily CI catches drift within 24h |
| Breaking change in main | Tests fail | Fix in test repo, clear error messages |
| Developer forgets to update tests | Untested code | Document workflow, PR template reminder |
| CI credentials expire | Tests can't run | Use GitHub App or long-lived token |
| Main repo renamed/moved | Clone fails | Update test repo config, fail loudly |

---

## 8. Future Considerations

### 8.1 Potential Enhancements

- **Webhook integration**: Main repo pushes trigger test repo runs
- **Test result badges**: Display test status in main repo README
- **Selective testing**: Only run tests affected by changed files
- **Matrix testing**: Test against multiple main repo versions

### 8.2 Not In Scope

- Git submodules (too complex)
- Monorepo tooling (overkill)
- Shared CI runners (unnecessary)
- Real-time PR blocking (too slow)

---

## Appendix A: Test Inventory

| Category | Count | Files |
|----------|-------|-------|
| Unit Tests | 178 | 11 files |
| Integration Tests | 173 | 13 files |
| E2E Smoke Tests | 17 | 2 files |
| **Total** | **368** | **26 files** |

## Appendix B: Fixture Inventory

| Domain | GraphQL | REST | Synthetic |
|--------|---------|------|-----------|
| Identity | 4 | - | - |
| Repository | 3 | - | - |
| Milestone | 2 | 3 | 1 |
| Issue | 2 | - | - |
| PR | 2 | - | - |
| Project | 3 | - | - |
| Protection | 1 | 2 | 3 |
| Action | - | 5 | - |
| Secret | - | 2 | - |
| Variable | - | 2 | - |
| Release | 1 | 2 | - |
