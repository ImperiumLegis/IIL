# Verifying a public IIL release candidate

Run from a clean checkout of the candidate commit using Python 3.12. Install with `python -m pip install -r requirements-dev.txt` and run `python -m pytest -q`. The CI workflow also builds the source distribution and wheel on Linux and Windows and invokes the installed CLI from outside the checkout. CI artifacts belong to the commit that produced them.

## Checks for an independent reviewer

- Change one signed timestamp with the reviewer fixture key so the receipt has a valid signature over a lifetime of 899 or 901 seconds. The verifier must reject it.
- Change the enrolled binding between a valid challenge response and the final decision. Session matching must fail.
- Rotate the operator trust digest and restore the prior trust file. The old receipt must fail under the current digest.
- Submit a numeric field as a boolean, add an unexpected nested argument, change the MCP envelope or substitute the wrong manifest digest. The verifier must reject the call.
- Put a protected file second in an otherwise eligible update set. The result must withhold all before-text.
- Present an otherwise valid provider response with a moved branch, truncated tree, or mismatched Git blob hash. Snapshot resolution must fail.

Record the commit, tool versions, tests performed, findings, and reviewer affiliation. Publish an assessment only with the reviewer's approval. The current candidate has local engineering verification; the maintainers have yet to publish an independent assessment or a third-party production deployment.

## Publishing

The maintainer selects the release commit and version, records the changes in CHANGELOG.md, and verifies the artifacts from that commit. A public tag and GitHub release should identify the same commit. Keep the Gateway implementation and deployment credentials out of the distribution. The package version is defined by `imperium_iil.__version__`; schema and receipt format versions are protocol identifiers and evolve independently.

Maintainer access requires an actual contributor, their consent and an organization owner. A second commit identity, an automated review or a test installation does not establish a second maintainer or an independent deployment.
