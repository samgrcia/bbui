"""Parse Ansible inventory files (YAML and INI) into Inventory objects.

Supported sources
-----------------
- A single YAML file  (.yml / .yaml)
- A single INI file   (.ini / .cfg / no extension)
- A directory         (inventory/) — all YAML and INI files are merged,
                      then group_vars/ is applied on top.

group_vars/ convention (Ansible standard)
------------------------------------------
inventory/
└── group_vars/
    ├── webservers.yml          # vars for group "webservers"
    ├── webservers/             # or a sub-directory of YAML files …
    │   ├── main.yml            #   … all merged into the same group
    │   └── secrets.yml
    └── all.yml                 # vars applied to every group
"""

from __future__ import annotations

import configparser
import re
from pathlib import Path
from typing import Any

import yaml

from bbui.backend.models import Inventory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

YAML_SUFFIXES = {".yml", ".yaml"}
INI_SUFFIXES  = {".ini", ".cfg"}
GROUP_VARS_DIR = "group_vars"
VAULT_STEM    = "vault"  # Ansible-vault encrypted files — skipped during parsing

# Ansible INI: optional inline vars  web01 ansible_user=ubuntu ansible_port=22
_INI_HOST_RE = re.compile(r"^(?P<host>\S+)(?P<vars>(\s+\S+=\S+)*)$")

# Ansible range pattern: web[01:03], g[a:c], srv[1:3].dc
_RANGE_RE = re.compile(r"^(?P<prefix>[^[]*)\[(?P<start>[0-9a-z]+):(?P<end>[0-9a-z]+)\](?P<suffix>[^[]*)$")


# ===========================================================================
# Range expansion
# ===========================================================================

def _expand_hostpattern(pattern: str) -> list[str]:
    """Expand an Ansible host pattern into a list of hostnames.

    Supports numeric and alphabetic ranges with optional zero-padding.
    Examples:
        web[1:3]    -> web1, web2, web3
        web[01:03]  -> web01, web02, web03
        g[a:c]      -> ga, gb, gc
        srv[1:2].dc -> srv1.dc, srv2.dc
        web01       -> web01  (no range, returned as-is)
    """
    m = _RANGE_RE.match(pattern)
    if not m:
        return [pattern]

    prefix = m.group("prefix")
    start  = m.group("start")
    end    = m.group("end")
    suffix = m.group("suffix")

    # Numeric range — preserve zero-padding when start has a leading zero
    if start.isdigit() and end.isdigit():
        pad     = len(start) if (start.startswith("0") and len(start) > 1) else 0
        i_start = int(start)
        i_end   = int(end)
        step    = 1 if i_start <= i_end else -1
        return [
            f"{prefix}{str(i).zfill(pad)}{suffix}"
            for i in range(i_start, i_end + step, step)
        ]

    # Alphabetic range (single lowercase letters only)
    if len(start) == 1 and len(end) == 1 and start.isalpha() and end.isalpha():
        step = 1 if start <= end else -1
        return [
            f"{prefix}{chr(c)}{suffix}"
            for c in range(ord(start), ord(end) + step, step)
        ]

    # Unrecognised range format — return as-is
    return [pattern]



# ===========================================================================
# YAML parser
# ===========================================================================

def _parse_yaml_group(
    inventory: Inventory,
    group_name: str,
    group_data: dict[str, Any] | None,
) -> None:
    """Recursively parse a YAML group block into *inventory*."""
    if group_data is None:
        group_data = {}

    group = inventory._ensure_group(group_name)
    group.vars.update(group_data.get("vars", {}))

    hosts_data: dict[str, Any] | None = group_data.get("hosts")
    if hosts_data:
        for pattern, host_vars in hosts_data.items():
            for hostname in _expand_hostpattern(str(pattern)):
                _register_host(inventory, hostname, group_name, host_vars or {})

    children: dict[str, Any] | None = group_data.get("children")
    if children:
        for child_name, child_data in children.items():
            group.add_child(child_name)
            _parse_yaml_group(inventory, child_name, child_data)


def _load_yaml_file(inventory: Inventory, filepath: Path) -> None:
    """Merge a single YAML inventory file into *inventory*."""
    with filepath.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    for group_name, group_data in raw.items():
        _parse_yaml_group(inventory, group_name, group_data)


# ===========================================================================
# INI parser
# ===========================================================================

def _parse_ini_vars(raw: str) -> dict[str, Any]:
    """Parse ``key=value`` pairs from an Ansible INI host/group var string."""
    result: dict[str, Any] = {}
    for token in raw.split():
        if "=" in token:
            k, _, v = token.partition("=")
            result[k.strip()] = v.strip()
    return result


