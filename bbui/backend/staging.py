"""Staging layer: pending changes, pickle cache and commit to disk.

Two independent caches live under ``<inventory_dir>/.bbui/``:

inventory_cache.pkl  (read cache)
    Stores the fully-parsed Inventory together with a fingerprint
    (the maximum mtime of all source files).  Every read command checks
    whether the fingerprint is still valid before returning the cached
    object; if any source file is newer the cache is silently rebuilt.
    This avoids re-parsing all YAML/INI files on every CLI invocation.

cache.pkl  (staging cache)
    Stores a StagingArea (Inventory + Changes + SourceMap) for mutations
    that have not yet been committed.  When this file is present it takes
    absolute priority over the read cache: all commands see the staged
    state.  Cleared by ``bbcli commit`` and ``bbcli discard``.

Workflow
--------
1. Any mutating command calls ``stage()``, which writes ``cache.pkl`` and
   invalidates ``inventory_cache.pkl`` (so the next read rebuilds it from
   the staged inventory, not from disk).

2. ``bbcli pending`` shows staged changes grouped as NodeSets.

3. ``bbcli commit`` writes touched files to disk, deletes ``cache.pkl``,
   then rebuilds ``inventory_cache.pkl`` from the freshly written files.

4. ``bbcli discard`` deletes ``cache.pkl`` and invalidates
   ``inventory_cache.pkl`` so the next read reloads from disk.
"""

from __future__ import annotations

import copy
import pickle
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from bbui.backend.models import Group, Host, Inventory
from bbui.backend.nodeset import fold_nodeset
from bbui.backend.parser import dump_inventory, load_inventory_dir

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BBUI_DIR        = ".bbui"
CACHE_FILE      = "cache.pkl"
INV_CACHE_FILE  = "inventory_cache.pkl"


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
    """Maps each host and group name to ALL inventory files that mention it.

    A host may appear in several files (e.g. declared in hosts.yml and also
    listed in staging.ini).  On commit every one of those files must be
    rewritten so that removals and renames propagate everywhere.
    """
    # host/group name -> set of files that contain it
    hosts:  dict[str, set[Path]] = field(default_factory=dict)
    groups: dict[str, set[Path]] = field(default_factory=dict)
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
    """Delete the staging cache without writing any changes.

    Also invalidates the read cache so the next command reloads from disk,
    ensuring the view is consistent with the on-disk state.
    """
    path = _cache_path(inventory_dir)
    if path.exists():
        path.unlink()
    _invalidate_inv_cache(inventory_dir)
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
        YAML_SUFFIXES, INI_SUFFIXES, GROUP_VARS_DIR, VAULT_STEM,
        _load_yaml_file, _load_ini_file, _detect_format,
    )

    smap = SourceMap()
    yaml_files: list[Path] = []

    for filepath in sorted(inventory_dir.rglob("*")):
        if not filepath.is_file():
            continue
        if GROUP_VARS_DIR in filepath.parts:
            continue
        if filepath.stem.lower() == VAULT_STEM:
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
        if filepath.stem.lower() == VAULT_STEM:
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
            smap.hosts.setdefault(h.name, set()).add(filepath)
        for g in tmp.list_groups():
            smap.groups.setdefault(g.name, set()).add(filepath)

    # Default write target: first YAML file, or a new inventory.yml
    yaml_files_root = [
        f for f in sorted((inventory_dir).iterdir())
        if f.is_file() and f.suffix.lower() in YAML_SUFFIXES
    ]
    smap.default_file = yaml_files_root[0] if yaml_files_root else inventory_dir / "inventory.yml"

    return smap


# ---------------------------------------------------------------------------
# Read cache (inventory_cache.pkl)
# ---------------------------------------------------------------------------

@dataclass
class InvCache:
    """Pickled read cache: parsed inventory + source fingerprint."""
    inventory:   Inventory
    fingerprint: float          # max mtime of all source files at build time


def _inv_cache_path(inventory_dir: Path) -> Path:
    return inventory_dir / BBUI_DIR / INV_CACHE_FILE


def _source_fingerprint(inventory_dir: Path) -> float:
    """Return the maximum mtime across all inventory source files."""
    from bbui.backend.parser import YAML_SUFFIXES, INI_SUFFIXES, GROUP_VARS_DIR
    max_mtime = 0.0
    for filepath in inventory_dir.rglob("*"):
        if not filepath.is_file():
            continue
        suffix = filepath.suffix.lower()
        if suffix in YAML_SUFFIXES or suffix in INI_SUFFIXES or (
            suffix == "" and GROUP_VARS_DIR not in filepath.parts
        ):
            mtime = filepath.stat().st_mtime
            if mtime > max_mtime:
                max_mtime = mtime
    return max_mtime


