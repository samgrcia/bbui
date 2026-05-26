"""Tests for backend models and parser."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from bbui.backend.models import Group, Host, Inventory
from bbui.backend.parser import _expand_hostpattern, dump_inventory, load_inventory


# ---------------------------------------------------------------------------
# Range expansion
# ---------------------------------------------------------------------------


def test_expand_hostpattern_no_range() -> None:
    assert _expand_hostpattern("web01") == ["web01"]


def test_expand_hostpattern_numeric() -> None:
    assert _expand_hostpattern("web[1:3]") == ["web1", "web2", "web3"]


def test_expand_hostpattern_numeric_padded() -> None:
    assert _expand_hostpattern("web[01:03]") == ["web01", "web02", "web03"]


def test_expand_hostpattern_alpha() -> None:
    assert _expand_hostpattern("g[a:c]") == ["ga", "gb", "gc"]


def test_expand_hostpattern_with_suffix() -> None:
    assert _expand_hostpattern("srv[1:2].dc") == ["srv1.dc", "srv2.dc"]


def test_expand_hostpattern_multi_range() -> None:
    assert _expand_hostpattern("hmcr[11:12]s[0:1]") == [
        "hmcr11s0", "hmcr11s1", "hmcr12s0", "hmcr12s1"
    ]


def test_expand_hostpattern_multi_range_padded() -> None:
    assert _expand_hostpattern("n[01:02]c[1:3]") == [
        "n01c1", "n01c2", "n01c3", "n02c1", "n02c2", "n02c3"
    ]


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


# ---------------------------------------------------------------------------
# BbInventory tests
# ---------------------------------------------------------------------------

from bbui.backend.bbinventory import BbInventory


def _make_bb_root(tmp_path: Path) -> Path:
    """Return an empty directory for a BlueBanquise inventory root."""
    return tmp_path


class TestBbInventoryValidation:
    def test_add_host_requires_fn_hw_os(self) -> None:
        inv = BbInventory()
        with pytest.raises(ValueError, match="fn_"):
            inv.add_host("node01", groups=["hw_typeA", "os_ubuntu"])

    def test_add_host_missing_hw(self) -> None:
        inv = BbInventory()
        with pytest.raises(ValueError, match="hw_"):
            inv.add_host("node01", groups=["fn_compute", "os_ubuntu"])

    def test_add_host_missing_os(self) -> None:
        inv = BbInventory()
        with pytest.raises(ValueError, match="os_"):
            inv.add_host("node01", groups=["fn_compute", "hw_typeA"])

    def test_add_host_two_fn_groups_raises(self) -> None:
        inv = BbInventory()
        with pytest.raises(ValueError, match="exactly one"):
            inv.add_host("node01", groups=["fn_compute", "fn_visu", "hw_typeA", "os_ubuntu"])

    def test_add_host_valid(self) -> None:
        inv = BbInventory()
        host = inv.add_host("node01", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        assert host.name == "node01"
        assert "fn_compute" in host.groups

    def test_no_groups_raises(self) -> None:
        inv = BbInventory()
        with pytest.raises(ValueError):
            inv.add_host("node01")


class TestBbInventoryDump:
    def test_dump_creates_node_file(self, tmp_path: Path) -> None:
        root = _make_bb_root(tmp_path)
        inv = BbInventory()
        inv.add_host("mgt1", groups=["fn_management", "hw_typeA", "os_ubuntu"], vars={"ip": "10.0.0.1"})
        inv.write(root)

        node_file = root / "cluster" / "nodes" / "management.yml"
        assert node_file.exists()
        content = yaml.safe_load(node_file.read_text())
        assert "all" in content
        assert "mgt1" in content["all"]["hosts"]
        assert content["all"]["hosts"]["mgt1"]["ip"] == "10.0.0.1"

    def test_dump_creates_group_files(self, tmp_path: Path) -> None:
        root = _make_bb_root(tmp_path)
        inv = BbInventory()
        inv.add_host("c001", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv.write(root)

        fn_file = root / "cluster" / "groups" / "fn"
        hw_file = root / "cluster" / "groups" / "hw"
        os_file = root / "cluster" / "groups" / "os"
        assert fn_file.exists()
        assert hw_file.exists()
        assert os_file.exists()

        fn_text = fn_file.read_text()
        assert "[fn_compute]" in fn_text
        assert "c001" in fn_text

    def test_dump_multiple_fn_groups(self, tmp_path: Path) -> None:
        root = _make_bb_root(tmp_path)
        inv = BbInventory()
        inv.add_host("mgt1",  groups=["fn_management", "hw_typeA", "os_ubuntu"])
        inv.add_host("c001",  groups=["fn_compute",    "hw_typeA", "os_ubuntu"])
        inv.write(root)

        assert (root / "cluster" / "nodes" / "management.yml").exists()
        assert (root / "cluster" / "nodes" / "compute.yml").exists()

    def test_dump_other_groups_to_others_file(self, tmp_path: Path) -> None:
        root = _make_bb_root(tmp_path)
        inv = BbInventory()
        inv.add_host("c001", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv.add_group("storage")
        inv.get_group("storage").add_host("c001")
        inv.write(root)

        others_file = root / "cluster" / "groups" / "others"
        assert others_file.exists()
        assert "[storage]" in others_file.read_text()

    def test_write_creates_directories(self, tmp_path: Path) -> None:
        inv = BbInventory()
        inv.add_host("c001", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv.write(tmp_path)
        assert (tmp_path / "cluster" / "nodes").is_dir()
        assert (tmp_path / "cluster" / "groups").is_dir()

    def test_dump_group_vars(self, tmp_path: Path) -> None:
        root = _make_bb_root(tmp_path)
        inv = BbInventory()
        inv.add_host("c001", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv.get_group("hw_typeA").vars["bios"] = "v2"
        inv.write(root)

        hw_text = (root / "cluster" / "groups" / "hw").read_text()
        assert "[hw_typeA:vars]" in hw_text
        assert "bios=v2" in hw_text

    def test_dump_group_children(self, tmp_path: Path) -> None:
        root = _make_bb_root(tmp_path)
        inv = BbInventory()
        inv.add_host("c001", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv.get_group("hw_typeA").add_child("hw_typeB")
        inv._ensure_group("hw_typeB")
        inv.write(root)

        hw_text = (root / "cluster" / "groups" / "hw").read_text()
        assert "[hw_typeA:children]" in hw_text
        assert "hw_typeB" in hw_text


class TestBbInventoryLoad:
    def test_load_roundtrip(self, tmp_path: Path) -> None:
        root = _make_bb_root(tmp_path)
        inv = BbInventory()
        inv.add_host("mgt1", groups=["fn_management", "hw_typeA", "os_ubuntu"], vars={"ip": "10.0.0.1"})
        inv.add_host("c001", groups=["fn_compute",    "hw_typeA", "os_ubuntu"])
        inv.write(root)

        inv2 = BbInventory.load(root)
        assert {h.name for h in inv2.list_hosts()} == {"mgt1", "c001"}
        mgt1 = inv2.get_host("mgt1")
        assert mgt1.vars.get("ip") == "10.0.0.1"
        assert "fn_management" in mgt1.groups

    def test_load_group_membership(self, tmp_path: Path) -> None:
        root = _make_bb_root(tmp_path)
        inv = BbInventory()
        inv.add_host("c001", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv.write(root)

        inv2 = BbInventory.load(root)
        c001 = inv2.get_host("c001")
        assert "fn_compute" in c001.groups
        assert "hw_typeA"   in c001.groups
        assert "os_ubuntu"  in c001.groups

    def test_load_records_group_source_files(self, tmp_path: Path) -> None:
        root = _make_bb_root(tmp_path)
        inv = BbInventory()
        inv.add_host("c001", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv.add_group("storage")
        inv.write(root)

        inv2 = BbInventory.load(root)
        # Only non-base groups are tracked; base groups always go to canonical files.
        assert "storage" in inv2._group_source
        assert "fn_compute" not in inv2._group_source

    def test_load_other_groups_written_back_to_source(self, tmp_path: Path) -> None:
        """Groups loaded from a custom file are written back to that file."""
        root = _make_bb_root(tmp_path)
        inv0 = BbInventory()
        inv0.add_host("c001", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv0.write(root)
        custom = root / "cluster" / "groups" / "storage"
        custom.write_text("[storage]\nc001\n")

        inv = BbInventory.load(root)
        inv.add_host("c002", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv.get_group("storage").add_host("c002")
        inv.write(root)

        storage_text = custom.read_text()
        assert "[storage]" in storage_text
        # c001 and c002 are folded into a single Ansible range pattern
        assert "c[001:002]" in storage_text
        assert not (root / "cluster" / "groups" / "others").exists()

    def test_load_roundtrip_folded_ini(self, tmp_path: Path) -> None:
        """Hosts folded in INI files are expanded back correctly on load."""
        root = _make_bb_root(tmp_path)
        inv = BbInventory()
        for i in range(1, 6):
            inv.add_host(f"c{i:03d}", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv.write(root)

        # Verify the group file contains folded pattern, not individual lines
        fn_text = (root / "cluster" / "groups" / "fn").read_text()
        assert "c[001:005]" in fn_text
        assert "c001\n" not in fn_text  # individual lines should not appear

        # Verify load back gives all five hosts
        inv2 = BbInventory.load(root)
        assert {h.name for h in inv2.list_hosts()} == {f"c{i:03d}" for i in range(1, 6)}

    def test_new_host_written_to_existing_source_file(self, tmp_path: Path) -> None:
        """A new host goes into the same nodes file as its fn_* peers, not a new file."""
        root = _make_bb_root(tmp_path)
        inv0 = BbInventory()
        inv0.add_host("c001", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv0.write(root)
        # Rename the generated file to simulate an existing single-file layout
        generated = root / "cluster" / "nodes" / "compute.yml"
        shared = root / "cluster" / "nodes" / "nodes.yml"
        generated.rename(shared)

        inv = BbInventory.load(root)
        inv.add_host("c002", groups=["fn_compute", "hw_typeA", "os_ubuntu"])
        inv.write(root)

        # Only nodes.yml must exist — no new compute.yml should be created
        assert shared.exists()
        assert not generated.exists()
        content = yaml.safe_load(shared.read_text())
        assert "c001" in content["all"]["hosts"]
        assert "c002" in content["all"]["hosts"]


# ---------------------------------------------------------------------------
# fold_ansible tests
# ---------------------------------------------------------------------------

from bbui.backend.nodeset import fold_ansible


class TestFoldAnsible:
    def test_contiguous_range(self) -> None:
        assert fold_ansible(["web01", "web02", "web03"]) == ["web[01:03]"]

    def test_single_host(self) -> None:
        assert fold_ansible(["web01"]) == ["web01"]

    def test_empty(self) -> None:
        assert fold_ansible([]) == []

    def test_non_mergeable_hosts(self) -> None:
        result = fold_ansible(["web01", "db01"])
        assert result == ["db01", "web01"]

    def test_non_contiguous_same_prefix(self) -> None:
        result = fold_ansible(["web01", "web03"])
        assert result == ["web[01,03]"]

    def test_large_zero_padded_range(self) -> None:
        hosts = [f"c{i:03d}" for i in range(1, 11)]
        assert fold_ansible(hosts) == ["c[001:010]"]

    def test_mixed_groups_split_into_lines(self) -> None:
        # db01 and web[01-03] must be separate lines, not db01,web[01:03]
        result = fold_ansible(["web01", "web02", "web03", "db01"])
        assert len(result) == 2
        assert "db01" in result
        assert "web[01:03]" in result

    def test_colon_not_dash_in_range(self) -> None:
        result = fold_ansible(["node01", "node02"])
        assert result == ["node[01:02]"]
        assert "-" not in result[0]