def _load_ini_file(inventory: Inventory, filepath: Path) -> None:
    """Merge a single INI inventory file into *inventory*.

    Ansible INI format overview::

        web01 ansible_user=ubuntu          # ungrouped host
        web02

        [webservers]
        web01
        web02 ansible_port=2222

        [webservers:vars]
        ansible_user=deploy

        [webservers:children]
        nginx

        [nginx]
        proxy01
    """
    text = filepath.read_text(encoding="utf-8")

    current_section: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue

        if stripped.startswith("["):
            current_section = stripped.strip("[]")
            continue

        if current_section is None:
            current_section = "ungrouped"

        if current_section.endswith(":vars"):
            group_name = current_section[: -len(":vars")]
            if "=" in stripped:
                k, _, v = stripped.partition("=")
                inventory._ensure_group(group_name).vars[k.strip()] = v.strip()

        elif current_section.endswith(":children"):
            parent = current_section[: -len(":children")]
            child  = stripped.split()[0]
            inventory._ensure_group(parent).add_child(child)
            inventory._ensure_group(child)

        else:
            group_name = current_section
            m = _INI_HOST_RE.match(stripped)
            if not m:
                continue
            pattern   = m.group("host")
            host_vars = _parse_ini_vars(m.group("vars"))
            for hostname in _expand_hostpattern(pattern):
                _register_host(inventory, hostname, group_name, host_vars)


# ===========================================================================
# group_vars loader
# ===========================================================================

def _load_group_vars(inventory: Inventory, group_vars_dir: Path) -> None:
    """Apply variables from a ``group_vars/`` directory to *inventory*.

    Two layouts are supported and can be mixed freely:

    * **File layout** – ``group_vars/<group_name>.yml``
      The file name (without extension) is the group name.

    * **Directory layout** – ``group_vars/<group_name>/``
      Every ``.yml`` / ``.yaml`` file inside the sub-directory contributes
      vars to that group.  Files are loaded in alphabetical order so that
      the merge is deterministic.

    The special name ``all`` applies vars to every group currently known to
    the inventory (it does *not* create a new group).
    """
    if not group_vars_dir.is_dir():
        return

    def _apply(group_name: str, vars_dict: dict[str, Any]) -> None:
        if group_name == "all":
            for group in inventory.list_groups():
                group.vars.update(vars_dict)
        else:
            inventory._ensure_group(group_name).vars.update(vars_dict)

    def _read_yaml(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    for entry in sorted(group_vars_dir.iterdir()):
        if entry.is_file() and entry.suffix.lower() in YAML_SUFFIXES:
            # File layout: group_vars/webservers.yml
            if entry.stem.lower() == VAULT_STEM:
                continue
            group_name = entry.stem
            _apply(group_name, _read_yaml(entry))

        elif entry.is_dir():
            # Directory layout: group_vars/webservers/main.yml …
            group_name = entry.name
            merged: dict[str, Any] = {}
            for yaml_file in sorted(entry.glob("*.yml")) + sorted(entry.glob("*.yaml")):  # type: ignore[operator]
                if yaml_file.stem.lower() == VAULT_STEM:
                    continue
                merged.update(_read_yaml(yaml_file))
            if merged:
                _apply(group_name, merged)


# ===========================================================================
# Shared helpers
# ===========================================================================

def _register_host(
    inventory: Inventory,
    hostname: str,
    group_name: str,
    host_vars: dict[str, Any],
) -> None:
    """Add *hostname* to the inventory (or update it) and link it to *group_name*."""
    host_names = {h.name for h in inventory.list_hosts()}
    if hostname not in host_names:
        inventory.add_host(hostname, groups=[group_name], vars=host_vars)
    else:
        host = inventory.get_host(hostname)
        host.add_group(group_name)
        host.vars.update(host_vars)
        inventory._ensure_group(group_name).add_host(hostname)


def _detect_format(filepath: Path) -> str:
    """Return ``'yaml'`` or ``'ini'`` based on file suffix or content sniffing."""
    if filepath.suffix.lower() in YAML_SUFFIXES:
        return "yaml"
    if filepath.suffix.lower() in INI_SUFFIXES:
        return "ini"
    # No recognised suffix → sniff first non-blank line
    with filepath.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", ";")):
                return "yaml" if stripped.startswith(("-", "{")) or ":" in stripped else "ini"
    return "ini"


# ===========================================================================
# Public API
# ===========================================================================

def load_inventory(path: str | Path) -> Inventory:
    """Load a single YAML or INI inventory file."""
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"Inventory file not found: {filepath}")
    if not filepath.is_file():
        raise ValueError(f"Expected a file, got: {filepath}")

    inventory = Inventory()
    fmt = _detect_format(filepath)
    if fmt == "yaml":
        _load_yaml_file(inventory, filepath)
    else:
        _load_ini_file(inventory, filepath)
    return inventory


