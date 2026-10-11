from audit_engine import build_audit_report, make_sample_report


def test_synthetic_demo_exposure_is_7000_without_api():
    report = make_sample_report(covered_days=1)
    assert report["total_billed"] == 27000
    assert report["potential_exposure"] == 7000
    by_category = {f["category"]: f["potential_exposure"] for f in report["findings"]}
    assert by_category["room_limit"] == 5000
    assert by_category["duplicate"] == 2000


def test_room_cap_scales_with_covered_days():
    report = make_sample_report(covered_days=2)
    # INR 15,000 room charges are below the INR 20,000 two-day cap.
    assert not any(f["category"] == "room_limit" for f in report["findings"])
    assert report["potential_exposure"] == 2000  # only the suspected duplicate remains


def test_unverified_policy_quote_does_not_trigger_room_limit():
    items = [{"description": "Room Charges", "quantity": 1, "unit_price": 15000, "total": 15000, "category": "room", "page": 1}]
    rules = [{"rule_type": "room_daily_limit", "description": "Room cap", "amount_limit": 10000,
              "target_keywords": ["room"], "page": 9, "quote": "A made-up quote", "confidence": "high"}]
    report = build_audit_report(items, rules, covered_days=1, policy_text="[PAGE 1] Real policy text", notes=[])
    assert report["potential_exposure"] == 0
    assert not any(f["category"] == "room_limit" for f in report["findings"])
    assert any("could not be verified" in note for note in report["audit_notes"])


def test_arithmetic_check_calculates_excess_deterministically():
    items = [{"description": "Lab test", "quantity": 2, "unit_price": 100, "total": 300, "category": "lab", "page": 1}]
    report = build_audit_report(items, [], policy_text="", notes=[])
    assert report["potential_exposure"] == 100
    assert report["findings"][0]["category"] == "arithmetic"


def test_overlapping_findings_are_not_double_counted():
    quote = "Vitamin supplements are excluded unless explicitly approved."
    items = [{"description": "Vitamin supplement", "quantity": 2, "unit_price": 100, "total": 250, "category": "medication", "page": 1}]
    rules = [{"rule_type": "excluded_service", "description": "Vitamin supplements excluded", "amount_limit": None,
              "target_keywords": ["vitamin"], "page": 1, "quote": quote, "confidence": "high"}]
    report = build_audit_report(items, rules, policy_text=f"[PAGE 1]\n{quote}", notes=[])
    # Arithmetic exposure is 50, and the excluded-service finding may use only the remaining 200.
    assert report["potential_exposure"] <= 250
    assert report["potential_exposure"] == 250
