# bbui

Ansible YAML/INI inventory manager with a Python backend and a Typer CLI.

## Installation

```bash
poetry install
```

> **Requires** Python 3.14 and [ClusterShell](https://clustershell.readthedocs.io/) (`clustershell ^1.9`), installed automatically by Poetry.

---

## Workdir and inventory discovery

bbui resolves the active inventory using the following priority:

| Priority | How | Inventory loaded from |
|---|---|---|
| 1 | `--inventory-dir PATH` / `-I PATH` | `PATH/inventory/` |
| 2 | `BBUI_INVENTORY_DIR=PATH` env var | `PATH/inventory/` |
| 3 | Auto-discovery (no flag) | `<cwd>/inventory/` |
| 4 | `--inventory FILE` / `-i FILE` | `FILE` (single file, no staging) |

`-I` and `BBUI_INVENTORY_DIR` point to the **working directory** — bbui always looks for the `inventory/` subdirectory inside it.  
Running bbcli from a workdir without any flag has the same effect as passing `-I ./`.

---

## Workdir layout

```
<workdir>/                  ← pass to -I, or run bbcli from here
└── inventory/              ← bbui reads exclusively from here
    ├── cluster/
    │   ├── nodes/
    │   │   └── web.yml     # host declarations
    │   └── groups/
    │       └── webservers  # group declarations (INI, no extension)
    ├── staging.ini         # additional INI inventory (generic layout)
    └── group_vars/
        ├── all.yml         # vars applied to every group
        ├── webservers.yml  # vars for group "webservers"
        └── databases/      # vars for group "databases" (directory layout)
            ├── main.yml
            └── secrets.yml
```

Files are merged alphabetically; last-writer-wins on conflicts. `group_vars/` is applied last.

---

## BlueBanquise layout

When bbui detects `cluster/nodes/` or `cluster/groups/` inside `inventory/`, it automatically enables the stricter `BbInventory` mode.

```
<workdir>/
└── inventory/
    ├── cluster/
    │   ├── nodes/
    │   │   ├── compute.yml   # hosts in fn_compute + their vars
    │   │   ├── login.yml
    │   │   └── management.yml
    │   └── groups/
    │       ├── fn            # fn_* group declarations (INI, no extension)
    │       ├── hw            # hw_* group declarations
    │       ├── os            # os_* group declarations
    │       └── others        # user-defined groups
    └── group_vars/
        └── ...
```

### Mandatory group membership

Every host **must** belong to exactly one group from each of the three base prefixes:

| Prefix | Purpose | Example |
|---|---|---|
| `fn_` | Function (role) | `fn_compute`, `fn_management`, `fn_login` |
| `hw_` | Hardware type | `hw_cpu_server_type_A`, `hw_gpu_type_B` |
| `os_` | Operating system | `os_ubuntu_24`, `os_rhel_9` |

```bash
# Correct — all three prefixes present
bbcli host add c[001-010] --groups fn_compute,hw_typeA,os_ubuntu -I ./my-project/

# Error — missing hw_* group
bbcli host add c011 --groups fn_compute,os_ubuntu -I ./my-project/
```

### Write-back routing

On `commit`, each host is written back to the file it was loaded from. A newly added host is co-located with its existing `fn_*` peers. Non-base groups go to `cluster/groups/others` unless they were loaded from a named file.

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

```bash
bbcli host add web[11-20] --groups webservers,staging -I ./my-project/
bbcli pending   -I ./my-project/    # review what will be written and where
bbcli commit    -I ./my-project/    # write to disk
bbcli discard   -I ./my-project/    # abandon changes
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
bbcli host add web01 -I ./my-project/
bbcli host add 'web[01:10]' --groups webservers,staging -I ./my-project/

# Remove a host
bbcli host remove web01 -I ./my-project/

# List all hosts
bbcli host list -I ./my-project/

# Show host details and variables (dot-notation table)
bbcli host show web01 -I ./my-project/
```

### Group management

```bash
bbcli group add databases   -I ./my-project/
bbcli group remove databases -I ./my-project/
bbcli group list            -I ./my-project/
bbcli group show webservers -I ./my-project/
```

### Variable inspection

```bash
# Show every host and group that defines a variable, with source file
bbcli vars show ansible_user -I ./my-project/

# Dot-notation for nested variables
bbcli vars show network.ip      -I ./my-project/
bbcli vars show disks[0].name   -I ./my-project/

# Filter to hosts or groups only
bbcli vars show ansible_user -I ./my-project/ --hosts
bbcli vars show ntp_server   -I ./my-project/ --groups
```

### Staging commands

```bash
bbcli pending  -I ./my-project/          # show staged changes
bbcli commit   -I ./my-project/          # write changes to disk
bbcli discard  -I ./my-project/          # abandon changes
bbcli discard  -I ./my-project/ --force  # abandon without confirmation
```

---

## Variable display format

| Type | Key format | Example |
|---|---|---|
| Scalar | `key` | `ansible_user` → `deploy` |
| Nested dict | `key.sub` | `network.ip` → `10.0.0.1` |
| Dict of dicts | `key.sub1.sub2` | `interfaces.eth0.speed` → `1G` |
| List of scalars | `key[i]` | `dns_servers[0]` → `8.8.8.8` |
| List of dicts | `key[i].sub` | `disks[0].name` → `sda` |

---

## Environment variables

| Variable | Equivalent option | Description |
|---|---|---|
| `BBUI_INVENTORY_DIR` | `--inventory-dir` / `-I` | Working directory — inventory loaded from `PATH/inventory/` |
| `BBUI_INVENTORY` | `--inventory` / `-i` | Path to a single inventory file (single-file mode, no staging) |

---

## Development

```bash
poetry run pytest --cov=bbui
poetry run ruff check bbui
poetry run mypy bbui
```
