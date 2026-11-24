from hashlib import sha1
from base64 import b64encode
from pathlib import Path
import json
import pytest

from imperium_iil.github_snapshot import resolve

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("failure", ["", "moved", "truncated", "wrong_id", "corrupt", "symlink"])
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
    replies = {"":dict(id=1002 if failure=="wrong_id" else 1001, full_name="org/repo"),
               "/git/ref/heads/main":{"object":{"type":"commit","sha":"d"*40 if failure=="moved" else rev}},
               "/git/commits/"+rev:{"sha":rev,"tree":{"sha":tree}},
               "/git/trees/"+tree+"?recursive=1":{"sha":tree,"truncated":failure=="truncated",
                   "tree":[dict(entry,path=p) for p in ("docs/guide.md","src/auth.py")]},
               "/git/blobs/"+oid:dict(size=len(raw),encoding="base64",sha=oid,
                                       content=b64encode(b"changed" if failure=="corrupt" else raw).decode())}
    def get(path):
        return replies[path.removeprefix("/repos/org/repo")]
    args = json.dumps(policy).encode(),"org/repo","docs/guide.md"
    if failure:
        with pytest.raises(ValueError):
            resolve(*args, get=get)
    else:
        bundle = resolve(*args, get=get)
        assert bundle["baseline"]["entries"][0]["text"] == raw.decode()
        assert bundle["context"]["snapshots"][0]["files"]["docs/guide.md"] == "regular"
