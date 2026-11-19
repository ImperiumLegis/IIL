# Imperium Intent Language v0.1 preview

What should happen when an agent asks to update a file that one team maintains and another team protects? IIL makes the proposed operation explicit and lets each organization supply its own reviewed policy.

In the included offline demo, both teams see the same proposed update to `docs/guide.md`. The documentation team makes that update eligible for review. The release team includes the guide in a protected group. The validator reports `INVALID` with `POLICY_CONFLICT` for the release team. Switching the original proposal to the other team's context produces `NEEDS_CLARIFICATION` because the policy references no longer match.

After [setting up the environment](../README.md), run:

```powershell
.\.venv\Scripts\python.exe -m examples.compare_policies
```

The preview includes a Python library, CLI, two versioned JSON schemas, synthetic organization settings, automated tests and nine additional examples. Every verdict carries `authority_granted: false`. A ready proposal can go to an independent reviewer. Actual access control, credential isolation and runtime enforcement are future milestones. See the [threat model](THREAT_MODEL.md) for assumptions and limitations.
