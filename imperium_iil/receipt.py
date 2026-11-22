"""Issue and verify offline signed review receipts."""

import argparse
from datetime import UTC, datetime
import getpass
import json
import os
from pathlib import Path
import sys
from tempfile import mkstemp
import warnings

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from .__main__ import FIXTURES, FIXTURE_LIMIT, _read
from .context import load_context
from .receipts import RECEIPT_LIMIT, authenticate, check_time, make_claims, sign
from .review import review_update
from .requester_session import load_sessions
from .reviewer_trust import TRUST_LIMIT, load_trust, require
from .validator import PROPOSAL_LIMIT


def now():
    return datetime.now(UTC)


def review_inputs(args):
    return (_read(args.proposal, PROPOSAL_LIMIT), _read(args.context, FIXTURE_LIMIT),
            _read(args.baseline, FIXTURE_LIMIT))


def scoped_review(proposal, context, baseline, reviewer):
    result = review_update(proposal, context, baseline)
    require(result["status"] == "READY_FOR_REVIEW")
    artifact = result["review"]
    repo = load_context(context).repositories[artifact["target"]["repository_id"]]
    require(reviewer.allows(repo))
    return artifact, dict(repo)


def unlock(path):
    require(sys.stdin.isatty() and sys.stderr.isatty())
    pem = _read(path, 8192)
    require(len(pem) <= 8192 and pem.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"))
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass("Signing key passphrase: ").encode()
    require(bool(password))
    key = load_pem_private_key(pem, password)
    require(isinstance(key, Ed25519PrivateKey))
    return key


def publish(path, record):
    # Link only a fully written receipt, and never replace an existing destination.
    fd, name = mkstemp(dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(json.dumps(record, sort_keys=True).encode("ascii") + b"\n")
        if os.name == "nt":
            os.rename(temporary, path)  # On Windows an existing destination is an error.
        else:
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def current_trust(args):
    return load_trust(_read(args.trust, TRUST_LIMIT))


def issue(args):
    key = unlock(args.key)
    trust = current_trust(args)
    reviewer = trust.lookup(args.reviewer)
    require(key.public_key().public_bytes_raw() == reviewer.public_key)
    session = None
    if args.command == "issue-session":
        session = load_sessions(_read(args.sessions, TRUST_LIMIT), trust.organization)[args.session]
    artifact, repo = scoped_review(*review_inputs(args), reviewer)
    claims = make_claims(trust, args.reviewer, artifact["fingerprint"], now())
    if session is not None:
        claims.update(format_version="2", **session.claims())
    print(json.dumps({"approval": claims, "repository": repo, "review": artifact},
                     ensure_ascii=True, indent=2), file=sys.stderr)
    print("Type APPROVE to sign this exact edit: ", file=sys.stderr, end="", flush=True)
    require(sys.stdin.readline(16).rstrip("\r\n") == "APPROVE")
    latest = current_trust(args)
    current = latest.lookup(args.reviewer)
    require(latest.organization == trust.organization and current.public_key == reviewer.public_key)
    require(current.allows(repo))
    if session is not None:
        require(load_sessions(_read(args.sessions, TRUST_LIMIT), latest.organization).get(args.session) == session)
    record = sign(claims, key)
    check_time(record, now())
    publish(args.out, record)
    return "APPROVAL_ISSUED"


def verified_review(proposal, receipt, context, baseline, trust, at, *, version="1"):
    record = authenticate(receipt, trust, at, version=version)
    artifact, repo = scoped_review(proposal, context, baseline, trust.lookup(record["reviewer"]))
    require(record["review_fingerprint"] == artifact["fingerprint"])
    return record, artifact, repo


def verify(args):
    proposal, context, baseline = review_inputs(args)
    raw = _read(args.receipt, RECEIPT_LIMIT)
    record, _, _ = verified_review(proposal, raw, context, baseline, current_trust(args), now())
    check_time(record, now())
    return "APPROVAL_VERIFIED"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    issuer = commands.add_parser("issue")
    session_issuer = commands.add_parser("issue-session")
    verifier = commands.add_parser("verify")
    for command in (issuer, session_issuer, verifier):
        command.add_argument("proposal", type=Path)
        command.add_argument("--trust", required=True, type=Path)
        command.add_argument("--context", type=Path, default=FIXTURES / "exact-update-context.json")
        command.add_argument("--baseline", type=Path, default=FIXTURES / "demo-before-text.json")
    for command in (issuer, session_issuer):
        command.add_argument("--key", required=True, type=Path)
        command.add_argument("--reviewer", required=True)
        command.add_argument("--out", required=True, type=Path)
    session_issuer.add_argument("--sessions", required=True, type=Path)
    session_issuer.add_argument("--session", required=True)
    verifier.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        status = verify(args) if args.command == "verify" else issue(args)
    except (Exception, KeyboardInterrupt):
        # Public boundary: parser, key-provider and OS errors may include sensitive input.
        print(json.dumps({"status": "APPROVAL_REJECTED", "authority_granted": False}))
        return 1
    print(json.dumps({"status": status, "authority_granted": False}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
