"""Merkle construction, including the attacks the design defends against."""

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tally.merkle import (  # noqa: E402
    EMPTY_ROOT, encode_leaf, leaf_hash, node_hash, proof_for, root_of, verify,
)


def leaves(n: int) -> list[bytes]:
    return [leaf_hash(f"finding-{i}".encode()) for i in range(n)]


def test_known_vector_for_a_single_leaf():
    payload = b"hello"
    expected = hashlib.sha256(b"\x00" + payload).digest()
    assert leaf_hash(payload) == expected
    assert root_of([leaf_hash(payload)]) == expected


def test_known_vector_for_two_leaves():
    a, b = leaf_hash(b"a"), leaf_hash(b"b")
    assert root_of([a, b]) == hashlib.sha256(b"\x01" + a + b).digest()


def test_empty_tree_has_a_defined_root():
    assert root_of([]) == EMPTY_ROOT


def test_leaf_and_node_hashing_are_domain_separated():
    """Without separate prefixes an internal node could pose as a leaf."""
    data = b"x" * 64
    assert leaf_hash(data) != node_hash(data[:32], data[32:])


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 7, 8, 13, 64, 101])
def test_every_leaf_proves_against_the_root(count):
    ls = leaves(count)
    root = root_of(ls)
    for i, leaf in enumerate(ls):
        assert verify(leaf, proof_for(ls, i), root), f"leaf {i} of {count}"


def test_a_leaf_outside_the_tree_does_not_verify():
    ls = leaves(8)
    root = root_of(ls)
    outsider = leaf_hash(b"never added")
    assert not verify(outsider, proof_for(ls, 3), root)


def test_reordering_the_leaves_changes_the_root():
    ls = leaves(6)
    assert root_of(ls) != root_of(list(reversed(ls)))


def test_odd_level_promotes_rather_than_duplicates():
    """Duplicating the last node lets two lists share one root."""
    three = leaves(3)
    four = three + [three[-1]]
    assert root_of(three) != root_of(four)


def test_proof_is_rejected_when_a_sibling_is_altered():
    ls = leaves(9)
    root = root_of(ls)
    steps = proof_for(ls, 4)
    tampered = [
        type(steps[0])(bytes(32), steps[0].sibling_is_left)
    ] + steps[1:]
    assert not verify(ls[4], tampered, root)


def test_encoding_is_order_sensitive():
    assert encode_leaf(["R1", 13, "GS1083"]) != encode_leaf(["R1", "GS1083", 13])


def test_encoding_separator_cannot_be_forged_by_concatenation():
    """Two fields must not encode the same as one joined field."""
    assert encode_leaf(["ab", "c"]) != encode_leaf(["abc"])


def test_index_out_of_range_is_rejected():
    with pytest.raises(IndexError):
        proof_for(leaves(4), 9)
