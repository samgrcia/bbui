"""Nodeset utilities for bbui — wraps ClusterShell (required dependency).

ClusterShell NodeSet syntax supported:
    web[01-10]              range
    web[01-10/2]            step
    web[01-10,20-30]        union
    web[01-10]!web05        exclusion
    web[01-10],db[1:5]      comma-separated sets

Public API
----------
expand_nodeset(expression)   -> list[str]   expand a nodeset to hostnames
fold_nodeset(hostnames)      -> str         fold a list of hostnames to a nodeset string
fold_ansible(hostnames)      -> list[str]   fold to Ansible INI patterns (one per line)
"""

from __future__ import annotations

import re

from ClusterShell.NodeSet import NodeSet

# Matches a numeric range inside brackets written with ClusterShell's dash syntax.
_CS_RANGE_RE = re.compile(r"(\d)-(\d)")


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


def _cs_to_ansible(pattern: str) -> str:
    """Convert a single ClusterShell pattern to Ansible INI syntax.

    ClusterShell uses ``node[01-03]`` (dash); Ansible uses ``node[01:03]`` (colon).
    Only digits separated by a dash *inside* brackets are converted.
    """
    def _fix_brackets(m: re.Match) -> str:
        return "[" + _CS_RANGE_RE.sub(r"\1:\2", m.group(1)) + "]"

    return re.sub(r"\[([^\]]*)\]", _fix_brackets, pattern)


def _split_top_level(folded: str) -> list[str]:
    """Split *folded* on commas that are not inside brackets.

    ClusterShell may return ``db01,web[01-03]`` for mixed host sets.
    Each top-level part maps to one Ansible INI line.
    """
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in folded:
        if ch == "[":
            depth += 1
            current.append(ch)
        elif ch == "]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def fold_ansible(hostnames: list[str] | set[str]) -> list[str]:
    """Fold *hostnames* into Ansible INI range patterns.

    Returns one pattern string per line (a single host name or a folded
    range like ``node[01:10]``).  Hosts that share a common prefix and
    contiguous numbering are merged; non-mergeable hosts appear individually.

    Examples:
        ['web01', 'web02', 'web03']        ->  ['web[01:03]']
        ['web01', 'db01']                  ->  ['db01', 'web01']
        ['web01', 'web03', 'web02']        ->  ['web[01:03]']
        ['web01', 'web03', 'db01']         ->  ['db01', 'web[01,03]']
    """
    folded = fold_nodeset(hostnames)
    return [_cs_to_ansible(part) for part in _split_top_level(folded)]