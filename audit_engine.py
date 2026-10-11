"""Deterministic claim checks. The LLM never performs the final money calculations."""
from __future__ import annotations
import re
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _keywords(value: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (value or "").lower()) if len(w) > 2}


def _matches_keywords(item: dict[str, Any], rule: dict[str, Any]) -> bool:
    description = (item.get("description") or "").lower()
    category = (item.get("category") or "").lower()
    keys = [str(k).strip().lower() for k in (rule.get("target_keywords") or []) if str(k).strip()]
    # If the model doesn't return keywords, only use informative words from the rule description.
    if not keys:
        keys = sorted(_keywords(rule.get("description", "")) - {"service", "charges", "covered", "under", "policy", "must", "shall", "not", "the"})
    return any(k in description or k in category for k in keys)


def _quote_supported(quote: str, policy_text: str) -> bool:
    if not quote.strip() or not policy_text.strip():
        return False
    return _norm(quote) in _norm(policy_text)


def _page_for_quote(quote: str, policy_text: str) -> int | None:
    """Derive the citation page from the source text instead of trusting the LLM page number."""
    if not quote.strip():
        return None
    page_matches = list(re.finditer(r"\[PAGE\s+(\d+)\]\s*(.*?)(?=\[PAGE\s+\d+\]|$)", policy_text, flags=re.IGNORECASE | re.DOTALL))
    for match in page_matches:
        if _norm(quote) in _norm(match.group(2)):
            return int(match.group(1))
    return None


def _severity(category: str, amount: float) -> str:
    if category in {"duplicate", "excluded_service", "room_limit"} and amount >= 5000:
        return "High"
    if category in {"duplicate", "excluded_service", "room_limit", "arithmetic"}:
        return "Medium"
    return "Low"


