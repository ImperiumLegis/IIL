"""Structural checks for the locally bundled IIL proposal format."""

import json
import re

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .resources import resource_dir
from .results import Finding


_SCHEMA_DIR = resource_dir("schemas")
_SCHEMA = json.loads((_SCHEMA_DIR / "iil-v0.1.schema.json").read_bytes())
_VALIDATOR = Draft202012Validator(_SCHEMA)
_EXACT_SCHEMA = json.loads((_SCHEMA_DIR / "iil-v0.2.schema.json").read_bytes())
_REGISTRY = Registry().with_resources((
    ("urn:imperium:iil:0.1", Resource.from_contents(_SCHEMA)),
    ("urn:imperium:iil:0.2", Resource.from_contents(_EXACT_SCHEMA)),
))
_EXACT_VALIDATOR = Draft202012Validator(_EXACT_SCHEMA, registry=_REGISTRY)
_UTF8_VALIDATOR = Draft202012Validator(
    json.loads((_SCHEMA_DIR / "iil-v0.3.schema.json").read_bytes()), registry=_REGISTRY)
EXACT_TEXT_LIMIT = 16_384
UTF8_TEXT_LIMIT = 262_144
UTF8_ENVELOPE_LIMIT = 2 * 1024 * 1024
UTF8_NODE_LIMIT = 4096
_EXACT_TEXT = re.compile(r"[\x20-\x7e\t\n]*")
# C0/C1 except HT/LF/CRLF, plus the Unicode Bidi_Control code points.
_UNSAFE_UTF8 = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]|\r(?!\n)")
_FILE_CAPABILITIES = frozenset(
    _SCHEMA["$defs"]["operation"]["if"]["properties"]["capability"]["enum"]
)
_SELECTOR_GROUPS = _SCHEMA["$defs"]["selector"]["allOf"]
_SELECTOR_KINDS = {
    kind for group in _SELECTOR_GROUPS for kind in group["if"]["properties"]["kind"]["enum"]
}
_PATH = re.compile(_SCHEMA["$defs"]["path"]["pattern"])
_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+)+")
# Only these recognized, prohibited properties can be echoed in a diagnostic.
_PROHIBITED = {"approved", "approver", "passport", "status"}


def valid_path(value: str) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 512 and bool(_PATH.fullmatch(value))


def supported_exact_text(text: str) -> bool:
    return _EXACT_TEXT.fullmatch(text) is not None


def exact_text_error(text: str, version: str) -> str | None:
    """Check decoded text, preserving its original code points and line endings."""
    if version not in ("0.2", "0.3"):
        raise ValueError("Unknown exact update profile")
    limit = UTF8_TEXT_LIMIT if version == "0.3" else EXACT_TEXT_LIMIT
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError:
        return "UNSUPPORTED_TEXT"
    if size > limit:
        return "REPLACEMENT_TOO_LARGE"
    if version == "0.3":
        return "UNSUPPORTED_TEXT" if _UNSAFE_UTF8.search(text) else None
    return None if supported_exact_text(text) else "UNSUPPORTED_TEXT"


def _errors(document, validator):
    """Schema paths contain fixed field names and array indices only."""
    for error in validator.iter_errors(document):
        pointer = "".join(f"/{part}" for part in error.absolute_path)
        if error.validator == "required":
            for key in error.validator_value:
                if key not in error.instance:
                    yield Finding("REQUIRED_FIELD", f"{pointer}/{key}",
                                  "A required field is missing.", "INVALID")
        elif error.validator == "additionalProperties":
            for key in error.instance.keys() - error.schema["properties"].keys():
                location = f"{pointer}/{key}" if key in _PROHIBITED else pointer
                yield Finding("UNKNOWN_FIELD", location, "Unexpected object property.", "INVALID")
        else:
            yield Finding("INVALID_SHAPE", pointer, "Value violates the proposal schema.", "INVALID")


def _unsupported(code, pointer):
    return Finding(code, pointer, "Feature is unsupported in this version.", "UNSUPPORTED")


def _duplicates(items, section):
    ids = set()
    requests = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        pointer = f"/{section}/{index}"
        identifier = item.get("id")
        if isinstance(identifier, str):
            if identifier in ids:
                yield Finding("DUPLICATE_ID", pointer + "/id", "Repeated identifier.", "INVALID")
            ids.add(identifier)
        if section == "operations" and isinstance(item.get("capability"), str) and isinstance(item.get("resource"), dict):
            request = (item["capability"], json.dumps(item["resource"], sort_keys=True))
            if request in requests:
                yield Finding("DUPLICATE_REQUEST", pointer, "Repeated operation request.", "INVALID")
            requests.add(request)


def _opaque_payload_valid(value):
    # Unknown semantics still obey the known version's global data limits.
    if isinstance(value, dict):
        return all(_opaque_payload_valid(item) for item in value.values())
    if isinstance(value, list):
        return len(value) <= 64 and all(_opaque_payload_valid(item) for item in value)
    if isinstance(value, str):
        return len(value) <= 256
    return isinstance(value, bool)


def check_shape(document: dict) -> list[Finding]:
    return _check_shape(document, "0.1", _VALIDATOR)


