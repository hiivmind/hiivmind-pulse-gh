 How would you advise we design and develop tests for this bash-first architecture?

● Good question. Testing bash scripts that wrap external APIs requires a layered strategy. Here's a practical approach:

  Testing Strategy for Bash-Based API Wrappers

  Recommended Framework: BATS

  https://github.com/bats-core/bats-core is the standard. It's TAP-compliant, well-maintained, and handles the common bash testing patterns.

  # Install
  sudo apt install bats  # or brew install bats-core

  Architecture: Three Test Layers

  tests/
  ├── unit/                    # Fast, no API calls
  │   ├── test_jq_filters.bats
  │   ├── test_query_building.bats
  │   └── fixtures/
  │       └── sample_project.json
  ├── integration/             # Mock gh CLI
  │   ├── test_fetch_functions.bats
  │   ├── test_filter_functions.bats
  │   └── mocks/
  │       └── gh               # Mock gh executable
  └── e2e/                     # Real API (CI only)
      └── test_live_api.bats

  ---
  Layer 1: Unit Tests (jq Filters, Query Building)

  These are fast and don't need mocking. Test your jq filters against fixture data:

  # tests/unit/test_jq_filters.bats

  setup() {
      load '../test_helper'
      FIXTURES="$BATS_TEST_DIRNAME/fixtures"
  }

  @test "assignee filter extracts correct items" {
      filter=$(yq '.combined_filters.assignee_filter.filter' lib/github/gh-project-jq-filters.yaml)

      result=$(jq --arg assignee "octocat" "$filter" < "$FIXTURES/sample_project.json")

      # Assert expected count
      count=$(echo "$result" | jq '.items | length')
      [ "$count" -eq 3 ]
  }

  @test "universal filter with empty params returns all items" {
      filter=$(yq '.combined_filters.universal_filter.filter' lib/github/gh-project-jq-filters.yaml)

      result=$(jq --arg repo "" --arg assignee "" --arg status "" --arg priority "" \
          "$filter" < "$FIXTURES/sample_project.json")

      original_count=$(jq '.data.organization.projectV2.items.nodes | length' "$FIXTURES/sample_project.json")
      filtered_count=$(echo "$result" | jq '.items | length')

      [ "$filtered_count" -eq "$original_count" ]
  }

  @test "status filter handles null status field" {
      result=$(jq --arg status "Done" '.items[] | select(.status == $status or .status == null)' \
          < "$FIXTURES/items_with_nulls.json")

      # Should not error
      [ $? -eq 0 ]
  }

  Fixture file example (tests/unit/fixtures/sample_project.json):
  {
    "data": {
      "organization": {
        "projectV2": {
          "id": "PVT_test123",
          "title": "Test Project",
          "items": {
            "nodes": [
              {
                "id": "PVTI_1",
                "content": {"title": "Issue 1", "number": 1},
                "fieldValues": {
                  "nodes": [
                    {"field": {"name": "Status"}, "name": "In Progress"},
                    {"field": {"name": "Assignees"}, "users": {"nodes": [{"login": "octocat"}]}}
                  ]
                }
              }
            ]
          }
        }
      }
    }
  }

  ---
  Layer 2: Integration Tests (Mock gh CLI)

  Create a mock gh that returns canned responses:

  # tests/integration/mocks/gh
  #!/bin/bash
  # Mock gh CLI - returns fixtures based on arguments

  case "$*" in
      *"graphql"*"projectV2"*)
          cat "$(dirname "$0")/../fixtures/project_response.json"
          ;;
      *"api"*"/repos/"*"/milestones"*)
          cat "$(dirname "$0")/../fixtures/milestones.json"
          ;;
      *"api"*"/repos/"*"/branches"*)
          cat "$(dirname "$0")/../fixtures/branches.json"
          ;;
      *)
          echo "Mock gh: unhandled args: $*" >&2
          exit 1
          ;;
  esac

  # tests/integration/test_fetch_functions.bats

  setup() {
      # Prepend mock directory to PATH
      export PATH="$BATS_TEST_DIRNAME/mocks:$PATH"

      # Source the functions
      source "$BATS_TEST_DIRNAME/../../lib/github/gh-project-functions.sh"
  }

  @test "fetch_org_project returns valid JSON" {
      result=$(fetch_org_project 2 "test-org")

      # Should be valid JSON
      echo "$result" | jq . > /dev/null
      [ $? -eq 0 ]

      # Should have expected structure
      title=$(echo "$result" | jq -r '.data.organization.projectV2.title')
      [ "$title" = "Test Project" ]
  }

  @test "apply_assignee_filter pipes correctly" {
      result=$(fetch_org_project 2 "test-org" | apply_assignee_filter "octocat")

      # All items should have octocat as assignee
      non_matching=$(echo "$result" | jq '[.items[] | select(.assignees | index("octocat") | not)] | length')
      [ "$non_matching" -eq 0 ]
  }

  @test "list_assignees extracts unique assignees" {
      result=$(fetch_org_project 2 "test-org" | list_assignees)

      # Should contain expected assignee
      echo "$result" | grep -q "octocat"
  }

  ---
  Layer 3: E2E Tests (Real API)

  Run against real GitHub API in CI with a test repository:

  # tests/e2e/test_live_api.bats

  setup() {
      # Skip if not in CI or no token
      if [ -z "$GITHUB_TOKEN" ] || [ -z "$TEST_ORG" ]; then
          skip "E2E tests require GITHUB_TOKEN and TEST_ORG"
      fi

      source "$BATS_TEST_DIRNAME/../../lib/github/gh-project-functions.sh"
  }

  @test "fetch real project from test org" {
      result=$(fetch_org_project "$TEST_PROJECT_NUMBER" "$TEST_ORG")

      [ $? -eq 0 ]
      echo "$result" | jq -e '.data.organization.projectV2.id' > /dev/null
  }

  @test "create and delete draft issue" {
      # Create
      project_id=$(fetch_org_project "$TEST_PROJECT_NUMBER" "$TEST_ORG" | \
          jq -r '.data.organization.projectV2.id')

      result=$(create_draft_issue "$project_id" "BATS Test Item" "Automated test")
      item_id=$(echo "$result" | jq -r '.data.addProjectV2DraftIssue.projectItem.id')

      [ -n "$item_id" ]
      [ "$item_id" != "null" ]

      # Cleanup - archive the item
      archive_item "$project_id" "$item_id"
  }

  ---
  Test Helper Pattern

  # tests/test_helper.bash

  # Load bats-support and bats-assert if available
  load_helpers() {
      if [ -d "$BATS_TEST_DIRNAME/../node_modules/bats-support" ]; then
          load '../node_modules/bats-support/load'
          load '../node_modules/bats-assert/load'
      fi
  }

  # Assert JSON structure
  assert_json_path() {
      local json="$1"
      local path="$2"
      local expected="$3"

      actual=$(echo "$json" | jq -r "$path")
      if [ "$actual" != "$expected" ]; then
          echo "Expected $path to be '$expected', got '$actual'" >&2
          return 1
      fi
  }

  # Assert command succeeds and outputs valid JSON
  assert_valid_json() {
      local cmd="$1"
      result=$(eval "$cmd")
      [ $? -eq 0 ] || { echo "Command failed: $cmd" >&2; return 1; }
      echo "$result" | jq . > /dev/null || { echo "Invalid JSON output" >&2; return 1; }
  }

  ---
  GitHub Actions CI

  # .github/workflows/test.yml
  name: Tests

  on: [push, pull_request]

  jobs:
    unit-tests:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4

        - name: Install dependencies
          run: |
            sudo apt-get update
            sudo apt-get install -y bats jq
            sudo wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
            sudo chmod +x /usr/local/bin/yq

        - name: Run unit tests
          run: bats tests/unit/

    integration-tests:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4

        - name: Install dependencies
          run: |
            sudo apt-get install -y bats jq
            sudo wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
            sudo chmod +x /usr/local/bin/yq

        - name: Run integration tests
          run: bats tests/integration/

    e2e-tests:
      runs-on: ubuntu-latest
      if: github.event_name == 'push' && github.ref == 'refs/heads/main'
      steps:
        - uses: actions/checkout@v4

        - name: Install dependencies
          run: |
            sudo apt-get install -y bats jq gh
            sudo wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
            sudo chmod +x /usr/local/bin/yq

        - name: Run E2E tests
          env:
            GITHUB_TOKEN: ${{ secrets.TEST_GITHUB_TOKEN }}
            TEST_ORG: ${{ vars.TEST_ORG }}
            TEST_PROJECT_NUMBER: ${{ vars.TEST_PROJECT_NUMBER }}
          run: bats tests/e2e/
