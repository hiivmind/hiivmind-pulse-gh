---
name: hiivmind-corpus-octokit-net-navigate
description: Find relevant Octokit.NET documentation. Use when working with Octokit.NET code, APIs, or configuration.
---

# Octokit.NET Corpus Navigator

Find and retrieve relevant documentation from the Octokit.NET corpus.

## Process

1. **Read the index**: `data/index.md`
2. **Parse path format**: `{source_id}:{relative_path}`
3. **Look up source** in `data/config.yaml` by ID
4. **Get content** based on source type (see Source Access below)
5. **Answer** with citation to source and file path

## Path Format

Index entries use the format: `{source_id}:{relative_path}`

Examples:
- `octokit-net:reference/hooks.md` - Git source
- `local:team-standards/coding-guidelines.md` - Local uploads
- `web:blog-posts/article-name.md` - Cached web content

## Source Access

### For git sources

Look up the source in `data/config.yaml` to get `repo_owner`, `repo_name`, `branch`, and `docs_root`.

**If `.source/{source_id}/` exists (local clone):**
Read directly from `.source/{source_id}/{docs_root}/{path}`

**If no local clone:**

Option A - Fetch on demand:
```
https://raw.githubusercontent.com/{repo_owner}/{repo_name}/{branch}/{docs_root}/{path}
```
Use WebFetch to retrieve content. No clone needed.

Option B - Clone locally:
```bash
git clone --depth 1 {repo_url} .source/{source_id}
```

**Staleness check for git sources:**
After reading, compare the source's `last_commit_sha` in config to the local clone:
```bash
cd .source/{source_id} && git rev-parse HEAD
```
If clone is **newer** than indexed SHA → warn user: "The docs have been updated since the index was built. Consider running refresh to update the index."

### For local sources

Read directly from: `data/uploads/{source_id}/{path}`

Local sources are user-uploaded files stored within the corpus.

### For web sources

Read from cache: `.cache/web/{source_id}/{cached_file}`

If cache miss, look up the URL in `data/config.yaml` and fetch fresh content.

## File Locations

- **Index**: `data/index.md`
- **Config**: `data/config.yaml` (has sources array with per-source tracking)
- **Git sources**: `.source/{source_id}/` (cloned repos, gitignored)
- **Local sources**: `data/uploads/{source_id}/` (user-uploaded files)
- **Web cache**: `.cache/web/{source_id}/` (fetched web content, gitignored)

## Output

- Cite the source ID and file path for reference
- Include code examples from the docs
- Suggest related docs from the same index section
- Note source type and freshness warnings if relevant
