from app.risk.policy import RULES, allowed, is_critical, points, score_of, severity


def test_each_occurrence_adds_its_weight_up_to_the_types_cap():
    total = 0
    for _ in range(10):
        total += points("tab_switch", total)
    assert total == 30  # 6 points each, capped at 30: fifty tab switches cost no more than five


def test_a_capped_type_adds_nothing_more():
    assert points("tab_switch", 30) == 0 and points("tab_switch", 27) == 3


def test_confidence_scales_ai_findings():
    assert points("phone_detected", 0, scale=0.5) == 10 and points("phone_detected", 0, scale=1.0) == 20


def test_the_score_is_capped_at_100():
    assert score_of({"different_person": 40, "multiple_faces": 50, "terminated": 50}) == 100
    assert score_of({}) == 0


def test_severity_bands():
    assert [severity(s, clear_max=25, flag_min=50) for s in (0, 25, 26, 49, 50, 100)] == ["low", "low", "medium", "medium", "high", "high"]


def test_a_basic_session_takes_no_camera_or_ai_events_and_clients_cannot_report_ai_findings():
    assert allowed("tab_switch", "client", "basic") and allowed("camera_off", "client", "strict")
    assert not allowed("camera_off", "client", "basic")
    assert not allowed("multiple_faces", "client", "strict")  # only the analysis path may raise a finding
    assert allowed("multiple_faces", "ai", "strict") and not allowed("multiple_faces", "ai", "basic")
    assert not allowed("nonsense", "client", "strict") and not allowed("terminated", "client", "strict")


def test_the_events_that_always_need_a_human_are_marked_critical():
    assert {name for name in RULES if is_critical(name)} == {"terminated", "multiple_faces", "different_person", "identity_mismatch"}


def test_every_weight_is_within_its_cap():
    assert all(rule.weight <= rule.cap or rule.cap == 0 for rule in RULES.values())
