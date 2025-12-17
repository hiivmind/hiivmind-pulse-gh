# Release Operations Examples

Examples of release operations using hiivmind-pulse-gh.

**Note:** All Release operations use REST API.

## Create Release

**Natural language:**
```
/hiivmind-pulse-gh create release v2.0.0
/hiivmind-pulse-gh publish release for tag v1.5.0
/hiivmind-pulse-gh create release v2.0.0 with changelog
```

**REST endpoint:**
```
POST /repos/{owner}/{repo}/releases
```

**Request body:**
```json
{
  "tag_name": "v2.0.0",
  "target_commitish": "main",
  "name": "v2.0.0",
  "body": "## What's Changed\n- Feature A\n- Bug fix B",
  "draft": false,
  "prerelease": false,
  "generate_release_notes": true
}
```

**CLI shortcut (recommended):**
```bash
gh release create v2.0.0 --title "v2.0.0" --notes "Release notes here"
gh release create v2.0.0 --generate-notes
gh release create v2.0.0 --draft
```

---

## Create Draft Release

**Natural language:**
```
/hiivmind-pulse-gh create draft release v2.0.0
/hiivmind-pulse-gh prepare release v2.0.0 as draft
```

**CLI shortcut:**
```bash
gh release create v2.0.0 --draft --generate-notes
```

---

## Create Pre-release

**Natural language:**
```
/hiivmind-pulse-gh create prerelease v2.0.0-beta.1
/hiivmind-pulse-gh publish v2.0.0-rc1 as prerelease
```

**CLI shortcut:**
```bash
gh release create v2.0.0-beta.1 --prerelease
```

---

## Upload Release Asset

**Natural language:**
```
/hiivmind-pulse-gh upload dist/app.zip to release v2.0.0
/hiivmind-pulse-gh add asset build/binary to v2.0.0
```

**REST endpoint:**
```
POST /repos/{owner}/{repo}/releases/{release_id}/assets?name=app.zip
Content-Type: application/octet-stream

[binary data]
```

**CLI shortcut:**
```bash
gh release upload v2.0.0 dist/app.zip
gh release upload v2.0.0 dist/*.tar.gz
```

---

## List Releases

**Natural language:**
```
/hiivmind-pulse-gh list releases
/hiivmind-pulse-gh show recent releases
/hiivmind-pulse-gh list draft releases
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/releases
```

**CLI shortcut:**
```bash
gh release list
gh release list --limit 10
```

---

## View Release

**Natural language:**
```
/hiivmind-pulse-gh show release v2.0.0
/hiivmind-pulse-gh view latest release
```

**REST endpoint:**
```
GET /repos/{owner}/{repo}/releases/tags/{tag}
GET /repos/{owner}/{repo}/releases/latest
```

**CLI shortcut:**
```bash
gh release view v2.0.0
gh release view --json tagName,body,assets
```

---

## Update Release

**Natural language:**
```
/hiivmind-pulse-gh update release v2.0.0 notes
/hiivmind-pulse-gh edit release v2.0.0 title
/hiivmind-pulse-gh publish draft release v2.0.0
```

**REST endpoint:**
```
PATCH /repos/{owner}/{repo}/releases/{release_id}
```

**Request body:**
```json
{
  "draft": false,
  "name": "Production Release v2.0.0",
  "body": "Updated release notes"
}
```

**CLI shortcut:**
```bash
gh release edit v2.0.0 --draft=false
gh release edit v2.0.0 --notes "Updated notes"
```

---

## Delete Release

**Natural language:**
```
/hiivmind-pulse-gh delete release v1.0.0-beta
/hiivmind-pulse-gh remove release old-version
```

**REST endpoint:**
```
DELETE /repos/{owner}/{repo}/releases/{release_id}
```

**CLI shortcut:**
```bash
gh release delete v1.0.0-beta --yes
```

---

## Generate Release Notes

**Natural language:**
```
/hiivmind-pulse-gh generate release notes for v2.0.0
/hiivmind-pulse-gh auto-generate changelog from v1.0.0 to v2.0.0
```

**REST endpoint:**
```
POST /repos/{owner}/{repo}/releases/generate-notes
```

**Request body:**
```json
{
  "tag_name": "v2.0.0",
  "previous_tag_name": "v1.0.0"
}
```

**CLI equivalent:**
```bash
gh release create v2.0.0 --generate-notes
```
