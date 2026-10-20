"""Merkle tree over the findings of one audit run.

The published root is what lets anyone check the result without trusting
whoever produced it: download the same source files, run the same code,
rebuild the tree, compare the root with the one recorded on chain. For
that to mean anything the construction has to be unambiguous, so three
choices are made deliberately.

Domain separation. A leaf is SHA-256 of 0x00 || payload and an internal
node is SHA-256 of 0x01 || left || right. Without the distinct prefixes
an attacker can present an internal node as though it were a leaf and
produce a valid-looking proof for data that was never in the tree.

Odd levels promote the last node rather than duplicating it. Duplicating
lets two different finding lists produce the same root, which would make
the root useless as a commitment to a specific result.

Canonical encoding. Fields go in a fixed order, separated by a unit
separator byte that cannot occur in the data, and every amount is an
integer in thousandths. Reordering or reformatting changes the root,
which is the point: the root commits to exactly one rendering of exactly
one result.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"
FIELD_SEPARATOR = b"\x1f"

EMPTY_ROOT = bytes(32)


def _sha256(*parts: bytes) -> bytes:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part)
    return digest.digest()


def encode_leaf(fields: list[str | int]) -> bytes:
    """Canonical byte encoding of one finding."""
    out = []
    for field in fields:
        if isinstance(field, bool):
            raise TypeError("encode booleans as integers explicitly")
        if isinstance(field, int):
            out.append(str(field).encode("utf-8"))
        elif field is None:
            out.append(b"")
        else:
            out.append(str(field).encode("utf-8"))
    return FIELD_SEPARATOR.join(out)


def leaf_hash(payload: bytes) -> bytes:
    return _sha256(LEAF_PREFIX, payload)


def node_hash(left: bytes, right: bytes) -> bytes:
    return _sha256(NODE_PREFIX, left, right)


@dataclass(frozen=True)
class ProofStep:
    sibling: bytes
    sibling_is_left: bool


def build_levels(leaves: list[bytes]) -> list[list[bytes]]:
    """Every level of the tree, leaves first, root last."""
    if not leaves:
        return [[EMPTY_ROOT]]
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        current = levels[-1]
        nxt: list[bytes] = []
        for i in range(0, len(current) - 1, 2):
            nxt.append(node_hash(current[i], current[i + 1]))
        if len(current) % 2 == 1:
            nxt.append(current[-1])  # promote, never duplicate
        levels.append(nxt)
    return levels


def root_of(leaves: list[bytes]) -> bytes:
    return build_levels(leaves)[-1][0]


def proof_for(leaves: list[bytes], index: int) -> list[ProofStep]:
    """Sibling path proving that leaves[index] is in the tree."""
    if not 0 <= index < len(leaves):
        raise IndexError(f"leaf {index} out of range for {len(leaves)} leaves")

    steps: list[ProofStep] = []
    position = index
    for level in build_levels(leaves)[:-1]:
        if position == len(level) - 1 and len(level) % 2 == 1:
            position //= 2  # promoted; no sibling at this level
            continue
        if position % 2 == 0:
            steps.append(ProofStep(level[position + 1], sibling_is_left=False))
        else:
            steps.append(ProofStep(level[position - 1], sibling_is_left=True))
        position //= 2
    return steps


def verify(leaf: bytes, steps: list[ProofStep], expected_root: bytes) -> bool:
    current = leaf
    for step in steps:
        current = (
            node_hash(step.sibling, current) if step.sibling_is_left
            else node_hash(current, step.sibling)
        )
    return current == expected_root
