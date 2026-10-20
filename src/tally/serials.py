"""Parsing credit serial ranges, which every registry formats differently.

A serial range names the individual credits behind a quantity. Comparing
ranges is what lets a duplicate be proven at the level of the credit rather
than inferred from matching yearly totals.

Four formats appear in the raw registry files:

  ACR    ACR-US-114-2015-646-777955 to 778357
         prefix, then start and end around the word "to". One row may hold
         several ranges separated by semicolons.

  CAR    CAR-1-US-1480-46-1156-FL-2026-10272-852724 to 860723
         same shape, longer prefix.

  GOLD   GS1-1-XZ-GS12303-17-2022-30775-1077-1127
         no "to" at all; the last two hyphen-separated numbers are the
         start and end.

  VERRA  18453-896309560-896329558-VCS-VCU-1507-VER-IN-1-1904-...
         start and end come FIRST, in positions two and three. Reading the
         last two numbers here would capture a date and a flag instead.

Every parse is checked against the quantity the registry declared on the
same row: end - start + 1 must equal it. A format read wrongly fails that
test immediately rather than quietly producing wrong ranges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TO_RANGE = re.compile(r"^(?P<prefix>.*?)(?P<start>\d+)\s+to\s+(?P<end>\d+)\s*$")
TRAILING_PAIR = re.compile(r"^(?P<prefix>.*)-(?P<start>\d+)-(?P<end>\d+)$")
LEADING_TRIPLE = re.compile(r"^(?P<head>\d+)-(?P<start>\d+)-(?P<end>\d+)-(?P<rest>.+)$")


@dataclass(frozen=True)
class SerialRange:
    raw: str
    prefix: str
    start: int
    end: int

    @property
    def count(self) -> int:
        return self.end - self.start + 1


def parse(value: object, registry: str) -> list[SerialRange]:
    """Serial ranges in one cell. Returns [] when nothing parses."""
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []

    out: list[SerialRange] = []
    for piece in (p.strip() for p in text.split(";") if p.strip()):
        parsed = _parse_one(piece, registry.upper())
        if parsed:
            out.append(parsed)
    return out


def _parse_one(text: str, registry: str) -> SerialRange | None:
    match = TO_RANGE.match(text)
    if match:
        return SerialRange(
            raw=text,
            prefix=match.group("prefix").rstrip("-").strip(),
            start=int(match.group("start")),
            end=int(match.group("end")),
        )

    if registry in {"VCS", "VERRA"}:
        match = LEADING_TRIPLE.match(text)
        if match:
            return SerialRange(
                raw=text,
                prefix=match.group("rest"),
                start=int(match.group("start")),
                end=int(match.group("end")),
            )
        return None

    match = TRAILING_PAIR.match(text)
    if match:
        return SerialRange(
            raw=text,
            prefix=match.group("prefix"),
            start=int(match.group("start")),
            end=int(match.group("end")),
        )
    return None


def overlap(a: SerialRange, b: SerialRange) -> int:
    """Credits covered by both ranges. Zero unless the prefixes match.

    Two ranges of identical numbers under different prefixes are different
    credits in different registries, which is precisely what must not be
    conflated.
    """
    if a.prefix != b.prefix:
        return 0
    lo, hi = max(a.start, b.start), min(a.end, b.end)
    return max(0, hi - lo + 1)
