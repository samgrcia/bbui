"""bbcli – Command-line interface for bbui."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bbui.backend.models import Inventory
from bbui.backend.parser import load_inventory, load_inventory_dir
from bbui.backend.staging import (
    Change, ChangeKind,
    commit, discard, diff_summary,
    has_pending, load_cache, load_inventory_or_cache,
    stage,
)

app = typer.Typer(
    name="bbcli",
    help="Manage Ansible inventories (YAML / INI) from the command line.",
    no_args_is_help=True,
)

host_app  = typer.Typer(help="Manage hosts.",  no_args_is_help=True)
group_app = typer.Typer(help="Manage groups.", no_args_is_help=True)

app.add_typer(host_app,  name="host")
app.add_typer(group_app, name="group")

# ---------------------------------------------------------------------------
# Shared options & helpers
# ---------------------------------------------------------------------------

InventoryOption = Annotated[
    Path,
    typer.Option(
        "--inventory", "-i",
        help="Path to an Ansible inventory file (YAML or INI). "
             "Used only when --inventory-dir is not set.",
        envvar="BBUI_INVENTORY",
        show_default=True,
    ),
]

InventoryDirOption = Annotated[
    Optional[Path],
    typer.Option(
        "--inventory-dir", "-I",
        help="Directory containing inventory files (YAML and/or INI). "
             "Enables the staging workflow (pending / commit).",
        envvar="BBUI_INVENTORY_DIR",
    ),
]

DEFAULT_INVENTORY = Path("inventory.yml")

# ANSI-style labels for ChangeKind
_KIND_LABEL: dict[ChangeKind, tuple[str, str]] = {
    ChangeKind.HOST_ADDED:    ("[green]+[/green]", "host added"),
    ChangeKind.HOST_REMOVED:  ("[red]-[/red]",     "host removed"),
    ChangeKind.GROUP_ADDED:   ("[green]+[/green]", "group added"),
    ChangeKind.GROUP_REMOVED: ("[red]-[/red]",     "group removed"),
    ChangeKind.HOST_VAR_SET:  ("[yellow]~[/yellow]", "var set (host)"),
    ChangeKind.GROUP_VAR_SET: ("[yellow]~[/yellow]", "var set (group)"),
}


def _load_clean(inventory: Path, inventory_dir: Optional[Path]) -> Inventory:
    """Load directly from disk (ignores cache). Used for read-only commands."""
    try:
        if inventory_dir is not None:
            return load_inventory_dir(inventory_dir)
        return load_inventory(inventory)
    except FileNotFoundError as exc:
        rprint(f"[red]Not found:[/red] {exc}")
        raise typer.Exit(1)
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


def _load(inventory: Path, inventory_dir: Optional[Path]) -> Inventory:
    """Load inventory — from staging cache if present, otherwise from disk."""
    try:
        if inventory_dir is not None:
            return load_inventory_or_cache(inventory_dir)
        return load_inventory(inventory)
    except FileNotFoundError as exc:
        rprint(f"[red]Not found:[/red] {exc}")
        raise typer.Exit(1)
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


def _require_dir(inventory_dir: Optional[Path]) -> Path:
    """Exit with error when --inventory-dir is required but absent."""
    if inventory_dir is None:
        rprint("[red]This command requires --inventory-dir / BBUI_INVENTORY_DIR.[/red]")
        raise typer.Exit(1)
    return inventory_dir


# ===========================================================================
# TOP-LEVEL: pending / commit / discard
# ===========================================================================

@app.command("pending")
def cmd_pending(
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Show staged changes waiting to be committed."""
    inv_dir = _require_dir(inventory_dir)

    if not has_pending(inv_dir):
        rprint("[dim]No pending changes.[/dim]")
        return

    staging = load_cache(inv_dir)
    pairs   = diff_summary(staging)

    table = Table(title="Pending changes", show_lines=True, show_header=True)
    table.add_column("",        width=3,  no_wrap=True)
    table.add_column("Type",    style="dim",    no_wrap=True)
    table.add_column("Subject", style="cyan",   no_wrap=True)
    table.add_column("Detail",  style="white")
    table.add_column("Target file", style="magenta")

    files_touched: set[Path] = set()
    for change, target in pairs:
        icon, label = _KIND_LABEL.get(change.kind, ("?", str(change.kind)))
        table.add_row(
            icon,
            label,
            change.subject,
            change.detail,
            str(target) if target else "[dim]auto[/dim]",
        )
        if target:
            files_touched.add(target)

    rprint(table)
    if files_touched:
        rprint(f"\n[bold]Files to be written:[/bold] {', '.join(str(f) for f in sorted(files_touched))}")
    rprint(f"\n[dim]Cache:[/dim] {inv_dir / '.bbui' / 'cache.pkl'}")


