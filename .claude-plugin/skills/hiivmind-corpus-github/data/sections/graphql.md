# GraphQL

GitHub GraphQL API documentation.

> **27 files** | Source: `docs:graphql/`
> **Also see:** `graphql-schema:schema.docs.graphql` in main index (⚡ GREP - 70k lines)

---

## Overview

- **GraphQL Overview** `docs:graphql/index.md`
- **About GraphQL** `docs:graphql/overview/about-the-graphql-api.md`
- **Resource Limitations** `docs:graphql/overview/resource-limitations.md`

## Guides

- **Guides Overview** `docs:graphql/guides/index.md`
- **Forming Calls** `docs:graphql/guides/forming-calls-with-graphql.md`
- **Using the Explorer** `docs:graphql/guides/using-the-explorer.md`
- **Migrating from REST** `docs:graphql/guides/migrating-from-rest-to-graphql.md`
- **Managing Enterprise Accounts** `docs:graphql/guides/managing-enterprise-accounts.md`

## Reference

- **Reference Overview** `docs:graphql/reference/index.md`
- **Queries** `docs:graphql/reference/queries.md`
- **Mutations** `docs:graphql/reference/mutations.md`
- **Objects** `docs:graphql/reference/objects.md`
- **Interfaces** `docs:graphql/reference/interfaces.md`
- **Enums** `docs:graphql/reference/enums.md`
- **Unions** `docs:graphql/reference/unions.md`
- **Input Objects** `docs:graphql/reference/input-objects.md`
- **Scalars** `docs:graphql/reference/scalars.md`

---

## Schema Reference

For detailed type definitions, use the local GraphQL schema with Grep patterns:

**Path:** `graphql-schema:schema.docs.graphql` ⚡ GREP

**Search patterns:**
- Find type: `grep -n "^type Repository " schema.docs.graphql -A 50`
- Find input: `grep -n "^input CreateIssueInput " schema.docs.graphql -A 30`
- Find enum: `grep -n "^enum IssueState " schema.docs.graphql -A 20`
- Find mutation: `grep -n "createIssue" schema.docs.graphql -B 5 -A 30`
