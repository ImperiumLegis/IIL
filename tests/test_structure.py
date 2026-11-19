import pytest

from imperium_iil.structure import check_shape, valid_path


@pytest.fixture
def proposal():
    ref = {"id": "demo", "version": "1"}
    resource = {"type": "github.file", "repository_id": "repo-demo", "branch": "main",
                "revision": "a" * 40, "path": "README.md"}
    return {"iil_version": "0.1", "draft_id": "draft", "task": {"description": "Read."},
            "context": {k: ref.copy() for k in ("policy", "registry", "catalog")},
            "operations": [{"id": "one", "capability": "github.file.read", "resource": resource}],
            "restrictions": [], "unresolved": [], "evidence_refs": []}


def test_approval_field(proposal):
    assert any(f.pointer == "/approved" for f in check_shape(dict(proposal, approved=True)))


def test_valid_proposal(proposal):
    assert check_shape(proposal) == []


def test_unknown_version_dispatch():
    assert [f.status for f in check_shape({"iil_version": "0.2"})] == ["UNSUPPORTED"]


@pytest.mark.parametrize("version", [None, "", "future version", "0.1\n"])
def test_malformed_version(version):
    assert check_shape({"iil_version": version})[0].status == "INVALID"


@pytest.mark.parametrize("path", ["a//b", "dir/CON.txt", "aux", "docs/..", "x.", "hello\n",
                                  "a" * 101, "x%41", "/a", "a/", "é", "a\\b"])
def test_invalid_paths(path):
    assert not valid_path(path)


def test_path_limits():
    maximum = "/".join(["a" * 100] * 5 + ["b" * 7])
    assert valid_path(maximum)
    assert not valid_path(maximum + "c")


def test_unknown_capability_independent_error(proposal):
    proposal["task"]["secret-key"] = "sensitive input"
    proposal["operations"][0].update(capability="unknown.cap", resource={"opaque": "value"})
    findings = check_shape(proposal)
    assert {f.status for f in findings} == {"INVALID", "UNSUPPORTED"}
    assert "secret-key" not in repr(findings)
    assert "sensitive input" not in repr(findings)


def test_duplicate_request(proposal):
    op = proposal["operations"][0]
    proposal["operations"].append(dict(op, id="two"))
    assert any(f.status == "INVALID" for f in check_shape(proposal))
    proposal["operations"][1]["capability"] = "github.file.delete"
    assert check_shape(proposal) == []


@pytest.mark.parametrize("kind,value,status", [("basename", "docs/a", "INVALID"),
                                              ("exact_path", "a.", "INVALID"),
                                              ("catalog_group", "-group", "INVALID"),
                                              ("new_kind", "ok", "UNSUPPORTED")])
def test_selector_dispatch(proposal, kind, value, status):
    proposal["restrictions"] = [{"repository_id": "demo", "capabilities": ["github.file.read"],
                                 "selector": {"kind": kind, "value": value}}]
    assert {f.status for f in check_shape(proposal)} == {status}


def test_unknown_capability_requires_valid_wrapper(proposal):
    operation = proposal["operations"][0]
    del operation["id"]
    operation["capability"] = "future.capability"
    assert {f.status for f in check_shape(proposal)} == {"INVALID"}


def test_unknown_resource_kind(proposal):
    proposal["operations"][0]["resource"] = {"type": "future.resource", "opaque": True}
    assert {f.status for f in check_shape(proposal)} == {"UNSUPPORTED"}


def test_duplicate_question_id(proposal):
    item = {"id": "q", "code": "ambiguous_intent", "question": "Which branch?"}
    proposal["unresolved"] = [item, item.copy()]
    assert any(f.pointer == "/unresolved/1/id" for f in check_shape(proposal))


def test_prose_bounds(proposal):
    proposal["task"]["description"] = "é" * 2048
    assert check_shape(proposal) == []
    proposal["task"]["description"] += "é"
    assert {f.status for f in check_shape(proposal)} == {"INVALID"}
    proposal["task"]["description"] = "hi\u0081"
    assert {f.status for f in check_shape(proposal)} == {"INVALID"}


def test_id_bounds(proposal):
    proposal["draft_id"] = "a" * 64
    assert check_shape(proposal) == []
    proposal["draft_id"] += "a"
    assert {f.status for f in check_shape(proposal)} == {"INVALID"}


def test_array_bounds(proposal):
    proposal["evidence_refs"] = [f"ref{i}" for i in range(64)]
    assert check_shape(proposal) == []
    proposal["evidence_refs"].append("last")
    assert {f.status for f in check_shape(proposal)} == {"INVALID"}


def test_capability_bounds(proposal):
    op = proposal["operations"][0]
    op["capability"] = "x." + "y" * 126
    assert {f.status for f in check_shape(proposal)} == {"UNSUPPORTED"}
    op["capability"] += "y"
    assert {f.status for f in check_shape(proposal)} == {"INVALID"}