def build_audit_report(
    bill_items: list[dict[str, Any]],
    policy_rules: list[dict[str, Any]],
    covered_days: int = 1,
    policy_text: str = "",
    notes: list[str] | None = None,
    source_mode: str = "AI audit",
) -> dict[str, Any]:
    """Build an evidence-aware report with transparent and non-overlapping exposure calculations."""
    notes = list(notes or [])
    covered_days = max(1, int(covered_days))
    items: list[dict[str, Any]] = []
    for raw in bill_items:
        item = dict(raw)
        item["quantity"] = float(item.get("quantity", 1) or 0)
        item["unit_price"] = float(item.get("unit_price", 0) or 0)
        item["total"] = round(float(item.get("total", 0) or 0), 2)
        item["description"] = str(item.get("description", "Unspecified item"))
        item["category"] = str(item.get("category", "other")).lower()
        items.append(item)

    total_billed = round(sum(x["total"] for x in items), 2)
    # Validate the citation before allowing a policy clause to trigger a policy-based finding.
    verified_rules: list[dict[str, Any]] = []
    for rule in policy_rules:
        r = dict(rule)
        if r.get("rule_type") in {"room_daily_limit", "excluded_service", "not_covered"}:
            if not _quote_supported(str(r.get("quote", "")), policy_text):
                notes.append(
                    f"A possible policy rule was not used because its quoted evidence could not be verified: {r.get('description', 'rule')}"
                )
                continue
            source_page = _page_for_quote(str(r.get("quote", "")), policy_text)
            if source_page is not None:
                r["page"] = source_page
        verified_rules.append(r)

    candidates: list[dict[str, Any]] = []

    # Overcharges due to arithmetic mismatches.
    for i, item in enumerate(items):
        expected = round(item["quantity"] * item["unit_price"], 2)
        delta = round(item["total"] - expected, 2)
        if abs(delta) > 1.0:
            direction = "exceeds" if delta > 0 else "is lower than"
            candidates.append({
                "category": "arithmetic", "severity": _severity("arithmetic", abs(delta)),
                "title": "Line-item arithmetic mismatch", "description":
                f"{item['description']}: listed total {item['total']:.2f} {direction} quantity × unit price ({expected:.2f}).",
                "item_indices": [i], "raw_exposure": max(0.0, delta),
                "evidence_quote": f"Bill line: quantity {item['quantity']:g} × unit price {item['unit_price']:.2f} = {expected:.2f}; listed total {item['total']:.2f}.",
                "policy_quote": "", "policy_page": None, "bill_pages": [item.get("page")],
                "calculation": f"max(0, {item['total']:.2f} - ({item['quantity']:g} × {item['unit_price']:.2f})) = {max(0.0, delta):.2f}",
                "confidence": "High", "review_status": "Needs review", "source": "Deterministic arithmetic check",
                "priority": 0,
            })

    # Exact/near-exact repeated lines. Flag only subsequent occurrences to avoid pairwise double counting.
    seen: list[tuple[str, str, float, int]] = []
    for i, item in enumerate(items):
        desc = _norm(item["description"])
        service_date = str(item.get("service_date") or "").strip().lower()
        amount = round(item["total"], 2)
        prior_match = None
        for prev_desc, prev_date, prev_amount, prev_index in seen:
            similar_desc = desc == prev_desc or (len(desc) >= 7 and SequenceMatcher(None, desc, prev_desc).ratio() >= 0.94)
            date_compatible = not service_date or not prev_date or service_date == prev_date
            if similar_desc and date_compatible and abs(amount - prev_amount) <= 0.01:
                prior_match = prev_index
                break
        if prior_match is not None:
            candidates.append({
                "category": "duplicate", "severity": _severity("duplicate", amount),
                "title": "Possible duplicate charge", "description":
                f"'{item['description']}' matches bill line {prior_match + 1} by description and amount. Confirm against the underlying service record.",
                "item_indices": [i], "raw_exposure": amount,
                "evidence_quote": f"Bill line {prior_match + 1} and line {i + 1}: same normalized description and amount {amount:.2f}.",
                "policy_quote": "", "policy_page": None,
                "bill_pages": [items[prior_match].get("page"), item.get("page")],
                "calculation": f"Potential duplicate amount = min({amount:.2f}, {items[prior_match]['total']:.2f}) = {amount:.2f}",
                "confidence": "Medium", "review_status": "Needs review", "source": "Deterministic duplicate check",
                "priority": 1,
            })
        else:
            seen.append((desc, service_date, amount, i))

    # Room cap is calculated only when a matching rule and a verifiable policy quote exist.
    room_indexes = [i for i, item in enumerate(items)
                    if item.get("category") == "room" or any(k in item["description"].lower() for k in ("room charge", "room rent", "room accommodation", "ward charge"))]
    room_rules = [r for r in verified_rules if r.get("rule_type") == "room_daily_limit" and r.get("amount_limit") is not None]
    if room_indexes and room_rules:
        rule = room_rules[0]
        room_total = round(sum(items[i]["total"] for i in room_indexes), 2)
        cap = float(rule["amount_limit"])
        allowed = round(cap * covered_days, 2)
        excess = round(max(0.0, room_total - allowed), 2)
        if excess > 0:
            candidates.append({
                "category": "room_limit", "severity": _severity("room_limit", excess),
                "title": "Room charge may exceed policy limit", "description":
                f"Room-related charges total {room_total:.2f}; the extracted policy states a limit of {cap:.2f} per day. This estimate assumes {covered_days} covered day(s) and no exception.",
                "item_indices": room_indexes, "raw_exposure": excess,
                "evidence_quote": str(rule.get("quote", "")), "policy_quote": str(rule.get("quote", "")),
                "policy_page": rule.get("page"), "bill_pages": [items[i].get("page") for i in room_indexes],
                "calculation": f"max(0, {room_total:.2f} - ({cap:.2f} × {covered_days})) = {excess:.2f}",
                "confidence": str(rule.get("confidence", "medium")).title(), "review_status": "Needs review",
                "source": "Policy rule + deterministic calculation", "priority": 3,
            })

    for rule in verified_rules:
        if rule.get("rule_type") not in {"excluded_service", "not_covered"}:
            continue
        for i, item in enumerate(items):
            if _matches_keywords(item, rule):
                amount = item["total"]
                candidates.append({
                    "category": "excluded_service", "severity": _severity("excluded_service", amount),
                    "title": "Potentially excluded service", "description":
                    f"'{item['description']}' may match an exclusion in the supplied policy. Verify benefit eligibility and exceptions.",
                    "item_indices": [i], "raw_exposure": amount,
                    "evidence_quote": str(rule.get("quote", "")), "policy_quote": str(rule.get("quote", "")),
                    "policy_page": rule.get("page"), "bill_pages": [item.get("page")],
                    "calculation": f"Maximum charge flagged for review = {amount:.2f}; coverage is not determined automatically.",
                    "confidence": str(rule.get("confidence", "medium")).title(), "review_status": "Needs review",
                    "source": "Policy rule + keyword match", "priority": 2,
                })

    # Allocate exposure per bill line in priority order so overlapping flags cannot be summed twice.
    remaining = [max(0.0, item["total"]) for item in items]
    candidates.sort(key=lambda x: (x["priority"], -x["raw_exposure"]))
    findings: list[dict[str, Any]] = []
    for number, candidate in enumerate(candidates, start=1):
        idxs = [i for i in candidate["item_indices"] if 0 <= i < len(items)]
        raw_exposure = round(float(candidate["raw_exposure"]), 2)
        available = round(sum(remaining[i] for i in idxs), 2)
        allocated = min(raw_exposure, available)
        to_allocate = allocated
        for i in idxs:
            chunk = min(remaining[i], to_allocate)
            remaining[i] = round(remaining[i] - chunk, 2)
            to_allocate = round(to_allocate - chunk, 2)
            if to_allocate <= 0.001:
                break
        item_labels = [items[i]["description"] for i in idxs]
        finding = {k: v for k, v in candidate.items() if k not in {"priority", "raw_exposure", "item_indices"}}
        finding.update({
            "id": f"CG-{number:03d}", "potential_exposure": round(allocated, 2),
            "gross_estimate": raw_exposure, "related_items": item_labels,
        })
        if allocated + 0.01 < raw_exposure:
            finding["calculation"] += f"; non-overlap adjustment reduces this finding to {allocated:.2f}"
        findings.append(finding)

    total_exposure = round(sum(f["potential_exposure"] for f in findings), 2)
    if not findings:
        notes.append("No evidence-backed discrepancies were identified by the configured checks. This is not a guarantee that the claim is correct.")
    return {
        "product": "ClaimGuard AI", "created_at": datetime.now(timezone.utc).isoformat(),
        "source_mode": source_mode, "total_billed": total_billed,
        "finding_count": len(findings), "potential_exposure": total_exposure,
        "currency": "INR", "covered_days_assumed": covered_days,
        "bill_items": items, "findings": findings, "audit_notes": notes,
        "policy_rules_used": [r for r in verified_rules if r.get("rule_type") != "other"],
        "disclaimer": "Potential exposure is a review estimate, not confirmed overpayment, fraud, or guaranteed recovery. A qualified human reviewer must verify coverage, supporting records, and exceptions.",
    }


