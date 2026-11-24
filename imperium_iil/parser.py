"""Decode proposal JSON."""

import json
from decimal import Decimal
from typing import Never


class ParseError(ValueError):
    """Input violates an IIL parsing rule."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    fields = {}
    for name, value in pairs:
        if name in fields:
            raise ParseError("DUPLICATE_KEY")
        fields[name] = value
    return fields


def _reject_number(_token: str) -> Never:
    raise ParseError("NUMBER_NOT_ALLOWED")


def _action_number(token: str) -> int | float:
    # JSON's scanner has already checked the grammar. Bound work before conversion.
    if len(token) > 32 or len(token.lower().partition("e")[2].lstrip("+-")) > 2:
        raise ParseError("NUMBER_LIMIT")
    value = Decimal(token)
    if (value.is_zero() and value.is_signed() or abs(value) > 2**53 - 1
            or value.as_tuple().exponent < -6):
        raise ParseError("NUMBER_LIMIT")
    if "." not in token and "e" not in token.lower():
        return int(token)
    decoded = float(value)
    # Refuse any precision loss that would merge distinct inputs in the review display.
    if Decimal(str(decoded)) != value:
        raise ParseError("NUMBER_PRECISION")
    return decoded


def _check_unicode(document: dict) -> None:
    pending = [document]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                raise ParseError("INVALID_UNICODE") from None


def _check_depth(text: str) -> None:
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            if depth > 16:
                raise ParseError("DEPTH_LIMIT")
        elif char in "]}":
            depth -= 1
            if depth < 0:
                raise ParseError("INVALID_JSON")


def parse_bytes(raw: bytes, *, limit: int, numbers: bool = False) -> dict:
    if len(raw) > limit:
        raise ParseError("INPUT_TOO_LARGE")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ParseError("INVALID_ENCODING") from None
    if text.startswith("\ufeff"):
        raise ParseError("INVALID_ENCODING")
    _check_depth(text)
    try:
        document = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_int=_action_number if numbers else _reject_number,
            parse_float=_action_number if numbers else _reject_number,
            parse_constant=_reject_number,
        )
    except json.JSONDecodeError:
        raise ParseError("INVALID_JSON") from None
    if not isinstance(document, dict):
        raise ParseError("EXPECTED_OBJECT")
    _check_unicode(document)
    return document
