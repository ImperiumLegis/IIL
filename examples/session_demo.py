"""Disposable offline session proof demonstration with an automated synthetic reviewer."""

from argparse import Namespace
from base64 import b64encode
from contextlib import contextmanager
import json
from multiprocessing import get_context
from pathlib import Path
from secrets import token_hex
import socket
from tempfile import TemporaryDirectory
from time import monotonic

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from imperium_iil.receipt import FIXTURES, now
from imperium_iil.receipts import make_claims, sign
from imperium_iil.requester_session import Session, load_sessions
from imperium_iil.review import review_update
from imperium_iil.reviewer_trust import load_trust
from imperium_iil.session_match import check_session
from imperium_iil.session_proof import Presentation, receive, respond

EXAMPLES = Path(__file__).resolve().parent


def _requester(channels, ready, folder, sid, impersonate):
    key = Ed25519PrivateKey.generate()
    channels[0].sendall(key.public_key().public_bytes_raw())
    try:
        if not ready.wait(20):
            return
        doc = (folder / "receipt.json").read_bytes()
        call = (EXAMPLES / "tool-calls/guide-a.json").read_bytes()
        binding = Session("demo", "demo-agent", sid, key.public_key().public_bytes_raw())
        if impersonate:
            sessions = load_sessions((folder / "sessions.json").read_bytes(), "demo")
            binding = sessions[json.loads(doc)["session"]]
        pending = Presentation.for_submission(binding, doc, call)
        saved = None
        for channel in channels:
            challenge = receive(channel, 64, monotonic() + 20)
            if impersonate:
                # Negative fixture: B claims A's public identity but only holds B's key.
                response = key.sign(pending.message(challenge[:32]))
            elif saved is None:
                response = respond(key, pending, challenge)
                saved = response
            else:
                response = saved  # Present the previously recorded response to a fresh challenge.
            channel.sendall(response)
        channels[-1].settimeout(20)
        channels[-1].recv(1)  # Remain active until the launcher retires this session.
    except (EOFError, OSError):
        pass
    finally:
        for channel in channels:
            channel.close()


def _save_sessions(path, entries):
    new = path.with_suffix(".new")
    new.write_text(json.dumps({"version": "1", "organization": "demo", "sessions": entries}))
    new.replace(path)


@contextmanager
def requester(paths, entries, count=1, impersonate=False):
    ctx = get_context("spawn")
    sid = token_hex(32)
    pairs = [socket.socketpair() for _ in range(count)]
    local, remote = zip(*pairs)
    ready = ctx.Event()
    process = ctx.Process(target=_requester, args=(remote, ready, paths.sessions.parent, sid, impersonate))
    process.start()
    for channel in remote:
        channel.close()
    try:
        public = receive(local[0], 32, monotonic() + 20)
        entry = {"requester": "demo-agent", "session": sid, "public_key": b64encode(public).decode()}
        entries.append(entry)
        _save_sessions(paths.sessions, entries)
        yield sid, ready, local
    finally:
        entries[:] = [entry for entry in entries if entry["session"] != sid]
        _save_sessions(paths.sessions, entries)
        ready.set()
        for channel in local:
            channel.close()
        process.join(3)
        if process.is_alive():
            process.terminate()
            process.join()
        exitcode = process.exitcode
        process.close()
        if exitcode != 0:
            raise RuntimeError("Demo requester exited unexpectedly")


def demo(folder):
    paths = Namespace(sessions=folder / "sessions.json", trust=folder / "trust.json",
                      context=FIXTURES / "exact-update-context.json", baseline=FIXTURES / "demo-before-text.json")
    reviewer = Ed25519PrivateKey.generate()
    public = b64encode(reviewer.public_key().public_bytes_raw()).decode()
    paths.trust.write_text(json.dumps({"format_version": "1", "organization": "demo", "reviewers": [{
        "id": "demo-reviewer", "public_key": public, "grants": [
            {"host": "github.example", "provider_id": "1001", "action": "github.file.update"}]}]}))
    proposal = (EXAMPLES / "exact-update/guide-a.json").read_bytes()
    call = (EXAMPLES / "tool-calls/guide-a.json").read_bytes()
    artifact = review_update(proposal, paths.context.read_bytes(), paths.baseline.read_bytes())["review"]
    entries = []
    results = {}
    with requester(paths, entries, 2) as (sid, start_a, channels_a):
        with requester(paths, entries, impersonate=True) as (_, start_b, channels_b):
            session = load_sessions(paths.sessions.read_bytes(), "demo")[sid]
            trust = load_trust(paths.trust.read_bytes())
            claims = make_claims(trust, "demo-reviewer", artifact["fingerprint"], now())
            claims.update(format_version="2", **session.claims())
            receipt = json.dumps(sign(claims, reviewer)).encode()
            (folder / "receipt.json").write_bytes(receipt)
            start_a.set()
            start_b.set()
            def compare(channel):
                return check_session(paths, proposal, receipt, call, channel)
            results["approved_session"] = compare(channels_a[0])
            results["other_session"] = compare(channels_b[0])
            results["recorded_proof"] = compare(channels_a[1])
    with requester(paths, entries) as (_, start, channels):
        start.set()
        results["restarted_session"] = compare(channels[0])
    return results


if __name__ == "__main__":
    with TemporaryDirectory() as directory:
        print(json.dumps(demo(Path(directory)), indent=2))
