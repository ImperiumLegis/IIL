"""Structural checks for the locally bundled IIL proposal format."""

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from .results import Finding


_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "schemas" / "iil-v0.1.schema.json")
    .read_text(encoding="utf-8")
)
_VALIDATOR = Draft202012Validator(_SCHEMA)
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


def _errors(document):
    """Schema paths contain fixed field names and array indices only."""
    for error in _VALIDATOR.iter_errors(document):
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
    version = document.get("iil_version") if isinstance(document, dict) else None
    if not isinstance(version, str) or len(version) > 64 or not _VERSION.fullmatch(version):
        return [Finding("INVALID_VERSION", "/iil_version", "Expected a version string.", "INVALID")]
    if version != "0.1":
        return [_unsupported("UNSUPPORTED_VERSION", "/iil_version")]

    findings = list(_errors(document))
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
