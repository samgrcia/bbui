# CLI reference

## Global options

All commands accept these two options:

| Option | Short | Env | Description |
|---|---|---|---|
| `--inventory PATH` | `-i` | `BBUI_INVENTORY` | Single inventory file (YAML or INI). Writes immediately. |
| `--inventory-dir PATH` | `-I` | `BBUI_INVENTORY_DIR` | Inventory directory. Enables the staging workflow. |

When `--inventory-dir` is used, changes are **staged** and require a `bbcli commit` to be persisted.

---

## Hosts

### `bbcli host add <nodeset>`

Stages the addition of one or more hosts. Supports NodeSet syntax.

```bash
bbcli host add web01 -I ./inventory/
bbcli host add 'web[01:10]' --groups webservers,staging -I ./inventory/
bbcli host add 'c[001:100]' --groups fn_compute,hw_typeA,os_ubuntu -I ./inventory/
```

| Option | Short | Description |
|---|---|---|
| `--groups LIST` | `-g` | Comma-separated list of groups to assign to the hosts |

**BlueBanquise layout**: the three prefixes `fn_*`, `hw_*`, `os_*` are mandatory.  
A host that already exists is silently skipped.

---

### `bbcli host remove <hostname>`

Stages the removal of a host.

```bash
bbcli host remove web05 -I ./inventory/
```

---

### `bbcli host list`

Lists all hosts, their groups, and their variables.  
If changes are staged, the staged view is shown (with a warning).

```bash
bbcli host list -I ./inventory/
```

```
┌─ Hosts ──────────────────────────────────────────────────────┐
│ Name  │ Groups                          │ Vars               │
│ c001  │ fn_compute, hw_typeA, os_ubuntu │                    │
│ mgt1  │ fn_management, hw_typeC, os_rhel│ {'ip': '10.0.0.1'} │
└──────────────────────────────────────────────────────────────┘
```

---

### `bbcli host show <nodeset> [varname]`

Shows details and variables for one or more hosts.

```bash
# Full details for a single host
bbcli host show web01 -I ./inventory/

# Details for multiple hosts via NodeSet
bbcli host show 'web[01:05]' -I ./inventory/

# Show a single variable across a range of hosts
bbcli host show 'c[001:010]' bmc.ip4 -I ./inventory/
bbcli host show 'c[001:010]' disks[0].name -I ./inventory/
```

In single-variable mode, the output is a compact `Host | Value` table.  
In full mode, each host is shown in its own block with variables in dot-notation.

---

## Groups

### `bbcli group add <name>`

Stages the addition of a group.

```bash
bbcli group add storage -I ./inventory/
```

---

### `bbcli group remove <name>`

Stages the removal of a group.

```bash
bbcli group remove storage -I ./inventory/
```

---

### `bbcli group list`

Lists all groups with their hosts (folded NodeSet) and child groups.

```bash
bbcli group list -I ./inventory/
```

```
┌─ Groups ──────────────────────────────────────────┐
│ Name            │ Hosts        │ Children          │
│ fn_compute      │ c[001:004]   │                   │
│ fn_management   │ mgt[1:2]     │                   │
│ hw_cpu_type_A   │ c[001:004]   │                   │
└───────────────────────────────────────────────────┘
```

---

### `bbcli group show <name>`

Shows details of a group: hosts, child groups, and variables.

```bash
bbcli group show webservers -I ./inventory/
```

---

## Variables

### `bbcli vars show <varname>`

Shows every host and group that defines `<varname>`, with its value and source file.  
Supports dot-notation for nested values.

```bash
# Simple variable
bbcli vars show ansible_user -I ./inventory/

# Nested variable
bbcli vars show network.ip -I ./inventory/
bbcli vars show bmc.ip4 -I ./inventory/

# List element
bbcli vars show disks[0].name -I ./inventory/

# Filters
bbcli vars show ansible_user -I ./inventory/ --hosts   # hosts only
bbcli vars show ntp_server   -I ./inventory/ --groups  # groups only
```

| Option | Short | Description |
|---|---|---|
| `--hosts` | `-H` | Show only host matches |
| `--groups` | `-G` | Show only group matches |

Example output:

```
         Variable: ansible_user
┌───────┬────────────┬────────┬──────────────────────────────────────┐
│ Kind  │ Owner      │ Value  │ Source file                           │
│ host  │ web01      │ ubuntu │ inventory/cluster/nodes/web.yml       │
│ host  │ web02      │ ubuntu │ inventory/cluster/nodes/web.yml       │
│ group │ webservers │ deploy │ inventory/group_vars/webservers.yml   │
└───────┴────────────┴────────┴──────────────────────────────────────┘
```

### Dot-notation syntax

| Value type | Format | Example |
|---|---|---|
| Scalar | `key` | `ansible_user` |
| Nested dict | `key.sub` | `network.ip` |
| Deep dict | `key.sub1.sub2` | `interfaces.eth0.speed` |
| List element | `key[i]` | `dns_servers[0]` |
| Key in list | `key[i].sub` | `disks[0].name` |

---

## Staging

### `bbcli pending`

Shows staged changes and the files that will be written on the next `commit`.

```bash
bbcli pending -I ./inventory/
```

Requires `--inventory-dir`.

---

### `bbcli commit`

Writes all staged changes to disk and clears the staging cache.

```bash
bbcli commit -I ./inventory/
```

Requires `--inventory-dir`.

---

### `bbcli discard`

Drops all staged changes without writing to disk.

```bash
bbcli discard -I ./inventory/          # asks for confirmation
bbcli discard -I ./inventory/ --force  # no confirmation
```

| Option | Short | Description |
|---|---|---|
| `--force` | `-f` | Skip confirmation prompt |

Requires `--inventory-dir`.
