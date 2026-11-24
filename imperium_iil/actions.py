"""Review and compare an adopter-defined action in a disposable requester session."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from secrets import token_hex
import socket
from time import monotonic

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from nacl.bindings import crypto_core_ed25519_is_valid_point

from .action_call import FORMATS
from .action_manifest import read
from .action_receipt import issue, match
from .receipt import add_trust_arguments, current_trust, publish
from .requester_session import Session
from .reviewer_trust import identifier, require
from .session_proof import Presentation, receive, respond


def _worker(channel, organization, requester, sid, call):
    with channel:
        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes_raw()
        channel.sendall(public)
        binding = Session(organization, requester, sid, public)
        # The trusted launcher supplies the issued receipt after interactive confirmation.
        header = channel.recv(1)
        if header != b"R":
            return
        deadline = monotonic() + 60
        size = int.from_bytes(receive(channel, 4, deadline), "big")
        require(0 < size <= 8192)
        raw = receive(channel, size, deadline)
        pending = Presentation.for_submission(binding, raw, call)
        try:
            challenge = receive(channel, 64, deadline)
            channel.sendall(respond(key, pending, challenge))
            channel.recv(1)
        except EOFError:
            pass


def run(paths):
    proposal, call = read(paths.proposal), read(paths.call)
    org = current_trust(paths).organization
    requester = identifier(paths.requester)
    sid = token_hex(32)
    local, remote = socket.socketpair()
    with local, remote:
        command = [sys.executable, "-m", "imperium_iil.action_requester", org, requester, sid]
        options = {}
        if os.name != "nt":
            command.append(str(remote.fileno()))
            options["pass_fds"] = (remote.fileno(),)
        worker = subprocess.Popen(command, stdin=subprocess.PIPE, **options)
        try:
            with worker.stdin:
                if os.name == "nt":
                    shared = remote.share(worker.pid)
                    worker.stdin.write(len(shared).to_bytes(4, "big") + shared)
                worker.stdin.write(call)
            remote.close()
            public = receive(local, 32, monotonic() + 20)
            require(crypto_core_ed25519_is_valid_point(public))
            session = Session(org, requester, sid, public)
            def active():
                require(worker.poll() is None)
                return session
            raw = issue(paths, proposal, active)
            active()
            if paths.out:
                publish(paths.out, json.loads(raw))
            local.sendall(b"R" + len(raw).to_bytes(4, "big") + raw)
            return match(paths, proposal, raw, call, active, local)
        finally:
            local.close()
            try:
                worker.wait(timeout=2)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_trust_arguments(parser)
    for name in ("proposal", "call", "policy", "root", "registry", "key"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--call-format", choices=FORMATS, default="iil")
    parser.add_argument("--requester", required=True)
    parser.add_argument("--reviewer", required=True)
    paths = parser.parse_args(argv)
    try:
        result = run(paths)
    except (Exception, KeyboardInterrupt):
        result = {"status": "SESSION_CALL_REJECTED", "authority_granted": False}
    print(json.dumps(result))
    return int(result["status"] != "SESSION_CALL_MATCHED")


if __name__ == "__main__":
    raise SystemExit(main())
