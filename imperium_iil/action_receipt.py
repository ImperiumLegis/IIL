"""Review and authenticate a declarative action under current operator inputs."""

import json
import sys
from base64 import b64encode
from hashlib import sha256

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .action_call import FORMATS, decode_call
from .action_manifest import arguments, document, load_catalog, read
from .action_policy import evaluate
from .receipt import current_trust, now, unlock
from .receipts import SESSION_SIGNED, check_time, framed, make_claims
from .reviewer_trust import binary, fields, require
from .session_match import challenge_decision

NAMES = (*SESSION_SIGNED, "action", "version", "manifest", "permission")


def message(claims):
    return framed(b"IIL-DECLARATIVE-REVIEW-1", (claims[n].encode() for n in NAMES))


def review(paths, proposal, session):
    trust = current_trust(paths)
    require(trust.organization == session.organization)
    reviewer = trust.lookup(paths.reviewer)
    policy = read(paths.policy)
    catalog = load_catalog(paths.registry, paths.root)
    action, permission, values = evaluate(policy, proposal, catalog, trust.organization,
                                          session.requester, paths.reviewer)
    call_format = getattr(paths, "call_format", "iil")
    require(call_format in FORMATS)
    inputs = (proposal, action.raw, policy)
    snapshot = (framed(b"IIL-ACTION-SNAPSHOT-1", inputs) if call_format == "iil" else
                framed(b"IIL-ACTION-SNAPSHOT-2", (*inputs, call_format.encode("ascii"))))
    digest = sha256(snapshot).hexdigest()
    return trust, reviewer, action, permission, values, digest


def issue(paths, proposal, active):
    require(type(proposal) is bytes)
    key = unlock(paths.key)
    session = active()
    trust, reviewer, action, permission, values, digest = review(paths, proposal, session)
    require(key.public_key().public_bytes_raw() == reviewer.public_key)
    claims = make_claims(trust, paths.reviewer, digest, now())
    claims.update(format_version="action-1", action=action.name, version=action.version,
                  manifest=action.pin, permission=permission, **session.claims())
    require(active() == session)
    display = {"claims": claims, "call_format": getattr(paths, "call_format", "iil"),
               "tool": action.tool, "arguments": values}
    task = document(proposal, numbers=True).get("task")
    if task is not None:
        display["task"] = task
    print(json.dumps(display, indent=2), file=sys.stderr)
    print("Type APPROVE to sign: ", end="", file=sys.stderr, flush=True)
    require(sys.stdin.readline(16).rstrip("\r\n") == "APPROVE")
    require(active() == session)
    _, current, _, _, _, latest = review(paths, proposal, session)
    require(current.public_key == reviewer.public_key and latest == digest)
    require(active() == session)
    check_time(claims, now())
    record = {**claims, "signature": b64encode(key.sign(message(claims))).decode()}
    return (json.dumps(record, sort_keys=True) + "\n").encode("ascii")


def match(paths, proposal, receipt, call, active_session, channel):
    def check():
        require(all(type(data) is bytes for data in (proposal, receipt, call)))
        session = active_session()
        trust, reviewer, action, permission, values, digest = review(paths, proposal, session)
        record = document(receipt)
        fields(record, (*NAMES, "signature"))
        expected = {"format_version": "action-1", "organization": trust.organization,
                    "reviewer": paths.reviewer, "key_fingerprint": reviewer.fingerprint,
                    "review_fingerprint": digest, "action": action.name, "version": action.version,
                    "manifest": action.pin, "permission": permission, **session.claims()}
        require(all(record[k] == v for k, v in expected.items()))
        check_time(record, now())
        Ed25519PublicKey.from_public_bytes(reviewer.public_key).verify(binary(record["signature"], 64),
                                                                       message(record))
        tool, submitted = decode_call(call, getattr(paths, "call_format", "iil"))
        require(tool == action.tool)
        arguments(action, submitted)
        # Distinguish an integer from a decimal throughout nested objects and arrays.
        require(json.dumps(submitted, sort_keys=True) == json.dumps(values, sort_keys=True))
        return session, record
    return challenge_decision(check, receipt, call, channel)
