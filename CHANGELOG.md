# Changelog

## 0.3.0

- Package the review core as an installable Python distribution with an `iil` command and bundled schemas and demo fixtures.
- Define invisible-character handling for exact UTF-8 review, extend email and path allowlists, and support MCP request metadata and omitted arguments.
- Select trusted context and before-text explicitly on the CLI.
- Resolve GitHub tree and blob data against an operator-pinned revision with optional authenticated reads. Verify same-length content substitutions against the Git blob digest.
- Run unit tests and installed-wheel smoke tests in continuous integration.

- Add bounded typed manifests, standing-policy evaluation, MCP and OpenAI Chat call decoding, and a draft pull-request example.
- Add UTF-8 exact updates and all-or-nothing multi-file review.
- Show task text during signing and accept an independently protected reviewer trust digest.
- Add regression cases for receipt lifetimes and requester binding changes during a proof.

## Public core at b168f84

Declarative action manifests, policy grants, signed review receipts, and requester session matching. This commit identifies the GitHub baseline for the changes above.
