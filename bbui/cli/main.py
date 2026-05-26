"""bbcli – Command-line interface for bbui."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn, Optional

import typer
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bbui.backend.models import Inventory
from bbui.backend.vars_lookup import (
    build_var_source_map, lookup_var, _resolve_dotpath, _top_level_key,
)
from bbui.cli.vars_display import flatten_vars, host_vars_table, vars_table
from bbui.backend.nodeset import expand_nodeset, fold_nodeset
from bbui.backend.parser import load_inventory, load_inventory_dir
from bbui.backend.staging import (
    Change, ChangeKind,
    affected_files, commit, discard, diff_summary, grouped_changes,
    has_pending, load_cache, load_inventory_or_cache,
    stage,
)

app = typer.Typer(
    name="bbcli",
    help="Manage Ansible inventories (YAML / INI) from the command line.",
    no_args_is_help=True,
)

host_app  = typer.Typer(help="Manage hosts.",   no_args_is_help=True)
group_app = typer.Typer(help="Manage groups.",  no_args_is_help=True)
vars_app  = typer.Typer(help="Inspect variables.", no_args_is_help=True)

app.add_typer(host_app,  name="host")
app.add_typer(group_app, name="group")
app.add_typer(vars_app,  name="vars")

# ---------------------------------------------------------------------------
# Shared options & helpers
# ---------------------------------------------------------------------------

# Subdirectory name looked for during workdir auto-discovery
INVENTORY_SUBDIR = "inventory"

InventoryOption = Annotated[
    Optional[Path],
    typer.Option(
        "--inventory", "-i",
        help="Path to an Ansible inventory file (YAML or INI). "
             "Used only when --inventory-dir is not set.",
        envvar="BBUI_INVENTORY",
    ),
]

InventoryDirOption = Annotated[
    Optional[Path],
    typer.Option(
        "--inventory-dir", "-I",
        help="Working directory. The inventory is loaded from PATH/inventory/. "
             "Enables the staging workflow (pending / commit).",
        envvar="BBUI_INVENTORY_DIR",
    ),
]

# ANSI-style labels for ChangeKind
_KIND_LABEL: dict[ChangeKind, tuple[str, str]] = {
    ChangeKind.HOST_ADDED:    ("[green]+[/green]", "host added"),
    ChangeKind.HOST_REMOVED:  ("[red]-[/red]",     "host removed"),
    ChangeKind.GROUP_ADDED:   ("[green]+[/green]", "group added"),
    ChangeKind.GROUP_REMOVED: ("[red]-[/red]",     "group removed"),
    ChangeKind.HOST_VAR_SET:  ("[yellow]~[/yellow]", "var set (host)"),
    ChangeKind.GROUP_VAR_SET: ("[yellow]~[/yellow]", "var set (group)"),
}


def _resolve_inventory(
    inventory: Path | None,
    inventory_dir: Path | None,
) -> tuple[Path | None, Path | None]:
    """Return (inv_file, inv_dir) using CLI/env/workdir priority.

    Priority:
    1. --inventory-dir / BBUI_INVENTORY_DIR  → inventory at <workdir>/inventory/
    2. --inventory / BBUI_INVENTORY          → single file, used as-is
    3. cwd/inventory/ workdir auto-discovery → inventory at <cwd>/inventory/
    Returns (None, None) when nothing is found.
    """
    if inventory_dir is not None:
        return None, inventory_dir / INVENTORY_SUBDIR
    if inventory is not None:
        return inventory, None
    candidate = Path.cwd() / INVENTORY_SUBDIR
    if candidate.is_dir():
        return None, candidate
    return None, None


def _no_inventory_error() -> NoReturn:
    rprint(
        "[red]No inventory found.[/red]  "
        "Pass [bold]-i FILE[/bold] or [bold]-I DIR[/bold], "
        "set [bold]BBUI_INVENTORY[/bold] / [bold]BBUI_INVENTORY_DIR[/bold], "
        "or run from a workdir containing an [bold]inventory/[/bold] subdirectory."
    )
    raise typer.Exit(1)


def _load_clean(inventory: Path | None, inventory_dir: Path | None) -> Inventory:
    """Load directly from disk (ignores cache). Used for read-only commands."""
    try:
        if inventory_dir is not None:
            from bbui.backend.bbinventory import BbInventory
            if BbInventory.is_bb_layout(inventory_dir):
                return BbInventory.load(inventory_dir)
            return load_inventory_dir(inventory_dir)
        if inventory is not None:
            return load_inventory(inventory)
    except FileNotFoundError as exc:
        rprint(f"[red]Not found:[/red] {exc}")
        raise typer.Exit(1)
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    raise AssertionError("unreachable")


def _load(inventory: Path | None, inventory_dir: Path | None) -> Inventory:
    """Load inventory — from staging cache if present, otherwise from disk."""
    try:
        if inventory_dir is not None:
            return load_inventory_or_cache(inventory_dir)
        if inventory is not None:
            return load_inventory(inventory)
    except FileNotFoundError as exc:
        rprint(f"[red]Not found:[/red] {exc}")
        raise typer.Exit(1)
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    raise AssertionError("unreachable")


def _require_dir(inventory_dir: Path | None) -> Path:
    """Exit with error when an inventory directory is required but not found."""
    if inventory_dir is None:
        _no_inventory_error()
    return inventory_dir


# ===========================================================================
# TOP-LEVEL: pending / commit / discard
# ===========================================================================

@app.command("pending")
def cmd_pending(
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Show staged changes waiting to be committed."""
    _, inv_dir = _resolve_inventory(None, inventory_dir)
    inv_dir = _require_dir(inv_dir)

    if not has_pending(inv_dir):
        rprint("[dim]No pending changes.[/dim]")
        return

    staging = load_cache(inv_dir)
    by_file = affected_files(staging)
    grouped = grouped_changes(staging)

    # ── Changes table: one row per (kind, detail) group, subject as nodeset ─
    change_table = Table(title="Pending changes", show_lines=True)
    change_table.add_column("",        width=3,  no_wrap=True)
    change_table.add_column("Type",    style="dim",    no_wrap=True)
    change_table.add_column("Nodeset / Subject", style="cyan")
    change_table.add_column("Detail",  style="white")

    for kind, folded, detail, _files in grouped:
        icon, label = _KIND_LABEL.get(kind, ("?", str(kind)))
        change_table.add_row(icon, label, folded, detail)

    rprint(change_table)

    # ── Files table: one row per file, subjects folded as nodesets ──────────
    files_table = Table(title="Files to be written", show_lines=True)
    files_table.add_column("File",    style="magenta", no_wrap=True)
    files_table.add_column("Changes", style="cyan")

    from bbui.backend.nodeset import fold_nodeset
    from bbui.backend.staging import ChangeKind as CK

    HOST_KINDS = {CK.HOST_ADDED, CK.HOST_REMOVED, CK.HOST_VAR_SET}

    for filepath, changes_for_file in by_file.items():
        per_kind: dict[ChangeKind, list[str]] = {}
        for c in changes_for_file:
            per_kind.setdefault(c.kind, []).append(c.subject)

        parts = []
        for kind, subjects in per_kind.items():
            icon, _ = _KIND_LABEL.get(kind, ("?", ""))
            folded = fold_nodeset(subjects) if kind in HOST_KINDS else ", ".join(subjects)
            parts.append(f"{icon} {folded}")

        files_table.add_row(str(filepath), "  ".join(parts))

    rprint(files_table)
    rprint(f"[dim]Cache:[/dim] {inv_dir / '.bbui' / 'cache.pkl'}")