def _load_inv_cache(inventory_dir: Path) -> Inventory | None:
    """Return the cached Inventory if it is still valid, else None."""
    cache_path = _inv_cache_path(inventory_dir)
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("rb") as fh:
            inv_cache: InvCache = pickle.load(fh)  # noqa: S301
    except Exception:
        return None
    # Validate fingerprint
    if _source_fingerprint(inventory_dir) > inv_cache.fingerprint:
        return None
    return inv_cache.inventory


def _save_inv_cache(inventory: Inventory, inventory_dir: Path) -> None:
    """Persist *inventory* to the read cache with the current fingerprint."""
    cache_path = _inv_cache_path(inventory_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    inv_cache = InvCache(
        inventory=copy.deepcopy(inventory),
        fingerprint=_source_fingerprint(inventory_dir),
    )
    with cache_path.open("wb") as fh:
        pickle.dump(inv_cache, fh)


def _invalidate_inv_cache(inventory_dir: Path) -> None:
    """Delete the read cache so the next read rebuilds it."""
    p = _inv_cache_path(inventory_dir)
    if p.exists():
        p.unlink()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_inventory_or_cache(inventory_dir: Path) -> Inventory:
    """Return the active inventory for *inventory_dir*, using caches when valid.

    Priority:
    1. Staging cache (``cache.pkl``) — present when there are uncommitted changes.
    2. Read cache (``inventory_cache.pkl``) — valid when no source file is newer.
    3. Full parse — rebuilds the read cache.  Uses :class:`BbInventory` when the
       directory follows the BlucBanquise layout (contains ``nodes/`` or ``groups/``).
    """
    from bbui.backend.bbinventory import BbInventory

    # 1. Staging cache takes absolute priority
    if has_pending(inventory_dir):
        staging_inv = load_cache(inventory_dir).inventory
        if BbInventory.is_bb_layout(inventory_dir) and not isinstance(staging_inv, BbInventory):
            # Stale staging cache created before BbInventory migration — discard it.
            discard(inventory_dir)
        else:
            return staging_inv

    # 2. Read cache (fingerprint-validated)
    cached = _load_inv_cache(inventory_dir)
    if cached is not None:
        # Discard stale cache when the layout is BB but the cached type is not.
        # This happens after a migration from plain Inventory to BbInventory.
        if BbInventory.is_bb_layout(inventory_dir) and not isinstance(cached, BbInventory):
            _invalidate_inv_cache(inventory_dir)
        else:
            return cached

    # 3. Full parse + persist read cache
    if BbInventory.is_bb_layout(inventory_dir):
        inventory: Inventory = BbInventory.load(inventory_dir)
    else:
        inventory = load_inventory_dir(inventory_dir)
    _save_inv_cache(inventory, inventory_dir)
    return inventory


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

    # Annotate each new change with its primary target file.
    # For BbInventory, use _target_nodes_file() / group_file() which honour the
    # source-file tracking and produce correct paths for both existing and new
    # subjects.  For generic inventories, fall back to the source-map heuristic.
    from bbui.backend.bbinventory import BbInventory
    is_bb = isinstance(inventory, BbInventory)

    for change in changes:
        if change.target_file is not None:
            continue
        if is_bb:
            if change.kind == ChangeKind.HOST_ADDED:
                host = inventory.get_host(change.subject)
                change.target_file = inventory._target_nodes_file(host, inventory_dir)
            elif change.kind == ChangeKind.HOST_REMOVED:
                # Removed hosts: point to their known source file (or default nodes dir)
                change.target_file = inventory._host_source.get(
                    change.subject,
                    inventory_dir / "cluster" / "nodes" / "nodes.yml",
                )
            elif change.kind in (ChangeKind.GROUP_ADDED, ChangeKind.GROUP_REMOVED):
                change.target_file = inventory.group_file(change.subject, inventory_dir)
        else:
            files = (
                source_map.hosts.get(change.subject)
                or source_map.groups.get(change.subject)
                or set()
            )
            change.target_file = min(files) if files else source_map.default_file

    staging = StagingArea(
        inventory=copy.deepcopy(inventory),
        changes=all_changes,
        source_map=source_map,
    )
    _write_cache(staging, inventory_dir)
    # Invalidate the read cache: subsequent reads will see the staged state
    _invalidate_inv_cache(inventory_dir)


def commit(inventory_dir: Path) -> dict[Path, int]:
    """Write pending changes to disk and clear the cache.

    For BlucBanquise inventories (:class:`BbInventory`) the staged inventory
    is written via :meth:`BbInventory.dump`, which rewrites the whole
    ``nodes/`` + ``groups/`` layout in one shot.

    For all other inventories the standard file-by-file patching strategy is
    used:

    * A host removed from the global inventory is removed from **every**
      file that referenced it, not just its primary origin file.
    * Hosts/groups that live in other files are left untouched.

    Returns a mapping  {file_path: nb_of_changes_applied}.
    """
    from bbui.backend.bbinventory import BbInventory

    staging_area = load_cache(inventory_dir)

    # ── BlucBanquise fast path ──────────────────────────────────────────────
    if isinstance(staging_area.inventory, BbInventory):
        bb_inv = staging_area.inventory
        written = bb_inv.write(inventory_dir)
        discard(inventory_dir)
        fresh: Inventory = BbInventory.load(inventory_dir)
        _save_inv_cache(fresh, inventory_dir)
        return {p: 1 for p in written}

    # ── Standard path ───────────────────────────────────────────────────────
    from bbui.backend.parser import (
        YAML_SUFFIXES, INI_SUFFIXES, GROUP_VARS_DIR,
        _load_yaml_file, _load_ini_file, _detect_format,
        dump_inventory,
    )

    staging = staging_area
    inv     = staging.inventory   # final desired state
    smap    = staging.source_map
    changes = staging.changes

    # Build the full set of files to touch:
    #   - files that are the origin of any changed subject
    #   - for REMOVED subjects: ALL files that mentioned them
    touched: set[Path] = set()
    removed_hosts:  set[str] = {c.subject for c in changes if c.kind == ChangeKind.HOST_REMOVED}
    removed_groups: set[str] = {c.subject for c in changes if c.kind == ChangeKind.GROUP_REMOVED}
    added_hosts:    set[str] = {c.subject for c in changes if c.kind == ChangeKind.HOST_ADDED}
    added_groups:   set[str] = {c.subject for c in changes if c.kind == ChangeKind.GROUP_ADDED}

    for name in removed_hosts:
        touched.update(smap.hosts.get(name, set()))
    for name in removed_groups:
        touched.update(smap.groups.get(name, set()))
    for name in added_hosts:
        files = smap.hosts.get(name, set())
        touched.add(min(files) if files else smap.default_file)
    for name in added_groups:
        files = smap.groups.get(name, set())
        touched.add(min(files) if files else smap.default_file)
    # Catch any other change kinds (var sets, etc.)
    for c in changes:
        if c.target_file:
            touched.add(c.target_file)

    touched.discard(None)  # type: ignore[arg-type]
    if not touched and smap.default_file:
        touched.add(smap.default_file)

    file_change_counts: dict[Path, int] = {}

    for target in sorted(touched):
        # Re-parse this file in isolation to get its current on-disk state
        file_inv = Inventory()
        try:
            fmt = _detect_format(target)
            if fmt == "yaml":
                _load_yaml_file(file_inv, target)
            else:
                _load_ini_file(file_inv, target)
        except FileNotFoundError:
            pass  # new file — start empty

        count = 0

        # Apply removals: drop any host/group that was removed globally
        for hostname in list(removed_hosts):
            try:
                file_inv.remove_host(hostname)
                count += 1
            except KeyError:
                pass  # not in this file, fine

        for group_name in list(removed_groups):
            try:
                file_inv.remove_group(group_name)
                count += 1
            except KeyError:
                pass

        # Apply additions: only add when this file is the primary origin
        for hostname in added_hosts:
            primary = min(smap.hosts.get(hostname, set()), default=smap.default_file)
            if primary == target and hostname not in {h.name for h in file_inv.list_hosts()}:
                host = inv.get_host(hostname)
                file_inv.add_host(hostname, groups=host.groups, vars=host.vars)
                count += 1

        for group_name in added_groups:
            primary = min(smap.groups.get(group_name, set()), default=smap.default_file)
            if primary == target and group_name not in {g.name for g in file_inv.list_groups()}:
                grp = inv.get_group(group_name)
                file_inv.add_group(group_name, vars=grp.vars)
                count += 1

        target.parent.mkdir(parents=True, exist_ok=True)
        dump_inventory(file_inv, target)
        file_change_counts[target] = count

    discard(inventory_dir)

    # Rebuild the read cache from the freshly written files
    fresh = load_inventory_dir(inventory_dir)
    _save_inv_cache(fresh, inventory_dir)

    return file_change_counts


def diff_summary(staging: StagingArea) -> list[tuple[Change, Path | None]]:
    """Return a list of (change, target_file) pairs for display."""
    return [(c, c.target_file) for c in staging.changes]


def grouped_changes(staging: StagingArea) -> list[tuple[ChangeKind, str, str, set[Path]]]:
    """Fold changes with the same (kind, detail) into a single nodeset line.

    Returns a list of tuples:
        (kind, folded_nodeset_str, detail, set_of_target_files)

    Changes on groups (GROUP_ADDED, GROUP_REMOVED) are not folded because
    group names are not hostnames and ClusterShell should not process them.
    Host changes with identical (kind, detail) are merged so that e.g. 10
    individual HOST_ADDED changes appear as a single line ``web[01-10]``.
    """
    from collections import defaultdict

    HOST_KINDS = {ChangeKind.HOST_ADDED, ChangeKind.HOST_REMOVED, ChangeKind.HOST_VAR_SET}

    # key: (kind, detail) -> (subjects list, files set)
    buckets: dict[tuple[ChangeKind, str], tuple[list[str], set[Path]]] = defaultdict(
        lambda: ([], set())
    )

    for c in staging.changes:
        subjects, files = buckets[(c.kind, c.detail)]
        subjects.append(c.subject)
        if c.target_file:
            files.add(c.target_file)

    result = []
    for (kind, detail), (subjects, files) in buckets.items():
        if kind in HOST_KINDS:
            folded = fold_nodeset(subjects)
        else:
            # Groups: join with comma, no nodeset folding
            folded = ", ".join(subjects)
        result.append((kind, folded, detail, files))

    return result


def affected_files(staging: StagingArea) -> dict[Path, list[Change]]:
    """Return the complete mapping {file -> [changes]} that commit() will touch.

    Uses the same logic as commit() so that ``bbcli pending`` shows exactly
    the files that will be rewritten — including every file that contains a
    removed host/group, not just its primary origin file.
    """
    smap    = staging.source_map
    changes = staging.changes

    removed_hosts:  set[str] = {c.subject for c in changes if c.kind == ChangeKind.HOST_REMOVED}
    removed_groups: set[str] = {c.subject for c in changes if c.kind == ChangeKind.GROUP_REMOVED}
    added_hosts:    set[str] = {c.subject for c in changes if c.kind == ChangeKind.HOST_ADDED}
    added_groups:   set[str] = {c.subject for c in changes if c.kind == ChangeKind.GROUP_ADDED}

    # file -> list of changes that touch it (insertion-ordered, deduped)
    file_changes: dict[Path, list[Change]] = {}

    def _add(filepath: Path | None, change: Change) -> None:
        if filepath is None:
            return
        lst = file_changes.setdefault(filepath, [])
        if change not in lst:
            lst.append(change)

    for c in changes:
        subject = c.subject
        if c.kind == ChangeKind.HOST_REMOVED:
            for f in smap.hosts.get(subject, set()):
                _add(f, c)
        elif c.kind == ChangeKind.GROUP_REMOVED:
            for f in smap.groups.get(subject, set()):
                _add(f, c)
        elif c.kind == ChangeKind.HOST_ADDED:
            if c.target_file:
                _add(c.target_file, c)
            else:
                files = smap.hosts.get(subject, set())
                _add(min(files) if files else smap.default_file, c)
        elif c.kind == ChangeKind.GROUP_ADDED:
            if c.target_file:
                _add(c.target_file, c)
            else:
                files = smap.groups.get(subject, set())
                _add(min(files) if files else smap.default_file, c)
        else:
            _add(c.target_file or smap.default_file, c)

    if not file_changes and smap.default_file:
        file_changes[smap.default_file] = set()

    # Return sorted by path, changes already in staged order
    staged_order = {id(c): i for i, c in enumerate(changes)}
    return {
        k: sorted(v, key=lambda c: staged_order.get(id(c), 0))
        for k, v in sorted(file_changes.items())
    }