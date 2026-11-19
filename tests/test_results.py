from imperium_iil.results import Finding, ValidationResult


def test_invalid_wins_and_identical_findings_appear_once():
    invalid = Finding("CONFLICT", "/operations/0", "Restricted operation.", "INVALID")
    unknown = Finding("UNKNOWN", "/operations/1", "Unknown scope.", "NEEDS_CLARIFICATION")
    result = ValidationResult({}, [unknown, invalid, invalid])
    assert result.status == "INVALID"
    assert result.authority_granted is False
    assert list(result.findings) == [invalid, unknown]
