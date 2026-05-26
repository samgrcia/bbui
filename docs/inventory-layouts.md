# Inventory layouts

bbui supports two layouts: a generic Ansible layout and the structured BlueBanquise layout.  
Detection is automatic on every command.

---

## Generic layout

A directory containing any mix of YAML and INI files.

```
inventory/
├── hosts.yml           # hosts in YAML
├── staging.ini         # hosts in INI
└── group_vars/
    ├── all.yml         # vars applied to all groups
    ├── webservers.yml  # vars for group "webservers"
    └── databases/      # vars for "databases" (directory layout)
        ├── main.yml
        └── secrets.yml
```

Files are loaded alphabetically; last-writer-wins on conflicts.  
`group_vars/` is applied last, matching Ansible's own precedence rules.

### YAML format

```yaml
all:
  children:
    webservers:
      hosts:
        web01:
          ansible_user: ubuntu
        web02:
```

### INI format

```ini
[webservers]
web01 ansible_user=ubuntu
web02

[webservers:vars]
ansible_become=true

[production:children]
webservers
```

`:vars` and `:children` sections are supported.

---

## BlueBanquise layout

bbui automatically detects the BlueBanquise layout as soon as the directory passed to `-I` contains `cluster/nodes/` or `cluster/groups/`.

> **Important**: always point `-I` at the parent of `cluster/`, not at `cluster/` itself.

```
inventory-root/           ← pass this path to -I
├── cluster/
│   ├── nodes/
│   │   ├── compute.yml   # fn_compute hosts + their vars
│   │   ├── login.yml     # fn_login hosts + their vars
│   │   └── management.yml
│   └── groups/
│       ├── fn            # fn_* group declarations (INI, no extension)
│       ├── hw            # hw_* group declarations
│       ├── os            # os_* group declarations
│       └── others        # user-defined groups (default bucket)
└── group_vars/
    └── ...
```

### Mandatory group membership

Every host **must** belong to exactly one group from each of the three base prefixes:

| Prefix | Purpose | Examples |
|---|---|---|
| `fn_` | Function (functional role) | `fn_compute`, `fn_management`, `fn_login` |
| `hw_` | Hardware type | `hw_cpu_server_type_A`, `hw_gpu_type_B` |
| `os_` | Operating system | `os_ubuntu_24`, `os_rhel_9` |

```bash
# Correct — all three prefixes present
bbcli host add 'c[001:010]' --groups fn_compute,hw_typeA,os_ubuntu -I ./inventory-root/

# Error — missing hw_* group
bbcli host add c011 --groups fn_compute,os_ubuntu -I ./inventory-root/

# Error — two fn_* groups
bbcli host add c012 --groups fn_compute,fn_login,hw_typeA,os_ubuntu -I ./inventory-root/
```

### File routing

#### Node files (`cluster/nodes/`)

Each node file is a standard Ansible YAML file with `all` as the root key:

```yaml
all:
  hosts:
    c001:
      bmc_ip: 10.0.0.1
    c002:
```

- **Existing** hosts are written back to the file they were loaded from.
- **New** hosts are co-located with existing peers of the same `fn_*` group (alphabetically first peer file wins).
- If no peer exists yet, a new `<fn_suffix>.yml` file is created.

#### Group files (`cluster/groups/`)

Group files use INI format (no extension).  
Hosts appear as **Ansible NodeSet** expressions (`node[01:10]`) rather than one per line.

```ini
[fn_compute]
c[001:004]

[fn_management]
mgt[1:2]
```

- `fn_*`, `hw_*`, and `os_*` groups are always written to their canonical files (`fn`, `hw`, `os`).
- User-defined groups loaded from a named file are written back to that same file.
- User-defined groups created from scratch go to `cluster/groups/others`.

### Cache

bbui maintains two caches under `<inventory-root>/.bbui/`:

| File | Purpose |
|---|---|
| `inventory_cache.pkl` | Parsed inventory (read cache). Invalidated when any source file is newer. |
| `cache.pkl` | Staged mutations. Present only between `stage` and `commit` / `discard`. |

Caches are automatically invalidated when the layout type changes (e.g. after migrating to the BlueBanquise layout).
