"""Staging layer: pending changes, pickle cache and commit to disk.

Workflow
--------
1. Any mutating CLI command calls ``stage(inv, inventory_dir)`` instead of
   writing directly to disk.  This serialises the modified ``Inventory`` into
   ``<inventory_dir>/.bbui/cache.pkl`` together with a list of
   ``Change`` records describing what was modified.

2. ``bbcli pending`` calls ``show_pending(inventory_dir)`` to display the
   staged changes and the files that *would* be written on commit.

3. ``bbcli commit`` calls ``commit(inventory_dir)`` which:
   a. Writes each modified group's hosts back to the originating inventory
      file (tracked in ``SourceMap``).
   b. Deletes the cache file.

4. ``bbcli discard`` calls ``discard(inventory_dir)`` to delete the cache
   without writing anything.

Cache layout
------------
``<inventory_dir>/.bbui/cache.pkl`` contains a ``StagingArea`` dataclass
(pickled) with:
  - ``inventory``  : the full modified Inventory object
  - ``changes``    : ordered list of Change records
  - ``source_map`` : mapping  host/group → originating file path
"""

from __future__ import annotations

import copy
import pickle
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from bbui.backend.models import Group, Host, Inventory
from bbui.backend.parser import dump_inventory, load_inventory_dir

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BBUI_DIR   = ".bbui"
CACHE_FILE = "cache.pkl"


# ---------------------------------------------------------------------------
# Change records
# ---------------------------------------------------------------------------

class ChangeKind(Enum):
    HOST_ADDED   = auto()
    HOST_REMOVED = auto()
    GROUP_ADDED  = auto()
    GROUP_REMOVED = auto()
    HOST_VAR_SET  = auto()
    GROUP_VAR_SET = auto()


@dataclass
class Change:
    kind:    ChangeKind
    subject: str                        # hostname or group name
    detail:  str         = ""           # human-readable extra info
    target_file: Path | None = None     # file that will be written on commit


# ---------------------------------------------------------------------------
# Source map: tracks which file each host/group came from
# ---------------------------------------------------------------------------

@dataclass
class SourceMap:
    """Maps each host and group name to the inventory file it was loaded from."""
    hosts:  dict[str, Path] = field(default_factory=dict)
    groups: dict[str, Path] = field(default_factory=dict)
    # The "default" file receives new hosts/groups with no known origin
    default_file: Path | None = None


# ---------------------------------------------------------------------------
# StagingArea
# ---------------------------------------------------------------------------

@dataclass
class StagingArea:
    inventory:  Inventory
    changes:    list[Change]
    source_map: SourceMap


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_path(inventory_dir: Path) -> Path:
    return inventory_dir / BBUI_DIR / CACHE_FILE


def has_pending(inventory_dir: Path) -> bool:
    """Return True if an uncommitted staging cache exists."""
    return _cache_path(inventory_dir).exists()


def load_cache(inventory_dir: Path) -> StagingArea:
    """Load and return the staging area from the pickle cache."""
    path = _cache_path(inventory_dir)
    if not path.exists():
        raise FileNotFoundError(f"No pending changes found in {inventory_dir}")
    with path.open("rb") as fh:
        return pickle.load(fh)  # noqa: S301


def _write_cache(staging: StagingArea, inventory_dir: Path) -> None:
    cache = _cache_path(inventory_dir)
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("wb") as fh:
        pickle.dump(staging, fh)


def discard(inventory_dir: Path) -> None:
    """Delete the staging cache without writing any changes."""
    path = _cache_path(inventory_dir)
    if path.exists():
        path.unlink()
    # Remove .bbui dir if now empty
    bbui_dir = inventory_dir / BBUI_DIR
    if bbui_dir.exists() and not any(bbui_dir.iterdir()):
        bbui_dir.rmdir()


# ---------------------------------------------------------------------------
# Build a SourceMap from an inventory directory (best-effort)
# ---------------------------------------------------------------------------

