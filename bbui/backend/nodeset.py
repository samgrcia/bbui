"""Nodeset utilities for bbui — wraps ClusterShell (required dependency).

ClusterShell NodeSet syntax supported:
    web[01-10]              range
    web[01-10/2]            step
    web[01-10,20-30]        union
    web[01-10]!web05        exclusion
    web[01-10],db[1:5]      comma-separated sets

Public API
----------
expand_nodeset(expression)  -> list[str]   expand a nodeset to hostnames
fold_nodeset(hostnames)     -> str         fold a list of hostnames to a nodeset string
"""

from __future__ import annotations

from ClusterShell.NodeSet import NodeSet


def expand_nodeset(expression: str) -> list[str]:
    """Expand *expression* to a sorted list of hostnames.

    Raises ``ValueError`` on invalid expressions.
    """
    try:
        return list(NodeSet(expression))
    except Exception as exc:
        raise ValueError(f"Invalid nodeset {expression!r}: {exc}") from exc


def fold_nodeset(hostnames: list[str] | set[str]) -> str:
    """Fold a collection of hostnames into a compact NodeSet string.

    Examples:
        ['web01', 'web02', 'web03']  ->  'web[01-03]'
        ['web01', 'db01']            ->  'db01,web01'
        ['web01']                    ->  'web01'
    """
    ns = NodeSet.fromlist(hostnames)
    return str(ns)