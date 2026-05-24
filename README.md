# bbui

Ansible YAML/INI inventory manager with a Python backend and a Typer CLI.

## Installation

```bash
poetry install
```

> **Requires** Python 3.14 and [ClusterShell](https://clustershell.readthedocs.io/) (`clustershell ^1.9`), installed automatically by Poetry.

---

## Inventory directory layout

bbui reads a directory (`BBUI_INVENTORY_DIR`) containing any mix of YAML and INI Ansible inventory files, plus the standard `group_vars/` hierarchy:

```
inventory/
├── cluster/
│   ├── nodes/
│   │   └── web.yml          # host declarations
│   └── groups/
│       └── webservers.yml   # group declarations
├── staging.ini              # additional INI inventory
└── group_vars/
    ├── all.yml              # vars applied to every group
    ├── webservers.yml       # vars for group "webservers"  (file layout)
    └── databases/           # vars for group "databases"   (directory layout)
        ├── main.yml
        └── secrets.yml
```

Files are merged alphabetically; last-writer-wins on conflicts. `group_vars/` is applied last, matching Ansible's own precedence rules.

---

## Nodeset syntax

Any command that accepts a hostname also accepts a **ClusterShell NodeSet** expression:

| Expression | Expands to |
|---|---|
| `web01` | `web01` |
| `web[01:10]` | `web01` … `web10` |
| `web[01-10]` | `web01` … `web10` (ClusterShell native) |
| `web[01-10/2]` | `web01`, `web03`, `web05` … (step) |
| `web[01-10],db[1:5]` | union of both ranges |
| `web[01-10]!web05` | exclusion |

---

## Staging workflow

bbui uses a **git-like staging layer** so changes are never written to disk without an explicit commit.

```
bbcli host add web[11-20] --groups webservers,staging -I ./inventory/
bbcli pending   -I ./inventory/     # review what will be written and where
bbcli commit    -I ./inventory/     # write to disk
bbcli discard   -I ./inventory/     # abandon changes
```

Two cache files live under `inventory/.bbui/`:

| File | Purpose |
|---|---|
| `inventory_cache.pkl` | Parsed inventory (read cache). Invalidated automatically when source files change. |
| `cache.pkl` | Staged mutations (staging cache). Cleared on commit or discard. |

---

## Commands

### Host management

```bash
# Add one or more hosts (NodeSet syntax supported)
bbcli host add web01 -I ./inventory/
bbcli host add 'web[01:10]' --groups webservers,staging -I ./inventory/

# Remove a host
bbcli host remove web01 -I ./inventory/

# List all hosts (NodeSet-folded group column)
bbcli host list -I ./inventory/

# Show host details and all variables (dot-notation table)
bbcli host show web01 -I ./inventory/
```

### Group management

```bash
# Add / remove a group
bbcli group add databases -I ./inventory/
bbcli group remove databases -I ./inventory/

# List all groups (hosts displayed as folded NodeSet)
bbcli group list -I ./inventory/

# Show group details and all variables (dot-notation table)
bbcli group show webservers -I ./inventory/
```

### Variable inspection

```bash
# Show every host and group that defines a variable, with source file
bbcli vars show ansible_user -I ./inventory/

# Dot-notation for nested variables
bbcli vars show network.ip -I ./inventory/
bbcli vars show disks[0].name -I ./inventory/

# Filter to hosts or groups only
bbcli vars show ansible_user -I ./inventory/ --hosts
bbcli vars show ntp_server   -I ./inventory/ --groups
```

Example output:

```
         Variable: ansible_user
┏━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
│ Kind  │ Owner      │ Value  │ Source file                           │
│ host  │ web01      │ ubuntu │ inventory/cluster/nodes/web.yml       │
│ host  │ web02      │ ubuntu │ inventory/cluster/nodes/web.yml       │
│ group │ webservers │ deploy │ inventory/group_vars/webservers.yml   │
┗━━━━━━━┻━━━━━━━━━━━━┻━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### Staging commands

```bash
bbcli pending  -I ./inventory/          # show staged changes and target files
bbcli commit   -I ./inventory/          # write changes to disk
bbcli discard  -I ./inventory/          # abandon changes (asks for confirmation)
bbcli discard  -I ./inventory/ --force  # abandon without confirmation
```

`bbcli pending` output groups individual host changes into NodeSets:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
│   │ Type         │ Nodeset / Subject │ Detail        │
│ + │ host added   │ web[11-20]        │ groups=[...] │
│ - │ host removed │ web05             │              │
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
│ File                            │ Changes                    │
│ inventory/cluster/nodes/web.yml │ + web[11-20]  - web05      │
│ inventory/staging.ini           │ - web05                    │
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

---

## Variable display format

`host show` and `group show` display variables as a flat dot-notation table:

| Type | Key format | Example |
|---|---|---|
| Scalar | `key` | `ansible_user` → `deploy` |
| Nested dict | `key.sub` | `network.ip` → `10.0.0.1` |
| Dict of dicts | `key.sub1.sub2` | `interfaces.eth0.speed` → `1G` |
| List of scalars | `key[i]` | `dns_servers[0]` → `8.8.8.8` |
| List of dicts | `key[i].sub` | `disks[0].name` → `sda` |

---

## Environment variables

| Variable | Description |
|---|---|
| `BBUI_INVENTORY` | Path to a single inventory file (used when `--inventory-dir` is not set) |
| `BBUI_INVENTORY_DIR` | Path to the inventory directory (enables staging workflow) |

---

## Development

```bash
poetry run pytest --cov=bbui
poetry run ruff check bbui
poetry run mypy bbui
```