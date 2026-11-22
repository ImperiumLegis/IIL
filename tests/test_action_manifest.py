import hashlib
import json

import pytest

from imperium_iil.action_manifest import load_catalog, arguments


def install(root):
    text = {"type": "string", "min": "0", "max": "16384"}
    manifest = {"action": "acme.collect", "version": "1", "tool": "create_lead",
                "fields": {"name": text, "lists": {**text, "type": "list", "least": "0", "most": "64"}}}
    raw = json.dumps(manifest).encode()
    pin = {"action": manifest["action"], "version": "1", "sha256": hashlib.sha256(raw).hexdigest()}
    (root / "manifest.json").write_bytes(raw)
    registry = {"version": "1", "entries": [{**pin, "file": "manifest.json"}]}
    path = root / "registry.json"
    path.write_text(json.dumps(registry))
    return path, pin


def test_catalog_and_bounds(tmp_path):
    path, _ = install(tmp_path)
    action = load_catalog(path, tmp_path)["acme.collect", "1"]
    assert arguments(action, {"name": "x"*16384, "lists": [""]*64})["lists"] == [""]*64
    for args in ({"name":"x"*16385,"lists":[]}, {"name":"","lists":[""]*65},
                 {"name":"x","lists":"y"}, {"name":"x"}, {"name":"x","lists":[],"extra":""}):
        with pytest.raises(ValueError):
            arguments(action, args)


@pytest.mark.parametrize("change", ["pin", "duplicate", "case", "traverse", "device", "url", "extra"])
def test_reject_bad_registry(tmp_path, change):
    path, _ = install(tmp_path)
    doc = json.loads(path.read_bytes())
    entry = doc["entries"][0]
    if change == "pin":
        entry["sha256"] = "0"*64
    elif change == "duplicate":
        doc["entries"].append(entry)
    elif change == "case":
        doc["entries"].append({**entry, "file": "MANIFEST.json"})
    elif change == "extra":
        entry["loader"] = "custom"
    else:
        entry["file"] = {"device":"NUL.json","url":"https://example.org/x","traverse":"../x.json"}[change]
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        load_catalog(path, tmp_path)
