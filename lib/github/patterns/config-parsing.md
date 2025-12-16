# Pattern: Config Parsing

## Purpose

Extract fields from workspace `.hiivmind/github/config.yaml` files using available YAML parsing tools.

## When to Use

- Reading workspace info (type, login, id)
- Accessing project catalog (numbers, IDs, fields)
- Checking cache metadata
- Any operation that needs structured data from config.yaml

## Prerequisites

- **tool-detection.md** - Know which YAML parser is available
- Config file exists at `.hiivmind/github/config.yaml`

## Config Schema Reference

```yaml
# Workspace identification
workspace:
  type: organization|user     # GitHub workspace type
  login: string               # GitHub org/user login
  id: string|null             # GraphQL node ID

# Project configuration
projects:
  default: number|null        # Default project number
  catalog:
    - number: 1               # Project number (from URL)
      title: "Project Name"
      id: "PVT_xxx"           # GraphQL project ID
      fields:
        - name: "Status"
          id: "PVTF_xxx"      # GraphQL field ID
          type: "single_select"
          options:
            - name: "Todo"
              id: "xxx"       # GraphQL option ID

# Repository catalog
repositories:
  - name: "repo-name"
    full_name: "owner/repo-name"

# Milestone catalog (keyed by repository)
milestones:
  repo-name:
    - number: 1
      title: "v1.0"

# Cache metadata
cache:
  initialized_at: "2025-01-15T10:00:00Z"
  last_synced_at: "2025-01-15T10:00:00Z"|null
  last_freshness_check: "2025-01-15T10:00:00Z"|null
  toolkit_version: "4.0.0"
```

## Extraction Patterns

### Get Workspace Type

**Using yq:**
```bash
yq '.workspace.type' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "import yaml; print(yaml.safe_load(open('.hiivmind/github/config.yaml')).get('workspace', {}).get('type', ''))"
```

**Using grep (fallback):**
```bash
grep -A2 '^workspace:' .hiivmind/github/config.yaml | grep 'type:' | sed 's/.*type: *//' | tr -d '"'
```

---

### Get Workspace Login

**Using yq:**
```bash
yq '.workspace.login' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "import yaml; print(yaml.safe_load(open('.hiivmind/github/config.yaml')).get('workspace', {}).get('login', ''))"
```

**Using grep (fallback):**
```bash
grep -A2 '^workspace:' .hiivmind/github/config.yaml | grep 'login:' | sed 's/.*login: *//' | tr -d '"'
```

---

### Get Workspace ID

**Using yq:**
```bash
yq '.workspace.id // empty' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "import yaml; print(yaml.safe_load(open('.hiivmind/github/config.yaml')).get('workspace', {}).get('id', '') or '')"
```

---

### Get Default Project Number

**Using yq:**
```bash
yq '.projects.default // empty' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "import yaml; print(yaml.safe_load(open('.hiivmind/github/config.yaml')).get('projects', {}).get('default', '') or '')"
```

**Using grep (fallback):**
```bash
grep -A1 '^projects:' .hiivmind/github/config.yaml | grep 'default:' | sed 's/.*default: *//'
```

---

### List Project Numbers

**Using yq:**
```bash
yq '.projects.catalog[].number' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "import yaml; [print(p['number']) for p in yaml.safe_load(open('.hiivmind/github/config.yaml')).get('projects', {}).get('catalog', [])]"
```

**Using grep (fallback):**
```bash
grep '^ *- number:' .hiivmind/github/config.yaml | sed 's/.*number: *//'
```

---

### Get Project by Number

**Using yq:**
```bash
yq '.projects.catalog[] | select(.number == 2)' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "
import yaml
projects = yaml.safe_load(open('.hiivmind/github/config.yaml')).get('projects', {}).get('catalog', [])
project = next((p for p in projects if p.get('number') == 2), None)
if project:
    print(yaml.dump(project))
"
```

---

### Get Project ID by Number

**Using yq:**
```bash
yq '.projects.catalog[] | select(.number == 2) | .id' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "
import yaml
projects = yaml.safe_load(open('.hiivmind/github/config.yaml')).get('projects', {}).get('catalog', [])
project = next((p for p in projects if p.get('number') == 2), {})
print(project.get('id', ''))
"
```

---

### Get Field ID by Name

