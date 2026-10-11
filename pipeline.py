"""Uploaded bill + policy -> audit report. Shared by the Streamlit app and the web API."""
from __future__ import annotations
from typing import Any, Callable
from audit_engine import build_audit_report
from claude_auditor import analyze_documents, model_name
from document_reader import read_document


def audit_documents(
    bill_name: str, bill_bytes: bytes, policy_name: str, policy_bytes: bytes,
    covered_days: int = 0, progress: Callable[[str], None] = lambda message: None,
) -> dict[str, Any]:
    """Raises DocumentReadError or ClaudeAuditError with a user-readable message."""
    progress("📄 Reading documents…")
    bill = read_document(bill_name, bill_bytes)
    policy = read_document(policy_name, policy_bytes, allow_images=False)
    source = f"{len(bill.images)} page image(s)" if bill.is_visual else "bill text"
    progress(f"🧠 Claude ({model_name()}) is extracting line items and policy clauses from the {source}…")
    parsed = analyze_documents(bill, policy)
    progress("⚙️ Running the rule engine…")
    notes = list(parsed.notes)
    if bill.is_visual:
        notes.append("The bill was read from page images with Claude vision. Check extracted amounts against the original.")
    for doc in (bill, policy):
        if doc.truncated:
            notes.append(f"{doc.filename} was longer than the text limit and was truncated; later pages were not audited.")
    claim_info = parsed.claim_info.model_dump()
    claim_info["policy_name"] = policy_name
    report = build_audit_report(
        bill_items=[item.model_dump() for item in parsed.bill_items],
        policy_rules=[rule.model_dump() for rule in parsed.policy_rules],
        covered_days=covered_days or None, policy_text=policy.text, notes=notes,
        source_mode=f"Claude API · {model_name()}", claim_info=claim_info,
        observations=[o.model_dump() for o in parsed.observations],
    )
    report["reviewer_summary"] = parsed.reviewer_summary
    return report
