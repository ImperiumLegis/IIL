"""Verify a single session presentation on a private, caller-owned connected socket."""

from secrets import token_bytes
from time import monotonic

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .__main__ import FIXTURE_LIMIT, _read
from .match_call import compare_call
from .receipt import now, verified_review
from .receipts import check_time, parse_time
from .requester_session import load_sessions
from .reviewer_trust import TRUST_LIMIT, load_trust, require
from .session_proof import Presentation, receive
from .tool_call import parse_update_call


def _check_inputs(paths, proposal, receipt, submitted):
    context = _read(paths.context, FIXTURE_LIMIT)
    baseline = _read(paths.baseline, FIXTURE_LIMIT)
    trust = load_trust(_read(paths.trust, TRUST_LIMIT))
    sessions = load_sessions(_read(paths.sessions, TRUST_LIMIT), trust.organization)
    claims, artifact, repo = verified_review(proposal, receipt, context, baseline, trust, now(), version="2")
    compare_call(submitted, artifact, repo)
    binding = sessions[claims["session"]]
    require(all(claims[name] == value for name, value in binding.claims().items()))
    return binding, claims


def check_session(paths, proposal, receipt, call, channel):
    """One invocation consumes at most one response. Use a dedicated channel per comparison."""
    try:
        require(all(type(data) is bytes for data in (proposal, receipt, call)))
        submitted = parse_update_call(call)
        binding, claims = _check_inputs(paths, proposal, receipt, submitted)
        presentation = Presentation.for_submission(binding, receipt, call)
        nonce = token_bytes(32)
        start = monotonic()
        wall = now()
        check_time(claims, wall)
        lifetime = min(60.0, (parse_time(claims["expires_at"]) - wall).total_seconds())
        deadline = start + lifetime
        channel.settimeout(lifetime)
        channel.sendall(presentation.challenge(nonce))
        response = receive(channel, 64, deadline)
        Ed25519PublicKey.from_public_bytes(binding.public_key).verify(response, presentation.message(nonce))
        current, claims = _check_inputs(paths, proposal, receipt, submitted)
        require(current == binding)
        check_time(claims, now())
        require(monotonic() < deadline)
    except Exception:
        return {"status": "SESSION_CALL_REJECTED", "authority_granted": False}
    return {"status": "SESSION_CALL_MATCHED", "authority_granted": False}
