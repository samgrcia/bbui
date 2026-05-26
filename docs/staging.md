# Staging workflow

bbui uses a git-inspired staging system: changes accumulate in memory and are never written to disk without an explicit `commit`.

Staging is enabled as soon as you use `--inventory-dir` / `-I`.  
With `--inventory` / `-i` (single file), changes are written immediately.

---

## Overview

```
bbcli host add 'c[011:020]' --groups fn_compute,hw_typeA,os_ubuntu -I ./inventory/
      │
      ▼
  [staging cache]   ←  inventory_cache.pkl (read) + cache.pkl (mutations)
      │
      ├──  bbcli pending   →  preview changes and target files
      │
      ├──  bbcli commit    →  write to disk, clear cache
      │
      └──  bbcli discard   →  drop changes, clear cache
```

---

## The two caches

Both caches live under `<inventory-dir>/.bbui/`:

| File | Purpose | Lifecycle |
|---|---|---|
| `inventory_cache.pkl` | Parsed inventory (speeds up successive reads) | Invalidated when any source file is newer |
| `cache.pkl` | Staged mutations (modified inventory + change list) | Created by `stage`, deleted by `commit` or `discard` |

While `cache.pkl` is present, all read commands (`host list`, `host show`, etc.) use it and display a warning that uncommitted changes are active.

---

## Commands

### `bbcli pending`

Shows staged changes and the files that will be written.

```
┌─ Pending changes ────────────────────────────────────┐
│   │ Type       │ Nodeset / Subject │ Detail           │
│ + │ host added │ c[011:020]        │ groups=[...]     │
└──────────────────────────────────────────────────────┘

┌─ Files to be written ──────────────────────────────────┐
│ File                              │ Changes             │
│ inventory/cluster/nodes/nodes.yml │ + c[011:020]        │
│ inventory/cluster/groups/fn       │ + c[011:020]        │
│ inventory/cluster/groups/hw       │ + c[011:020]        │
│ inventory/cluster/groups/os       │ + c[011:020]        │
└────────────────────────────────────────────────────────┘
```

### `bbcli commit`

Writes all mutations to disk and deletes `cache.pkl`.

In BlueBanquise layout, each host is written back to the file it was loaded from.  
New hosts are co-located with existing peers of the same `fn_*` group.

```bash
bbcli commit -I ./inventory/
# ✓ inventory/cluster/nodes/nodes.yml  (10 change(s))
# ✓ inventory/cluster/groups/fn        (1 change(s))
# Commit complete.
```

### `bbcli discard`

Drops all staged mutations without writing to disk.

```bash
bbcli discard -I ./inventory/          # asks for confirmation
bbcli discard -I ./inventory/ --force  # no confirmation
```

---

## Accumulating changes

Multiple successive commands accumulate in the same `cache.pkl`:

```bash
bbcli host add 'c[011:015]' --groups fn_compute,hw_typeA,os_ubuntu -I ./inventory/
bbcli host add 'mgt3'       --groups fn_management,hw_typeC,os_rhel -I ./inventory/
bbcli host remove c005 -I ./inventory/
bbcli pending -I ./inventory/   # shows all 3 changes together
bbcli commit  -I ./inventory/   # writes everything in one pass
```

---

## Read consistency

While `cache.pkl` is present, read commands (`host list`, `host show`, `vars show`) return the **staged** state rather than the on-disk state.  
A warning banner indicates this:

```
⚠ Showing staged inventory (uncommitted changes present)
```
