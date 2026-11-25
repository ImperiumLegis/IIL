"""Resolve a reviewed GitHub revision to offline context and before-text."""

import argparse
from base64 import b64decode
from hashlib import sha1
from http.client import HTTPSConnection
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote

from .baseline import load_baseline
from .context import load_context
from .parser import parse_bytes
from .policy import check_scope
from .reviewer_trust import require
from .structure import valid_path

MAX_RESPONSE = 4 * 1024 * 1024


def get_json(path, *, token=None):
    headers = {"User-Agent": "imperium-iil-snapshot", "Accept": "application/vnd.github+json"}
    if token is not None:
        require(isinstance(token, str) and re.fullmatch(r"[!-~]{1,4096}", token))
        headers["Authorization"] = "Bearer " + token
    conn = HTTPSConnection("api.github.com", timeout=10)
    try:
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        require(response.status == 200)
        raw = response.read(MAX_RESPONSE + 1)
        require(len(raw) <= MAX_RESPONSE)
        return json.loads(raw)
    finally:
        conn.close()


def resolve(raw, repository, path, *, baseline_format="1", get=get_json):
    require(re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repository)
            and repository.split("/")[1] not in (".", "..") and valid_path(path))
    context = parse_bytes(raw, limit=1048576)
    snapshot, = context["snapshots"]
    repo, branch, revision = (snapshot[k] for k in ("repository_id", "branch", "revision"))
    require(re.fullmatch("[a-f0-9]{40}", revision) and valid_path(branch))
    api = "/repos/" + repository
    identity = get(api)
    require(identity["full_name"].lower() == repository.lower() and
            context["repositories"][repo] == {"host":"github.com", "provider_id":str(identity["id"])})
    ref = get(api + "/git/ref/heads/" + quote(branch, safe="/"))["object"]
    require(ref["type"] == "commit" and ref["sha"] == revision)
    commit = get(api + "/git/commits/" + revision)
    tree = commit["tree"]["sha"]
    require(commit["sha"] == revision and re.fullmatch("[a-f0-9]{40}", tree))
    listing = get(api + "/git/trees/" + tree + "?recursive=1")
    require(listing["truncated"] is False and listing["sha"] == tree)
    kinds = {("blob","100644"):"regular", ("blob","100755"):"regular",
             ("blob","120000"):"symlink", ("commit","160000"):"submodule"}
    files = {}
    seen = set()
    blob = None
    for entry in listing["tree"]:
        name = entry["path"]
        require(isinstance(name, str) and "\x00" not in name and name not in seen
                and all(component not in ("", ".", "..") for component in name.split("/")))
        seen.add(name)
        kind = entry["type"], entry["mode"]
        if kind == ("tree", "040000"):
            continue
        require(kind in kinds)
        # Preserve exact Git paths. Other names have no representation in IIL.
        if not valid_path(name):
            continue
        files[name] = kinds[kind]
        if name == path:
            blob = entry["sha"]
    snapshot["files"] = files
    trusted = load_context(json.dumps(context).encode())
    target = dict(type="github.file",repository_id=repo,branch=branch,revision=revision,path=path)
    read = {"operations":[{"capability":"github.file.read", "resource":target}], "restrictions":[]}
    require(not check_scope(read, trusted) and blob and re.fullmatch("[a-f0-9]{40}", blob))
    obj = get(api + "/git/blobs/" + blob)
    require(obj["sha"] == blob and obj["encoding"] == "base64" and 0 <= obj["size"] <= 262144)
    data = b64decode(obj["content"].replace("\n",""), validate=True)
    require(len(data) == obj["size"] and sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == blob)
    del target["type"]
    baseline = {"format_version":baseline_format, "catalog_ref":context["refs"]["catalog"],
                "entries":[{**target,"text":data.decode("utf-8")}]}
    load_baseline(json.dumps(baseline).encode(), trusted, allow_utf8=baseline_format == "2")
    return {"context":context, "baseline":baseline}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--baseline-format", choices=["1","2"], default="1")
    parser.add_argument("--authenticated", action="store_true",
                        help="use the operator-supplied IIL_GITHUB_TOKEN for read requests")
    args = parser.parse_args(argv)
    try:
        token = os.environ["IIL_GITHUB_TOKEN"] if args.authenticated else None
        with args.context.open("rb") as stream:
            bundle = resolve(stream.read(1048577), args.repository, args.path, baseline_format=args.baseline_format,
                             get=lambda path: get_json(path, token=token))
    except Exception:
        print("Snapshot unavailable. Check the operator policy, pinned revision and provider response.", file=sys.stderr)
        return 1
    print(json.dumps(bundle, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
