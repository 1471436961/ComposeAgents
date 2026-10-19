"""The member container preserves order, names and live member references."""

from types import MappingProxyType

import pytest

from nooa_patterns import Members


def test_sequence_snapshot_keeps_order_negative_indices_and_member_state() -> None:
    first, second = {"calls": 0}, object()
    source = [first, second]
    members = Members(source)
    source[:] = [object()]
    first["calls"] += 1

    assert len(members) == 2
    assert list(members) == [first, second]
    assert members[0] is first and members[-1] is second
    assert members[0]["calls"] == 1
    assert members.names == () and not members.has_name("first")
    with pytest.raises(KeyError):
        members["first"]
    with pytest.raises(IndexError):
        members[2]


def test_mapping_snapshot_keeps_names_value_order_and_original_references() -> None:
    first, second = object(), object()
    source = {"security": first, "architecture": second}
    members = Members(MappingProxyType(source))
    source.clear()
    source["replacement"] = object()

    assert members.names == ("security", "architecture")
    assert list(members) == [first, second]
    assert members[0] is members["security"] is first
    assert members[1] is members["architecture"] is second
    assert members.has_name("security") and not members.has_name("replacement")
    with pytest.raises(KeyError):
        members["replacement"]


@pytest.mark.parametrize("source", [[], {}], ids=["sequence", "mapping"])
def test_empty_members_are_representable_but_have_no_names_or_values(source) -> None:
    members = Members(source)
    assert not members and len(members) == 0
    assert list(members) == [] and members.names == ()
    assert not members.has_name("anything")


def test_snapshot_has_no_public_item_or_names_mutation() -> None:
    member = object()
    members = Members({"only": member})
    with pytest.raises(TypeError):
        members[0] = object()
    with pytest.raises(TypeError):
        members["only"] = object()
    with pytest.raises(AttributeError):
        members.names = ("replacement",)
    assert members["only"] is member


def test_explicit_name_zero_is_not_positional_index_zero() -> None:
    first, named_zero = object(), object()
    members = Members({"first": first, "0": named_zero})
    assert members[0] is first
    assert members["0"] is named_zero


def test_two_names_can_refer_to_the_same_member_without_copying_or_deduplication() -> None:
    member = object()
    members = Members({"primary": member, "alias": member})
    assert len(members) == 2
    assert members["primary"] is members["alias"] is member


@pytest.mark.parametrize("key", [0, None], ids=["integer", "none"])
def test_mapping_names_must_be_strings(key) -> None:
    with pytest.raises(TypeError, match="names must be strings"):
        Members({key: object()})


def test_slice_access_is_not_part_of_the_index_or_name_contract() -> None:
    with pytest.raises(TypeError, match="int or str"):
        Members([object()])[:]
