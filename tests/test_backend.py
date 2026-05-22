"""Tests for backend models and parser."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from bbui.backend.models import Group, Host, Inventory
from bbui.backend.parser import dump_inventory, load_inventory


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_host_creation() -> None:
    host = Host(name="web01")
    assert host.name == "web01"
    assert host.groups == []
    assert host.vars == {}


def test_host_add_group() -> None:
    host = Host(name="web01")
    host.add_group("webservers")
    assert "webservers" in host.groups
    host.add_group("webservers")  # idempotent
    assert host.groups.count("webservers") == 1


def test_group_add_remove_host() -> None:
    group = Group(name="webservers")
    group.add_host("web01")
    assert "web01" in group.hosts
    group.remove_host("web01")
    assert "web01" not in group.hosts


def test_inventory_add_host() -> None:
    inv = Inventory()
    host = inv.add_host("web01", groups=["webservers"])
    assert inv.get_host("web01") is host
    assert "web01" in inv.get_group("webservers").hosts


def test_inventory_duplicate_host_raises() -> None:
    inv = Inventory()
    inv.add_host("web01")
    with pytest.raises(ValueError, match="already exists"):
        inv.add_host("web01")


def test_inventory_remove_host_cleans_groups() -> None:
    inv = Inventory()
    inv.add_host("web01", groups=["webservers"])
    inv.remove_host("web01")
    assert "web01" not in inv.get_group("webservers").hosts
    assert inv.list_hosts() == []


def test_inventory_remove_unknown_host_raises() -> None:
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.remove_host("ghost")


def test_inventory_add_remove_group() -> None:
    inv = Inventory()
    inv.add_group("dbs")
    assert inv.get_group("dbs").name == "dbs"
    inv.remove_group("dbs")
    with pytest.raises(KeyError):
        inv.get_group("dbs")


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

SAMPLE_INVENTORY = textwrap.dedent("""\
    all:
      children:
        webservers:
          hosts:
            web01:
              ansible_user: ubuntu
            web02: ~
        databases:
          hosts:
            db01: ~
""")


@pytest.fixture()
def inventory_file(tmp_path: Path) -> Path:
    p = tmp_path / "inventory.yml"
    p.write_text(SAMPLE_INVENTORY)
    return p


def test_load_inventory(inventory_file: Path) -> None:
    inv = load_inventory(inventory_file)
    assert {h.name for h in inv.list_hosts()} == {"web01", "web02", "db01"}
    web01 = inv.get_host("web01")
    assert web01.vars == {"ansible_user": "ubuntu"}
    assert "webservers" in web01.groups


def test_load_inventory_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_inventory("/nonexistent/path/inventory.yml")


def test_dump_and_reload(tmp_path: Path, inventory_file: Path) -> None:
    inv = load_inventory(inventory_file)
    out = tmp_path / "out.yml"
    dump_inventory(inv, out)
    inv2 = load_inventory(out)
    assert {h.name for h in inv2.list_hosts()} == {h.name for h in inv.list_hosts()}


# ---------------------------------------------------------------------------
# INI parser tests
# ---------------------------------------------------------------------------

SAMPLE_INI = """\
# bare host (ungrouped)
bastion

[webservers]
web01 ansible_user=ubuntu ansible_port=22
web02

[webservers:vars]
ansible_become=true

[databases]
db01

[production:children]
webservers
databases
"""


@pytest.fixture()
def ini_file(tmp_path: Path) -> Path:
    p = tmp_path / "hosts.ini"
    p.write_text(SAMPLE_INI)
    return p


def test_load_ini_hosts(ini_file: Path) -> None:
    inv = load_inventory(ini_file)
    assert {h.name for h in inv.list_hosts()} >= {"web01", "web02", "db01", "bastion"}


def test_load_ini_host_vars(ini_file: Path) -> None:
    inv = load_inventory(ini_file)
    web01 = inv.get_host("web01")
    assert web01.vars.get("ansible_user") == "ubuntu"
    assert web01.vars.get("ansible_port") == "22"


def test_load_ini_group_vars(ini_file: Path) -> None:
    inv = load_inventory(ini_file)
    assert inv.get_group("webservers").vars.get("ansible_become") == "true"


def test_load_ini_children(ini_file: Path) -> None:
    inv = load_inventory(ini_file)
    production = inv.get_group("production")
    assert "webservers" in production.children
    assert "databases" in production.children


# ---------------------------------------------------------------------------
# Directory loader tests
# ---------------------------------------------------------------------------

def test_load_inventory_dir_merges(tmp_path: Path) -> None:
    """A directory with one YAML and one INI file should be fully merged."""
    yaml_content = textwrap.dedent("""\
        webservers:
          hosts:
            web01:
              ansible_user: ubuntu
    """)
    ini_content = textwrap.dedent("""\
        [databases]
        db01 ansible_user=postgres
    """)
    (tmp_path / "web.yml").write_text(yaml_content)
    (tmp_path / "db.ini").write_text(ini_content)

    from bbui.backend.parser import load_inventory_dir
    inv = load_inventory_dir(tmp_path)

    assert {h.name for h in inv.list_hosts()} == {"web01", "db01"}
    assert {g.name for g in inv.list_groups()} >= {"webservers", "databases"}


def test_load_inventory_dir_not_found() -> None:
    from bbui.backend.parser import load_inventory_dir
    with pytest.raises(FileNotFoundError):
        load_inventory_dir("/nonexistent/inventory")


def test_load_inventory_dir_empty(tmp_path: Path) -> None:
    from bbui.backend.parser import load_inventory_dir
    with pytest.raises(FileNotFoundError, match="No inventory files"):
        load_inventory_dir(tmp_path)
