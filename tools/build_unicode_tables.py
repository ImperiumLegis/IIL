"""Derive the exact-review tables from a local Unicode 17.0.0 release directory."""

from argparse import ArgumentParser
from itertools import groupby
from pathlib import Path


def rows(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        data = line.partition("#")[0].strip()
        if data:
            yield [field.strip() for field in data.split(";")]


def build(source, destination):
    blocked = {0x2800}  # BRAILLE PATTERN BLANK has an empty glyph.
    for name, properties in [
        ("ucd/DerivedCoreProperties.txt", {"Default_Ignorable_Code_Point"}),
        ("ucd/extracted/DerivedGeneralCategory.txt", {"Cf", "Zs", "Zl", "Zp"}),
    ]:
        for interval, prop, *_ in rows(source / name):
            if prop in properties:
                bounds = interval.split("..")
                blocked.update(range(int(bounds[0], 16), int(bounds[-1], 16) + 1))
    blocked.remove(0x20)
    ranges = []
    for _, group in groupby(enumerate(sorted(blocked)), lambda item: item[1] - item[0]):
        points = [value for _, value in group]
        ranges.append(f"{points[0]:04X} {points[-1]:04X}")
    sequences = set()
    for name in ("emoji/emoji-sequences.txt", "emoji/emoji-zwj-sequences.txt"):
        for codes, _, *_ in rows(source / name):
            if {"200D", "FE0F"}.intersection(codes.split()):
                sequences.add(codes)
    destination.mkdir(parents=True, exist_ok=True)
    for name, values in (("invisible-17.0.txt", ranges), ("emoji-17.0.txt", sorted(sequences))):
        (destination / name).write_text("\n".join(values) + "\n", encoding="ascii", newline="\n")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("unicode_release", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    build(args.unicode_release, args.destination)
