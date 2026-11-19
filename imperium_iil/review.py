"""Offline exact-update review and reproducible review fingerprints."""

from difflib import unified_diff
from hashlib import sha256

from .baseline import load_baseline
from .context import ContextError, load_context
from .parser import ParseError, parse_bytes
from .policy import check_scope
from .results import Finding, ValidationResult
from .structure import check_exact_shape
from .validator import PROPOSAL_LIMIT, evaluate_scope


def review_fingerprint(proposal: bytes, context: bytes, baseline: bytes) -> str:
    digest = sha256(b"IIL-EXACT-UPDATE\0")
    for field in (b"1", proposal, context, baseline):
        digest.update(len(field).to_bytes(8, "big"))
        digest.update(field)
    return digest.hexdigest()


def review_update(proposal: bytes, context: bytes, baseline: bytes) -> dict:
    """Review immutable input bytes using independently selected trusted fixtures."""
    if any(type(raw) is not bytes for raw in (proposal, context, baseline)):
        raise TypeError("Exact review requires immutable bytes.")
    trusted = load_context(context)
    if trusted.refs["registry"] != {"id": "exact-update-registry", "version": "0.2"}:
        raise ContextError("Unexpected exact-update registry")
    originals = load_baseline(baseline, trusted)

    def response(findings):
        payload = ValidationResult(trusted.refs, findings).as_dict()
        payload["validator_version"] = "0.2.0"
        return payload

    try:
        document = parse_bytes(proposal, limit=PROPOSAL_LIMIT)
    except ParseError as error:
        return response([Finding(str(error), "", "Proposal failed a parsing rule.", "INVALID")])
    findings = check_exact_shape(document)
    if document.get("iil_version") != "0.2":
        return response(findings)
    result = evaluate_scope(document, trusted, findings)
    if result.status != "READY_FOR_REVIEW":
        return response(result.findings)

    operation = document["operations"][0]
    target = operation["resource"]
    # Showing the before-text discloses file contents. Check read scope too.
    read = {"operations": [{**operation, "capability": "github.file.read"}],
            "restrictions": document["restrictions"]}
    read_findings = check_scope(read, trusted)
    if read_findings:
        return response(read_findings)
    key = tuple(target[field] for field in ("repository_id", "branch", "revision", "path"))
    if key not in originals:
        return response([Finding("MISSING_BASE_TEXT", "/operations/0/resource",
                                 "Reviewed before-text is needed.", "NEEDS_CLARIFICATION")])
    before = originals[key]
    after = operation["replacement"]["text"]
    payload = response([])
    payload["review"] = {
        "format_version": "1",
        "target": target,
        "before": before,
        "after": after,
        "diff": list(unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                  fromfile="before", tofile="after")),
        "fingerprint": review_fingerprint(proposal, context, baseline),
    }
    return payload
