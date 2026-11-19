"""Evaluate a structurally valid v0.1 proposal against a validated context."""

from .results import Finding


SELECTORS = frozenset({"exact_path", "directory", "basename", "catalog_group"})
UNSUPPORTED_FEATURE = "Feature is unsupported in this version."


def _resolve(operation, context, pointer):
    """Return the exact snapshot if resolved and any blocking resource finding."""
    resource = operation["resource"]
    if not context.capabilities.get(operation["capability"]):
        return None, Finding("UNSUPPORTED_CAPABILITY", pointer + "/capability",
                             UNSUPPORTED_FEATURE, "UNSUPPORTED")
    pointer += "/resource"
    if resource["type"] != "github.file":
        return None, Finding("UNSUPPORTED_RESOURCE", pointer + "/type",
                             UNSUPPORTED_FEATURE, "UNSUPPORTED")
    repo, branch = resource["repository_id"], resource["branch"]
    snapshot = context.snapshots.get((repo, branch))
    if snapshot is None:
        field = "branch" if any(key[0] == repo for key in context.snapshots) else "repository_id"
        return None, Finding("UNKNOWN_RESOURCE", f"{pointer}/{field}",
                             "Repository or branch is unknown.", "NEEDS_CLARIFICATION")
    if resource["revision"] != snapshot["revision"]:
        return None, Finding("REVISION_MISMATCH", pointer + "/revision",
                             "Revision conflicts with the catalog snapshot.", "INVALID")
    file_kind = snapshot["files"].get(resource["path"])
    if file_kind is None:
        return snapshot, Finding("UNKNOWN_RESOURCE", pointer + "/path",
                                 "File is absent from the snapshot.", "NEEDS_CLARIFICATION")
    if file_kind != "regular":
        return snapshot, Finding("UNSUPPORTED_FILE_KIND", pointer + "/path",
                                 "Catalog file kind is unsupported.", "UNSUPPORTED")
    return snapshot, None


def _group_members(snapshot, name, evidence):
    group = snapshot["groups"].get(name)
    if group and group["complete"] and evidence.get(group["review_ref"]) == "reviewed":
        return group["members"]
    return None


def _group_finding(pointer):
    return Finding("UNRESOLVED_GROUP", pointer,
                   "Classification requires a complete reviewed group for the snapshot.",
                   "NEEDS_CLARIFICATION")


def _matches(selector, path, snapshot, evidence):
    kind = selector["kind"]
    if kind not in SELECTORS:
        return False
    value = selector["value"]
    if kind == "exact_path":
        return path == value
    if kind == "directory":
        return path.startswith(value + "/")
    if kind == "basename":
        return path.rsplit("/", 1)[-1] == value
    members = _group_members(snapshot, value, evidence)
    return None if members is None else path in members


def _restriction_findings(rule, pointer, context, snapshot_keys):
    repo = rule["repository_id"]
    if not any(key[0] == repo for key in context.snapshots):
        yield Finding("UNKNOWN_RESOURCE", pointer + "/repository_id",
                      "Restriction repository is unknown.", "NEEDS_CLARIFICATION")
    for index, capability in enumerate(rule["capabilities"]):
        if not context.capabilities.get(capability):
            yield Finding("UNSUPPORTED_CAPABILITY", f"{pointer}/capabilities/{index}",
                          UNSUPPORTED_FEATURE, "UNSUPPORTED")
    selector = rule["selector"]
    if selector["kind"] not in SELECTORS:
        yield Finding("UNSUPPORTED_SELECTOR", pointer + "/selector/kind",
                      UNSUPPORTED_FEATURE, "UNSUPPORTED")
    elif selector["kind"] == "catalog_group":
        snapshots = [context.snapshots[key] for key in snapshot_keys if key[0] == repo]
        if not snapshots or any(_group_members(snapshot, selector["value"], context.evidence)
                                is None for snapshot in snapshots):
            yield _group_finding(pointer + "/selector")


def check_scope(document: dict, context, *, invalid_items=frozenset()) -> list[Finding]:
    findings = []
    snapshot_keys = set()
    def usable_items(section):
        if "/" + section in invalid_items:
            return
        for index, item in enumerate(document.get(section, ())):
            if f"/{section}/{index}" not in invalid_items:
                yield index, item

    restrictions = list(usable_items("restrictions"))
    for index, op in usable_items("operations"):
        pointer = f"/operations/{index}"
        snapshot, issue = _resolve(op, context, pointer)
        resource = op["resource"]
        if snapshot is not None:
            snapshot_keys.add((resource["repository_id"], resource["branch"]))
        if issue:
            findings.append(issue)
            continue
        repo, path = resource["repository_id"], resource["path"]
        capability = op["capability"]
        if path not in snapshot["eligible"].get(capability, ()):
            findings.append(Finding("POLICY_CONFLICT", pointer,
                                    "Operation is outside the trusted review envelope.", "INVALID"))
        for rules, code, message in (
            (context.denials, "POLICY_CONFLICT", "Operation matches a policy denial."),
            ((r for _, r in restrictions), "RESTRICTION_CONFLICT", "Operation matches a proposal restriction."),
        ):
            for rule in rules:
                if repo != rule["repository_id"] or capability not in rule["capabilities"]:
                    continue
                match = _matches(rule["selector"], path, snapshot, context.evidence)
                if match:
                    findings.append(Finding(code, pointer, message, "INVALID"))
                elif match is None and code == "POLICY_CONFLICT":
                    findings.append(_group_finding(pointer))

    for index, restriction in restrictions:
        findings.extend(_restriction_findings(restriction, f"/restrictions/{index}",
                                              context, snapshot_keys))
    return findings
