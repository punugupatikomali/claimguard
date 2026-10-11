"""Deterministic claim checks. The LLM never performs the final money calculations."""
from __future__ import annotations
import re
from collections import defaultdict
from datetime import date, datetime, timezone
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
    if category in {"duplicate", "excluded_service", "room_limit", "total_mismatch"} and amount >= 5000:
        return "High"
    if category in {"duplicate", "excluded_service", "room_limit", "arithmetic", "total_mismatch"}:
        return "Medium"
    return "Low"


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _resolve_covered_days(covered_days: int | None, claim_info: dict[str, Any], items: list[dict[str, Any]], room_indexes: list[int]) -> tuple[int, str]:
    """Use the reviewer's number when given; otherwise derive the stay from the bill."""
    if covered_days:
        return max(1, int(covered_days)), "entered by reviewer"
    admitted, discharged = _parse_date(claim_info.get("admission_date")), _parse_date(claim_info.get("discharge_date"))
    if admitted and discharged and discharged >= admitted:
        return max(1, (discharged - admitted).days), f"admission {admitted} to discharge {discharged}"
    room_quantity = sum(items[i]["quantity"] for i in room_indexes)
    if room_quantity >= 1:
        return int(round(room_quantity)), "quantity on room-charge lines"
    return 1, "default (no stay dates found)"


def build_audit_report(
    bill_items: list[dict[str, Any]],
    policy_rules: list[dict[str, Any]],
    covered_days: int | None = 1,
    policy_text: str = "",
    notes: list[str] | None = None,
    source_mode: str = "AI audit",
    claim_info: dict[str, Any] | None = None,
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an evidence-aware report with transparent and non-overlapping exposure calculations.

    Pass covered_days=None (or 0) to derive the stay length from claim_info dates or room quantities.
    """
    notes = list(notes or [])
    claim_info = dict(claim_info or {})
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
    room_indexes = [i for i, item in enumerate(items)
                    if item.get("category") == "room" or any(k in item["description"].lower() for k in ("room charge", "room rent", "room accommodation", "ward charge"))]
    covered_days, covered_days_source = _resolve_covered_days(covered_days, claim_info, items, room_indexes)
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

    # The printed bill total should equal the sum of its lines; a higher printed total is billed but unitemised.
    stated_total = claim_info.get("stated_total")
    if stated_total is not None:
        stated_total = round(float(stated_total), 2)
        gap = round(stated_total - total_billed, 2)
        if gap > 1.0:
            candidates.append({
                "category": "total_mismatch", "severity": _severity("total_mismatch", gap),
                "title": "Bill total exceeds the sum of its line items", "description":
                f"The bill states a total of {stated_total:.2f}, but its line items add up to {total_billed:.2f}. The difference is not itemised; check for missing lines or an addition error.",
                "item_indices": [], "raw_exposure": gap,
                "evidence_quote": f"Printed total {stated_total:.2f}; sum of {len(items)} extracted line items {total_billed:.2f}.",
                "policy_quote": "", "policy_page": None, "bill_pages": [],
                "calculation": f"{stated_total:.2f} - {total_billed:.2f} = {gap:.2f}",
                "confidence": "Medium", "review_status": "Needs review", "source": "Deterministic bill-total check",
                "priority": 0,
            })
        elif gap < -1.0:
            notes.append(f"The printed bill total ({stated_total:.2f}) is lower than the sum of extracted line items ({total_billed:.2f}); a discount or an extraction error may explain it.")

    # Room cap is calculated only when a matching rule and a verifiable policy quote exist.
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
                f"Room-related charges total {room_total:.2f}; the extracted policy states a limit of {cap:.2f} per day. This estimate assumes {covered_days} covered day(s) ({covered_days_source}) and no exception.",
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
        # Findings tied to no bill line (e.g. an unitemised total) cannot overlap with line-level findings.
        available = round(sum(remaining[i] for i in idxs), 2) if idxs else raw_exposure
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
            "gross_estimate": raw_exposure, "related_items": item_labels, "related_indices": idxs,
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
        "currency": "INR", "covered_days_assumed": covered_days, "covered_days_source": covered_days_source,
        "claim_info": claim_info, "observations": list(observations or []),
        "bill_items": items, "findings": findings, "audit_notes": notes,
        "policy_rules_used": [r for r in verified_rules if r.get("rule_type") != "other"],
        "disclaimer": "Potential exposure is a review estimate, not confirmed overpayment, fraud, or guaranteed recovery. A qualified human reviewer must verify coverage, supporting records, and exceptions.",
    }


def assess_report(report: dict[str, Any]) -> dict[str, Any]:
    """Turn findings into a risk level and a recommended next step. Never recommends an automatic denial."""
    findings = report.get("findings", [])
    observations = report.get("observations", [])
    billed = float(report.get("total_billed", 0) or 0)
    exposure = float(report.get("potential_exposure", 0) or 0)
    share = exposure / billed if billed > 0 else 0.0
    has_high = any(f.get("severity") == "High" for f in findings)
    has_high_observation = any(str(o.get("severity", "")).lower() == "high" for o in observations)

    if has_high or share >= 0.15:
        risk, action = "HIGH", "HOLD FOR MANUAL REVIEW"
    elif exposure > 0:
        risk, action = "MEDIUM", "APPROVE WITH ADJUSTMENT"
    elif has_high_observation:
        risk, action = "MEDIUM", "REVIEW FLAGGED ITEMS"
    elif findings:
        risk, action = "LOW", "REVIEW FLAGGED ITEMS"
    else:
        risk, action = "LOW", "APPROVE"

    if findings:
        largest = max(findings, key=lambda f: f.get("potential_exposure", 0))
        reasoning = (
            f"{len(findings)} discrepanc{'y' if len(findings) == 1 else 'ies'} found, with {exposure:,.2f} of potential "
            f"overpayment ({share:.1%} of the billed amount). The largest is \"{largest.get('title')}\" "
            f"at {float(largest.get('potential_exposure', 0)):,.2f}. Each finding cites the bill line or policy clause it rests on; "
            "verify them against the source records before adjusting payment."
        )
    else:
        reasoning = "No configured check found a duplicate, arithmetic error, total mismatch, room-cap breach, or excluded service. This does not guarantee the claim is correct."
    if observations:
        reasoning += f" Claude also noted {len(observations)} item(s) outside the rule checks; these are unverified and carry no exposure."

    citations = []
    for f in findings:
        if f.get("policy_quote") and f["policy_quote"] not in [c["quote"] for c in citations]:
            citations.append({"quote": f["policy_quote"], "page": f.get("policy_page")})
    return {
        "risk_level": risk, "recommended_action": action, "overpayment_share": round(share, 4),
        "recommended_payable": round(max(0.0, billed - exposure), 2), "reasoning": reasoning, "citations": citations,
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
