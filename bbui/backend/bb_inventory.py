"""BlucBanquise-specific inventory layout (BbInventory).

Directory structure under root_dir:
    cluster/
    ├── nodes/
    │   ├── management   YAML — hosts from fn_management + all their vars
    │   ├── compute      YAML — hosts from fn_compute + all their vars
    │   └── …
    └── groups/
        ├── fn           INI — fn_* group membership
        ├── hw           INI — hw_* group membership
        ├── os           INI — os_* group membership
        └── others       INI — any other groups (default sink for new groups)
                             unless a group's source file is already known, in
                             which case that file is updated in-place.

Rules
-----
* Every host must belong to exactly one group of each base type: fn_*, hw_*, os_*.
* add_host() enforces this contract (bypassed internally during load()).
* Hosts and their vars are written to cluster/nodes/<fn-name> (YAML).
* Group membership is written to cluster/groups/<type> (INI, no extension).
* Additional user-defined groups go to cluster/groups/others by default.
  If those groups were previously loaded from a specific file, that file
  is updated instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bbui.backend.models import Group, Host, Inventory
from bbui.backend.parser import _load_ini_file, _load_yaml_file

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_GROUP_TYPES: tuple[str, ...] = ("fn", "hw", "os")

# Ansible implicit groups that BbInventory never writes explicitly
_IMPLICIT_GROUPS: frozenset[str] = frozenset({"all", "ungrouped"})

# These are relative to the inventory_dir the user passes (e.g. cluster/).
# Full on-disk paths: <inventory_dir>/nodes/<fn_name> and <inventory_dir>/groups/<type>
_NODES_SUBPATH  = Path("nodes")
_GROUPS_SUBPATH = Path("groups")


def is_bb_layout(directory: Path | str) -> bool:
    """Return True when *directory* follows the BlucBanquise layout.

    Detection: the directory contains a ``nodes/`` or ``groups/`` sub-directory.
    """
    d = Path(directory)
    return (d / "nodes").is_dir() or (d / "groups").is_dir()


# ---------------------------------------------------------------------------
# BbInventory
# ---------------------------------------------------------------------------

class BbInventory(Inventory):
    """Inventory variant that enforces the BlucBanquise file layout.

    Parameters
    ----------
    root_dir:
        Path to the inventory root (parent of ``cluster/``). Optional at
        construction time but required before calling :meth:`dump`.
    """

    def __init__(self, root_dir: Path | str | None = None) -> None:
        super().__init__()
        self.root_dir: Path | None = Path(root_dir) if root_dir else None
        # Maps group name -> the file it was loaded from (for "others" routing)
        self._group_source_files: dict[str, Path] = {}
        # Internal flag: skip group validation while loading from disk
        self._loading: bool = False

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _check_base_groups(self, groups: list[str]) -> None:
        """Raise ValueError if *groups* does not include one of each base type."""
        for base_type in BASE_GROUP_TYPES:
            matches = [g for g in groups if g.startswith(f"{base_type}_")]
            if not matches:
                raise ValueError(
                    f"A host must belong to a '{base_type}_*' group. "
                    f"Provide a group like '{base_type}_<name>'."
                )
            if len(matches) > 1:
                raise ValueError(
                    f"A host must belong to exactly one '{base_type}_*' group; "
                    f"got: {', '.join(matches)}."
                )

    # ------------------------------------------------------------------
    # Inventory overrides
    # ------------------------------------------------------------------

    def add_host(
        self,
        hostname: str,
        groups: list[str] | None = None,
        vars: dict[str, Any] | None = None,
    ) -> Host:
        """Add a host, enforcing the fn/hw/os group contract.

        During an internal load (``_loading=True``) validation is skipped
        because groups are populated incrementally from multiple files.
        """
        if not self._loading:
            self._check_base_groups(groups or [])
        return super().add_host(hostname, groups, vars)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, root_dir: Path | str) -> "BbInventory":
        """Load a BlucBanquise inventory from *root_dir*.

        Reads:
        * ``cluster/nodes/*``  — YAML files, one per fn_* group
        * ``cluster/groups/*`` — INI files (no extension), fn/hw/os/others/…
        """
        root_dir = Path(root_dir)
        inv = cls(root_dir=root_dir)
        inv._loading = True
        try:
            nodes_dir  = root_dir / _NODES_SUBPATH
            groups_dir = root_dir / _GROUPS_SUBPATH

            if nodes_dir.is_dir():
                for filepath in sorted(nodes_dir.iterdir()):
                    if filepath.is_file():
                        _load_yaml_file(inv, filepath)

            if groups_dir.is_dir():
                for filepath in sorted(groups_dir.iterdir()):
                    if filepath.is_file() and filepath.suffix == "":
                        _load_ini_file(inv, filepath)
                        # Record which file each group came from
                        _tmp = BbInventory()
                        _tmp._loading = True
                        _load_ini_file(_tmp, filepath)
                        for g in _tmp.list_groups():
                            inv._group_source_files.setdefault(g.name, filepath)
        finally:
            inv._loading = False

        return inv

    # ------------------------------------------------------------------
    # Dump
    # ------------------------------------------------------------------

    def dump(self) -> list[Path]:
        """Write this inventory to disk in BlucBanquise layout.

        Creates ``nodes/`` and ``groups/`` under ``root_dir`` if they do not exist.
        Returns the list of files actually written.
        """
        if self.root_dir is None:
            raise ValueError("BbInventory.root_dir must be set before calling dump().")
        written: list[Path] = []
        written.extend(self._dump_nodes())
        written.extend(self._dump_groups())
        return written

    # ------------------------------------------------------------------
    # Internal — nodes
    # ------------------------------------------------------------------

    def _dump_nodes(self) -> list[Path]:
        """Write one YAML file per fn_* group under nodes/. Returns written paths."""
        nodes_dir = self.root_dir / _NODES_SUBPATH  # type: ignore[operator]
        nodes_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        # Bucket hosts by their fn_ group
        fn_buckets: dict[str, dict[str, Any]] = {}
        for host in sorted(self.list_hosts(), key=lambda h: h.name):
            fn_group = next((g for g in host.groups if g.startswith("fn_")), None)
            if fn_group is None:
                continue  # malformed host — skip silently
            fn_name = fn_group[len("fn_"):]
            fn_buckets.setdefault(fn_name, {})[host.name] = host.vars or None

        for fn_name, hosts_data in sorted(fn_buckets.items()):
            filepath = nodes_dir / fn_name
            content: dict[str, Any] = {f"fn_{fn_name}": {"hosts": hosts_data}}
            with filepath.open("w", encoding="utf-8") as fh:
                yaml.dump(content, fh, default_flow_style=False, allow_unicode=True)
            written.append(filepath)

        return written

    # ------------------------------------------------------------------
    # Internal — groups
    # ------------------------------------------------------------------

    def _dump_groups(self) -> list[Path]:
        """Write group INI files under groups/. Returns written paths."""
        groups_dir = self.root_dir / _GROUPS_SUBPATH  # type: ignore[operator]
        groups_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        fn_groups    = [g for g in self.list_groups() if g.name.startswith("fn_")]
        hw_groups    = [g for g in self.list_groups() if g.name.startswith("hw_")]
        os_groups    = [g for g in self.list_groups() if g.name.startswith("os_")]
        other_groups = [
            g for g in self.list_groups()
            if not any(g.name.startswith(f"{t}_") for t in BASE_GROUP_TYPES)
            and g.name not in _IMPLICIT_GROUPS
        ]

        for base_type, groups in (("fn", fn_groups), ("hw", hw_groups), ("os", os_groups)):
            if groups:
                fp = groups_dir / base_type
                self._write_ini(groups, fp)
                written.append(fp)

        if other_groups:
            written.extend(self._write_other_groups(other_groups, groups_dir))

        return written

    def _write_other_groups(self, groups: list[Group], groups_dir: Path) -> list[Path]:
        """Route other groups to their source file or groups/others."""
        file_buckets: dict[Path, list[Group]] = {}
        for group in groups:
            source = self._group_source_files.get(group.name)
            target = source if (source and source.exists()) else groups_dir / "others"
            file_buckets.setdefault(target, []).append(group)

        written: list[Path] = []
        for filepath, grps in sorted(file_buckets.items()):
            self._write_ini(grps, filepath)
            written.append(filepath)
        return written

    def _write_ini(self, groups: list[Group], filepath: Path) -> None:
        """Serialize *groups* to an Ansible INI file at *filepath*.

        Host membership is written as plain names (one per line, sorted).
        Inline vars are intentionally omitted — all host vars live in the
        YAML node files, not in the group INI files.
        """
        lines: list[str] = []

        for group in sorted(groups, key=lambda g: g.name):
            lines.append(f"[{group.name}]")
            for hostname in sorted(group.hosts):
                lines.append(hostname)
            lines.append("")

            if group.vars:
                lines.append(f"[{group.name}:vars]")
                for k, v in sorted(group.vars.items()):
                    lines.append(f"{k}={v}")
                lines.append("")

            if group.children:
                lines.append(f"[{group.name}:children]")
                for child in sorted(group.children):
                    lines.append(child)
                lines.append("")

        with filepath.open("w", encoding="utf-8") as fh:
            fh.write("\n".join(lines).rstrip() + "\n")