**Using yq:**
```bash
# Get Status field ID from project 2
yq '.projects.catalog[] | select(.number == 2) | .fields[] | select(.name == "Status") | .id' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "
import yaml
projects = yaml.safe_load(open('.hiivmind/github/config.yaml')).get('projects', {}).get('catalog', [])
project = next((p for p in projects if p.get('number') == 2), {})
field = next((f for f in project.get('fields', []) if f.get('name') == 'Status'), {})
print(field.get('id', ''))
"
```

---

### Get Option ID by Name

**Using yq:**
```bash
# Get "Todo" option ID from Status field in project 2
yq '.projects.catalog[] | select(.number == 2) | .fields[] | select(.name == "Status") | .options[] | select(.name == "Todo") | .id' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "
import yaml
projects = yaml.safe_load(open('.hiivmind/github/config.yaml')).get('projects', {}).get('catalog', [])
project = next((p for p in projects if p.get('number') == 2), {})
field = next((f for f in project.get('fields', []) if f.get('name') == 'Status'), {})
option = next((o for o in field.get('options', []) if o.get('name') == 'Todo'), {})
print(option.get('id', ''))
"
```

---

### List Repositories

**Using yq:**
```bash
yq '.repositories[].name' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "import yaml; [print(r['name']) for r in yaml.safe_load(open('.hiivmind/github/config.yaml')).get('repositories', [])]"
```

---

### Get Cache Timestamp

**Using yq:**
```bash
yq '.cache.initialized_at' .hiivmind/github/config.yaml
yq '.cache.last_synced_at // empty' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "import yaml; print(yaml.safe_load(open('.hiivmind/github/config.yaml')).get('cache', {}).get('initialized_at', ''))"
```

---

## Writing Patterns

### Update Last Synced Timestamp

**Using yq (in-place):**
```bash
yq -i '.cache.last_synced_at = "2025-01-15T10:00:00Z"' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "
import yaml
from datetime import datetime, timezone

with open('.hiivmind/github/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

config.setdefault('cache', {})['last_synced_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

with open('.hiivmind/github/config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
"
```

---

### Set Default Project

**Using yq (in-place):**
```bash
yq -i '.projects.default = 2' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "
import yaml

with open('.hiivmind/github/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

config.setdefault('projects', {})['default'] = 2

with open('.hiivmind/github/config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
"
```

---

### Add Project to Catalog

**Using yq (in-place):**
```bash
yq -i '.projects.catalog += [{"number": 3, "title": "New Project", "id": "PVT_xxx", "fields": []}]' .hiivmind/github/config.yaml
```

**Using Python:**
```bash
python3 -c "
import yaml

with open('.hiivmind/github/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

config.setdefault('projects', {}).setdefault('catalog', []).append({
    'number': 3,
    'title': 'New Project',
    'id': 'PVT_xxx',
    'fields': []
})

with open('.hiivmind/github/config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
"
```

---

## Error Handling

### Config File Not Found

```
Configuration file not found at .hiivmind/github/config.yaml

This workspace may not be initialized. Run:
  /hiivmind-pulse-gh init

Or check that you're in a directory with .hiivmind/github/ config.
```

### Parse Error

```
Failed to parse config.yaml - the file may be malformed.

Common issues:
- Incorrect indentation (YAML uses spaces, not tabs)
- Missing quotes around strings with special characters
- Duplicate keys

Try validating with: yq '.' .hiivmind/github/config.yaml
```

### Field Not Found

Return empty/default values rather than erroring:
- `// empty` in yq (returns nothing instead of null)
- `.get('field', '')` in Python
- Handle missing grep output gracefully with `|| echo ""`

---

## Fallback Limitations

The grep/sed fallback has significant limitations:

| Works For | Fails For |
|-----------|-----------|
| Simple `key: value` pairs | Multi-line values |
| Top-level keys | Deeply nested structures |
| Single values | Arrays (partial support) |
| Unquoted strings | Quoted strings with colons |

**Recommendation:** If using grep fallback frequently, strongly encourage user to install yq or PyYAML.

**Critical limitation:** Getting field/option IDs by name is impractical with grep due to the nested structure. For these operations, yq or Python is effectively required.

---

## Cross-Platform Notes

| Operation | Unix | Windows (PowerShell) |
|-----------|------|---------------------|
| File path | `.hiivmind/github/config.yaml` | `.hiivmind\github\config.yaml` |
| yq command | Same syntax | Same syntax |
| python3 | `python3` | `python` (usually) |

---

## Related Patterns

- **tool-detection.md** - Determines which parsing method to use
- **workspace-detection.md** - Creates initial config during init
- **authentication.md** - Config stores workspace context for auth
- **graphql-queries.md** - Uses cached IDs from config
