# Issues

**All 4 methods fully supported for core operations.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| List | ✓ | ✓ | ✓ | ✓ | All methods work |
| Get | ✓ | ✓ | ✓ | ✓ | |
| Create | ✓ | ✓ | ✓ | ✓ | |
| Update | ✓ | ✓ | ✓ | ✓ | |
| Close | ✓ | ✓ | ✓ | ✓ | |
| Add comment | ✓ | ✓ | ✓ | ✓ | |
| Add labels | ✓ | ✓ | ✓ | ✓ | Separate endpoint in REST |
| Set milestone | ✓ | ✓ | ✓ | ✓ | Via PATCH in REST |
| Lock | ✗ | ✓ | ✗ | ✓ | REST-only, no GraphQL |
| Unlock | ✗ | ✓ | ✗ | ✓ | REST-only, no GraphQL |

## CLI Command Reference

| Operation | Command |
|-----------|---------|
| List | `gh issue list` |
| Get | `gh issue view {number}` |
| Create | `gh issue create --title {title}` |
| Update | `gh issue edit {number}` |
| Close | `gh issue close {number}` |
| Add comment | `gh issue comment {number} --body {body}` |
| Add labels | `gh issue edit {number} --add-label {label}` |
| Set milestone | `gh issue edit {number} --milestone {milestone}` |
| Lock | (Web UI only) |
| Unlock | (Web UI only) |

## Corpus Lookup Guide

| API | Endpoints/Mutations | Search Keywords |
|-----|---------------------|-----------------|
| REST | `GET /repos/{owner}/{repo}/issues`, `GET /issues/{number}`, `POST /issues`, `PATCH /issues/{number}`, `POST /issues/{number}/comments`, `POST /issues/{number}/labels` | `GET /repos`, `POST /issues`, `PATCH /issues/{number}`, `issues/{number}/comments`, `issues/{number}/labels` |
| GraphQL | `issue`, `issues` (queries), `createIssue`, `updateIssue`, `closeIssue`, `addComment`, `addLabelsToLabelable`, `removeLabelsFromLabelable` (mutations) | `query { issue }`, `query { repository { issues } }`, `mutation { createIssue }`, `mutation { updateIssue }` |
