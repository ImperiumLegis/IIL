"""Evaluate one named action permission for both enrolled participants."""

from .action_manifest import arguments, document
from .reviewer_trust import fields, identifier, require
from .structure import supported_exact_text


def names(items):
    require(isinstance(items, list))
    return {identifier(item) for item in items}


def evaluate(raw, proposal, catalog, organization, requester, reviewer):
    policy = document(raw)
    fields(policy, ("organization", "groups", "permissions"))
    require(policy["organization"] == organization)
    groups = policy["groups"]
    require(isinstance(groups, dict))
    for group, values in groups.items():
        identifier(group)
        require(isinstance(values, list) and all(isinstance(v, str) and supported_exact_text(v) for v in values))
    doc = document(proposal)
    fields(doc, ("action", "version", "permission", "arguments"))
    selected = identifier(doc["permission"])
    permissions = policy["permissions"]
    require(isinstance(permissions, dict) and selected in permissions)
    for name, rule in permissions.items():
        identifier(name)
        fields(rule, ("action", "version", "sha256", "constraints", "requesters", "reviewers"))
        action = catalog[rule["action"], rule["version"]]
        require(rule["sha256"] == action.pin)
        callers, approvers = names(rule["requesters"]), names(rule["reviewers"])
        constraints = rule["constraints"]
        require(isinstance(constraints, dict))
        for field, group in constraints.items():
            require(field in action.schema and group in groups)
        if name == selected:
            require((doc["action"], doc["version"]) == (action.name, action.version))
            require(requester in callers and reviewer in approvers)
            values = arguments(action, doc["arguments"])
            for field, group in constraints.items():
                items = values[field] if isinstance(values[field], list) else [values[field]]
                require(all(value in groups[group] for value in items))
            decision = action, selected, values
    return decision
