"""Look up a variable name across all hosts and groups in an Inventory.

The lookup supports dot-notation to reach nested values:
    ansible_user              top-level key
    network.ip                nested dict
    disks[0].name             list item key

Variable source tracking
------------------------
Variables can be defined in multiple files:
    cluster/nodes/web.yml    declares web01 with ansible_user
    cluster/groups/all.yml   declares group vars for webservers
    group_vars/webservers/   adds more vars to webservers group

A VarSourceMap records, for each host or group, which file contributed
each top-level variable key.  This is built by re-parsing every inventory
file in isolation and merging the results in load order (last-write-wins,
matching parser.py merge behaviour).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bbui.backend.bb_inventory import BbInventory
from bbui.backend.models import Inventory


# ---------------------------------------------------------------------------
# Variable source map
# ---------------------------------------------------------------------------

@dataclass
class VarSourceMap:
    """Tracks which file defined each top-level variable key per owner.

    Structure:
        host_vars[hostname][var_key]   -> Path
        group_vars[group_name][var_key] -> Path
    """
    host_vars:  dict[str, dict[str, Path]] = field(default_factory=dict)
    group_vars: dict[str, dict[str, Path]] = field(default_factory=dict)

    def file_for_host_var(self, hostname: str, var_key: str) -> Path | None:
        """Return the file that defined *var_key* on *hostname*, or None."""
        return self.host_vars.get(hostname, {}).get(var_key)

    def file_for_group_var(self, group_name: str, var_key: str) -> Path | None:
        """Return the file that defined *var_key* on *group_name*, or None."""
        return self.group_vars.get(group_name, {}).get(var_key)


def build_var_source_map(inventory_dir: Path) -> VarSourceMap:
    """Scan *inventory_dir* and build a complete :class:`VarSourceMap`.

    Each inventory file (YAML, INI, group_vars/) is parsed in isolation.
    Files are processed in the same alphabetical order as
    ``load_inventory_dir`` so that last-writer-wins matches the merge.

    group_vars/ files are processed last (same as the parser), so they
    correctly override vars defined inline in inventory files.
    """
    from bbui.backend.parser import (
        YAML_SUFFIXES, INI_SUFFIXES, GROUP_VARS_DIR,
        _load_yaml_file, _load_ini_file, _detect_format,
    )
    import yaml

    vsmap = VarSourceMap()

    def _record_host_vars(hostname: str, vars_dict: dict[str, Any], filepath: Path) -> None:
        target = vsmap.host_vars.setdefault(hostname, {})
        for key in vars_dict:
            target[key] = filepath

    def _record_group_vars(group_name: str, vars_dict: dict[str, Any], filepath: Path) -> None:
        target = vsmap.group_vars.setdefault(group_name, {})
        for key in vars_dict:
            target[key] = filepath

    # ── Step 1: inventory files (non group_vars) ─────────────────────────
    for filepath in sorted(inventory_dir.rglob("*")):
        if not filepath.is_file():
            continue
        if GROUP_VARS_DIR in filepath.parts:
            continue
        suffix = filepath.suffix.lower()
        if suffix not in YAML_SUFFIXES and suffix not in INI_SUFFIXES and suffix != "":
            continue

        tmp = BbInventory()
        tmp._loading = True
        try:
            fmt = _detect_format(filepath)
            if fmt == "yaml":
                _load_yaml_file(tmp, filepath)
            else:
                _load_ini_file(tmp, filepath)
        except Exception:
            continue

        for h in tmp.list_hosts():
            if h.vars:
                _record_host_vars(h.name, h.vars, filepath)
        for g in tmp.list_groups():
            if g.vars:
                _record_group_vars(g.name, g.vars, filepath)

    # ── Step 2: group_vars/ ──────────────────────────────────────────────
    group_vars_dir = inventory_dir / GROUP_VARS_DIR
    if group_vars_dir.is_dir():
        for entry in sorted(group_vars_dir.iterdir()):
            if entry.is_file() and entry.suffix.lower() in YAML_SUFFIXES:
                # group_vars/webservers.yml
                group_name = entry.stem
                try:
                    with entry.open("r", encoding="utf-8") as fh:
                        data = yaml.safe_load(fh) or {}
                    _record_group_vars(group_name, data, entry)
                except Exception:
                    pass

            elif entry.is_dir():
                # group_vars/webservers/main.yml …
                group_name = entry.name
                for yaml_file in sorted(list(entry.glob("*.yml")) + list(entry.glob("*.yaml"))):
                    try:
                        with yaml_file.open("r", encoding="utf-8") as fh:
                            data = yaml.safe_load(fh) or {}
                        _record_group_vars(group_name, data, yaml_file)
                    except Exception:
                        pass

    return vsmap


# ---------------------------------------------------------------------------
# Dot-path resolver
# ---------------------------------------------------------------------------

_SEGMENT = re.compile(r"(\w+)(?:\[(\d+)\])?")


def _resolve_dotpath(vars_dict: dict[str, Any], dotpath: str) -> tuple[bool, Any]:
    """Traverse *vars_dict* following *dotpath* (dot-notation + list indices).

    Returns (found, value).  Supports:
        key                 top-level key
        key.sub             nested dict
        key[0]              list element
        key[0].sub          list element dict key
    """
    node: Any = vars_dict
    for m in _SEGMENT.finditer(dotpath):
        key   = m.group(1)
        index = m.group(2)

        if not isinstance(node, dict) or key not in node:
            return False, None
        node = node[key]

        if index is not None:
            if not isinstance(node, list):
                return False, None
            idx = int(index)
            if idx >= len(node):
                return False, None
            node = node[idx]

    return True, node


def _top_level_key(dotpath: str) -> str:
    """Return the first segment of a dotpath: 'network.ip' -> 'network'."""
    m = _SEGMENT.match(dotpath)
    return m.group(1) if m else dotpath


# ---------------------------------------------------------------------------
# VarMatch and lookup
# ---------------------------------------------------------------------------

@dataclass
class VarMatch:
    """A single occurrence of a variable on a host or group."""
    owner_kind:  str           # "host" or "group"
    owner_name:  str           # hostname or group name
    value:       Any           # resolved value (may be nested)
    source_file: Path | None   # file that defined the top-level var key


def lookup_var(
    varname: str,
    inventory: Inventory,
    var_source_map: VarSourceMap | None = None,
) -> list[VarMatch]:
    """Return all :class:`VarMatch` where *varname* is defined.

    *var_source_map* is an optional :class:`VarSourceMap` built by
    :func:`build_var_source_map`.  When provided each match is annotated
    with the exact file that contributed the top-level variable key,
    correctly handling hosts declared in one file and vars defined in
    another (e.g. ``group_vars/``).
    """
    results: list[VarMatch] = []
    top_key = _top_level_key(varname)

    # ── Hosts ────────────────────────────────────────────────────────────
    for host in sorted(inventory.list_hosts(), key=lambda h: h.name):
        found, value = _resolve_dotpath(host.vars, varname)
        if found:
            source: Path | None = None
            if var_source_map is not None:
                source = var_source_map.file_for_host_var(host.name, top_key)
            results.append(VarMatch(
                owner_kind="host",
                owner_name=host.name,
                value=value,
                source_file=source,
            ))

    # ── Groups ───────────────────────────────────────────────────────────
    for group in sorted(inventory.list_groups(), key=lambda g: g.name):
        found, value = _resolve_dotpath(group.vars, varname)
        if found:
            source = None
            if var_source_map is not None:
                source = var_source_map.file_for_group_var(group.name, top_key)
            results.append(VarMatch(
                owner_kind="group",
                owner_name=group.name,
                value=value,
                source_file=source,
            ))

    return results