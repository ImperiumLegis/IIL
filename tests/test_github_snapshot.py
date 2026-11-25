from hashlib import sha1
from base64 import b64encode
from pathlib import Path
import json
import pytest

from imperium_iil import github_snapshot
from imperium_iil.github_snapshot import resolve

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("failure", ["", "moved", "truncated", "wrong_id", "corrupt", "symlink",
                                     "wrong_name", "ref_type", "commit_sha", "tree_sha", "blob_sha",
                                     "tamper", "unsupported_eligible", "unsupported_target",
                                     "malformed_path", "duplicate_path"])
def test_live_snapshot(failure):
    policy = json.loads((ROOT/"fixtures/exact-update-context.json").read_bytes())
    policy["repositories"]["repo-demo"]["host"] = "github.com"
    snap = policy["snapshots"][0]
    snap["files"] = {}
    snap["eligible"] = {k:["docs/guide.md"] for k in ("github.file.update", "github.file.read")}
    rev = snap["revision"]
    raw = b"Independent baseline\n"
    oid = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    tree = "b"*40
    entry = dict(mode="120000" if failure == "symlink" else "100644", type="blob", sha=oid)
    other_sha = "d" * 40
    data = b"changed" if failure == "corrupt" else raw
    if failure == "tamper":
        data = raw.replace(b"Independent", b"iNdependent")
    unrelated = "../design/Release notes.txt" if failure == "malformed_path" else "design/Release notes.txt"
    if failure == "unsupported_eligible":
        snap["eligible"]["github.file.read"].append(unrelated)
    replies = {"":dict(id=1002 if failure=="wrong_id" else 1001,
                       full_name="other/repo" if failure=="wrong_name" else "org/repo"),
               "/git/ref/heads/main":{"object":{"type":"tag" if failure=="ref_type" else "commit",
                                                "sha":other_sha if failure=="moved" else rev}},
               "/git/commits/"+rev:{"sha":other_sha if failure=="commit_sha" else rev,"tree":{"sha":tree}},
               "/git/trees/"+tree+"?recursive=1":{"sha":other_sha if failure=="tree_sha" else tree,
                   "truncated":failure=="truncated",
                   "tree":[dict(entry,path=p) for p in ("docs/guide.md","src/auth.py",unrelated)]},
               "/git/blobs/"+oid:dict(size=len(raw),encoding="base64",sha=other_sha if failure=="blob_sha" else oid,
                                       content=b64encode(data).decode())}
    def get(path):
        return replies[path.removeprefix("/repos/org/repo")]
    if failure == "duplicate_path":
        replies["/git/trees/" + tree + "?recursive=1"]["tree"].append(dict(entry, path=unrelated))
    args = json.dumps(policy).encode(),"org/repo",unrelated if failure=="unsupported_target" else "docs/guide.md"
    if failure:
        with pytest.raises(ValueError):
            resolve(*args, get=get)
    else:
        bundle = resolve(*args, get=get)
        assert bundle["baseline"]["entries"][0]["text"] == raw.decode()
        assert bundle["context"]["snapshots"][0]["files"]["docs/guide.md"] == "regular"
        assert unrelated not in bundle["context"]["snapshots"][0]["files"]


@pytest.mark.parametrize("opt_in, configured, sent", [
    (False, "disposable-fixture", False), (True, "disposable-fixture", True),
    (True, None, False), (True, "disposable-fixture\r\n", False),
])
def test_cli_token_requires_opt_in_and_stays_on_fixed_host(opt_in, configured, sent, monkeypatch, capsys):
    requests = []
    class RejectedConnection:
        def __init__(self, host, timeout):
            assert host == "api.github.com"
        def request(self, method, path, headers):
            requests.append((method, path, headers))
        def getresponse(self):
            return type("Forbidden", (), {"status": 403})()
        def close(self):
            pass

    monkeypatch.setattr(github_snapshot, "HTTPSConnection", RejectedConnection)
    if configured is None:
        monkeypatch.delenv("IIL_GITHUB_TOKEN", raising=False)
    else:
        monkeypatch.setenv("IIL_GITHUB_TOKEN", configured)
    args = ["--context", str(ROOT / "fixtures/exact-update-context.json"),
            "--repository", "org/repo", "--path", "docs/guide.md"]
    if opt_in:
        args.append("--authenticated")
    assert github_snapshot.main(args) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "disposable-fixture" not in captured.err
    if opt_in and not sent:
        assert requests == []
    else:
        (method, path, headers), = requests
        assert (method, path) == ("GET", "/repos/org/repo")
        assert headers.get("Authorization") == ("Bearer disposable-fixture" if sent else None)
