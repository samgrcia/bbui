# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
poetry install

# Run tests with coverage
poetry run pytest --cov=bbui

# Run a single test
poetry run pytest tests/test_backend.py::test_load_inventory -v

# Lint
poetry run ruff check bbui

# Type-check (strict mode)
poetry run mypy bbui

# Run the CLI
poetry run bbcli --help
poetry run bbcli host list -I ./samples/bluebanquise-simple/
```

## Architecture

The project is a CLI tool (`bbcli`) for managing Ansible YAML/INI inventory files, with a git-like staging workflow.

### Layer overview

**`bbui/backend/models.py`** — Domain model. `Host`, `Group`, and `Inventory` are plain dataclasses. `Inventory` is the central aggregate: it keeps `_hosts` and `_groups` dicts and enforces referential integrity (e.g. adding a host auto-registers it in its groups).

**`bbui/backend/parser.py`** — Reads/writes inventory files. `load_inventory()` handles a single file; `load_inventory_dir()` merges all YAML/INI files in a directory (alphabetically, last-writer-wins) then applies `group_vars/` on top. `dump_inventory()` round-trips back to the original format (detected by extension). Internal helpers `_load_yaml_file` / `_load_ini_file` are imported by the staging layer to reparse individual files at commit time.

**`bbui/backend/staging.py`** — Two-cache staging system under `<inventory_dir>/.bbui/`:

| File | Purpose |
|---|---|
| `inventory_cache.pkl` | Parsed `Inventory` + mtime fingerprint. Auto-invalidated when any source file is newer. |
| `cache.pkl` | `StagingArea` (Inventory + Changes + SourceMap). Present only when mutations are staged; takes priority over the read cache. |

`stage()` writes `cache.pkl`. `commit()` re-parses each affected file individually, applies only the changes belonging to it, and writes it back — ensuring that a removal propagates to every file that referenced the host/group, not just its origin. `discard()` deletes `cache.pkl` and invalidates the read cache. `clear_cache()` removes both cache files and the `.bbui/` directory if it becomes empty.

**`bbui/backend/nodeset.py`** — Thin wrapper around ClusterShell's `NodeSet` for expanding (`expand_nodeset`) and folding (`fold_nodeset`) host range expressions like `web[01-10]`.

**`bbui/backend/vars_lookup.py`** — Variable inspection: `build_var_source_map()` maps each variable key to the file that contributed it; `lookup_var()` resolves dot-notation paths (e.g. `network.ip`, `disks[0].name`) across all hosts and groups.

**`bbui/cli/main.py`** — Typer app. Four sub-apps: `host`, `group`, `vars`, `network`. Top-level workflow commands: `pending`, `commit`, `discard`, `clear`. Two load helpers: `_load_clean()` reads directly from disk (for read-only commands that should ignore staged state) and `_load()` calls `load_inventory_or_cache()` (for commands that respect staged changes).

**`bbui/cli/vars_display.py`** — Rich table rendering for variable display in flat dot-notation format.

### Key design invariant

Mutating commands (`host add`, `host remove`, etc.) always go through `stage()` when `--inventory-dir` is set — changes are never written directly. The CLI must call `bbcli commit` to persist. When `--inventory` (single file) is used instead, mutations are written immediately via `dump_inventory()`.
