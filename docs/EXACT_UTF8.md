# UTF-8 exact file review

Use proposal version `0.3` to review the complete new contents of one existing regular file. Run the example from the project root.

```console
python -m imperium_iil review examples/exact-update/guide-utf8.json
```

The proposed greeting contains accented letters, a joined emoji, and a final CRLF. The review shows the task, target, complete before and after text, UTF-8 byte counts and SHA-256 digests. The terminal and CLI render the text as ASCII JSON escapes so tabs, line endings and non-ASCII characters have visible, unambiguous spellings. The Python API returns the decoded strings. Clients displaying them to a reviewer should use the same escaping.

| Property | Proposal 0.2 | Proposal 0.3 |
| --- | --- | --- |
| Maximum decoded bytes per file | 16 KiB | 256 KiB |
| Maximum raw proposal or tool call | 64 KiB | 2 MiB |
| Text | Printable ASCII, tab, LF | UTF-8 scalar values, tab, LF and CRLF |
| Before-text inventory format | `1` | `1` or `2` |
| Review artifact and tool call version | `1` | `2` |

Each before-text inventory has a 1 MiB JSON limit. Inventory format `1` keeps its ASCII and 16 KiB limits in both proposal profiles. To supply Unicode baseline data, set the operator inventory's `format_version` to `"2"`. The exact-update registry continues to use version `0.2` because both profiles use the same file capabilities.

Version 0.3 preserves UTF-8 bytes after JSON string decoding. A literal emoji and its JSON surrogate-pair escape decode to the same content. A CRLF and an LF produce distinct bytes, as do precomposed and decomposed accents. The validator rejects unpaired surrogates, lone CR, other C0/C1 control characters, and Unicode bidi controls. It preserves the zero-width joiner used in emoji sequences. It applies no Unicode or newline normalization.

The version 0.3 proposal limits each array and object to 64 entries and the entire document to 4,096 values, counting the root and excluding property names. The reviewer includes a unified diff when each side has at most 512 lines. Above that threshold, `diff_omitted` is `LINE_LIMIT`, and the full before and after strings and digests remain available.

For a format 2 review fingerprint, use the format 1 framing from the IIL specification with the first framed field set to the ASCII byte `2`. It covers the original proposal, context, and baseline bytes. Reformatting the proposal JSON therefore changes a receipt's fingerprint even when the decoded file bytes match. The signed and session-bound comparators require a version `2` tool-call envelope for a version `0.3` proposal, and compare the decoded replacement bytes and target exactly.
