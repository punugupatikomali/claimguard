"""Synthetic demo claims. Each runs through the real rules engine, so no API call is needed."""
from __future__ import annotations
from typing import Any
from audit_engine import build_audit_report

POLICY_NAME = "ShieldCare Gold Health Policy (synthetic)"
ROOM_CLAUSE = "Room rent is covered up to INR 5,000 per day for a standard private room."
VITAMIN_CLAUSE = "Vitamins, tonics and nutritional supplements are excluded unless prescribed as part of active treatment."
NON_MEDICAL_CLAUSE = "Non-medical items such as toiletries, attendant food and admission kits are not covered."
POLICY_TEXT = (
    "[PAGE 1]\nSYNTHETIC DEMONSTRATION POLICY — SHIELDCARE GOLD\nSection 4.2 — Room rent\n" + ROOM_CLAUSE +
    "\n\n[PAGE 2]\nSection 7.1 — Permanent exclusions\n" + VITAMIN_CLAUSE +
    "\nSection 7.3 — Non-medical expenses\n" + NON_MEDICAL_CLAUSE
)
POLICY_RULES = [
    {"rule_type": "room_daily_limit", "description": "Room rent capped at INR 5,000 per day", "amount_limit": 5000,
     "target_keywords": ["room"], "page": 1, "quote": ROOM_CLAUSE, "confidence": "high"},
    {"rule_type": "excluded_service", "description": "Vitamins, tonics and supplements excluded", "amount_limit": None,
     "target_keywords": ["vitamin", "tonic", "supplement"], "page": 2, "quote": VITAMIN_CLAUSE, "confidence": "high"},
    {"rule_type": "not_covered", "description": "Non-medical consumables not covered", "amount_limit": None,
     "target_keywords": ["toiletries", "attendant food", "admission kit"], "page": 2, "quote": NON_MEDICAL_CLAUSE, "confidence": "high"},
]


def _item(description: str, quantity: float, unit_price: float, category: str, service_date: str, total: float | None = None) -> dict[str, Any]:
    return {"description": description, "service_date": service_date, "quantity": quantity, "unit_price": unit_price,
            "total": quantity * unit_price if total is None else total, "category": category, "page": 1}


SCENARIOS: dict[str, dict[str, Any]] = {
    "room_cap": {
        "title": "Room Rent Over Policy Cap",
        "subtitle": "Deluxe room billed at INR 8,500/day against a INR 5,000/day limit",
        "claim_info": {"invoice_number": "CLM-2026-10421", "provider": "Sunrise Multispeciality Hospital",
                       "bill_date": "2026-08-06", "admission_date": "2026-08-03", "discharge_date": "2026-08-06"},
        "bill_items": [
            _item("Room Rent - Deluxe Room", 3, 8500, "room", "2026-08-03"),
            _item("Consultation - Physician visit", 3, 1200, "consultation", "2026-08-03"),
            _item("Complete Blood Count", 1, 650, "lab", "2026-08-03"),
            _item("IV Fluids - Normal Saline", 6, 320, "medication", "2026-08-04"),
            _item("Pharmacy - Discharge medicines", 1, 4280, "medication", "2026-08-06"),
        ],
    },
    "duplicate": {
        "title": "Duplicate Billing Pattern",
        "subtitle": "Same scan and doctor visit billed twice on the same day",
        "claim_info": {"invoice_number": "CLM-2026-10388", "provider": "Lakeview Care Hospital",
                       "bill_date": "2026-07-16", "admission_date": "2026-07-14", "discharge_date": "2026-07-16"},
        "bill_items": [
            _item("Room Rent - Private Room", 2, 4500, "room", "2026-07-14"),
            _item("CT Scan - Abdomen with contrast", 1, 6500, "lab", "2026-07-14"),
            _item("CT Scan - Abdomen with contrast", 1, 6500, "lab", "2026-07-14"),
            _item("Consultation - Surgeon visit", 1, 1200, "consultation", "2026-07-15"),
            _item("Consultation - Surgeon visit", 1, 1200, "consultation", "2026-07-15"),
            _item("Liver and Kidney Function Panel", 1, 2400, "lab", "2026-07-14"),
        ],
    },
    "excluded": {
        "title": "Excluded Services Billed",
        "subtitle": "Supplements, toiletries and attendant food the policy excludes",
        "claim_info": {"invoice_number": "CLM-2026-10455", "provider": "Green Valley Hospital",
                       "bill_date": "2026-09-02", "admission_date": "2026-09-01", "discharge_date": "2026-09-02"},
        "bill_items": [
            _item("Room Rent - Private Room", 1, 4000, "room", "2026-09-01"),
            _item("Minor Procedure - Wound debridement", 1, 28500, "procedure", "2026-09-01"),
            _item("Vitamin B-Complex supplement", 1, 1850, "medication", "2026-09-01"),
            _item("Multivitamin tonic", 2, 450, "medication", "2026-09-02"),
            _item("Admission kit and toiletries", 1, 1200, "consumable", "2026-09-01"),
            _item("Attendant food", 2, 350, "other", "2026-09-01"),
        ],
    },
    "inflated": {
        "title": "Inflated Line Items",
        "subtitle": "Totals don't match quantity × price, and the bill total is padded",
        "claim_info": {"invoice_number": "CLM-2026-10502", "provider": "Metro Heart Institute",
                       "bill_date": "2026-10-04", "admission_date": "2026-10-02", "discharge_date": "2026-10-04",
                       "stated_total": 25300},
        "bill_items": [
            _item("Room Rent - Private Room", 2, 4800, "room", "2026-10-02"),
            _item("Injection Ceftriaxone 1g", 10, 450, "medication", "2026-10-02", total=6300),
            _item("Physiotherapy session", 4, 800, "procedure", "2026-10-03"),
            _item("Liver Function Test", 1, 1100, "lab", "2026-10-02"),
            _item("Consultation - Cardiologist visit", 2, 1000, "consultation", "2026-10-02", total=2600),
        ],
    },
    "clean": {
        "title": "Clean Claim",
        "subtitle": "Legitimate two-day stay that is within policy limits",
        "claim_info": {"invoice_number": "CLM-2026-10377", "provider": "City General Hospital",
                       "bill_date": "2026-06-22", "admission_date": "2026-06-20", "discharge_date": "2026-06-22",
                       "stated_total": 16100},
        "bill_items": [
            _item("Room Rent - Private Room", 2, 4500, "room", "2026-06-20"),
            _item("Consultation - Physician visit", 2, 1200, "consultation", "2026-06-20"),
            _item("Complete Blood Count", 1, 650, "lab", "2026-06-20"),
            _item("Chest X-Ray", 1, 900, "lab", "2026-06-20"),
            _item("Pharmacy - Prescribed medicines", 1, 3150, "medication", "2026-06-21"),
        ],
    },
}


def run_scenario(key: str) -> dict[str, Any]:
    scenario = SCENARIOS[key]
    claim_info = dict(scenario["claim_info"], policy_name=POLICY_NAME)
    return build_audit_report(
        scenario["bill_items"], POLICY_RULES, covered_days=None, policy_text=POLICY_TEXT,
        notes=["Synthetic example only. The policy, hospital, dates, and amounts are fictional."],
        source_mode="Demo scenario · rule-based (no API call)", claim_info=claim_info,
    )
