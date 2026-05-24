"""Utilities for displaying Ansible variables as a flat dot-notation table.

Flattening rules
----------------
Scalar:
    ansible_user: deploy          ->  ansible_user          deploy

Nested dict:
    network:
      ip: 1.2.3.4                 ->  network.ip            1.2.3.4
      gateway: 1.2.3.1            ->  network.gateway       1.2.3.1

Dict of dicts:
    interfaces:
      eth0:
        speed: 1G                 ->  interfaces.eth0.speed   1G

List of scalars:
    dns_servers:                  ->  dns_servers[]         8.8.8.8
      - 8.8.8.8                   ->  dns_servers[]         8.8.8.4
      - 8.8.8.4

List of dicts:
    disks:                        ->  disks[].name          sda
      - name: sda                 ->  disks[].size          500G
        size: 500G                ->  disks[].name          sdb
      - name: sdb                 ->  disks[].size          1T
        size: 1T
"""

from __future__ import annotations

from typing import Any

from rich.table import Table


def flatten_vars(
    vars_dict: dict[str, Any],
    prefix: str = "",
) -> list[tuple[str, str]]:
    """Recursively flatten *vars_dict* into ``(dotted_key, str_value)`` pairs.

    The pairs are yielded in definition order (dicts preserve insertion order
    in Python 3.7+), with nested keys sorted alphabetically for readability.
    """
    rows: list[tuple[str, str]] = []

    for key, value in vars_dict.items():
        full_key = f"{prefix}.{key}" if prefix else key
        _flatten_value(full_key, value, rows)

    return rows


def _flatten_value(key: str, value: Any, rows: list[tuple[str, str]]) -> None:
    if isinstance(value, dict):
        for subkey, subval in value.items():
            _flatten_value(f"{key}.{subkey}", subval, rows)

    elif isinstance(value, list):
        if not value:
            rows.append((f"{key}[]", ""))
        else:
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    for subkey, subval in item.items():
                        _flatten_value(f"{key}[{i}].{subkey}", subval, rows)
                else:
                    rows.append((f"{key}[{i}]", str(item)))

    else:
        rows.append((key, str(value) if value is not None else ""))


def vars_table(vars_dict: dict[str, Any], title: str = "Variables") -> Table:
    """Build and return a Rich :class:`Table` from *vars_dict*.

    Returns ``None`` when *vars_dict* is empty so callers can display a
    placeholder instead.
    """
    table = Table(title=title, show_header=True, show_lines=False, box=None, padding=(0, 2))
    table.add_column("Variable", style="yellow", no_wrap=True)
    table.add_column("Value",    style="white")

    for dotted_key, str_value in flatten_vars(vars_dict):
        table.add_row(dotted_key, str_value)

    return table
