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

## Inventory discovery

bbui resolves the active inventory using the following priority:

| Priority | Method | Inventory loaded from |
|---|---|---|
| 1 | `--inventory-dir PATH` / `-I PATH` | `PATH/inventory/` |
| 2 | `BBUI_INVENTORY_DIR=PATH` | `PATH/inventory/` |
| 3 | Auto-discovery (no flag) | `<cwd>/inventory/` |
| 4 | `--inventory FILE` / `-i FILE` | `FILE` (single file, no staging) |

`-I` and `BBUI_INVENTORY_DIR` point to the **working directory** of the project.  
bbui always looks for and loads exclusively from the `inventory/` subdirectory inside it.

Running bbcli from your project directory without any flag (auto-discovery) is equivalent to passing `-I ./`:

```bash
# These two are equivalent when run from my-project/
cd my-project/
bbcli host list

bbcli host list -I ./my-project/
```

---

## Environment variables

Instead of passing flags on every command, export the working directory:

```bash
export BBUI_INVENTORY_DIR=/path/to/my-project
bbcli host list    # loads from /path/to/my-project/inventory/
bbcli pending      # same
```

| Variable | Equivalent option | Description |
|---|---|---|
| `BBUI_INVENTORY_DIR` | `--inventory-dir` / `-I` | Working directory — inventory at `PATH/inventory/` |
| `BBUI_INVENTORY` | `--inventory` / `-i` | Path to a single inventory file (no staging) |

When both are set, `BBUI_INVENTORY_DIR` takes precedence.
