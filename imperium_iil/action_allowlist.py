"""Data-only, component-aware selectors for email addresses and repository paths."""

import re

from .reviewer_trust import require
from .structure import valid_path


_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_DOMAIN = re.compile(rf"{_LABEL}(?:\.{_LABEL})+", re.ASCII)
_LOCAL = re.compile(r"[A-Za-z0-9_+%-]+(?:\.[A-Za-z0-9_+%-]+)*", re.ASCII)


def mailbox(value, *, selector=False):
    require(isinstance(value, str) and len(value) <= 254)
    local, separator, domain = value.partition("@")
    require(separator and _DOMAIN.fullmatch(domain) and len(local) <= 64)
    require(_LOCAL.fullmatch(local) or (selector and local == "*"))
    return local, domain.lower()


def email_allowlist(entries):
    require(isinstance(entries, list) and 1 <= len(entries) <= 64)
    allowed = {mailbox(entry, selector=True) for entry in entries}

    def accepts(value):
        local, domain = mailbox(value)
        return (local, domain) in allowed or ("*", domain) in allowed

    return accepts


def path_glob(selector):
    # Validate literal components with the repository path grammar, including
    # its device-name and dot-segment checks. Validate each actual path again.
    require(isinstance(selector, str) and valid_path(selector.replace("*", "x")))
    parts = selector.split("/")
    require(selector != "*" and parts.count("**") <= 1)
    recursive = "**" in parts
    split = parts.index("**") if recursive else len(parts)
    if recursive:
        require(split > 0 and "*" not in parts[0])

    def compile_segment(part):
        require(part.count("*") <= 1)
        expression = "[^/]*".join(re.escape(literal) for literal in part.split("*"))
        return re.compile(expression, re.ASCII)

    head = [compile_segment(part) for part in parts[:split]]
    tail = [compile_segment(part) for part in parts[split + 1:]]

    def accepts(segments):
        fixed = len(head) + len(tail)
        if recursive:
            if len(segments) < fixed or (not tail and len(segments) == fixed):
                return False
        elif len(segments) != fixed:
            return False
        return (all(spec.fullmatch(item) for spec, item in zip(head, segments)) and
                all(spec.fullmatch(item) for spec, item in zip(reversed(tail), reversed(segments))))

    return accepts


def path_allowlist(entries):
    require(isinstance(entries, list) and 1 <= len(entries) <= 64)
    globs = [path_glob(entry) for entry in entries]

    def accepts(value):
        if not valid_path(value):
            return False
        segments = value.split("/")
        return any(glob(segments) for glob in globs)

    return accepts
