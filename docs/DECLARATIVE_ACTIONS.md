# Add an action to IIL

A support team can define a reply and restrict its recipients without writing Python. Copy the [email action directory](../examples/actions/email) to an operator-controlled folder. Keep registered files and their directory writable only by trusted administrators. The agent can supply its proposal and call.

## Run a local review

Use the project's Python 3.12 environment with the pinned requirements. Set PYTHONPATH to the absolute IIL checkout if running from outside it. From your copied action directory, with the demo-reviewer encrypted key and public trust file from the [signed review walkthrough](../README.md#verify-a-signed-review-in-another-process), run:

```powershell
python -m imperium_iil.actions --root . --registry registry.json --policy policy.json --trust "$demo/trust.json" --key "$demo/signer.pem" --reviewer demo-reviewer --requester agent --proposal proposal.json --call call.json --out reviewed.json
```

Unlock the key, read the complete recipient lists and message, and type `APPROVE`. The command launches a fresh, disposable requester process under the identity selected by the operator. It verifies possession of the session key over a private channel. Success returns `SESSION_CALL_MATCHED` and exit 0. Repeat with `--call extra-bcc.json` and a new output filename. The reviewed reply is eligible, but the submitted call adds Bob and returns `SESSION_CALL_REJECTED` with exit 1. The optional output is the signed approval of the proposal and may exist even when the call fails. Every result keeps `authority_granted` false.

## Define your own files

- **Manifest.** Give the action a lowercase dotted ID, a version, a unique tool name, and a map of required fields. Manifests without `format_version` use format 1. A `string` has `min` and `max` UTF-8 byte lengths. A `list` adds `least` and `most` item counts and applies the string lengths to each item. Bounds are unsigned decimal strings. Supported text includes printable ASCII, tabs and newlines. Empty strings and lists require minimum zero. All fields and list order participate in review.
- **Registry.** Version `"1"` entries contain `action`, `version`, `file` and `sha256`. Use a simple local JSON basename and lowercase SHA-256 of the exact file bytes. PowerShell can compute this with `(Get-FileHash ./reply.json -Algorithm SHA256).Hash.ToLowerInvariant()`. Changing a manifest requires updating both the registry pin and the permission pin. Limits are 64 manifests, 32 fields per action, 64 items per list, 16 KiB per string, and 64 KiB per input.
- **Policy.** Select an organization and name its groups and permissions. Each permission contains the action/version/digest, explicit requester and reviewer ID lists, and a map of field names to group names. Every value in each constrained field must belong to its group. Both participants need the same permission. The reviewer trust file enrolls public keys; reviewers with empty repository grants can review extension actions under the extension policy.
- **Proposal.** Name the action, version, permission and complete arguments. Add an optional `"task": {"description": "Reply about ticket 42."}` to show the requester's stated purpose to the reviewer. It accepts 1–1024 characters of supported text and must contain a non-whitespace character. The reviewer reads it alongside the concrete tool and arguments. The signed snapshot binds the complete proposal, including this text. The operator independently supplies trust, policy, registry and requester identity.
- **Call.** Supply the tool name and complete arguments. IIL checks exact equality of decoded values. Additional or missing fields reject the call. Data files cannot run code, import modules or fetch schemas.

Use the same command with a different manifest and policy for another action. This profile checks closed synthetic tool requests offline. Connecting a real provider requires accounting for its defaults and side effects. The disposable walkthrough assumes an operator-controlled launcher, configuration, clock and terminal. It performs no email delivery or CRM writes.

## Model nested arguments with manifest format 2

Set `"format_version": "2"` on the manifest. Keep the action's own `version` and the registry's `version` independent. Every declared object key is required, including keys on each object in an array. Unknown keys reject the proposal or call at any depth. The parser limits each input to 64 KiB and 16 levels of JSON containers.

| Field type | Required specification | Accepted value |
| --- | --- | --- |
| `string` | `min`, `max` as unsigned decimal strings | Supported text within the inclusive byte bounds. An optional `pattern` can narrow it. |
| `boolean` | Only `type` | JSON `true` or `false`. |
| `enum` | `values` | One of 1–64 distinct strings, each at most 256 characters of supported text. |
| `integer` | JSON integers `min`, `max` | An integer token in the inclusive range. |
| `number` | JSON numbers `min`, `max` | An integer or decimal in the inclusive range. |
| `object` | `fields` | An object with exactly the declared fields, between 1 and 32 per object. |
| `array` | `least`, `most` as unsigned decimal strings and an `items` field specification | An ordered array of 0–64 items within the declared bounds. Each item is checked. |

The numeric profile accepts finite JSON numbers with magnitude at most 9,007,199,254,740,991. Decimal tokens support at most six fractional places after applying the exponent and must round-trip through the JSON number used for display without changing their decimal value. Number tokens are limited to 32 characters and exponents to two digits. Negative zero rejects. The comparison distinguishes integers from decimal or exponent tokens. For example, `2.50` and `2.5` match, while `2` and `2.0` differ. Quoted numbers and booleans never satisfy numeric fields.

### Restrict fields inside an array

Format 2 permissions use slash-separated field paths. A `*` path segment visits **every element** of an array. Literal segments select declared object fields. An empty array has no elements to check. Use a positive `least` on the array if the action requires an item. Each rule acts in addition to the manifest and both participants' permission grants.

```json
{
  "/tickets/*/hours": {"min": 0, "max": 8},
  "/tickets/*/team": {"pattern": "team-east-*"},
  "/tickets/*/priority": "priorities",
  "/tickets/*/notify": {"equals": false}
}
```

The group name limits a string or enum to exact group members. Numeric bounds are inclusive. A boolean rule fixes the required value. String patterns match the whole value and support one optional `*` with at least one literal character elsewhere. Within a string, `*` consumes one or more ASCII letters, digits, underscores or hyphens. Other permitted pattern characters are literal letters, digits, `_`, `@`, `.`, `/`, `:` and `-`. Patterns are limited to 128 characters. Thus `team-east-*` accepts `team-east-ops` and rejects both `team-east-` and `team-east-ops/admin`.

## Compare a tool-call envelope

The [ticket example](../examples/actions/ticket) includes a pinned nested manifest, a policy, a proposal and two representations of the same tool call. From that directory, with the reviewer files from the walkthrough, run either command.

```powershell
python -m imperium_iil.actions --root . --registry registry.json --policy policy.json --trust "$demo/trust.json" --key "$demo/signer.pem" --reviewer demo-reviewer --requester agent --proposal proposal.json --call mcp.json --call-format mcp
python -m imperium_iil.actions --root . --registry registry.json --policy policy.json --trust "$demo/trust.json" --key "$demo/signer.pem" --reviewer demo-reviewer --requester agent --proposal proposal.json --call openai-chat.json --call-format openai-chat
```

- `iil` accepts the existing object with `tool` and `arguments`. It is the default.
- `mcp` accepts one JSON-RPC 2.0 `tools/call` request with an integer or identifier `id` and exactly `name` and `arguments` in `params`. [MCP tool request](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- `openai-chat` accepts one Chat Completions function tool-call item with an identifier `id`, `type` equal to `function`, and a `function` object containing `name` and a JSON-encoded `arguments` string. The inner JSON receives the same size, depth, duplicate-key and numeric checks. [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)

These adapters accept only the fields listed above. Batches, metadata and extra provider options reject. The operator selects the format and the signer sees it alongside all reviewed arguments. The review snapshot binds the adapter selection, proposal, manifest and policy. The requester proof covers the exact submitted envelope bytes, including the correlation ID. Matching only compares the supplied data offline.
