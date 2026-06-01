"""Domain models for Ansible inventory objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bbui.backend.network import Network


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
        # Typed view of the ``networks`` variable from group_vars/all.
        self.networks: dict[str, Network] = {}
        # File from which ``networks`` was loaded (None if not yet persisted).
        self._networks_source: Path | None = None

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

    # ------------------------------------------------------------------
    # Synthetic "all" group
    # ------------------------------------------------------------------

    def _create_all_group(self) -> None:
        """Create (or update) the synthetic ``all`` group.

        After loading, the ``all`` group contains every host in the inventory.
        Idempotent: safe to call multiple times.
        """
        all_group = self._ensure_group("all")
        for host in self._hosts.values():
            host.add_group("all")
            all_group.add_host(host.name)

    # ------------------------------------------------------------------
    # Networks synchronisation
    # ------------------------------------------------------------------

    def _sync_networks_from_vars(self) -> None:
        """Populate ``self.networks`` from the ``all`` group's ``networks`` var.

        Call this after ``_create_all_group()`` and ``_load_group_vars()``.
        """
        all_grp = self._groups.get("all")
        if all_grp is None:
            return
        raw: Any = all_grp.vars.get("networks")
        if not isinstance(raw, dict):
            return
        for name, data in raw.items():
            if isinstance(data, dict):
                self.networks[name] = Network.from_dict(name, data)

    # ------------------------------------------------------------------
    # Pickle compatibility
    # ------------------------------------------------------------------

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        if not hasattr(self, "networks"):
            self.networks = {}
        if not hasattr(self, "_networks_source"):
            self._networks_source = None

    def __repr__(self) -> str:
        return f"Inventory(hosts={len(self._hosts)}, groups={len(self._groups)})"
