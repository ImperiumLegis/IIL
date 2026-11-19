from types import SimpleNamespace

import pytest

from imperium_iil.policy import check_scope


READ = "github.file.read"
UPDATE = "github.file.update"
REV = "a" * 40


def rule(kind, value, capability=READ, repository="demo"):
    return {"repository_id": repository, "capabilities": [capability],
            "selector": {"kind": kind, "value": value}}


@pytest.fixture
def context():
    paths = ["README.md", "docs/guide.md", "docs-old/guide.md"]
    snapshot = {
        "revision": REV,
        "files": dict.fromkeys(paths, "regular"),
        "eligible": {READ: paths, UPDATE: ["README.md"]},
        "groups": {"auth": {"members": ["README.md"], "complete": True,
                            "review_ref": "e1"}},
    }
    return SimpleNamespace(
        snapshots={("demo", "main"): snapshot},
        capabilities={READ: True, UPDATE: True, "github.file.delete": True,
                      "github.pull_request.create": False},
        evidence={"e1": "reviewed", "e2": "claimed"}, denials=[],
    )


@pytest.fixture
def proposal():
    resource = {"type": "github.file", "repository_id": "demo", "branch": "main",
                "revision": REV, "path": "README.md"}
    return {"operations": [{"id": "one", "capability": READ, "resource": resource}],
            "restrictions": []}


def test_readme_in_excluded_group(proposal, context):
    proposal["restrictions"] = [rule("catalog_group", "auth")]
    assert any(f.code == "RESTRICTION_CONFLICT" for f in check_scope(proposal, context))


@pytest.mark.parametrize(("kind", "value", "path", "expected"), [
    ("directory", "docs", "docs/guide.md", True),
    ("directory", "docs", "docs-old/guide.md", False),
    ("directory", "README.md", "README.md", False),
    ("basename", "guide.md", "docs-old/guide.md", True),
    ("exact_path", "guide.md", "docs/guide.md", False),
    ("exact_path", "README.md", "README.md", True),
])
def test_selector_boundaries(proposal, context, kind, value, path, expected):
    proposal["operations"][0]["resource"]["path"] = path
    proposal["restrictions"] = [rule(kind, value)]
    assert [f.code for f in check_scope(proposal, context)] == (
        ["RESTRICTION_CONFLICT"] if expected else [])


def test_both_denials_survive(proposal, context):
    context.denials.append(rule("exact_path", "README.md"))
    proposal["restrictions"] = [rule("basename", "README.md")]
    assert {f.code for f in check_scope(proposal, context)} == {
        "POLICY_CONFLICT", "RESTRICTION_CONFLICT"}


@pytest.mark.parametrize("capability", [READ, UPDATE, "github.file.delete"])
def test_eligible_operations(proposal, context, capability):
    context.snapshots["demo", "main"]["eligible"][capability] = ["README.md"]
    proposal["operations"][0]["capability"] = capability
    assert check_scope(proposal, context) == []


@pytest.mark.parametrize("capability", ["future.operation", "github.pull_request.create"])
def test_uninterpreted_operation(proposal, context, capability):
    proposal["operations"][0].update(capability=capability, resource={})
    assert [f.status for f in check_scope(proposal, context)] == ["UNSUPPORTED"]


@pytest.mark.parametrize(("field", "value", "status"), [
    ("type", "future.file", "UNSUPPORTED"),
    ("branch", "MAIN", "NEEDS_CLARIFICATION"),
    ("repository_id", "Demo", "NEEDS_CLARIFICATION"),
    ("revision", "b" * 40, "INVALID"),
    ("path", "Readme.md", "NEEDS_CLARIFICATION"),
])
def test_unresolved_identity_blocks_lexical_matching(proposal, context, field, value, status):
    resource = proposal["operations"][0]["resource"]
    resource[field] = value
    proposal["restrictions"] = [rule("exact_path", resource["path"])]
    assert [f.status for f in check_scope(proposal, context)] == [status]


@pytest.mark.parametrize("kind", ["symlink", "submodule", "alias"])
def test_special_files(proposal, context, kind):
    context.snapshots["demo", "main"]["files"]["README.md"] = kind
    assert [f.status for f in check_scope(proposal, context)] == ["UNSUPPORTED"]


def test_envelope_is_required(proposal, context):
    proposal["operations"][0]["capability"] = UPDATE
    proposal["operations"][0]["resource"]["path"] = "docs/guide.md"
    assert [f.code for f in check_scope(proposal, context)] == ["POLICY_CONFLICT"]


@pytest.mark.parametrize(("complete", "ref"), [(False, "e1"), (True, "e2")])
def test_group_requires_review_and_completeness(proposal, context, complete, ref):
    group = context.snapshots["demo", "main"]["groups"]["auth"]
    group.update(complete=complete, review_ref=ref, members=[])
    assert check_scope(proposal, context) == []
    context.denials = [rule("catalog_group", "auth", UPDATE)]
    assert check_scope(proposal, context) == []
    proposal["restrictions"] = [rule("catalog_group", "auth")]
    assert [f.status for f in check_scope(proposal, context)] == ["NEEDS_CLARIFICATION"]


def test_empty_and_overlapping_groups(proposal, context):
    groups = context.snapshots["demo", "main"]["groups"]
    groups["credentials"] = {**groups["auth"], "members": []}
    context.denials = [rule("catalog_group", "credentials")]
    assert check_scope(proposal, context) == []
    groups["credentials"]["members"] = ["README.md"]
    proposal["restrictions"] = [rule("catalog_group", "auth")]
    assert {f.code for f in check_scope(proposal, context)} == {
        "POLICY_CONFLICT", "RESTRICTION_CONFLICT"}


@pytest.mark.parametrize(("restriction", "status"), [
    (rule("catalog_group", "auth"), "NEEDS_CLARIFICATION"),
    (rule("new_kind", "opaque"), "UNSUPPORTED"),
    (rule("basename", "README.md", "future.operation"), "UNSUPPORTED"),
    (rule("basename", "README.md", repository="missing"), "NEEDS_CLARIFICATION"),
])
def test_validate_restrictions_without_operations(proposal, context, restriction, status):
    proposal["operations"] = []
    proposal["restrictions"] = [restriction]
    assert [f.status for f in check_scope(proposal, context)] == [status]


def test_missing_proposal_group(proposal, context):
    proposal["restrictions"] = [rule("catalog_group", "unknown")]
    assert [f.status for f in check_scope(proposal, context)] == ["NEEDS_CLARIFICATION"]