def make_sample_report(covered_days: int = 1) -> dict[str, Any]:
    """Synthetic demo: room cap plus a repeated medicine line. No API call required."""
    policy_quote = "Standard room charges are covered up to INR 10,000 per day for an eligible inpatient stay."
    bill_items = [
        {"description": "Room Charges", "service_date": "2026-09-12", "quantity": 1, "unit_price": 15000, "total": 15000, "category": "room", "page": 1},
        {"description": "Laboratory Tests", "service_date": "2026-09-12", "quantity": 1, "unit_price": 8000, "total": 8000, "category": "lab", "page": 1},
        {"description": "Medicine A", "service_date": "2026-09-12", "quantity": 1, "unit_price": 2000, "total": 2000, "category": "medication", "page": 1},
        {"description": "Medicine A", "service_date": "2026-09-12", "quantity": 1, "unit_price": 2000, "total": 2000, "category": "medication", "page": 1},
    ]
    policy_rules = [{
        "rule_type": "room_daily_limit", "description": "Daily room-charge limit",
        "amount_limit": 10000, "target_keywords": ["room", "room charges"],
        "page": 1, "quote": policy_quote, "confidence": "high",
    }]
    policy_text = "[PAGE 1]\nSYNTHETIC DEMONSTRATION POLICY\n" + policy_quote + "\nOther eligible charges are subject to benefit review."
    report = build_audit_report(
        bill_items, policy_rules, covered_days=covered_days, policy_text=policy_text,
        notes=["Synthetic example only. The policy, bill, dates, and amounts are fictional."],
        source_mode="Synthetic demo — no API call",
    )
    report["sample_policy_quote"] = policy_quote
    return report
