# IIL validator and exact-update review reference

The [proposal schema](../schemas/iil-v0.1.schema.json) defines the required fields, types and length limits. The [context schema](../schemas/context-v0.1.schema.json) describes the operator's policy, capability registry and resource catalog. After structural validation, IIL resolves references and evaluates policy against the bound repository snapshot.

## v0.1 library entry point

```python
from pathlib import Path
from imperium_iil.context import load_demo_context
from imperium_iil.validator import validate

proposal = Path("examples/valid/read_docs.json").read_bytes()
result = validate(proposal, load_demo_context())
print(result.status)
print(result.as_dict())
```

Use bounded reads when accepting files or streams from other parties. The CLI reads at most 65,537 bytes. The parser accepts at most 65,536 bytes and 16 container levels. A caller may load independent, controlled bundle bytes with `load_context(raw)`. Never allow a proposal to select its own trusted context.

## Proposal and context

A proposal carries a language version, draft label, task description, context references, operations, restrictions, unresolved questions and evidence references. Each file operation binds a capability, repository ID, branch, immutable base revision and case-sensitive path. Read, update and delete have separate meanings. PR creation is reserved. Write proposals describe scope and still need independent payload and effect review before any execution.

Organizational policy bounds each requested operation. Task restrictions may narrow it further. Selectors can match an exact path, the final path component, a directory at a slash boundary or a reviewed group in the exact snapshot. Group membership describes a resource. The applicable rule supplies the denial. Eligibility never overrides a denial; one conflict invalidates the proposal.

## Results and replay

| CLI exit | Outcome | Interpretation |
| --- | --- | --- |
| 0 | READY_FOR_REVIEW | All supported checks passed |
| 1 | OPERATIONAL_ERROR | Validation could not complete, e.g. an unreadable proposal or broken trusted fixture |
| 2 | NEEDS_CLARIFICATION | Unresolved intent, resource, evidence or expected context |
| 3 | UNSUPPORTED | Well-formed request outside the supported language |
| 4 | INVALID | Malformed input, inconsistent identity or explicit scope conflict |

Status precedence is INVALID, UNSUPPORTED, NEEDS_CLARIFICATION, READY_FOR_REVIEW. Operational errors sit outside this ordering. All results grant zero authority. Findings have stable codes, sanitized pointers and fixed messages. Replay requires the exact proposal, schema and context bytes, pinned dependencies and validator revision. Version strings identify artifacts but do not authenticate their contents.

## v0.2 exact-update review

Use `review` for a proposal with `iil_version` set to `"0.2"` and a single `github.file.update` operation. The operation's required `replacement.text` gives the complete proposed contents of the existing regular file. The v0.1 `validate` command continues to review update scope. See the [v0.2 proposal schema](../schemas/iil-v0.2.schema.json).

```console
python -m imperium_iil review examples/exact-update/guide-a.json
python -m imperium_iil review examples/exact-update/guide-b.json
```

These proposals differ by a single digit in `replacement.text`. Compare the full strings in `review.before` and `review.after` to see the exact contents, including the final LF. The adjacent `diff` array shows line changes. Each ready result binds its target and a fingerprint to this review while keeping `authority_granted` false. The second command returns a different fingerprint. Repeating either command with identical inputs reproduces its result.

The library entry point `imperium_iil.review.review_update(proposal, context, baseline)` accepts three byte strings and returns a dictionary. The CLI uses fixed, operator-controlled fixtures for the last two inputs. The baseline maps repository ID, branch, revision and path to text. Missing before-text for an otherwise eligible target yields `NEEDS_CLARIFICATION`. Broken trusted input yields a CLI operational error. Every non-ready outcome omits the review object.

The proposal limit is 65,536 bytes. Each trusted fixture has a 1 MiB limit. The decoded replacement and baseline file contents each have a 16,384-byte UTF-8 limit. This profile supports printable ASCII, tab and LF, and preserves the decoded text exactly. An empty replacement proposes clearing the existing file's contents. An update with identical before and after strings can also be ready.

For review format 1, start SHA-256 with ASCII `IIL-EXACT-UPDATE` followed by one zero byte. Append four fields in order, prefixing each with its byte length as an unsigned eight-byte big-endian integer.

1. The ASCII byte for `1`.
2. The original proposal bytes.
3. The original trusted context bytes.
4. The original before-text fixture bytes.

Render the digest as lowercase hexadecimal. Formatting changes to any JSON input can change the fingerprint. The digest identifies the inputs used for review. Authorization requires a separate decision.
