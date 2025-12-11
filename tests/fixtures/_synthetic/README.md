# Synthetic Fixtures

> **Hand-crafted test fixtures for edge cases**

These fixtures are NOT recorded from live APIs. They are carefully crafted to test specific edge cases that may not occur naturally during recording.

## Why Synthetic Fixtures?

Live-recorded fixtures capture real API responses, but some scenarios are hard to trigger:
- Error responses (404, 401, 403, 422, 500)
- Empty states (no items, null values)
- Edge cases (very large arrays, deeply nested objects)
- Malformed data (testing error handling)

## Categories

### `errors/`
Error responses from GitHub APIs

- `404_not_found.json` - Resource not found
- `401_unauthorized.json` - Authentication required
- `403_forbidden.json` - Permission denied
- `422_validation.json` - Validation failed with field errors
- `graphql_error.json` - GraphQL-specific error format

### `empty/`
Empty or minimal valid responses

- `empty_array.json` - `[]`
- `empty_object.json` - `{}`

### `null_fields/`
Objects with null/missing optional fields

- `user_with_nulls.json` - User with all optional fields null

### `large_arrays/` _(to be created)_
Fixtures with many items to test pagination, performance

## Usage in Tests

```bash
# Load synthetic fixture
local error_fixture=$(load_synthetic_fixture "errors" "404_not_found")

# Test error handling
run some_function_that_should_fail
assert_failure
assert_json_contains "$output" "$error_fixture"
```

## Maintenance

When adding synthetic fixtures:
1. Document WHY it exists (what edge case it tests)
2. Keep structure aligned with actual API responses
3. Update this README with the new fixture
4. Reference official GitHub API docs for error formats

## References

- [GitHub REST API Errors](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#client-errors)
- [GitHub GraphQL Errors](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql#handling-errors)
