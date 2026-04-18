from sentinel.call_handler import build_check_in_twiml


def test_twiml_still_ok():
    xml = build_check_in_twiml(patient_name="X", action_url="http://x")
    assert "X" in xml
