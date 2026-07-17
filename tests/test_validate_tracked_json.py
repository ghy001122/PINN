from scripts.validate_tracked_json import validate_tracked_json


def test_all_tracked_json_is_strictly_parseable() -> None:
    summary = validate_tracked_json()
    assert summary["status"] == "pass"
    assert summary["failure_count"] == 0
