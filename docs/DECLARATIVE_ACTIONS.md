# Add an action to IIL

A support team can define a reply and restrict its recipients without writing Python. Copy the [email action directory](../examples/actions/email) to an operator-controlled folder. Keep registered files and their directory writable only by trusted administrators. The agent can supply its proposal and call.

## Run a local review

Use the project's Python 3.12 environment with the pinned requirements. Set PYTHONPATH to the absolute IIL checkout if running from outside it. From your copied action directory, with the demo-reviewer encrypted key and public trust file from the [signed review walkthrough](../README.md#verify-a-signed-review-in-another-process), run:

```powershell
python -m imperium_iil.actions --root . --registry registry.json --policy policy.json --trust "$demo/trust.json" --key "$demo/signer.pem" --reviewer demo-reviewer --requester agent --proposal proposal.json --call call.json --out reviewed.json
```

Unlock the key, read the complete recipient lists and message, and type `APPROVE`. The command launches a fresh, disposable requester process under the identity selected by the operator. It verifies possession of the session key over a private channel. Success returns `SESSION_CALL_MATCHED` and exit 0. Repeat with `--call extra-bcc.json` and a new output filename. The reviewed reply is eligible, but the submitted call adds Bob and returns `SESSION_CALL_REJECTED` with exit 1. The optional output is the signed approval of the proposal and may exist even when the call fails. Every result keeps `authority_granted` false.

## Define your own files

- **Manifest.** Give the action a lowercase dotted ID, a version, a unique tool name, and a map of required fields. A `string` has `min` and `max` UTF-8 byte lengths. A `list` adds `least` and `most` item counts, and applies the string lengths to each item. Bounds are unsigned decimal strings. Supported text includes printable ASCII, tabs and newlines. Empty strings and lists require minimum zero. All fields and list order participate in review.
- **Registry.** Version `"1"` entries contain `action`, `version`, `file` and `sha256`. Use a simple local JSON basename and lowercase SHA-256 of the exact file bytes. PowerShell can compute this with `(Get-FileHash ./reply.json -Algorithm SHA256).Hash.ToLowerInvariant()`. Changing a manifest requires updating both the registry pin and the permission pin. Limits are 64 manifests, 32 fields per action, 64 items per list, 16 KiB per string, and 64 KiB per input.
- **Policy.** Select an organization and name its groups and permissions. Each permission contains the action/version/digest, explicit requester and reviewer ID lists, and a map of field names to group names. Every value in each constrained field must belong to its group. Both participants need the same permission. The reviewer trust file enrolls public keys; reviewers with empty repository grants can review extension actions under the extension policy.
- **Proposal.** Name the action, version, permission and complete arguments. The operator independently supplies trust, policy, registry and requester identity.
- **Call.** Supply the tool name and complete arguments. IIL checks exact equality of decoded values. Additional or missing fields reject the call. Data files cannot run code, import modules or fetch schemas.

Use the same command with a different manifest and policy for another action. This profile checks closed synthetic tool requests offline. Connecting a real provider requires accounting for its defaults and side effects. The disposable walkthrough assumes an operator-controlled launcher, configuration, clock and terminal. It performs no email delivery or CRM writes.
