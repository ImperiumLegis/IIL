"""Stable, non-authorizing validation results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    code: str
    pointer: str
    message: str
    status: str


class ValidationResult:
    def __init__(self, context, findings):
        self.context = {key: dict(ref) for key, ref in context.items()}
        self.findings = tuple(sorted(set(findings), key=lambda f: (f.pointer, f.code, f.message, f.status)))

    @property
    def status(self):
        statuses = {item.status for item in self.findings}
        for status in ("INVALID", "UNSUPPORTED", "NEEDS_CLARIFICATION"):
            if status in statuses:
                return status
        return "READY_FOR_REVIEW"

    @property
    def authority_granted(self):
        return False

    def as_dict(self):
        return {
            "validator_version": "0.1.0",
            "status": self.status,
            "authority_granted": False,
            "context": self.context,
            "findings": [{"code": f.code, "pointer": f.pointer, "message": f.message}
                         for f in self.findings],
        }
