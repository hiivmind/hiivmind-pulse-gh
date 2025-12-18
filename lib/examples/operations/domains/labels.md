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

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/labels`, `POST /labels`, `PATCH /labels/{name}`, `DELETE /labels/{name}`, `POST /issues/{number}/labels`, `DELETE /issues/{number}/labels/{name}` | `GET /repos`, `POST /labels`, `PATCH /labels/{name}`, `issues/{number}/labels` |
| GraphQL | `labels` (query), `addLabelsToLabelable`, `removeLabelsFromLabelable` (mutations) | `query { repository { labels } }`, `mutation { addLabelsToLabelable }`, `mutation { removeLabelsFromLabelable }` |
