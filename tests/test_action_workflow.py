import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from test_action_manifest import install
from test_reviewer_trust import trust_for

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("case", ["email", "bcc", "cc", "outsider", "crm", "mailbox", "option"])
def test_external_operator_workflow(tmp_path, case):
    if case == "crm":
        registry, pin = install(tmp_path)
        rule = {**pin, "requesters":["agent"], "reviewers":["alice"], "constraints":{"lists":"markets"}}
        data = {"name":"Acme lead","lists":["north"]}
        files = {"policy":{"organization":"demo","groups":{"markets":["north"]},"permissions":{"add-lead":rule}},
                 "proposal":{"action":pin["action"],"version":"1","permission":"add-lead","arguments":data},
                 "call":{"tool":"create_lead","arguments":data}}
        for name, value in files.items():
            (tmp_path / (name + ".json")).write_text(json.dumps(value))
    else:
        shutil.copytree(ROOT / "examples/actions/email", tmp_path, dirs_exist_ok=True)
        policy = tmp_path / "policy.json"
        policy.write_text(policy.read_text().replace("demo-reviewer","alice"))
        path = tmp_path / ("proposal.json" if case == "outsider" else "call.json")
        doc = json.loads(path.read_bytes())
        if case in ("bcc","cc"):
            doc["arguments"][case] = ["bob@example.test"]
        elif case == "outsider":
            doc["arguments"]["to"] = ["unapproved@example.test"]
        elif case == "mailbox":
            doc["arguments"]["mailbox"] = "sales"
        elif case == "option":
            doc["arguments"]["notify"] = "yes"
        path.write_text(json.dumps(doc))
    key = Ed25519PrivateKey.generate()
    trust = trust_for(key)
    trust["reviewers"][0]["grants"] = []
    (tmp_path / "trust.json").write_text(json.dumps(trust))
    (tmp_path / "key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(b"disposable")))
    # Substitute the operator's terminal only. The real command and its spawned
    # requester load the source distribution from the external working directory.
    runner = tmp_path / "terminal.py"
    runner.write_text("""if __name__ == '__main__':
    import sys, io, getpass, runpy
    class Terminal(io.StringIO):
        def isatty(self): return True
    sys.stdin = Terminal('APPROVE\\n')
    sys.stderr.isatty = lambda: True
    getpass.getpass = lambda *args: 'disposable'
    runpy.run_module('imperium_iil.actions',run_name='__main__')
""")
    args = ["--requester","agent","--reviewer","alice","--root",".","--key","key.pem","--out","signed.json"]
    for name in ("trust","proposal","call","policy","registry"):
        args.extend(["--"+name,name+".json"])
    run = subprocess.run([sys.executable,str(runner),*args],cwd=tmp_path,
                         env={**os.environ,"PYTHONPATH":str(ROOT)},capture_output=True,text=True,timeout=30)
    success = case in ("email","crm")
    assert run.returncode == (0 if success else 1), run.stderr
    assert json.loads(run.stdout) == {"status":"SESSION_CALL_MATCHED" if success else "SESSION_CALL_REJECTED",
                                      "authority_granted":False}
    if case == "outsider":
        assert "unapproved" not in run.stderr and not (tmp_path / "signed.json").exists()
