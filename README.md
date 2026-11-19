# Imperium Intent Language

Created by [@oneezeeroo](https://github.com/oneezeeroo), founder of **Imperium Legis**, a project of **Provenance Supply LLC**. Released under the [MIT License](LICENSE).

IIL v0.1 checks a proposed agent task before it reaches an authorization reviewer. Give it a JSON proposal and a trusted resource snapshot. It returns a reproducible verdict with reasons. The CLI runs locally with a synthetic GitHub repository and requires no account or service credentials.

## Try a narrow read, then a protected read

From the repository root on Windows with Python 3.12 installed, create the environment. If your interpreter is outside PATH, substitute its absolute path for `py -3.12` (in PowerShell, use `& "path-to-python.exe" -m venv .venv`).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe examples/run_demo.py
.\.venv\Scripts\python.exe -m examples.compare_policies
.\.venv\Scripts\python.exe -m imperium_iil validate examples/valid/read_docs.json
.\.venv\Scripts\python.exe -m imperium_iil validate examples/invalid/protected.json
.\.venv\Scripts\python.exe -m pytest -q
```

On Linux or macOS, use `python3.12 -m venv .venv` and `.venv/bin/python` for the subsequent commands. Installing the pinned packages requires a package index or a local wheel cache. Validation itself is offline. For validation alone install `requirements.txt`.

The first proposal requests a read of `README.md` and excludes the reviewed authentication group. It returns **READY_FOR_REVIEW**. The second asks for the same kind of read on `src/auth.py`. The catalog places that file in the excluded group, so the result is **INVALID**. Inspect the findings to see which rule applied. Both results contain `"authority_granted": false`.

| Example under examples/ | Expected result | What it exercises |
| --- | --- | --- |
| valid/read_docs.json | READY_FOR_REVIEW | Exact file at a known repository revision |
| clarification/cleanup.json | NEEDS_CLARIFICATION | No operation inferred from “clean up” |
| valid/update_docs.json | READY_FOR_REVIEW | Update scope with a reviewed exclusion |
| unsupported/admin.json | UNSUPPORTED | Unknown capability |
| invalid/protected.json | INVALID | Protected file requested explicitly |
| invalid/forged_approval.json | INVALID | Unrecognized approval field |
| invalid/duplicate_key.json | INVALID | Ambiguous input rejected during parsing |
| invalid/hidden_effect.json | INVALID | Extra structured effect rejected |
| valid/prose_mismatch.json | READY_FOR_REVIEW | Human review still needed to detect divergence between prose and structured scope |

## Try the same update at two organizations

Run `python -m examples.compare_policies` from the project root using the project environment. Both teams receive the same request to update `docs/guide.md`. The documentation team can send it for review. The release team places the guide in a reviewed group called `release-docs` and denies updates to that group. Its verdict is `INVALID`, with the reason `POLICY_CONFLICT`.

Compare the [documentation team's trusted settings](fixtures/demo-context.json) with the [release team's settings](fixtures/release-team-context.json). The change uses existing IIL capabilities. Each proposal names the policy and catalog it expects, so the two documents differ only in those references. The demo also submits the original proposal unchanged under the other team's settings and gets `CONTEXT_MISMATCH`. The operator supplies each bundle independently.

## What the verdict covers

The parser checks size, encoding, duplicate keys and nesting before the schema and semantic checks interpret the proposal. The validator resolves explicit capabilities and exact file identities against the caller's trusted context, then checks eligibility, organizational denials, task exclusions and evidence. Each result records the context versions used.

The CLI reads the proposal file supplied by its operator. File paths inside the proposal are identifiers compared against fixture data. The validator never opens those target files or performs GitHub operations. Review readiness does not certify intent fidelity, the live repository, credentials, approval or execution safety. Task Passports, Gateway mediation and the isolated operation broker are future components.

Read the [language specification](docs/IIL_SPEC.md), [threat model](docs/THREAT_MODEL.md), [proposal schema](schemas/iil-v0.1.schema.json), and [synthetic trusted context](fixtures/demo-context.json).
