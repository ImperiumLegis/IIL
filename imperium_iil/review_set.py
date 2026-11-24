"""All-or-nothing review of distinct exact updates sharing one task and policy."""

import json
from hashlib import sha256

from .baseline import load_baseline
from .context import load_context
from .parser import ParseError, parse_bytes
from .results import Finding, ValidationResult
from .review import EXACT_PROPOSAL_LIMIT, review_update
from .structure import check_exact_shape
from .validator import evaluate_scope


def review_set(proposal, context, baseline):
    if any(type(raw) is not bytes for raw in (proposal, context, baseline)):
        raise TypeError("Update-set review requires immutable bytes")
    trusted = load_context(context)
    load_baseline(baseline, trusted, allow_utf8=True)

    def reject(code, pointer, status):
        finding = Finding(code, pointer, "Proposal failed an update-set rule.", status)
        return ValidationResult(trusted.refs, [finding]).as_dict()

    try:
        doc = parse_bytes(proposal, limit=EXACT_PROPOSAL_LIMIT)
    except ParseError as error:
        return reject(str(error), "", "INVALID")
    if doc.get("iil_version") != "set-1":
        return reject("UNSUPPORTED_VERSION", "/iil_version", "UNSUPPORTED")
    doc["iil_version"] = "0.3"
    findings = [f for f in check_exact_shape(doc) if f.code != "UNSUPPORTED_OPERATION_COUNT"]
    if any(f.pointer == "" and f.status == "INVALID" for f in findings):
        return ValidationResult(trusted.refs, findings).as_dict()
    if isinstance(doc.get("operations"), list) and len(doc["operations"]) > 8:
        return reject("SET_TOO_LARGE", "/operations", "INVALID")
    result = evaluate_scope(doc, trusted, findings).as_dict()
    if result["status"] != "READY_FOR_REVIEW":
        return result
    edits = []
    for index, op in enumerate(doc["operations"]):
        applicable = [r for r in doc["restrictions"] if r["repository_id"] == op["resource"]["repository_id"]]
        single = json.dumps({**doc, "operations":[op], "restrictions":applicable}, ensure_ascii=False).encode()
        member = review_update(single, context, baseline)
        if member["status"] != "READY_FOR_REVIEW":
            for f in member["findings"]:
                f["pointer"] = f["pointer"].replace("/operations/0", f"/operations/{index}", 1)
            return member
        edits.append(member["review"])
    digest = sha256(b"IIL-UPDATE-SET-1\0")
    for field in (proposal, context, baseline):
        digest.update(len(field).to_bytes(8, "big"))
        digest.update(field)
    result["review"] = {"format_version":"set-1", "edits":edits, "fingerprint":digest.hexdigest()}
    return result
