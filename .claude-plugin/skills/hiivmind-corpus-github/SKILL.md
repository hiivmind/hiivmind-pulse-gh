---
name: hiivmind-corpus-github-navigate
description: Find relevant GitHub documentation. Use when working with GitHub GraphQL API, REST API, or gh CLI commands.
---

# GitHub Documentation Corpus Navigator

Find and retrieve relevant documentation from the GitHub documentation corpus.

**Focus areas**: GraphQL API, REST API, gh CLI

## Process

1. **Read the index**: `data/index.md`
2. **Parse path format**: `{source_id}:{relative_path}`
3. **Look up source** in `data/config.yaml` by ID
4. **Get content** based on source type (see Source Access below)
5. **Answer** with citation to source and file path

## Path Format

Index entries use the format: `{source_id}:{relative_path}`

Examples:
- `github-docs:graphql/guides/forming-calls-with-graphql.md` - GraphQL guide
- `github-docs:rest/issues/issues.md` - REST API reference
- `github-docs:github-cli/github-cli/about-github-cli.md` - gh CLI docs

## Source Access

### For git sources

Look up the source in `data/config.yaml` to get `repo_owner`, `repo_name`, `branch`, and `docs_root`.

**IMPORTANT: Always check for local clone first!**

**Step 1 - Check for local clone:**
Use Glob or Bash to check if `.source/{source_id}/` exists.

**Step 2a - If local clone exists (PREFERRED):**
Read directly from `.source/{source_id}/{docs_root}/{path}` using the Read tool.
This is faster and works offline.

**Step 2b - If NO local clone exists (fallback only):**
Fetch from GitHub:
```
https://raw.githubusercontent.com/{repo_owner}/{repo_name}/{branch}/{docs_root}/{path}
```
Use WebFetch to retrieve content.

**Tip:** If web fetching is slow or unreliable, suggest cloning locally:
```bash
git clone --depth 1 https://github.com/github/docs.git .source/github-docs
```
This improves performance and enables offline access.

**Staleness check for git sources:**
After reading, compare the source's `last_commit_sha` in config to the local clone:
```bash
cd .source/{source_id} && git rev-parse HEAD
```
If clone is **newer** than indexed SHA, warn user: "The docs have been updated since the index was built. Consider running refresh to update the index."

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
