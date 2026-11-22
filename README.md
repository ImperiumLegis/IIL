# Imperium Intent Language (IIL)

Imperium Intent Language is the proposal and review core of **Imperium Legis**. It gives an agent a precise way to say what it wants to do, an organization a way to check that request against its rules, and a reviewer a record of the exact edit they approved.

Consider the instruction “Read the README and leave the authentication files alone.” Someone has to decide which repository you meant, which revision of the README to read, and which files count as authentication files. IIL gives those details a place in the proposal or the organization’s resource catalog. If the agent asks for a file in the excluded group, the reviewer can see exactly which rule blocked the request.

This repository contains the Python library, command-line tools, schemas, and working offline examples. You can use the core independently in your own agent workflow. Within the larger Imperium Legis project, the planned Gateway and isolated operation broker will handle authorization checks at execution time and access to service credentials. The core shipped here stops at review. Every result carries `authority_granted: false`.

## How a request moves through IIL

1. **Describe the task.** The agent or its host application submits a JSON proposal. Each file operation identifies an action, repository, branch, revision, and path. A reviewer can compare those fields with the original instruction. “Clean up the docs” alone leaves too much open to infer an operation.
2. **Check the organization’s rules.** The operator supplies a trusted snapshot of the repository and its policy independently of the proposal. IIL checks the input’s size, encoding, nesting, and duplicate keys, then validates its structure. It looks up the target, checks eligibility, restrictions, denials, and evidence, and returns a verdict with findings and context versions.
3. **Inspect the edit.** For an exact update to one existing file, the reviewer sees the old text, the complete replacement, and a line diff. IIL computes a fingerprint over the proposal, trusted context, and original-text fixture. Changing even one digit in the proposed text changes that fingerprint.
4. **Record the decision.** A reviewer can confirm an edit in one terminal session or sign a receipt that another process can verify for 15 minutes. The verifier checks the signature, current reviewer permissions, time window, and exact edit. The decision can travel with the proposal while the signing key stays with the reviewer.

## Using the core in another project

A host application can submit the same proposal format through the CLI or call the Python library directly. For scope checks, load your operator-controlled bundle with `load_context(raw)` and pass it to `validate(proposal_bytes, context)`. For an exact update, call `review_update(proposal_bytes, context_bytes, baseline_bytes)`. Your organization defines its repository catalog, file groups, and policies within the supported schema. The proposal names the context it expects. The operator chooses which context to trust. [Library reference and schemas](docs/IIL_SPEC.md)

The examples model GitHub files at a specific revision. Paths in a proposal are identifiers in the supplied snapshot. Running the CLI reads the input files you select and performs its checks locally, without a GitHub account or service credentials. The operator is responsible for the snapshot’s accuracy. A human reviewer is responsible for judging whether the structured request reflects the user’s intent. [Threat model](docs/THREAT_MODEL.md)

## Set up and run the tests

