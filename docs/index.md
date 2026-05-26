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
| Auto-discovery | Detects `inventory/` inside the current working directory |

---

## Quick start

```bash
# Install
poetry install

# Run from your project directory — bbcli auto-discovers inventory/
cd my-project/
bbcli host list

# Or pass the working directory explicitly
bbcli host list -I ./my-project/

# Add hosts (BlueBanquise layout)
bbcli host add 'c[001:010]' --groups fn_compute,hw_typeA,os_ubuntu -I ./my-project/

# Review what will be written
bbcli pending -I ./my-project/

# Write to disk
bbcli commit -I ./my-project/
```

---

## Documentation

- [Installation](installation.md)
- [Inventory layouts](inventory-layouts.md)
- [NodeSet syntax](nodeset.md)
- [Staging workflow](staging.md)
- [CLI reference](cli-reference.md)