def _build_source_map(inventory_dir: Path) -> SourceMap:
    """Walk the inventory dir and record which file each host/group comes from.

    Files are processed in the same alphabetical order as ``load_inventory_dir``
    so that last-writer-wins matches the merge behaviour.
    """
    from bbui.backend.parser import (
        YAML_SUFFIXES, INI_SUFFIXES, GROUP_VARS_DIR,
        _load_yaml_file, _load_ini_file, _detect_format,
    )

    smap = SourceMap()
    yaml_files: list[Path] = []

    for filepath in sorted(inventory_dir.rglob("*")):
        if not filepath.is_file():
            continue
        if GROUP_VARS_DIR in filepath.parts:
            continue
        suffix = filepath.suffix.lower()
        if suffix in YAML_SUFFIXES:
            yaml_files.append(filepath)
        elif suffix in INI_SUFFIXES:
            pass  # handled below generically

    # Generic scan: parse each file in isolation and record origins
    for filepath in sorted(inventory_dir.rglob("*")):
        if not filepath.is_file():
            continue
        if GROUP_VARS_DIR in filepath.parts:
            continue
        suffix = filepath.suffix.lower()
        if suffix not in YAML_SUFFIXES and suffix not in INI_SUFFIXES and suffix != "":
            continue

        tmp = Inventory()
        try:
            fmt = _detect_format(filepath)
            if fmt == "yaml":
                _load_yaml_file(tmp, filepath)
            else:
                _load_ini_file(tmp, filepath)
        except Exception:
            continue

        for h in tmp.list_hosts():
            smap.hosts[h.name] = filepath
        for g in tmp.list_groups():
            smap.groups[g.name] = filepath

    # Default write target: first YAML file, or a new inventory.yml
    yaml_files_root = [
        f for f in sorted((inventory_dir).iterdir())
        if f.is_file() and f.suffix.lower() in YAML_SUFFIXES
    ]
    smap.default_file = yaml_files_root[0] if yaml_files_root else inventory_dir / "inventory.yml"

    return smap


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_inventory_or_cache(inventory_dir: Path) -> Inventory:
    """Return the staged inventory if a cache exists, otherwise load from disk."""
    if has_pending(inventory_dir):
        return load_cache(inventory_dir).inventory
    return load_inventory_dir(inventory_dir)


def stage(
    inventory: Inventory,
    changes: list[Change],
    inventory_dir: Path,
    existing_staging: StagingArea | None = None,
) -> None:
    """Persist *inventory* + *changes* to the staging cache.

    If *existing_staging* is provided its previous changes are prepended so
    that ``bbcli pending`` shows the full accumulated diff.
    """
    if existing_staging is not None:
        source_map = existing_staging.source_map
        all_changes = existing_staging.changes + changes
    else:
        source_map = _build_source_map(inventory_dir)
        all_changes = changes

    # Annotate each new change with its target file
    for change in changes:
        if change.target_file is None:
            change.target_file = (
                source_map.hosts.get(change.subject)
                or source_map.groups.get(change.subject)
                or source_map.default_file
            )

    staging = StagingArea(
        inventory=copy.deepcopy(inventory),
        changes=all_changes,
        source_map=source_map,
    )
    _write_cache(staging, inventory_dir)


def commit(inventory_dir: Path) -> dict[Path, int]:
    """Write pending changes to disk and clear the cache.

    Returns a mapping  {file_path: nb_of_changes_written}.
    """
    staging = load_cache(inventory_dir)
    inv     = staging.inventory
    smap    = staging.source_map

    # Collect the set of files that need to be rewritten
    touched: set[Path] = set()
    for change in staging.changes:
        if change.target_file:
            touched.add(change.target_file)
    if not touched and smap.default_file:
        touched.add(smap.default_file)

    # For each touched file, rebuild an Inventory containing only the hosts/
    # groups that originate from that file, then dump it.
    file_change_counts: dict[Path, int] = {}

    for target in sorted(touched):
        # Build a per-file sub-inventory
        sub = Inventory()
        for g in inv.list_groups():
            origin = smap.groups.get(g.name, smap.default_file)
            if origin == target:
                sub._ensure_group(g.name).vars = dict(g.vars)
                sub._ensure_group(g.name).children = list(g.children)
        for h in inv.list_hosts():
            origin = smap.hosts.get(h.name, smap.default_file)
            if origin == target:
                for gname in h.groups:
                    sub._ensure_group(gname).add_host(h.name)
                sub._hosts[h.name] = copy.deepcopy(h)

        target.parent.mkdir(parents=True, exist_ok=True)
        dump_inventory(sub, target)

        nb = sum(1 for c in staging.changes if c.target_file == target)
        file_change_counts[target] = nb

    discard(inventory_dir)
    return file_change_counts


def diff_summary(staging: StagingArea) -> list[tuple[Change, Path | None]]:
    """Return a list of (change, target_file) pairs for display."""
    return [(c, c.target_file) for c in staging.changes]
