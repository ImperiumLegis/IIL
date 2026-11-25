"""Evaluate one named action permission for both enrolled participants."""

from .action_allowlist import email_allowlist, path_allowlist
from .action_manifest import arguments, document
from .action_types import TypedField, numeric_range, pattern
from .reviewer_trust import fields, identifier, require
from .structure import supported_exact_text


def names(items):
    require(isinstance(items, list))
    return {identifier(item) for item in items}


def typed_constraint(action, selector, rule, groups):
    require(selector.startswith("/"))
    path = selector[1:].split("/")
    field = TypedField("object", properties=action.schema)
    for part in path:
        if part == "*":
            require(field.kind == "array")
            field = field.item
        else:
            require(field.kind == "object" and part in field.properties)
            field = field.properties[part]
    if isinstance(rule, str):
        require(field.kind in ("string", "enum") and rule in groups)
        return path, groups[rule].__contains__
    require(isinstance(rule, dict))
    for key, compile_rule in (("email_allowlist", email_allowlist), ("path_allowlist", path_allowlist)):
        if key in rule:
            fields(rule, (key,))
            require(field.kind in ("string", "enum"))
            return path, compile_rule(rule[key])
    if "pattern" in rule:
        fields(rule, ("pattern",))
        require(field.kind in ("string", "enum"))
        return path, pattern(rule["pattern"]).fullmatch
    if "equals" in rule:
        fields(rule, ("equals",))
        require(field.kind == "boolean" and type(rule["equals"]) is bool)
        return path, lambda value: value is rule["equals"]
    fields(rule, ("min", "max"))
    require(field.kind in ("integer", "number"))
    low, high = numeric_range(field.kind, rule["min"], rule["max"])
    return path, lambda value: low <= value <= high


def selected_values(values, path):
    pending = [values]
    for part in path:
        if part == "*":
            pending = [item for array in pending for item in array]
        else:
            pending = [obj[part] for obj in pending]
    return pending


def evaluate(raw, proposal, catalog, organization, requester, reviewer):
    policy = document(raw, numbers=True)
    doc = document(proposal, numbers=True)
    return evaluate_document(policy, doc, catalog, organization, requester, reviewer)


def evaluate_document(policy, doc, catalog, organization, requester, reviewer):
    """Apply policy to arguments already decoded by the bounded wire parser."""
    fields(policy, ("organization", "groups", "permissions"))
    require(policy["organization"] == organization)
    groups = policy["groups"]
    require(isinstance(groups, dict))
    for group, values in groups.items():
        identifier(group)
        require(isinstance(values, list) and all(isinstance(v, str) and supported_exact_text(v) for v in values))
    groups = {group: frozenset(values) for group, values in groups.items()}
    required = ("action", "version", "permission", "arguments")
    fields(doc, (*required, "task") if "task" in doc else required)
    if "task" in doc:
        task = doc["task"]
        fields(task, ("description",))
        description = task["description"]
        require(isinstance(description, str) and 0 < len(description) <= 1024
                and description.strip() and supported_exact_text(description))
    selected = identifier(doc["permission"])
    permissions = policy["permissions"]
    require(isinstance(permissions, dict) and selected in permissions)
    for name, rule in permissions.items():
        identifier(name)
        fields(rule, ("action", "version", "sha256", "constraints", "requesters", "reviewers"))
        key = identifier(rule["action"]), identifier(rule["version"])
        require(key in catalog)
        action = catalog[key]
        require(rule["sha256"] == action.pin)
        callers, approvers = names(rule["requesters"]), names(rule["reviewers"])
        constraints = rule["constraints"]
        require(isinstance(constraints, dict))
        checks = []
        for field, restriction in constraints.items():
            if action.format_version == "2":
                checks.append(typed_constraint(action, field, restriction, groups))
            else:
                require(field in action.schema and isinstance(restriction, str) and restriction in groups)
                path = [field, "*"] if action.schema[field].cardinality is not None else [field]
                checks.append((path, groups[restriction].__contains__))
        if name == selected:
            require((doc["action"], doc["version"]) == (action.name, action.version))
            require(requester in callers and reviewer in approvers)
            values = arguments(action, doc["arguments"])
            for path, accepts in checks:
                require(all(accepts(value) for value in selected_values(values, path)))
            decision = action, selected, values
    return decision
