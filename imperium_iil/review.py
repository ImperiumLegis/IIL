"""Offline exact-update review and reproducible review fingerprints."""

from difflib import unified_diff
from hashlib import sha256

from .baseline import load_baseline
from .context import ContextError, load_context
from .parser import ParseError, parse_bytes
from .policy import check_scope
from .results import Finding, ValidationResult
from .structure import UTF8_ENVELOPE_LIMIT, check_exact_shape
from .validator import PROPOSAL_LIMIT, evaluate_scope


EXACT_PROPOSAL_LIMIT = UTF8_ENVELOPE_LIMIT
DIFF_LINE_LIMIT = 512


def review_fingerprint(proposal: bytes, context: bytes, baseline: bytes, *, format_version="1") -> str:
    if format_version not in ("1", "2"):
        raise ValueError("Unknown exact review format")
    digest = sha256(b"IIL-EXACT-UPDATE\0")
    for field in (format_version.encode("ascii"), proposal, context, baseline):
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
    def response(findings):
        return ValidationResult(trusted.refs, findings).as_dict()

    try:
        document = parse_bytes(proposal, limit=EXACT_PROPOSAL_LIMIT)
        extended = document.get("iil_version") == "0.3"
        if not extended and len(proposal) > PROPOSAL_LIMIT:
            raise ParseError("INPUT_TOO_LARGE")
    except ParseError as error:
        # Broken operator data is an operational failure even for a malformed proposal.
        load_baseline(baseline, trusted, allow_utf8=True)
        return response([Finding(str(error), "", "Proposal failed a parsing rule.", "INVALID")])
    originals = load_baseline(baseline, trusted, allow_utf8=extended)
    findings = check_exact_shape(document)
    if (document.get("iil_version") not in ("0.2", "0.3")
            or any(f.pointer == "" and f.status == "INVALID" for f in findings)):
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
    format_version = "2" if extended else "1"
    artifact = {
        "format_version": format_version,
        "task": document["task"],
        "target": target,
        "before": before,
        "after": after,
        "fingerprint": review_fingerprint(proposal, context, baseline, format_version=format_version),
    }
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    if extended:
        for name, value in (("before", before), ("after", after)):
            encoded = value.encode("utf-8")
            artifact[f"{name}_bytes"] = len(encoded)
            artifact[f"{name}_sha256"] = sha256(encoded).hexdigest()
    if extended and max(len(before_lines), len(after_lines)) > DIFF_LINE_LIMIT:
        artifact["diff_omitted"] = "LINE_LIMIT"
    else:
        artifact["diff"] = list(unified_diff(before_lines, after_lines, fromfile="before", tofile="after"))
    payload["review"] = artifact
    return payload
