"""Network model: typed representation of BlueBanquise *networks* entries.

A ``Network`` maps to one entry inside the ``networks:`` dict that lives in
``group_vars/all/…/networks.yml``.  The canonical format (based on the
BlueBanquise sample inventory) uses *subnet* + *prefix* rather than CIDR
notation:

    networks:
      net-admin:
        subnet: 10.0.3.0
        prefix: 16
        netmask: 255.255.0.0      # optional, derived
        broadcast: 10.0.5.255     # optional, derived
        gateway: 10.0.10.1        # optional
        dhcp_server: true
        dns_server:  true
        shared_network: mgtadmin  # optional
        firewall:                 # optional
          zone: public
        services: "{{ services.regionadmin.admin }}"  # optional, kept as-is

``validate_network_interfaces`` checks that the IPs declared on host NICs
belong to the subnet of the referenced network, and returns a list of
``IpInconsistency`` objects (one per offending NIC).  The caller decides how
to surface them (warnings, errors, …).
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bbui.backend.models import Inventory


# ---------------------------------------------------------------------------
# Network dataclass
# ---------------------------------------------------------------------------


@dataclass
class Network:
    """Typed representation of one entry in the ``networks`` dict."""

    name: str
    subnet: str                                   # e.g. "10.0.3.0"
    prefix: int                                   # e.g. 16
    netmask: str | None = None                    # e.g. "255.255.0.0"
    broadcast: str | None = None                  # e.g. "10.0.5.255"
    gateway: str | None = None                    # e.g. "10.0.10.1"
    dhcp_server: bool = False
    dns_server: bool = False
    shared_network: str | None = None
    firewall: dict[str, Any] = field(default_factory=dict)
    services: Any = None                          # str Jinja2 template or dict

    # ------------------------------------------------------------------
    # IP containment
    # ------------------------------------------------------------------

    def contains_ip(self, ip: str) -> bool:
        """Return ``True`` if *ip* belongs to this network's subnet/prefix.

        The check is deliberately permissive: if the IP or subnet is
        unparseable (e.g. a Jinja2 template string) it returns ``True`` so as
        not to generate spurious warnings.
        """
        try:
            net = ipaddress.ip_network(f"{self.subnet}/{self.prefix}", strict=False)
            return ipaddress.ip_address(ip) in net
        except ValueError:
            return True

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a YAML-compatible dict (``name`` key excluded; None/empty omitted)."""
        out: dict[str, Any] = {
            "subnet": self.subnet,
            "prefix": self.prefix,
        }
        if self.netmask is not None:
            out["netmask"] = self.netmask
        if self.broadcast is not None:
            out["broadcast"] = self.broadcast
        if self.gateway is not None:
            out["gateway"] = self.gateway
        if self.dhcp_server:
            out["dhcp_server"] = self.dhcp_server
        if self.dns_server:
            out["dns_server"] = self.dns_server
        if self.shared_network is not None:
            out["shared_network"] = self.shared_network
        if self.firewall:
            out["firewall"] = self.firewall
        if self.services is not None:
            out["services"] = self.services
        return out

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "Network":
        """Deserialise from an inventory dict entry.

        Unknown keys are silently ignored so that future BlueBanquise fields
        do not cause crashes.
        """
        return cls(
            name=name,
            subnet=str(data.get("subnet", "")),
            prefix=int(data.get("prefix", 0)),
            netmask=data.get("netmask"),
            broadcast=data.get("broadcast"),
            gateway=data.get("gateway"),
            dhcp_server=bool(data.get("dhcp_server", False)),
            dns_server=bool(data.get("dns_server", False)),
            shared_network=data.get("shared_network"),
            firewall=dict(data.get("firewall") or {}),
            services=data.get("services"),
        )

    def __repr__(self) -> str:
        return f"Network(name={self.name!r}, subnet={self.subnet}/{self.prefix})"


# ---------------------------------------------------------------------------
# IP consistency validation
# ---------------------------------------------------------------------------


@dataclass
class IpInconsistency:
    """One IP/subnet mismatch detected on a host NIC."""

    hostname: str
    interface: str   # value of the ``interface`` field in network_interfaces
    ip: str          # the offending IP (may be bare or from ip4_manual)
    network_name: str
    expected_subnet: str
    expected_prefix: int

    def __str__(self) -> str:
        return (
            f"{self.hostname} [{self.interface}]: {self.ip} "
            f"is not in {self.network_name} "
            f"({self.expected_subnet}/{self.expected_prefix})"
        )


def _bare_ip(ip_or_cidr: str) -> str:
    """Strip an optional /prefix from an IP string.

    Handles both ``10.0.17.21`` and ``10.0.17.21/24``.
    """
    return ip_or_cidr.split("/")[0]


def validate_network_interfaces(inventory: "Inventory") -> list[IpInconsistency]:
    """Check that NIC IPs match the subnet of their declared network.

    Iterates every host's ``network_interfaces`` list.  For each NIC that
    declares both an IP (``ip4`` or entries in ``ip4_manual``) and a
    ``network`` name that exists in ``inventory.networks``, the IP is checked
    against the network's subnet.

    Returns a (possibly empty) list of :class:`IpInconsistency` objects.
    Unparseable IPs / subnets are silently skipped.
    """
    issues: list[IpInconsistency] = []

    for host in inventory.list_hosts():
        nics: list[dict[str, Any]] = host.vars.get("network_interfaces", [])
        if not isinstance(nics, list):
            continue

        for nic in nics:
            if not isinstance(nic, dict):
                continue

            net_name: str | None = nic.get("network")
            if not net_name or net_name not in inventory.networks:
                continue

            net = inventory.networks[net_name]
            iface: str = str(nic.get("interface", "?"))

            # Check plain ip4
            ip4: str | None = nic.get("ip4")
            if isinstance(ip4, str) and ip4:
                bare = _bare_ip(ip4)
                if not net.contains_ip(bare):
                    issues.append(
                        IpInconsistency(
                            hostname=host.name,
                            interface=iface,
                            ip=bare,
                            network_name=net_name,
                            expected_subnet=net.subnet,
                            expected_prefix=net.prefix,
                        )
                    )

            # Check ip4_manual list (entries like "10.0.17.21/24")
            ip4_manual: Any = nic.get("ip4_manual")
            if isinstance(ip4_manual, list):
                for entry in ip4_manual:
                    if isinstance(entry, str) and entry:
                        bare = _bare_ip(entry)
                        if not net.contains_ip(bare):
                            issues.append(
                                IpInconsistency(
                                    hostname=host.name,
                                    interface=iface,
                                    ip=bare,
                                    network_name=net_name,
                                    expected_subnet=net.subnet,
                                    expected_prefix=net.prefix,
                                )
                            )

    return issues