@app.command("commit")
def cmd_commit(
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Write pending changes to disk and clear the staging cache."""
    _, inv_dir = _resolve_inventory(None, inventory_dir)
    inv_dir = _require_dir(inv_dir)

    if not has_pending(inv_dir):
        rprint("[dim]Nothing to commit.[/dim]")
        return

    try:
        counts = commit(inv_dir)
    except Exception as exc:
        rprint(f"[red]Commit failed:[/red] {exc}")
        raise typer.Exit(1)

    for filepath, count in sorted(counts.items()):
        rprint(f"[green]✓[/green] {filepath}  ([dim]{count} change(s)[/dim])")
    rprint("[bold green]Commit complete.[/bold green]")


@app.command("discard")
def cmd_discard(
    inventory_dir: InventoryDirOption = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Discard all pending changes without writing to disk."""
    _, inv_dir = _resolve_inventory(None, inventory_dir)
    inv_dir = _require_dir(inv_dir)

    if not has_pending(inv_dir):
        rprint("[dim]No pending changes to discard.[/dim]")
        return

    if not force:
        typer.confirm("Discard all pending changes?", abort=True)

    discard(inv_dir)
    rprint("[yellow]Pending changes discarded.[/yellow]")


# ===========================================================================
# HOST commands
# ===========================================================================

@host_app.command("add")
def host_add(
    nodeset: Annotated[str, typer.Argument(
        help="Hostname or Nodeset to add (e.g. web01 or web[01:10])."
    )],
    groups: Annotated[
        Optional[str],
        typer.Option("--groups", "-g",
                     help="Comma-separated list of groups to assign the hosts to "
                          "(e.g. --groups webservers,staging)."),
    ] = None,
    inventory: InventoryOption = None,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Stage the addition of one or more hosts (Nodeset syntax supported)."""
    group_list: list[str] = [g.strip() for g in groups.split(",")] if groups else []

    try:
        hostnames = expand_nodeset(nodeset)
    except ValueError as exc:
        rprint(f"[red]Invalid nodeset:[/red] {exc}")
        raise typer.Exit(1)

    inv_file, inv_dir = _resolve_inventory(inventory, inventory_dir)
    if inv_file is None and inv_dir is None:
        _no_inventory_error()

    inv = _load(inv_file, inv_dir)
    changes: list[Change] = []
    added: list[str] = []
    skipped: list[str] = []

    for hostname in hostnames:
        try:
            inv.add_host(hostname, groups=group_list)
            changes.append(Change(
                kind=ChangeKind.HOST_ADDED,
                subject=hostname,
                detail=f"groups={group_list}" if group_list else "",
            ))
            added.append(hostname)
        except ValueError as exc:
            msg = str(exc)
            if "already exists" in msg:
                skipped.append(hostname)
            else:
                rprint(f"[red]Error:[/red] {exc}")
                raise typer.Exit(1)

    if skipped:
        rprint(f"[yellow]Skipped (already exist):[/yellow] {', '.join(skipped)}")
    if not added:
        raise typer.Exit(0)

    if inv_dir is not None:
        existing = load_cache(inv_dir) if has_pending(inv_dir) else None
        stage(inv, changes, inv_dir, existing)
        rprint(
            f"[green]Staged:[/green] {len(added)} host(s) added"
            + (f" → groups {group_list}" if group_list else "")
            + "  [dim](bbcli commit to write)[/dim]"
        )
        for h in added:
            rprint(f"  [dim]+[/dim] {h}")
    else:
        from bbui.backend.parser import dump_inventory
        dump_inventory(inv, inv_file)  # type: ignore[arg-type]
        rprint(f"[green]{len(added)} host(s) added:[/green] {', '.join(added)}")


@host_app.command("remove")
def host_remove(
    hostname: Annotated[str, typer.Argument(help="Hostname to remove.")],
    inventory: InventoryOption = None,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Stage the removal of a host."""
    inv_file, inv_dir = _resolve_inventory(inventory, inventory_dir)
    if inv_file is None and inv_dir is None:
        _no_inventory_error()

    inv = _load(inv_file, inv_dir)

    try:
        inv.remove_host(hostname)
    except KeyError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    change = Change(kind=ChangeKind.HOST_REMOVED, subject=hostname)

    if inv_dir is not None:
        existing = load_cache(inv_dir) if has_pending(inv_dir) else None
        stage(inv, [change], inv_dir, existing)
        rprint(f"[yellow]Staged:[/yellow] host '{hostname}' removed  [dim](bbcli commit to write)[/dim]")
    else:
        from bbui.backend.parser import dump_inventory
        dump_inventory(inv, inv_file)  # type: ignore[arg-type]
        rprint(f"[yellow]Host removed:[/yellow] {hostname}")


@host_app.command("list")
def host_list(
    inventory: InventoryOption = None,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """List all hosts (includes staged changes if any)."""
    inv_file, inv_dir = _resolve_inventory(inventory, inventory_dir)
    if inv_file is None and inv_dir is None:
        _no_inventory_error()

    inv   = _load(inv_file, inv_dir)
    hosts = inv.list_hosts()

    if inv_dir and has_pending(inv_dir):
        rprint("[yellow]⚠ Showing staged inventory (uncommitted changes present)[/yellow]")

    if not hosts:
        rprint("[dim]No hosts found.[/dim]")
        return

    table = Table(title="Hosts", show_lines=True)
    table.add_column("Name",   style="cyan",    no_wrap=True)
    table.add_column("Groups", style="magenta")
    table.add_column("Vars",   style="dim")

    for host in sorted(hosts, key=lambda h: h.name):
        table.add_row(host.name, ", ".join(host.groups), str(host.vars) if host.vars else "")

    rprint(table)


@host_app.command("show")
def host_show(
    nodeset: Annotated[str, typer.Argument(
        help="Hostname or NodeSet to inspect (e.g. web01 or web[01:10])."
    )],
    varname: Annotated[Optional[str], typer.Argument(
        help="Variable to display (dot-notation: bmc.ip4, disks[0].name). "
             "Shows only that variable's value for each host in a compact table."
    )] = None,
    show_files: Annotated[bool, typer.Option(
        "-v", "--verbose",
        help="Show the source file for each variable. "
             "If the same variable is defined in multiple files, all are shown.",
    )] = False,
    inventory: InventoryOption = None,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Show details and variables of one or more hosts (NodeSet syntax supported).

    Displays both host variables and variables inherited from each group.
    Use -f to see which file each variable comes from.

    With a second argument, restricts output to a single variable across all matched hosts.
    """
    try:
        hostnames = expand_nodeset(nodeset)
    except ValueError as exc:
        rprint(f"[red]Invalid nodeset:[/red] {exc}")
        raise typer.Exit(1)

    inv_file, inv_dir = _resolve_inventory(inventory, inventory_dir)
    if inv_file is None and inv_dir is None:
        _no_inventory_error()

    inv = _load(inv_file, inv_dir)

    hosts = []
    missing = []
    for name in hostnames:
        try:
            hosts.append(inv.get_host(name))
        except KeyError:
            missing.append(name)

    if missing:
        rprint(f"[yellow]Not found:[/yellow] {', '.join(missing)}")
    if not hosts:
        raise typer.Exit(1)

    if varname is not None:
        # ── Single-variable mode: compact table Host | Value ─────────────
        table = Table(
            title=f"[bold yellow]{varname}[/bold yellow]",
            show_lines=True,
        )
        table.add_column("Host",  style="cyan",  no_wrap=True)
        table.add_column("Value", style="white")

        for host in hosts:
            found, value = _resolve_dotpath(host.vars, varname)
            table.add_row(host.name, _format_value(value) if found else "[dim]—[/dim]")

        rprint(table)
    else:
        # ── Full display mode: one block per host ─────────────────────────
        vsmap = None
        workdir = inv_dir.parent if inv_dir is not None else None
        if show_files and inv_dir is not None:
            try:
                vsmap = build_var_source_map(inv_dir)
            except Exception:
                pass

        def _rel(paths: list[Path]) -> list[Path]:
            if workdir is None:
                return paths
            return [p.relative_to(workdir) if p.is_relative_to(workdir) else p for p in paths]

        for i, host in enumerate(hosts):
            if i > 0:
                rprint("")
            rprint(f"[bold cyan]{host.name}[/bold cyan]")
            rprint(f"  [dim]groups:[/dim] {', '.join(host.groups) if host.groups else 'none'}")

            # Collect all variable rows: (dotted_key, type_label, str_value, files)
            rows: list[tuple[str, str, str, list[Path]]] = []

            for dotted_key, str_value in flatten_vars(host.vars):
                top = _top_level_key(dotted_key)
                files = _rel(vsmap.file_for_host_var(host.name, top)) if vsmap else []
                rows.append((dotted_key, "hostvar", str_value, files))

            for group_name in sorted(host.groups):
                try:
                    group = inv.get_group(group_name)
                except KeyError:
                    continue
                if not group.vars:
                    continue
                label = f"groupvar ({group_name})"
                for dotted_key, str_value in flatten_vars(group.vars):
                    top = _top_level_key(dotted_key)
                    files = _rel(vsmap.file_for_group_var(group_name, top)) if vsmap else []
                    rows.append((dotted_key, label, str_value, files))

            if rows:
                rprint(host_vars_table(rows, show_files=show_files))
            else:
                rprint("  [dim]vars:   none[/dim]")


# ===========================================================================
# GROUP commands
# ===========================================================================

@group_app.command("add")
def group_add(
    group_name: Annotated[str, typer.Argument(help="Group name to add.")],
    inventory: InventoryOption = None,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Stage the addition of a group."""
    inv_file, inv_dir = _resolve_inventory(inventory, inventory_dir)
    if inv_file is None and inv_dir is None:
        _no_inventory_error()

    inv = _load(inv_file, inv_dir)

    try:
        inv.add_group(group_name)
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    change = Change(kind=ChangeKind.GROUP_ADDED, subject=group_name)

    if inv_dir is not None:
        existing = load_cache(inv_dir) if has_pending(inv_dir) else None
        stage(inv, [change], inv_dir, existing)
        rprint(f"[green]Staged:[/green] group '{group_name}' added  [dim](bbcli commit to write)[/dim]")
    else:
        from bbui.backend.parser import dump_inventory
        dump_inventory(inv, inv_file)  # type: ignore[arg-type]
        rprint(f"[green]Group added:[/green] {group_name}")


@group_app.command("remove")
def group_remove(
    group_name: Annotated[str, typer.Argument(help="Group name to remove.")],
    inventory: InventoryOption = None,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Stage the removal of a group."""
    inv_file, inv_dir = _resolve_inventory(inventory, inventory_dir)
    if inv_file is None and inv_dir is None:
        _no_inventory_error()

    inv = _load(inv_file, inv_dir)

    try:
        inv.remove_group(group_name)
    except KeyError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    change = Change(kind=ChangeKind.GROUP_REMOVED, subject=group_name)

    if inv_dir is not None:
        existing = load_cache(inv_dir) if has_pending(inv_dir) else None
        stage(inv, [change], inv_dir, existing)
        rprint(f"[yellow]Staged:[/yellow] group '{group_name}' removed  [dim](bbcli commit to write)[/dim]")
    else:
        from bbui.backend.parser import dump_inventory
        dump_inventory(inv, inv_file)  # type: ignore[arg-type]
        rprint(f"[yellow]Group removed:[/yellow] {group_name}")


@group_app.command("show")
def group_show(
    group_name: Annotated[str, typer.Argument(help="Group name to inspect.")],
    inventory: InventoryOption = None,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Show details and all variables of a specific group."""
    inv_file, inv_dir = _resolve_inventory(inventory, inventory_dir)
    if inv_file is None and inv_dir is None:
        _no_inventory_error()

    inv = _load(inv_file, inv_dir)
    try:
        group = inv.get_group(group_name)
    except KeyError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    rprint(f"[bold cyan]{group.name}[/bold cyan]")

    hosts_str    = fold_nodeset(group.hosts) if group.hosts else "[dim]none[/dim]"
    children_str = ", ".join(sorted(group.children)) if group.children else "[dim]none[/dim]"
    rprint(f"  [dim]hosts:[/dim]    {hosts_str}")
    rprint(f"  [dim]children:[/dim] {children_str}")

    if group.vars:
        rprint(vars_table(group.vars))
    else:
        rprint("  [dim]vars:   none[/dim]")


@group_app.command("list")
def group_list(
    inventory: InventoryOption = None,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """List all groups (includes staged changes if any)."""
    inv_file, inv_dir = _resolve_inventory(inventory, inventory_dir)
    if inv_file is None and inv_dir is None:
        _no_inventory_error()

    inv    = _load(inv_file, inv_dir)
    groups = inv.list_groups()

    if inv_dir and has_pending(inv_dir):
        rprint("[yellow]⚠ Showing staged inventory (uncommitted changes present)[/yellow]")

    if not groups:
        rprint("[dim]No groups found.[/dim]")
        return

    table = Table(title="Groups", show_lines=True)
    table.add_column("Name",     style="cyan",    no_wrap=True)
    table.add_column("Hosts",    style="magenta")
    table.add_column("Children", style="green")

    for group in sorted(groups, key=lambda g: g.name):
        hosts_str    = fold_nodeset(group.hosts) if group.hosts else ""
        children_str = ", ".join(sorted(group.children))
        table.add_row(group.name, hosts_str, children_str)

    rprint(table)


# ===========================================================================
# VARS commands
# ===========================================================================

@vars_app.command("show")
def vars_show(
    varname: Annotated[str, typer.Argument(
        help="Variable name to look up. Supports dot-notation: network.ip, disks[0].name"
    )],
    inventory: InventoryOption = None,
    inventory_dir: InventoryDirOption = None,
    hosts_only:  Annotated[bool, typer.Option("--hosts",  "-H", help="Show only host matches.")] = False,
    groups_only: Annotated[bool, typer.Option("--groups", "-G", help="Show only group matches.")] = False,
) -> None:
    """Show every host and group that defines <varname>, with its value and source file."""
    inv_file, inv_dir = _resolve_inventory(inventory, inventory_dir)
    if inv_file is None and inv_dir is None:
        _no_inventory_error()

    inv = _load(inv_file, inv_dir)

    # Build a VarSourceMap to track which file contributed each variable key
    var_source_map = None
    if inv_dir is not None:
        try:
            var_source_map = build_var_source_map(inv_dir)
        except Exception:
            pass

    matches = lookup_var(varname, inv, var_source_map)

    if hosts_only:
        matches = [m for m in matches if m.owner_kind == "host"]
    if groups_only:
        matches = [m for m in matches if m.owner_kind == "group"]

    if not matches:
        rprint(f"[dim]No match found for variable [bold]{varname}[/bold].[/dim]")
        raise typer.Exit(0)

    if inv_dir and has_pending(inv_dir):
        rprint("[yellow]⚠ Showing staged inventory (uncommitted changes present)[/yellow]")

    table = Table(
        title=f"Variable: [bold yellow]{varname}[/bold yellow]",
        show_lines=True,
    )
    table.add_column("Kind",   style="dim",     width=6,  no_wrap=True)
    table.add_column("Owner",  style="cyan",              no_wrap=True)
    table.add_column("Value",  style="white")
    table.add_column("Source file", style="magenta")

    for m in matches:
        kind_str  = "host" if m.owner_kind == "host" else "group"
        value_str = _format_value(m.value)
        file_str  = "\n".join(str(p) for p in m.source_file) if m.source_file else "[dim]unknown[/dim]"
        table.add_row(kind_str, m.owner_name, value_str, file_str)

    rprint(table)


def _format_value(value: object) -> str:
    """Format a variable value for display in the vars show table."""
    if isinstance(value, dict):
        return "\n".join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, list):
        return "\n".join(f"[{i}] {item}" for i, item in enumerate(value))
    return str(value) if value is not None else ""


if __name__ == "__main__":
    app()