@app.command("commit")
def cmd_commit(
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Write pending changes to disk and clear the staging cache."""
    inv_dir = _require_dir(inventory_dir)

    if not has_pending(inv_dir):
        rprint("[dim]Nothing to commit.[/dim]")
        return

    try:
        counts = commit(inv_dir)
    except Exception as exc:
        rprint(f"[red]Commit failed:[/red] {exc}")
        raise typer.Exit(1)

    for filepath, nb in sorted(counts.items()):
        rprint(f"[green]✓[/green] {filepath}  ([dim]{nb} change(s)[/dim])")
    rprint("[bold green]Commit complete.[/bold green]")


@app.command("discard")
def cmd_discard(
    inventory_dir: InventoryDirOption = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Discard all pending changes without writing to disk."""
    inv_dir = _require_dir(inventory_dir)

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
    hostname: Annotated[str, typer.Argument(help="Hostname to add.")],
    group: Annotated[
        Optional[list[str]],
        typer.Option("--group", "-g", help="Group(s) to assign the host to."),
    ] = None,
    inventory: InventoryOption = DEFAULT_INVENTORY,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Stage the addition of a host."""
    inv = _load(inventory, inventory_dir)

    try:
        host = inv.add_host(hostname, groups=list(group or []))
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    change = Change(
        kind=ChangeKind.HOST_ADDED,
        subject=hostname,
        detail=f"groups={host.groups}" if host.groups else "",
    )

    if inventory_dir is not None:
        existing = load_cache(inventory_dir) if has_pending(inventory_dir) else None
        stage(inv, [change], inventory_dir, existing)
        rprint(f"[green]Staged:[/green] host '{hostname}' added  [dim](bbcli commit to write)[/dim]")
    else:
        from bbui.backend.parser import dump_inventory
        dump_inventory(inv, inventory)
        rprint(f"[green]Host added:[/green] {host}")


@host_app.command("remove")
def host_remove(
    hostname: Annotated[str, typer.Argument(help="Hostname to remove.")],
    inventory: InventoryOption = DEFAULT_INVENTORY,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Stage the removal of a host."""
    inv = _load(inventory, inventory_dir)

    try:
        inv.remove_host(hostname)
    except KeyError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    change = Change(kind=ChangeKind.HOST_REMOVED, subject=hostname)

    if inventory_dir is not None:
        existing = load_cache(inventory_dir) if has_pending(inventory_dir) else None
        stage(inv, [change], inventory_dir, existing)
        rprint(f"[yellow]Staged:[/yellow] host '{hostname}' removed  [dim](bbcli commit to write)[/dim]")
    else:
        from bbui.backend.parser import dump_inventory
        dump_inventory(inv, inventory)
        rprint(f"[yellow]Host removed:[/yellow] {hostname}")


@host_app.command("list")
def host_list(
    inventory: InventoryOption = DEFAULT_INVENTORY,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """List all hosts (includes staged changes if any)."""
    inv   = _load(inventory, inventory_dir)
    hosts = inv.list_hosts()

    if inventory_dir and has_pending(inventory_dir):
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
    hostname: Annotated[str, typer.Argument(help="Hostname to inspect.")],
    inventory: InventoryOption = DEFAULT_INVENTORY,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Show details of a specific host."""
    inv = _load(inventory, inventory_dir)
    try:
        rprint(inv.get_host(hostname))
    except KeyError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


# ===========================================================================
# GROUP commands
# ===========================================================================

@group_app.command("add")
def group_add(
    group_name: Annotated[str, typer.Argument(help="Group name to add.")],
    inventory: InventoryOption = DEFAULT_INVENTORY,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Stage the addition of a group."""
    inv = _load(inventory, inventory_dir)

    try:
        inv.add_group(group_name)
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    change = Change(kind=ChangeKind.GROUP_ADDED, subject=group_name)

    if inventory_dir is not None:
        existing = load_cache(inventory_dir) if has_pending(inventory_dir) else None
        stage(inv, [change], inventory_dir, existing)
        rprint(f"[green]Staged:[/green] group '{group_name}' added  [dim](bbcli commit to write)[/dim]")
    else:
        from bbui.backend.parser import dump_inventory
        dump_inventory(inv, inventory)
        rprint(f"[green]Group added:[/green] {group_name}")


@group_app.command("remove")
def group_remove(
    group_name: Annotated[str, typer.Argument(help="Group name to remove.")],
    inventory: InventoryOption = DEFAULT_INVENTORY,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """Stage the removal of a group."""
    inv = _load(inventory, inventory_dir)

    try:
        inv.remove_group(group_name)
    except KeyError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    change = Change(kind=ChangeKind.GROUP_REMOVED, subject=group_name)

    if inventory_dir is not None:
        existing = load_cache(inventory_dir) if has_pending(inventory_dir) else None
        stage(inv, [change], inventory_dir, existing)
        rprint(f"[yellow]Staged:[/yellow] group '{group_name}' removed  [dim](bbcli commit to write)[/dim]")
    else:
        from bbui.backend.parser import dump_inventory
        dump_inventory(inv, inventory)
        rprint(f"[yellow]Group removed:[/yellow] {group_name}")


@group_app.command("list")
def group_list(
    inventory: InventoryOption = DEFAULT_INVENTORY,
    inventory_dir: InventoryDirOption = None,
) -> None:
    """List all groups (includes staged changes if any)."""
    inv    = _load(inventory, inventory_dir)
    groups = inv.list_groups()

    if inventory_dir and has_pending(inventory_dir):
        rprint("[yellow]⚠ Showing staged inventory (uncommitted changes present)[/yellow]")

    if not groups:
        rprint("[dim]No groups found.[/dim]")
        return

    table = Table(title="Groups", show_lines=True)
    table.add_column("Name",     style="cyan",    no_wrap=True)
    table.add_column("Hosts",    style="magenta")
    table.add_column("Children", style="green")

    for group in sorted(groups, key=lambda g: g.name):
        table.add_row(group.name, ", ".join(group.hosts), ", ".join(group.children))

    rprint(table)


if __name__ == "__main__":
    app()
