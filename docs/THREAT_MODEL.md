# Threat model for the offline validator

The protected asset in this milestone is the integrity of a proposal review result. The adversary can control every proposal byte, including prose, identifiers, claimed context versions, strings resembling credentials and extra properties. The operator chooses and protects the interpreter, dependencies, validator, schemas and context bundle. The demo assumes those components are trustworthy.

| Failure mode | Implemented control to verify | Residual limitation |
| --- | --- | --- |
| Ambiguous interpretation | Strict UTF-8, duplicate-key rejection on decoded names, bounded nesting and one JSON document | Byte and depth limits are prototype availability controls |
| Self-appointed administrator | Strict known shapes, explicit registry, fixed false authority flag | Independent approval is outside the validator |
| Substituted repository, path or revision | Exact snapshot matching, conservative path grammar and cataloged file kind | Local fixtures cannot attest live provider state |
| Hidden or conflicting scope | Check operation eligibility and all applicable denials; incomplete classifications block readiness | Omitted user intent and malicious content in a file can escape proposal-level checks |
| Forged provenance or policy downgrade | Load context independently, validate references and require expected versions | A local attacker who can edit trusted files can defeat these assumptions |
| Overclaim about execution | Structured results and offline examples, including a prose/operation mismatch | No credential isolation, runtime mediation, side-effect binding or replay-resistant authorization |

The public CLI diagnostics omit input values and stack traces. Do not submit real secrets. Free-form descriptions can contain sensitive text, and this language has no secret scanner. Anyone who can modify the caller, bypass the future broker, or run code with a service credential can bypass a proposal review entirely.

The repository is MIT-licensed. Security reports and the current support scope are described in [SECURITY.md](../SECURITY.md). Independent security assessment and production deployment evidence remain open.
