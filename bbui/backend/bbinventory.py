"""BlueBanquise-specific Inventory subclass.

Directory layout managed by this class
---------------------------------------
<inventory_dir>/
├── cluster/
│   ├── nodes/
│   │   ├── compute.yml       # hosts in fn_compute + all their vars
│   │   ├── management.yml    # hosts in fn_management + all their vars
│   │   └── ...               # one file per fn_* group (prefix stripped)
│   └── groups/
│       ├── fn                # fn_* group declarations  (INI, no suffix)
│       ├── hw                # hw_* group declarations  (INI, no suffix)
│       ├── os                # os_* group declarations  (INI, no suffix)
│       └── others            # user-defined groups (default; INI, no suffix)
└── group_vars/               # Ansible group_vars (untouched, applied at load)
    └── ...

Rules enforced by this class
-----------------------------
* A host MUST belong to exactly one fn_*, one hw_*, and one os_* group.
  ``add_host()`` raises ``ValueError`` if any of the three is missing.

* Hosts are written to nodes files by their fn_* group:
      fn_compute   ->  cluster/nodes/compute.yml
      fn_login     ->  cluster/nodes/login.yml

* Group membership files are pure INI (no .ini suffix).  ``:children``
  and ``:vars`` sections are supported on both read and write.

* Non-base groups (not fn_/hw_/os_) are written to
  ``cluster/groups/others`` **unless** they were loaded from a named
  file — in which case they are written back to that same source file.

* Inline host vars in group files (Ansible INI syntax) are silently
  ignored on load; all host vars live exclusively in the nodes YAML files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bbui.backend.models import Group, Host, Inventory
from bbui.backend.nodeset import fold_ansible
from bbui.backend.parser import _expand_hostpattern, _load_group_vars  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

class _NullDumper(yaml.Dumper):
    """Dumps None as an empty scalar instead of 'null'.

    Produces ``hostname:`` (no trailing value) for hosts with no vars,
    matching the standard Ansible YAML inventory format.
    """

_NullDumper.add_representer(
    type(None),
    lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

NODES_DIR  = Path("cluster") / "nodes"
GROUPS_DIR = Path("cluster") / "groups"

_BASE_PREFIXES: tuple[str, ...] = ("fn_", "hw_", "os_")
_BASE_FILE: dict[str, str] = {"fn_": "fn", "hw_": "hw", "os_": "os"}


# ---------------------------------------------------------------------------
# BbInventory
# ---------------------------------------------------------------------------

class BbInventory(Inventory):
    """Inventory subclass that enforces the BlueBanquise directory layout.

    Use :meth:`load` to read an existing inventory from disk and
    :meth:`write` to persist it back.  Direct instantiation gives an empty
    inventory with group validation active.
    """

    def __init__(self) -> None:
        super().__init__()
        # Tracks the source file for each non-base group so that
        # write() can send it back to the right place.
        self._group_source: dict[str, Path] = {}
        # Tracks the source nodes file for each host loaded from disk.
        # New hosts (not yet on disk) are absent from this dict.
        self._host_source: dict[str, Path] = {}

    def __setstate__(self, state: dict) -> None:
        state.setdefault("_host_source", {})
        state.setdefault("_group_source", {})
        self.__dict__.update(state)

    # -----------------------------------------------------------------------
    # Overridden mutating methods
    # -----------------------------------------------------------------------

    def add_host(
        self,
        hostname: str,
        groups: list[str] | None = None,
        vars: dict[str, Any] | None = None,
    ) -> Host:
        """Add *hostname*, enforcing fn_/hw_/os_ group membership.

        Raises:
            ValueError: if *groups* does not contain at least one group
                whose name starts with ``fn_``, ``hw_``, and ``os_``
                respectively.
        """
        groups = groups or []
        self._validate_bb_groups(hostname, groups)
        return super().add_host(hostname, groups=groups, vars=vars)

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_bb_groups(hostname: str, groups: list[str]) -> None:
        """Raise ValueError when fn/hw/os groups are not all present exactly once."""
        for prefix in _BASE_PREFIXES:
            matches = [g for g in groups if g.startswith(prefix)]
            if not matches:
                raise ValueError(
                    f"Cannot add host '{hostname}': must belong to an fn_*, hw_*, "
                    f"and os_* group. Missing: {prefix}*"
                )
            if len(matches) > 1:
                raise ValueError(
                    f"Cannot add host '{hostname}': must belong to exactly one "
                    f"{prefix}* group; got: {', '.join(matches)}."
                )

    # -----------------------------------------------------------------------
    # Group / file helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def fn_suffix(fn_group: str) -> str:
        """Strip the ``fn_`` prefix: ``'fn_compute'`` → ``'compute'``."""
        if not fn_group.startswith("fn_"):
            raise ValueError(f"Not an fn_ group: {fn_group!r}")
        return fn_group[3:]

    def fn_group_of(self, hostname: str) -> str:
        """Return the ``fn_*`` group of *hostname*.

        Raises:
            KeyError: if the host has no fn_ group.
        """
        host = self.get_host(hostname)
        for g in host.groups:
            if g.startswith("fn_"):
                return g
        raise KeyError(f"Host '{hostname}' has no fn_ group.")

    def nodes_file(self, fn_group: str, inventory_dir: Path) -> Path:
        """Return the path to the YAML nodes file for *fn_group*.

        Example: ``fn_compute``  →  ``<inventory_dir>/cluster/nodes/compute.yml``
        """
        return inventory_dir / NODES_DIR / f"{self.fn_suffix(fn_group)}.yml"

    def group_file(self, group_name: str, inventory_dir: Path) -> Path:
        """Return the canonical write destination for *group_name*.

        * ``fn_*`` groups  →  ``cluster/groups/fn``
        * ``hw_*`` groups  →  ``cluster/groups/hw``
        * ``os_*`` groups  →  ``cluster/groups/os``
        * Other groups     →  tracked source file, or ``cluster/groups/others``
        """
        for prefix, fname in _BASE_FILE.items():
            if group_name.startswith(prefix):
                return inventory_dir / GROUPS_DIR / fname
        return self._group_source.get(group_name, inventory_dir / GROUPS_DIR / "others")

    # -----------------------------------------------------------------------
    # Write
    # -----------------------------------------------------------------------

    def write(self, inventory_dir: Path) -> list[Path]:
        """Persist the full inventory to the BlueBanquise directory layout.

        * Writes ``cluster/nodes/<fn_suffix>.yml`` for every fn_* group that
          has at least one host.
        * Writes ``cluster/groups/{fn,hw,os,others,...}`` for every group.

        Returns the list of files written.
        """
        written: list[Path] = []
        written.extend(self._write_nodes(inventory_dir))
        written.extend(self._write_groups(inventory_dir))
        return written

    def _target_nodes_file(self, host: Host, inventory_dir: Path) -> Path:
        """Return the file where *host*'s vars should be written.

        Existing hosts go back to their source file.  New hosts (no source)
        are co-located with other hosts sharing the same fn_* group; if none
        exist yet, a new per-fn-group file is created.
        """
        if host.name in self._host_source:
            return self._host_source[host.name]
        fn_group = next((g for g in host.groups if g.startswith("fn_")), None)
        if fn_group:
            peer_sources = {
                self._host_source[h.name]
                for h in self.list_hosts()
                if fn_group in h.groups and h.name in self._host_source
            }
            if peer_sources:
                return min(peer_sources)  # alphabetically first = deterministic
        return self.nodes_file(fn_group, inventory_dir) if fn_group else inventory_dir / NODES_DIR / "nodes.yml"

    def _write_nodes(self, inventory_dir: Path) -> list[Path]:
        """Write node vars back to each host's source file.

        Existing hosts go back to the file they were loaded from.
        New hosts are written alongside existing hosts of the same fn_* group,
        or to a new per-fn-group file when no peer exists.
        """
        nodes_dir = inventory_dir / NODES_DIR
        nodes_dir.mkdir(parents=True, exist_ok=True)

        file_buckets: dict[Path, list[Host]] = {}
        for host in self.list_hosts():
            target = self._target_nodes_file(host, inventory_dir)
            file_buckets.setdefault(target, []).append(host)

        written: list[Path] = []
        for filepath, hosts in sorted(file_buckets.items()):
            hosts_block: dict[str, Any] = {
                host.name: (host.vars if host.vars else None)
                for host in sorted(hosts, key=lambda h: h.name)
            }
            data: dict[str, Any] = {"all": {"hosts": hosts_block}}
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with filepath.open("w", encoding="utf-8") as fh:
                yaml.dump(data, fh, Dumper=_NullDumper, default_flow_style=False, allow_unicode=True, sort_keys=True)
            written.append(filepath)

        return written

    def _write_groups(self, inventory_dir: Path) -> list[Path]:
        """Write INI group files under ``cluster/groups/``."""
        groups_dir = inventory_dir / GROUPS_DIR
        groups_dir.mkdir(parents=True, exist_ok=True)

        # Bucket groups by their target file.
        file_buckets: dict[Path, list[Group]] = {}
        for group in self.list_groups():
            target = self.group_file(group.name, inventory_dir)
            file_buckets.setdefault(target, []).append(group)

        written: list[Path] = []
        for filepath, groups in sorted(file_buckets.items()):
            lines: list[str] = []
            for group in sorted(groups, key=lambda g: g.name):
                # [group]
                lines.append(f"[{group.name}]")
                for pattern in fold_ansible(group.hosts):
                    lines.append(pattern)
                lines.append("")
                # [group:vars]
                if group.vars:
                    lines.append(f"[{group.name}:vars]")
                    for k, v in sorted(group.vars.items()):
                        lines.append(f"{k}={v}")
                    lines.append("")
                # [group:children]
                if group.children:
                    lines.append(f"[{group.name}:children]")
                    for child in sorted(group.children):
                        lines.append(child)
                    lines.append("")

            with filepath.open("w", encoding="utf-8") as fh:
                fh.write("\n".join(lines).rstrip() + "\n")
            written.append(filepath)

        return written

    # -----------------------------------------------------------------------
    # Load
    # -----------------------------------------------------------------------

    @classmethod
    def load(cls, inventory_dir: Path) -> "BbInventory":
        """Load a :class:`BbInventory` from a BlueBanquise directory layout.

        Steps:
        1. Collect host vars from ``cluster/nodes/*.yml``.
        2. Load group memberships from ``cluster/groups/*``.
        3. Apply ``group_vars/`` (standard Ansible behaviour).
        """
        inv: BbInventory = cls.__new__(cls)
        Inventory.__init__(inv)
        inv._group_source = {}
        inv._host_source = {}

        pending_vars = inv._collect_node_vars(inventory_dir)
        inv._load_groups(inventory_dir, pending_vars)
        _load_group_vars(inv, inventory_dir / "group_vars")
        return inv

    def _collect_node_vars(self, inventory_dir: Path) -> dict[str, dict[str, Any]]:
        """Read ``cluster/nodes/*.yml`` and return ``{hostname: vars}``."""
        pending: dict[str, dict[str, Any]] = {}
        nodes_dir = inventory_dir / NODES_DIR
        if not nodes_dir.is_dir():
            return pending
        for filepath in sorted(nodes_dir.glob("*.yml")):
            with filepath.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            hosts_data: dict[str, Any] = (data.get("all") or {}).get("hosts") or {}
            for hostname, vars_data in hosts_data.items():
                pending[str(hostname)] = vars_data or {}
                self._host_source[str(hostname)] = filepath
        return pending

    def _load_groups(
        self,
        inventory_dir: Path,
        pending_vars: dict[str, dict[str, Any]],
    ) -> None:
        """Parse ``cluster/groups/*`` and populate hosts + groups.

        Group files are plain INI (no suffix).  Inline host vars are
        ignored — vars live exclusively in the nodes YAML files.
        """
        groups_dir = inventory_dir / GROUPS_DIR
        if not groups_dir.is_dir():
            return

        # Accumulate across all group files before creating any objects so
        # that hosts are built with their complete group list in one shot.
        host_groups: dict[str, list[str]] = {}          # hostname -> [group, ...]
        group_meta: dict[str, dict[str, Any]] = {}      # group_name -> {vars, children}

        for filepath in sorted(groups_dir.iterdir()):
            if not filepath.is_file():
                continue
            self._parse_ini_group_file(filepath, host_groups, group_meta)

        # Create groups (without hosts — the add_host calls below wire them).
        for group_name, meta in group_meta.items():
            g = self._ensure_group(group_name)
            if meta["vars"]:
                g.vars.update(meta["vars"])

        # Wire :children relationships.
        for group_name, meta in group_meta.items():
            for child in meta["children"]:
                self._groups[group_name].add_child(child)
                self._ensure_group(child)

        # Create hosts — bypass BbInventory.add_host() validation since we
        # are reconstituting existing data, not accepting user input.
        for hostname, groups in host_groups.items():
            vars_data = pending_vars.get(hostname, {})
            Inventory.add_host(self, hostname, groups=groups, vars=vars_data)

    def _parse_ini_group_file(
        self,
        filepath: Path,
        host_groups: dict[str, list[str]],
        group_meta: dict[str, dict[str, Any]],
    ) -> None:
        """Parse one INI group file into the accumulator dicts."""
        text = filepath.read_text(encoding="utf-8")
        current: str | None = None   # current section (bare name)
        mode: str = "hosts"          # "hosts" | "vars" | "children"

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", ";")):
                continue

            if stripped.startswith("["):
                raw = stripped[1 : stripped.index("]")]
                if raw.endswith(":vars"):
                    current = raw[: -len(":vars")]
                    mode = "vars"
                elif raw.endswith(":children"):
                    current = raw[: -len(":children")]
                    mode = "children"
                else:
                    current = raw
                    mode = "hosts"

                if current not in group_meta:
                    group_meta[current] = {"vars": {}, "children": []}
                    # Track source file for non-base groups.
                    if not any(current.startswith(p) for p in _BASE_PREFIXES):
                        self._group_source.setdefault(current, filepath)
                continue

            if current is None:
                continue

            if mode == "hosts":
                # Strip any inline Ansible vars (key=value after the hostname).
                raw_host = stripped.split()[0]
                for hostname in _expand_hostpattern(raw_host):
                    host_groups.setdefault(hostname, [])
                    if current not in host_groups[hostname]:
                        host_groups[hostname].append(current)

            elif mode == "vars":
                if "=" in stripped:
                    k, _, v = stripped.partition("=")
                    group_meta[current]["vars"][k.strip()] = v.strip()

            elif mode == "children":
                child = stripped.split()[0]
                if child not in group_meta[current]["children"]:
                    group_meta[current]["children"].append(child)
                if child not in group_meta:
                    group_meta[child] = {"vars": {}, "children": []}

    # -----------------------------------------------------------------------
    # Layout detection
    # -----------------------------------------------------------------------

    @staticmethod
    def is_bb_layout(inventory_dir: Path) -> bool:
        """Return ``True`` if *inventory_dir* looks like a BlueBanquise layout.

        Detection is based on the presence of ``cluster/nodes/`` or
        ``cluster/groups/`` under the given directory.
        """
        return (
            (inventory_dir / NODES_DIR).is_dir()
            or (inventory_dir / GROUPS_DIR).is_dir()
        )
