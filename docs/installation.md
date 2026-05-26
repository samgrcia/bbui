# Installation

## Requirements

| Dependency | Version |
|---|---|
| Python | 3.14+ |
| [ClusterShell](https://clustershell.readthedocs.io/) | ^1.9 |
| [Poetry](https://python-poetry.org/) | For development |

ClusterShell is installed automatically by Poetry.

---

## From the repository

```bash
git clone https://github.com/samgrcia/bbui.git
cd bbui
poetry install
```

Verify:

```bash
poetry run bbcli --help
```

---

## Environment variables

Instead of passing `--inventory` or `--inventory-dir` on every command, you can export them:

```bash
export BBUI_INVENTORY_DIR=/path/to/my-inventory
bbcli host list          # equivalent to bbcli host list -I /path/to/my-inventory
```

| Variable | Equivalent option | Description |
|---|---|---|
| `BBUI_INVENTORY` | `--inventory` / `-i` | Path to a single inventory file |
| `BBUI_INVENTORY_DIR` | `--inventory-dir` / `-I` | Inventory directory (enables staging) |

When both are set, `--inventory-dir` / `BBUI_INVENTORY_DIR` takes precedence.
