import pytest

from imperium_iil.action_policy import evaluate
from test_action_v2 import encode, install_v2


def review(tmp_path, rule, values):
    def text_field(manifest, record):
        record["target"] = {"type": "string", "min": "0", "max": "512"}

    catalog, policy, proposal = install_v2(tmp_path, text_field)
    policy["permissions"]["assign"]["constraints"]["/tickets/*/target"] = rule
    template = proposal["arguments"]["tickets"][0]
    proposal["arguments"]["tickets"] = [{**template, "target": value} for value in values]
    return evaluate(encode(policy), encode(proposal), catalog, "demo", "agent", "demo-reviewer")


EMAIL = {"email_allowlist": ["*@example.test", "Owner@vendor.test"]}
PATH = {"path_allowlist": ["docs/**/*.md", "src/*/index.py", "LICENSE"]}


def test_email_allowlist_matches_addresses_and_exact_domains(tmp_path):
    values = ["first.last+case@EXAMPLE.test", "Owner@VENDOR.test"]
    result = review(tmp_path, EMAIL, values)
    assert [ticket["target"] for ticket in result[2]["tickets"]] == values


@pytest.mark.parametrize("value", ["outside@sub.example.test", "outside@example.test.other",
                                   "other@vendor.test", "owner@vendor.test", "a..b@example.test",
                                   "Alice <a@example.test>", "alice@evil.test,bob@example.test",
                                   "a@b@example.test", "ümlaut@example.test", "a@example.test\n"])
def test_email_allowlist_rejects_entire_batch_on_invalid_member(tmp_path, value):
    with pytest.raises(ValueError):
        review(tmp_path, EMAIL, ["ok@example.test", value])


def test_path_allowlist_matches_one_segment_or_recursive_descendants(tmp_path):
    values = ["docs/start.md", "docs/en/guide/index.md", "src/editor/index.py", "LICENSE"]
    result = review(tmp_path, PATH, values)
    assert [ticket["target"] for ticket in result[2]["tickets"]] == values


@pytest.mark.parametrize("value", ["docs/../README.md", "/docs/start.md", "docs/./start.md",
                                   "docs//start.md", "docs/%2e%2e/start.md", "docs\\a.md",
                                   "docs/NUL.md", "docsetc/start.md", "Docs/start.md",
                                   "src/a/b/index.py", "docs/start.txt", "LICENSE/child"])
def test_path_globs_keep_repository_containment(tmp_path, value):
    with pytest.raises(ValueError):
        review(tmp_path, PATH, ["docs/start.md", value])


@pytest.mark.parametrize("rule", [
    {"email_allowlist": ["*@*.example.test"]}, {"email_allowlist": ["*@bad-.test"]},
    {"email_allowlist": []}, {"email_allowlist": ["*@example.test"], "pattern": "*"},
    {"path_allowlist": ["**"]}, {"path_allowlist": ["**/*.md"]}, {"path_allowlist": ["docs/../*"]},
    {"path_allowlist": ["docs/**/**/x"]}, {"path_allowlist": ["docs/**.md"]},
])
def test_invalid_allowlist_rule_rejects_before_evaluation(tmp_path, rule):
    with pytest.raises(ValueError):
        review(tmp_path, rule, ["docs/readme.md"])


def test_recursive_directory_rule_excludes_the_directory_itself(tmp_path):
    rule = {"path_allowlist": ["docs/**"]}
    assert review(tmp_path, rule, ["docs/en/readme"])
    with pytest.raises(ValueError):
        review(tmp_path, rule, ["docs"])
