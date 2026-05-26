# bbui

**bbui** is a command-line Ansible inventory manager.  
It supports YAML and INI formats, the BlueBanquise layout, and a git-like staging workflow.

---

## Features

| Feature | Description |
|---|---|
| Multi-format | Read and write YAML and INI inventories |
| BlueBanquise | Layout and group rules enforced automatically |
| Staging | Changes are never written without an explicit `commit` |
| NodeSet | Host range expressions (`c[001:100]`) via ClusterShell |
| Dot-notation | Inspect nested variables (`bmc.ip4`, `disks[0].name`) |

---

## Quick start

```bash
# Install
poetry install

# List hosts in an inventory
bbcli host list -I ./my-inventory/

# Add hosts (BlueBanquise layout)
bbcli host add 'c[001:010]' --groups fn_compute,hw_typeA,os_ubuntu -I ./my-inventory/

# Review what will be written
bbcli pending -I ./my-inventory/

# Write to disk
bbcli commit -I ./my-inventory/
```

---

## Documentation

- [Installation](installation.md)
- [Inventory layouts](inventory-layouts.md)
- [NodeSet syntax](nodeset.md)
- [Staging workflow](staging.md)
- [CLI reference](cli-reference.md)
