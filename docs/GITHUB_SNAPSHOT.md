# Resolve an operator snapshot from GitHub

Use an independently reviewed context template with one snapshot. Supply the GitHub numeric repository ID and host `github.com`, the branch, the approved full commit SHA, evidence, group membership, eligibility and denials. The connector fills in the file inventory. The provider supplies file facts. The operator remains responsible for classification and policy at that commit.

```sh
iil-snapshot --context team-context.json --repository ORG/REPO --path docs/guide.md --baseline-format 2 > snapshot.json
iil review proposal.json --snapshot snapshot.json
```

Use a UTF-8 stdout redirect (for example bash or PowerShell 7.4+). Use baseline format 1 for legacy v0.2 reviews. The CLI also accepts separately protected `--context` and `--baseline` files. The snapshot must come from the operator.

The connector reads public repositories at api.github.com without credentials. It verifies repository identity and branch tip before using immutable commit, tree and blob IDs. It rejects a truncated recursive tree, unsupported catalog paths anywhere in the tree (including an unrelated filename with spaces), unreadable targets, malformed or oversized blobs and Git blob digest mismatches. The resulting context describes the pinned revision even if the branch subsequently moves. Re-review policy and classifications before adopting a new revision. This profile supports a bounded complete tree and one selected baseline file per invocation. [Git trees](https://docs.github.com/en/rest/git/trees) and [Git blobs](https://docs.github.com/en/rest/git/blobs).
