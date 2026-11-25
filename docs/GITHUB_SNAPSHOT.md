# Resolve an operator snapshot from GitHub

Use an independently reviewed context template with one snapshot. Supply the GitHub numeric repository ID and host `github.com`, the branch, the approved full commit SHA, evidence, group membership, eligibility and denials. The connector fills in the file inventory. The provider supplies file facts. The operator remains responsible for classification and policy at that commit.

```sh
iil-snapshot --context team-context.json --repository ORG/REPO --path docs/guide.md --baseline-format 2 > snapshot.json
iil review proposal.json --snapshot snapshot.json
```

Use a UTF-8 stdout redirect (for example bash or PowerShell 7.4+). Use baseline format 1 for legacy v0.2 reviews. The CLI also accepts separately protected `--context` and `--baseline` files. The snapshot must come from the operator.

Public reads use anonymous HTTPS by default. For a private repository, have the operator's launcher or secret manager set `IIL_GITHUB_TOKEN`, then add `--authenticated` to the snapshot command. Scope a fine-grained token to the intended repository with Contents read access. The connector sends the token only in GET request headers to `api.github.com`. It rejects redirects. The resulting bundle contains the selected file's contents, so distribute private snapshots only to their intended reviewers. [GitHub permissions for reading blobs](https://docs.github.com/en/rest/git/blobs#get-a-blob)

The connector verifies repository identity and branch tip before using immutable commit, tree and blob IDs. It rejects truncated recursive trees, malformed paths, duplicate tree entries, unreadable targets, oversized blobs and Git blob digest mismatches. It omits filenames outside IIL's path grammar, such as an unrelated filename containing a space, without renaming or normalizing them. Selected files and policy inventory references must remain representable. The resulting context describes the pinned revision even if the branch subsequently moves. Re-review policy and classifications before adopting a new revision. Each invocation produces one baseline file. [Git trees](https://docs.github.com/en/rest/git/trees) and [Git blobs](https://docs.github.com/en/rest/git/blobs).
