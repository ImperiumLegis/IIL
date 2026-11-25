"""Unicode 17.0 visibility checks for version 0.3 file contents."""

from functools import cache
from importlib.resources import files
import re


@cache
def _tables():
    directory = files("imperium_iil").joinpath("data")
    ranges = []
    for line in directory.joinpath("invisible-17.0.txt").read_text("ascii").splitlines():
        start, end = (chr(int(value, 16)) for value in line.split())
        ranges.append(re.escape(start) + "-" + re.escape(end))
    invisible = re.compile("[" + "".join(ranges) + "]")
    trie = {}
    for line in directory.joinpath("emoji-17.0.txt").read_text("ascii").splitlines():
        node = trie
        for code in line.split():
            node = node.setdefault(chr(int(code, 16)), {})
        node[None] = True  # A complete RGI emoji can also prefix a longer one.
    return invisible, trie


def visible_text(text):
    if text.isascii():
        return True  # The calling profile checks C0/C1 and line endings separately.
    invisible, trie = _tables()
    if not invisible.search(text):
        return True
    start = 0
    while start < len(text):
        node = trie
        end = start
        complete = start
        while end < len(text) and text[end] in node:
            node = node[text[end]]
            end += 1
            if None in node:
                complete = end
        if complete > start:
            start = complete
        elif invisible.fullmatch(text[start]):
            return False
        else:
            start += 1
    return True
