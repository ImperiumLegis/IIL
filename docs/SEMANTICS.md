# IIL syntax and evaluation

IIL uses UTF-8 JSON as its concrete syntax. The productions below describe its abstract syntax. Braces denote closed records, brackets denote ordered sequences, and a vertical bar separates alternatives. JSON member order has no semantic meaning. Duplicate decoded member names are errors. The versioned wire schemas define the exact member names, bounds and escaping rules.

```text
FileProposal ::= { iil_version, draft_id, task, context, operations,
                   restrictions, unresolved, evidence_refs }
Operation    ::= { id, capability, resource } | { id, capability, resource, replacement }
FileResource ::= { type, repository_id, branch, revision, path }
Restriction  ::= { repository_id, capabilities, selector }
Selector     ::= exact_path(path) | basename(name) | directory(path) | catalog_group(id)
Action       ::= { action, version, permission, arguments, [task] }
Arguments    ::= closed record described by the selected manifest
FieldV2      ::= string(bounds, optional pattern) | integer(interval) | number(interval)
               | boolean | enum(strings) | array(counts, FieldV2) | object(named fields)
```

## Scope judgment

For trusted context C, file operation o and proposal P, readiness requires all of the following.

1. The version and shape are supported, operations are unique, and the context references in P equal the references in C.
2. Resolve the repository and branch in C. The revision must match exactly. Resolve the case-sensitive path in that snapshot to an existing regular file.
3. Require membership of the path in the eligibility set for the requested capability. Match each applicable organizational denial and proposal restriction against the same path. Directory matching observes slash boundaries. A group selector requires a complete membership list tied to reviewed evidence.
4. Any matching denial or restriction produces a conflict. An unresolved group or evidence reference blocks readiness. Aggregate findings across operations with precedence INVALID, UNSUPPORTED, NEEDS_CLARIFICATION, READY_FOR_REVIEW.
5. Exact review additionally requires read access under those rules and a matching before-text entry. The replacement is the entire proposed file. Task prose is signed as input and displayed for human judgment. Prose cannot introduce a capability, override a denial, or attest that a file belongs to a group.

## Ordered update sets

Use `iil review-set PROPOSAL --context CONTEXT --baseline BASELINE` with `iil_version` set to `"set-1"`. It accepts one to eight distinct v0.3 exact updates under one task, in the specified order. Every edit must pass scope and before-text checks before the result exposes any edit. The set fingerprint is SHA-256 of the ASCII domain `IIL-UPDATE-SET-1`, one zero byte, and the original proposal, context and baseline in order, each prefixed by its eight-byte big-endian length. This command produces a review record. Individual signing profiles continue to cover a single action. Atomic execution of a set requires a separate provider contract.

## Action judgment

Resolve the action/version in the operator registry and check the digest of its manifest. Resolve the named permission under the operator organization. Check both participant IDs, the manifest pin, every argument against its type, and every selected value against its constraint. All checks must succeed. The adapter selects how an independently observed call is decoded. A signed match additionally requires the reviewed tool, arguments, receipt, current trust, and proof of possession of the enrolled session key. The public result always carries `authority_granted: false`.

For standing policy evaluation run `python -m imperium_iil.standing` with the operator-selected permission, requester, reviewer, registry, policy and call. This evaluates the actual call without interactive signing. The host must authenticate the requester and protect the policy and identity inputs. POLICY_MATCHED expresses eligibility under the configured standing rule. It supplies no proof of an individual human decision. A draft PR example with branch and draft-mode restrictions is provided under [examples/actions/pull-request](../examples/actions/pull-request).
