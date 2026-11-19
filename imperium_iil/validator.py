"""Validate an untrusted proposal against independently loaded context."""

from .context import TrustedContext
from .parser import ParseError, parse_bytes
from .policy import check_scope
from .results import Finding, ValidationResult
from .structure import check_shape


PROPOSAL_LIMIT = 65536


def validate(raw: bytes, context: TrustedContext) -> ValidationResult:
    try:
        document = parse_bytes(raw, limit=PROPOSAL_LIMIT)
    except ParseError as error:
        return ValidationResult(context.refs, [
            Finding(str(error), "", "Proposal failed a parsing rule.", "INVALID")
        ])

    findings = list(check_shape(document))
    if document.get("iil_version") != "0.1":
        return ValidationResult(context.refs, findings)

    invalid = {f.pointer for f in findings if f.status == "INVALID"}

    def usable(section):
        pointer = "/" + section
        return section in document and not any(
            path == pointer or path.startswith(pointer + "/") for path in invalid
        )

    def clarify(code, pointer, message):
        findings.append(Finding(code, pointer, message, "NEEDS_CLARIFICATION"))

    if usable("operations") and not document["operations"]:
        clarify("EMPTY_OPERATIONS", "/operations", "Specify at least one proposed operation.")
    if usable("unresolved") and document["unresolved"]:
        clarify("OPEN_QUESTIONS", "/unresolved", "Resolve the outstanding proposal questions.")
    if not usable("context"):
        return ValidationResult(context.refs, findings)
    if document["context"] != context.refs:
        clarify("CONTEXT_MISMATCH", "/context", "Review against the specified context versions.")
    else:
        for index, evidence_id in enumerate(document["evidence_refs"] if usable("evidence_refs") else ()):
            if context.evidence.get(evidence_id) != "reviewed":
                clarify("UNREVIEWED_EVIDENCE", f"/evidence_refs/{index}", "Reviewed evidence is required.")
        invalid_items = {"/".join(path.split("/")[:3]) for path in invalid}
        known = {(f.code, f.pointer) for f in findings}
        findings.extend(f for f in check_scope(document, context, invalid_items=invalid_items)
                        if (f.code, f.pointer) not in known)
    return ValidationResult(context.refs, findings)
