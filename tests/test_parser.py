import json

import pytest

from imperium_iil.parser import ParseError, parse_bytes


def test_duplicate_names():
    with pytest.raises(ParseError, match="^DUPLICATE_KEY$"):
        parse_bytes(b'{"path":"README.md","path":"src/auth.py"}', limit=65536)


def test_distinct_names():
    assert parse_bytes(b'{"path":"README.md","branch":"main"}', limit=65536) == {
        "path": "README.md",
        "branch": "main",
    }


def test_byte_limit():
    with pytest.raises(ParseError, match="^INPUT_TOO_LARGE$"):
        parse_bytes(b'{} ', limit=2)
    assert parse_bytes(b'{}', limit=2) == {}


@pytest.mark.parametrize("raw", [b'{"label":"\xff"}', b'\xef\xbb\xbf{}', '{}'.encode('utf-16')])
def test_rejects_invalid_encoding(raw):
    with pytest.raises(ParseError, match="^INVALID_ENCODING$"):
        parse_bytes(raw, limit=65536)


def test_utf8_text():
    raw = '{"label":"café"}'.encode("utf-8")
    assert parse_bytes(raw, limit=len(raw)) == {"label": "café"}


@pytest.mark.parametrize("raw", [b'{"path":"README.md"', b'{} {}'])
def test_requires_one_complete_json_document(raw):
    with pytest.raises(ParseError, match="^INVALID_JSON$"):
        parse_bytes(raw, limit=65536)


def test_requires_top_level_object():
    with pytest.raises(ParseError, match="^EXPECTED_OBJECT$"):
        parse_bytes(b'[{"action":"read"}]', limit=65536)


def test_accepts_list_inside_object():
    assert parse_bytes(b'{"operations":[]}', limit=65536) == {"operations": []}


@pytest.mark.parametrize("token", [b"1", b"-2", b"0.1", b"1e2", b"NaN", b"Infinity", b"-Infinity"])
def test_rejects_number_tokens(token):
    with pytest.raises(ParseError, match="^NUMBER_NOT_ALLOWED$"):
        parse_bytes(b'{"value":[' + token + b']}', limit=65536)


def test_quoted_version_stays_text():
    assert parse_bytes(b'{"version":"1"}', limit=65536) == {"version": "1"}


@pytest.mark.parametrize("raw", [br'{"label":["\ud83d"]}', br'{"\ude00":"value"}'])
def test_rejects_unpaired_surrogate(raw):
    with pytest.raises(ParseError, match="^INVALID_UNICODE$"):
        parse_bytes(raw, limit=65536)


def test_complete_pair_and_literal_escape():
    raw = br'{"emoji":"\ud83d\ude00","example":"\\ud83d"}'
    assert parse_bytes(raw, limit=65536) == {"emoji": "😀", "example": r"\ud83d"}


def test_accepts_depth_16_with_brackets_and_escapes_in_text():
    value = 'a quote " then [[[[ then a backslash \\'
    for _ in range(15):
        value = [value]
    document = {"value": value}
    assert parse_bytes(json.dumps(document).encode(), limit=65536) == document


@pytest.mark.parametrize("lists", [16, 2000])
def test_rejects_excessive_depth_before_decoding(lists):
    raw = b'{"value":' + b"[" * lists + b"]" * lists + b"}"
    with pytest.raises(ParseError, match="^DEPTH_LIMIT$"):
        parse_bytes(raw, limit=65536)
