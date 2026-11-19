# IIL v0.1 validator reference

The [proposal schema](../schemas/iil-v0.1.schema.json) defines the required fields, types and length limits. The [context schema](../schemas/context-v0.1.schema.json) describes the operator's policy, capability registry and resource catalog. After structural validation, IIL resolves references and evaluates policy against the bound repository snapshot.

## Library entry point

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
