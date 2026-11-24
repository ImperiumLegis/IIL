# Pin the reviewer trust file

An operator can pin the exact reviewer trust file accepted by a verifier. After a key or grant is revoked, a verifier configured with the new digest rejects a restored copy of the old file, even when the old file and receipt are otherwise valid.

## Configure the pin

1. On the trusted enrollment machine, approve the trust file and compute its SHA-256 digest. In PowerShell, run `(Get-FileHash ./trust.json -Algorithm SHA256).Hash`.
2. Distribute those 64 hex digits through an authenticated operator channel. Keep the expected value in verifier configuration protected independently of the trust file, proposal, receipt and requester. Computing a fresh pin from the candidate file during verification would accept whatever version was presented.
3. Supply the approved digest alongside the path. For example, if the launcher sets `IIL_APPROVED_TRUST_SHA256` from its protected configuration, use the following PowerShell command from the checkout.

```powershell
python -m imperium_iil.receipt verify examples/exact-update/guide-a.json --receipt reviewed.json --trust trust.json --trust-sha256 "$env:IIL_APPROVED_TRUST_SHA256"
```

The same `--trust-sha256` option applies to `receipt issue`, `receipt issue-session`, `match_call` and `actions`. Python callers of `check_session` set `paths.trust_sha256` to the approved digest. Callers supplying a trust object to `authenticate` or `verified_review` can construct it with `load_trust(raw_bytes, expected_sha256=pin)`. The signer rechecks the file after interactive confirmation. Both session matchers recheck it after the requester responds.

## Rotate or revoke

Create and approve a replacement file, compute its digest, then deploy the file and the new pin together. While they disagree, pinned operations reject. Restart launchers holding the previous configuration so subsequent operations use the new pin. Record the approved digest in protected deployment history for later inspection.

The pin covers every byte, including whitespace and line endings. Uppercase and lowercase hexadecimal are accepted. Omitting the pin preserves the original operator-selected file behavior. Anyone able to roll back both the file and its protected configuration can restore an earlier trust decision. This mechanism relies on the operator for freshness and distribution. It covers reviewer enrollment and repository grants only. Context, baseline, action policy and session enrollment have their own trust requirements. Receipts can still be presented again within their lifetime.
