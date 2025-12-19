# Labels

**Full CLI + REST support. GraphQL for read and add/remove only.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | All methods work |
| Create | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Update | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Delete | ✓ | ✓ | ✗ | ✓ | No GraphQL mutation |
| Clone | ✓ | ✗ | ✗ | ✗ | CLI-only bulk copy |
| Add to issue | ✓ | ✓ | ✓ | ✓ | Via gh issue edit or GraphQL |
| Remove from issue | ✓ | ✓ | ✓ | ✓ | Via gh issue edit or GraphQL |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| List | `gh label list` | |
| Create | `gh label create {name} --color {hex}` | Color without # prefix |
| Update | `gh label edit {name} --name {new-name}` | Rename, change color/description |
| Delete | `gh label delete {name}` | |
| Clone | `gh label clone {source-repo}` | Copy all labels from another repo |
| Add to issue | `gh issue edit {number} --add-label {label}` | |
| Remove from issue | `gh issue edit {number} --remove-label {label}` | |

## REST API Reference

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List | GET | `/repos/{owner}/{repo}/labels` | |
| Get | GET | `/repos/{owner}/{repo}/labels/{name}` | |
| Create | POST | `/repos/{owner}/{repo}/labels` | |
| Update | PATCH | `/repos/{owner}/{repo}/labels/{name}` | |
| Delete | DELETE | `/repos/{owner}/{repo}/labels/{name}` | |
| Add to issue | POST | `/repos/{owner}/{repo}/issues/{number}/labels` | |
| Remove from issue | DELETE | `/repos/{owner}/{repo}/issues/{number}/labels/{name}` | |

## GraphQL Reference

| Operation | Type | Name | Notes |
|-----------|------|------|-------|
| List | Query | `repository.labels` | |
| Add to issue | Mutation | `addLabelsToLabelable` | |
| Remove from issue | Mutation | `removeLabelsFromLabelable` | |
