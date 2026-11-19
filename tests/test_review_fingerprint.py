import pytest

from imperium_iil.review import review_fingerprint


@pytest.mark.parametrize(("proposal", "context", "baseline", "expected"), [
    (b"", b"", b"", "b6036082e333694174311dfa5116c6e59bcf6df6c9516c9e60ca6f9b7d85faa7"),
    (b"ab", b"c", b"", "0b6299b335eff13eda7fe34277349b566a7bb03bb68139bbe8316fc3ec5a3a83"),
    (b"a", b"bc", b"", "89820f2aa96deacdcbaef8f3ca52afb21968cbf934a671058bfee3586894a4ca"),
])
def test_framed_sha256(proposal, context, baseline, expected):
    assert review_fingerprint(proposal, context, baseline) == expected