def load_inventory_dir(directory: str | Path) -> Inventory:
    """Load and merge all inventory files in *directory*, then apply group_vars/.

    Processing order (deterministic, alphabetical within each step):

    1. All YAML / INI inventory files at the **root** of *directory*
       (``group_vars/`` is skipped at this stage).
    2. All YAML / INI inventory files in **sub-directories** other than
       ``group_vars/``.
    3. ``group_vars/`` — vars are merged on top of whatever was loaded in
       steps 1-2.  Unknown groups are created automatically (Ansible behaviour).
    """
    dirpath = Path(directory)
    if not dirpath.exists():
        raise FileNotFoundError(f"Inventory directory not found: {dirpath}")
    if not dirpath.is_dir():
        raise ValueError(f"Expected a directory, got: {dirpath}")

    inventory = Inventory()
    loaded: list[Path] = []

    def _try_load(filepath: Path) -> None:
        suffix = filepath.suffix.lower()
        if suffix in YAML_SUFFIXES:
            _load_yaml_file(inventory, filepath)
            loaded.append(filepath)
        elif suffix in INI_SUFFIXES:
            _load_ini_file(inventory, filepath)
            loaded.append(filepath)
        elif suffix == "":
            fmt = _detect_format(filepath)
            if fmt == "yaml":
                _load_yaml_file(inventory, filepath)
            else:
                _load_ini_file(inventory, filepath)
            loaded.append(filepath)

    for filepath in sorted(dirpath.rglob("*")):
        if not filepath.is_file():
            continue
        # Skip anything inside group_vars/ — handled separately below
        if GROUP_VARS_DIR in filepath.parts:
            continue
        if filepath.stem.lower() == VAULT_STEM:
            continue
        _try_load(filepath)

    if not loaded:
        raise FileNotFoundError(f"No inventory files found in: {dirpath}")

    # Apply group_vars/ on top
    group_vars_path = dirpath / GROUP_VARS_DIR
    _load_group_vars(inventory, group_vars_path)

    return inventory


def dump_inventory_yaml(inventory: Inventory, filepath: Path) -> None:
    """Write *inventory* as an Ansible YAML inventory file."""
    def _build_group(group_name: str) -> dict[str, Any]:
        group = inventory._groups.get(group_name)
        if group is None:
            return {}
        data: dict[str, Any] = {}
        if group.vars:
            data["vars"] = group.vars
        if group.hosts:
            data["hosts"] = {h: inventory.get_host(h).vars or None for h in group.hosts}
        if group.children:
            data["children"] = {c: _build_group(c) for c in group.children}
        return data

    all_children: set[str] = set()
    for g in inventory.list_groups():
        all_children.update(g.children)

    top_level = [g.name for g in inventory.list_groups() if g.name not in all_children]
    output = {name: _build_group(name) for name in top_level}

    with filepath.open("w", encoding="utf-8") as fh:
        yaml.dump(output, fh, default_flow_style=False, allow_unicode=True)


def dump_inventory_ini(inventory: Inventory, filepath: Path) -> None:
    """Write *inventory* as an Ansible INI inventory file.

    Layout produced:
    - One section ``[group_name]`` per group (top-level groups first,
      then children, alphabetically within each tier).
    - Inline ``key=value`` pairs for host vars.
    - ``[group_name:vars]`` sections for group vars.
    - ``[group_name:children]`` sections for child relationships.
    """
    lines: list[str] = []

    # Collect all groups, parents first
    all_children: set[str] = set()
    for g in inventory.list_groups():
        all_children.update(g.children)
    ordered = (
        [g for g in sorted(inventory.list_groups(), key=lambda g: g.name) if g.name not in all_children]
        + [g for g in sorted(inventory.list_groups(), key=lambda g: g.name) if g.name in all_children]
    )

    for group in ordered:
        # [group]
        lines.append(f"[{group.name}]")
        for hostname in sorted(group.hosts):
            try:
                hv = inventory.get_host(hostname).vars
            except KeyError:
                hv = {}
            if hv:
                vars_str = " ".join(f"{k}={v}" for k, v in sorted(hv.items()))
                lines.append(f"{hostname} {vars_str}")
            else:
                lines.append(hostname)
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


def dump_inventory(inventory: Inventory, path: str | Path) -> None:
    """Serialize *inventory* back to disk, preserving the original file format.

    The format is detected from the file extension (or content sniffing for
    extension-less files), so a ``.ini`` file is rewritten as INI and a
    ``.yml`` / ``.yaml`` file as YAML.
    """
    filepath = Path(path)
    fmt = _detect_format(filepath) if filepath.exists() else (
        "ini" if filepath.suffix.lower() in INI_SUFFIXES else "yaml"
    )
    if fmt == "ini":
        dump_inventory_ini(inventory, filepath)
    else:
        dump_inventory_yaml(inventory, filepath)