From the repository root on Windows with Python 3.12 installed, run the following in PowerShell. If Python is outside your PATH, substitute its absolute path for `py -3.12`, for example `& "path-to-python.exe" -m venv .venv`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe examples/run_demo.py
.\.venv\Scripts\python.exe -m examples.compare_policies
.\.venv\Scripts\python.exe -m imperium_iil validate examples/valid/read_docs.json
.\.venv\Scripts\python.exe -m imperium_iil validate examples/invalid/protected.json
.\.venv\Scripts\python.exe -m pytest -q
```

On Linux or macOS, create the environment with `python3.12 -m venv .venv` and use `.venv/bin/python` for the subsequent commands. Installation requires a package index or local wheel cache. For the runtime alone, install `requirements.txt`. Later examples use `python` as shorthand for the interpreter in this environment.

### Read the two verdicts

The first `validate` command asks to read `README.md` and excludes the authentication group. It returns `READY_FOR_REVIEW`. The second asks to read `src/auth.py`, which the catalog places in that group. It returns `INVALID` (exit code 4). That rejection is the expected demo result. Inspect the findings to see why the rule applied.

| Proposal under `examples/` | Expected verdict | What to look for |
| --- | --- | --- |
| `valid/read_docs.json` | `READY_FOR_REVIEW` | One specific file at a known revision |
| `clarification/cleanup.json` | `NEEDS_CLARIFICATION` | An open-ended task with no specified operation |
| `valid/update_docs.json` | `READY_FOR_REVIEW` | Update scope with an explicit exclusion |
| `unsupported/admin.json` | `UNSUPPORTED` | An unknown capability |
| `invalid/protected.json` | `INVALID` | A requested file in an excluded group |
| `invalid/forged_approval.json` | `INVALID` | An unrecognized approval field |
| `invalid/duplicate_key.json` | `INVALID` | Two values competing for the same JSON key |
| `invalid/hidden_effect.json` | `INVALID` | An extra structured effect |
| `valid/prose_mismatch.json` | `READY_FOR_REVIEW` | A reviewer still needs to catch the mismatch between the prose and the operation |

## Try the same update at two organizations

Run `python -m examples.compare_policies` in the project environment. Both teams receive a request to update `docs/guide.md`. The documentation team can send the update for review. The release team places the guide in its `release-docs` group and denies updates to that group. Its result is `INVALID` with a `POLICY_CONFLICT` finding.

The two proposals differ only in the policy and catalog references they expect. The demo also submits the documentation team’s proposal unchanged under the release team’s settings. IIL reports `CONTEXT_MISMATCH`, making the switch visible to the reviewer. Compare the [documentation team’s settings](fixtures/demo-context.json) and the [release team’s settings](fixtures/release-team-context.json).

## Compare two exact guide edits

The v0.1 `validate` command checks the scope of an operation. The v0.2 `review` command adds the complete replacement text for a single file update. To see what the reviewer sees, run both proposals.

```console
python -m imperium_iil review examples/exact-update/guide-a.json
python -m imperium_iil review examples/exact-update/guide-b.json
```

Both propose editing the same revision of `docs/guide.md` under the same draft ID. Guide A says `Run step 1 from the repository root.` followed by a newline. Guide B changes the digit to `2`. Both are eligible for review. Compare `review.before`, `review.after`, and `review.diff` to find the change. JSON displays the final newline as `\n`. The `review.fingerprint` values differ. Rerunning either command with the same inputs reproduces its fingerprint. [Original text](fixtures/demo-before-text.json) · [Exact-update context](fixtures/exact-update-context.json)

## Confirm one edit in a local terminal

Run each command and inspect the target, revision, old text, and replacement. Type `APPROVE` to compare the preview with the submitted edit.

```powershell
python -m imperium_iil.approval examples/exact-update/guide-a.json examples/exact-update/guide-a.json
python -m imperium_iil.approval examples/exact-update/guide-a.json examples/exact-update/guide-b.json
```

The first comparison returns `APPROVAL_MATCHED` and exits with code zero. The second previews guide A and submits guide B, so it returns `FRESH_REVIEW_REQUIRED`. Each command reads the submitted proposal and trusted fixtures again. Confirmation lasts for that comparison. This mode relies on the operator controlling the terminal, process, and fixtures. For an approval tied to an enrolled reviewer’s key, use a signed receipt.

## Verify a signed review in another process

In a local PowerShell terminal with the pinned requirements installed, create a disposable reviewer in a new directory under your user temp folder. Choose a demo passphrase when prompted.

```powershell
$demo = Join-Path ([IO.Path]::GetTempPath()) ("iil-receipt-" + [guid]::NewGuid())
python -m examples.setup_receipt_demo $demo
python -m imperium_iil.receipt issue examples/exact-update/guide-a.json --trust "$demo/trust.json" --reviewer demo-reviewer --key "$demo/signer.pem" --out "$demo/receipt.json"
```

Unlock the key, inspect the repository identity, time window, and replacement, then type `APPROVE`. The signer refuses to overwrite an existing receipt. Now run each verification in a fresh process.

```powershell
python -m imperium_iil.receipt verify examples/exact-update/guide-a.json --trust "$demo/trust.json" --receipt "$demo/receipt.json"
python -m imperium_iil.receipt verify examples/exact-update/guide-b.json --trust "$demo/trust.json" --receipt "$demo/receipt.json"
```

Guide A returns `APPROVAL_VERIFIED` during the 15-minute window. Guide B returns `APPROVAL_REJECTED` and exits with code 1. At the expiry second, both fail. A verifier can check a receipt more than once while it is valid.

The submitting party supplies the proposal and receipt. The verifier’s operator supplies the current organization trust file, trusted context, original text, and clock. The demo uses synthetic fixtures by default. Use `--context` and `--baseline` to select your own. The signature proves possession of the enrolled key. The organization authenticates reviewers at enrollment, protects signing keys, and distributes the trust file. Removing a key or grant takes effect when the verifier receives the update. Detecting a rolled-back trust file and enforcing one-time execution remain future work.

## Compare a tool call with a signed edit

Use the guide A receipt from the walkthrough above while it is valid. The proposal records what the reviewer approved. The separate call file records what the demo tool was asked to do. Run both comparisons in the same PowerShell environment.

```powershell
python -m imperium_iil.match_call examples/exact-update/guide-a.json --receipt "$demo/receipt.json" --trust "$demo/trust.json" --call examples/tool-calls/guide-a.json
python -m imperium_iil.match_call examples/exact-update/guide-a.json --receipt "$demo/receipt.json" --trust "$demo/trust.json" --call examples/tool-calls/guide-b.json
```

The first call requests the signed “Run step 1” edit and returns `TOOL_CALL_MATCHED` (exit 0). The second requests “Run step 2” and returns `TOOL_CALL_REJECTED` (exit 1). The matcher checks the complete synthetic call, including the provider host, repository ID, branch, base revision, case-sensitive path, and replacement text through the final newline. An unknown option also rejects the call. Each result applies to the supplied files and current trust snapshot and carries `authority_granted: false`. Live tool interception and execution remain future Gateway work.

## Bind an approval to one running requester

Run the disposable two-process example in the project environment:

```powershell
python -m examples.session_demo
```

A synthetic reviewer signs a 15-minute receipt for session A. A and B belong to the same demo requester and hold separate in-memory keys. The approved session returns `SESSION_CALL_MATCHED`. B claiming A's identity, a recorded response, and a restarted requester each return `SESSION_CALL_REJECTED`.

For a human-reviewed v2 receipt, use the existing signing walkthrough with `issue-session` in place of `issue` and supply `--sessions PATH --session ID`. The launcher must independently enroll the public session key and retire its binding when the process ends. Inspect the requester, session ID and key fingerprint when confirming. The session verifier requires this receipt version and uses a fresh challenge for each comparison, with up to 60 seconds to respond within the receipt lifetime.

The offline verifier checks possession of the enrolled key and rechecks current reviewer trust, policy, enrollment and expiry before returning a match. The operator controls the launcher, clock, trust sources and private communication channel. Key theft, a live signing relay, runtime interception and execution are outside this check. All outcomes keep `authority_granted` false.

## Project and license

Created by [@oneezeeroo](https://github.com/oneezeeroo), founder of **Imperium Legis**, a project of **Provenance Supply LLC**. IIL is available under the [MIT License](LICENSE).

[Language specification](docs/IIL_SPEC.md) · [Threat model](docs/THREAT_MODEL.md) · [Scope proposal schema](schemas/iil-v0.1.schema.json) · [Exact-update schema](schemas/iil-v0.2.schema.json) · [Sample trusted context](fixtures/demo-context.json)
