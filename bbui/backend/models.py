"""Domain models for Ansible inventory objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Host:
    """Represents an Ansible inventory host."""

    name: str
    groups: list[str] = field(default_factory=list)
    vars: dict[str, Any] = field(default_factory=dict)

    def add_group(self, group_name: str) -> None:
        if group_name not in self.groups:
            self.groups.append(group_name)

    def remove_group(self, group_name: str) -> None:
        self.groups = [g for g in self.groups if g != group_name]

    def __repr__(self) -> str:
        return f"Host(name={self.name!r}, groups={self.groups})"


@dataclass
class Group:
    """Represents an Ansible inventory group."""

    name: str
    hosts: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    vars: dict[str, Any] = field(default_factory=dict)

    def add_host(self, hostname: str) -> None:
        if hostname not in self.hosts:
            self.hosts.append(hostname)

    def remove_host(self, hostname: str) -> None:
        self.hosts = [h for h in self.hosts if h != hostname]

    def add_child(self, group_name: str) -> None:
        if group_name not in self.children:
            self.children.append(group_name)

    def __repr__(self) -> str:
        return f"Group(name={self.name!r}, hosts={self.hosts}, children={self.children})"


class Inventory:
    """Aggregates hosts and groups parsed from an Ansible YAML inventory."""

    def __init__(self) -> None:
        self._hosts: dict[str, Host] = {}
        self._groups: dict[str, Group] = {}

    # ------------------------------------------------------------------
    # Host operations
    # ------------------------------------------------------------------

    def add_host(self, hostname: str, groups: list[str] | None = None, vars: dict[str, Any] | None = None) -> Host:
        if hostname in self._hosts:
            raise ValueError(f"Host '{hostname}' already exists.")
        host = Host(name=hostname, groups=groups or [], vars=vars or {})
        self._hosts[hostname] = host
        # Register host in each group
        for group_name in host.groups:
            self._ensure_group(group_name).add_host(hostname)
        return host

    def remove_host(self, hostname: str) -> Host:
        if hostname not in self._hosts:
            raise KeyError(f"Host '{hostname}' not found.")
        host = self._hosts.pop(hostname)
        for group in self._groups.values():
            group.remove_host(hostname)
        return host

    def get_host(self, hostname: str) -> Host:
        if hostname not in self._hosts:
            raise KeyError(f"Host '{hostname}' not found.")
        return self._hosts[hostname]

    def list_hosts(self) -> list[Host]:
        return list(self._hosts.values())

    # ------------------------------------------------------------------
    # Group operations
    # ------------------------------------------------------------------

    def add_group(self, group_name: str, vars: dict[str, Any] | None = None) -> Group:
        if group_name in self._groups:
            raise ValueError(f"Group '{group_name}' already exists.")
        group = Group(name=group_name, vars=vars or {})
        self._groups[group_name] = group
        return group

    def remove_group(self, group_name: str) -> Group:
        if group_name not in self._groups:
            raise KeyError(f"Group '{group_name}' not found.")
        group = self._groups.pop(group_name)
        for host in self._hosts.values():
            host.remove_group(group_name)
        return group

    def get_group(self, group_name: str) -> Group:
        if group_name not in self._groups:
            raise KeyError(f"Group '{group_name}' not found.")
        return self._groups[group_name]

    def list_groups(self) -> list[Group]:
        return list(self._groups.values())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_group(self, group_name: str) -> Group:
        if group_name not in self._groups:
            self._groups[group_name] = Group(name=group_name)
        return self._groups[group_name]

    def __repr__(self) -> str:
        return f"Inventory(hosts={len(self._hosts)}, groups={len(self._groups)})"