def _bounded_exact_structure(document):
    pending = [document]
    count = 1
    while pending:
        value = pending.pop()
        if isinstance(value, (list, dict)):
            count += len(value)
            if len(value) > 64 or count > UTF8_NODE_LIMIT:
                return False
            pending.extend(value.values() if isinstance(value, dict) else value)
    return True


def check_exact_shape(document: dict) -> list[Finding]:
    version = document.get("iil_version") if isinstance(document, dict) else None
    if version == "0.3":
        if not _bounded_exact_structure(document):
            return [Finding("STRUCTURE_LIMIT", "", "Proposal exceeds the structure limit.", "INVALID")]
        findings = _check_shape(document, "0.3", _UTF8_VALIDATOR)
    else:
        findings = _check_shape(document, "0.2", _EXACT_VALIDATOR)
    if version not in ("0.2", "0.3"):
        return findings

    # The exact profile reports malformed fields before unsupported features.
    invalid = [f for f in findings if f.status == "INVALID"]
    operations = document.get("operations")
    if isinstance(operations, list):
        for index, op in enumerate(operations):
            replacement = op.get("replacement") if isinstance(op, dict) else None
            text = replacement.get("text") if isinstance(replacement, dict) else None
            if not isinstance(text, str):
                continue
            pointer = f"/operations/{index}/replacement/text"
            error = exact_text_error(text, version)
            if error == "REPLACEMENT_TOO_LARGE":
                invalid.append(Finding(error, pointer,
                                       "Replacement exceeds the byte limit.", "INVALID"))
            elif error:
                findings.append(_unsupported(error, pointer))
    if invalid:
        return invalid
    if not operations:
        findings.append(Finding("EMPTY_OPERATIONS", "/operations", "Specify one proposed update.",
                                "NEEDS_CLARIFICATION"))
    elif len(operations) > 1:
        findings.append(_unsupported("UNSUPPORTED_OPERATION_COUNT", "/operations"))
    for index, op in enumerate(operations):
        if op["capability"] in _FILE_CAPABILITIES and op["capability"] != "github.file.update":
            findings.append(_unsupported("UNSUPPORTED_CAPABILITY", f"/operations/{index}/capability"))
    return findings


def _check_shape(document, expected_version, validator):
    version = document.get("iil_version") if isinstance(document, dict) else None
    if not isinstance(version, str) or len(version) > 64 or not _VERSION.fullmatch(version):
        return [Finding("INVALID_VERSION", "/iil_version", "Expected a version string.", "INVALID")]
    if version != expected_version:
        return [_unsupported("UNSUPPORTED_VERSION", "/iil_version")]

    findings = list(_errors(document, validator))
    invalid = {finding.pointer for finding in findings}
    invalid_subtrees = invalid.copy()
    for path in invalid:
        while "/" in path:
            path = path.rsplit("/", 1)[0]
            invalid_subtrees.add(path)
    for section in ("operations", "unresolved"):
        items = document.get(section)
        if isinstance(items, list):
            findings.extend(_duplicates(items, section))
    operations = document.get("operations")
    for index, operation in enumerate(operations if isinstance(operations, list) else []):
        pointer = f"/operations/{index}"
        if not isinstance(operation, dict):
            continue
        if pointer in invalid_subtrees:
            continue
        capability = operation.get("capability")
        resource = operation.get("resource")
        if not isinstance(capability, str) or not isinstance(resource, dict):
            continue
        if capability not in _FILE_CAPABILITIES:
            findings.append(_unsupported("UNSUPPORTED_CAPABILITY", pointer + "/capability"))
        else:
            if resource.get("type") == "github.file":
                continue
            findings.append(_unsupported("UNSUPPORTED_RESOURCE", pointer + "/resource/type"))
        if not _opaque_payload_valid(resource):
            findings.append(Finding("INVALID_SHAPE", pointer + "/resource",
                                    "Opaque payload exceeds language bounds.", "INVALID"))

    restrictions = document.get("restrictions")
    for index, restriction in enumerate(restrictions if isinstance(restrictions, list) else []):
        if not isinstance(restriction, dict):
            continue
        pointer = f"/restrictions/{index}"
        capabilities = restriction.get("capabilities")
        if isinstance(capabilities, list):
            for cap_index, capability in enumerate(capabilities):
                location = f"{pointer}/capabilities/{cap_index}"
                if isinstance(capability, str) and capability not in _FILE_CAPABILITIES and location not in invalid:
                    findings.append(_unsupported("UNSUPPORTED_CAPABILITY", location))
        selector = restriction.get("selector")
        location = pointer + "/selector"
        if isinstance(selector, dict) and location not in invalid_subtrees:
            if selector["kind"] not in _SELECTOR_KINDS:
                findings.append(_unsupported("UNSUPPORTED_SELECTOR", location + "/kind"))
                if len(selector["value"]) > 256:
                    findings.append(Finding("INVALID_SHAPE", location + "/value",
                                            "Value exceeds the free-text bound.", "INVALID"))

    ordered = {(f.pointer, f.code, f.message): f for f in findings}
    return [ordered[key] for key in sorted(ordered)]
