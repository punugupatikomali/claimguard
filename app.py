from __future__ import annotations
import csv
import io
import json
import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from audit_engine import build_audit_report, make_sample_report
from document_reader import extract_document_text, DocumentReadError
from claude_auditor import analyze_documents, ClaudeAuditError

load_dotenv()
st.set_page_config(page_title="ClaimGuard AI", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --cg-ink: #e9eef8; --cg-muted: #9aa8bd; }
.block-container { padding-top: 1.7rem; max-width: 1400px; }
.hero { padding: 1.45rem 1.6rem; border-radius: 18px; background: linear-gradient(125deg, #101c32 0%, #183b55 55%, #116b68 100%); border: 1px solid rgba(255,255,255,.12); margin-bottom: 1.15rem; }
.hero h1 { margin: 0; color: #f7fbff; letter-spacing: -.035em; font-size: 2.35rem; }
.hero p { color: #d0dfeb; margin: .35rem 0 0 0; font-size: 1rem; }
.kicker { color: #65e0ca; font-weight: 700; font-size: .75rem; text-transform: uppercase; letter-spacing: .14em; }
.small-muted { color: #728099; font-size: .88rem; }
div[data-testid="stMetric"] { border: 1px solid rgba(128,150,180,.25); padding: 14px 16px; border-radius: 13px; background: rgba(110,130,160,.045); }
.finding-header { display:flex; align-items:center; gap:.6rem; flex-wrap:wrap; }
.pill { display:inline-block; border-radius:999px; padding:.18rem .55rem; font-size:.75rem; font-weight:700; background:#26374d; color:#d5e3f2; }
.pill-high { background:#512929; color:#ffb6b6; }
.pill-medium { background:#574321; color:#ffe0a1; }
.pill-low { background:#21473f; color:#a8f3d5; }
div.stButton > button[kind="primary"] { background: #0c887e; border-color:#0c887e; }
</style>
""", unsafe_allow_html=True)

if "audit_result" not in st.session_state:
    st.session_state.audit_result = None
if "review_status" not in st.session_state:
    st.session_state.review_status = {}

with st.sidebar:
    st.markdown("## 🛡️ ClaimGuard AI")
    st.caption("Evidence-based medical bill auditing")
    st.markdown("---")
    st.markdown("**How to demo**")
    st.markdown("1. Click **Load synthetic demo**.\n2. Open each finding to see its evidence.\n3. Download the audit report.\n4. For a live audit, upload two text-based PDFs and add your API key to `.env`.")
    st.markdown("---")
    key_present = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    if key_present:
        st.success("Claude API key detected")
    else:
        st.info("Demo mode is ready. No API key needed.")
    st.caption("MVP limitation: scanned image-only PDFs need OCR first.")

st.markdown("""
<div class="hero">
  <div class="kicker">AI audit workspace · MVP</div>
  <h1>ClaimGuard <span style="color:#65e0ca">AI</span></h1>
  <p>Find possible billing discrepancies. Trace every policy-based finding to its source. Keep the math transparent.</p>
</div>
""", unsafe_allow_html=True)

st.warning("Use synthetic data for demos. Findings are review leads, not determinations of fraud, coverage, or guaranteed recovery.")

with st.expander("How ClaimGuard works", expanded=False):
    st.markdown("""
    **1 · Extract:** Read selectable text from the bill and policy PDFs. **2 · Interpret:** Claude returns structured bill items and explicit policy rules. **3 · Verify:** The app checks quoted clauses against source text. **4 · Calculate:** Python calculates duplicate, arithmetic, and supported room-limit exposure. **5 · Review:** A human confirms or dismisses findings.

    **Important:** This hackathon MVP does not replace a claims professional, policy administrator, or legal review. It does not automatically deny claims.
    """)

st.subheader("01 · Add claim documents")
left, right = st.columns(2, gap="large")
with left:
    bill_file = st.file_uploader("Hospital bill", type=["pdf", "txt"], key="bill_file", help="Text-based PDF or TXT; maximum 10 MB.")
with right:
    policy_file = st.file_uploader("Insurance policy", type=["pdf", "txt"], key="policy_file", help="Text-based PDF or TXT; maximum 10 MB.")
covered_days = st.number_input("Covered inpatient days (used for room-cap calculation)", min_value=1, max_value=365, value=1, step=1)

button_col1, button_col2 = st.columns([1.2, 1])
with button_col1:
    run_ai = st.button("⚡ Audit uploaded documents", type="primary", use_container_width=True, disabled=not (bill_file and policy_file))
with button_col2:
    run_demo = st.button("✨ Load synthetic demo", use_container_width=True)

if run_demo:
    st.session_state.audit_result = make_sample_report(int(covered_days))
    st.session_state.review_status = {}
    st.success("Synthetic audit loaded without calling Claude or using API credits.")

if run_ai:
    try:
        with st.spinner("Reading documents and running evidence-backed audit…"):
            bill_text = extract_document_text(bill_file.name, bill_file.getvalue())
            policy_text = extract_document_text(policy_file.name, policy_file.getvalue())
            parsed = analyze_documents(bill_text, policy_text)
            report = build_audit_report(
                bill_items=[item.model_dump() for item in parsed.bill_items],
                policy_rules=[rule.model_dump() for rule in parsed.policy_rules],
                covered_days=int(covered_days), policy_text=policy_text,
                notes=parsed.notes, source_mode=f"Claude API · {os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-6')}",
            )
            st.session_state.audit_result = report
            st.session_state.review_status = {}
        st.success("Audit completed. Review the evidence for each finding before taking action.")
    except (DocumentReadError, ClaudeAuditError) as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")

report = st.session_state.audit_result
if report:
    st.markdown("---")
    st.subheader("02 · Audit results")
    st.caption(f"Mode: {report['source_mode']} · Generated: {report['created_at'][:19].replace('T', ' ')} UTC · Currency assumption: INR")
    findings = report.get("findings", [])
    high_count = sum(1 for f in findings if f.get("severity") == "High")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total billed", f"₹{report['total_billed']:,.2f}")
    m2.metric("Findings", str(report['finding_count']))
    m3.metric("High priority", str(high_count))
    m4.metric("Potential exposure", f"₹{report['potential_exposure']:,.2f}")

    if report.get("source_mode", "").startswith("Synthetic"):
        st.info("This is a fictional demo. Its expected result is ₹7,000 potential exposure: ₹5,000 room-cap estimate + ₹2,000 suspected duplicate.")

    tab_findings, tab_items, tab_notes = st.tabs(["Findings & evidence", "Extracted bill items", "Audit notes"])
    with tab_findings:
        if not findings:
            st.success("No evidence-backed discrepancies were identified by the configured checks. This does not guarantee the claim is correct.")
        for finding in findings:
            severity = finding.get("severity", "Low")
            severity_class = "pill-high" if severity == "High" else "pill-medium" if severity == "Medium" else "pill-low"
            exposure = float(finding.get("potential_exposure", 0) or 0)
            with st.container(border=True):
                st.markdown(f"<div class='finding-header'><span class='pill {severity_class}'>{severity.upper()} PRIORITY</span><span class='pill'>{finding.get('category', 'finding').replace('_', ' ').upper()}</span><span class='pill'>{finding.get('id', '')}</span></div>", unsafe_allow_html=True)
                st.markdown(f"### {finding.get('title', 'Audit finding')}")
                st.write(finding.get("description", ""))
                cols = st.columns([1, 1, 1.6])
                cols[0].metric("Exposure for review", f"₹{exposure:,.2f}")
                cols[1].metric("Evidence confidence", finding.get("confidence", "Unspecified"))
                cols[2].write("**Review status**")
                status_key = f"status_{finding.get('id', 'x')}"
                current_status = st.session_state.review_status.get(finding.get("id", ""), finding.get("review_status", "Needs review"))
                selected = cols[2].selectbox("Review status", ["Needs review", "Confirmed by auditor", "Dismissed by auditor", "Needs more evidence"], index=["Needs review", "Confirmed by auditor", "Dismissed by auditor", "Needs more evidence"].index(current_status) if current_status in ["Needs review", "Confirmed by auditor", "Dismissed by auditor", "Needs more evidence"] else 0, key=status_key, label_visibility="collapsed")
                st.session_state.review_status[finding.get("id", "")] = selected
                st.markdown(f"**Calculation**  \n`{finding.get('calculation', 'No financial calculation')}`")
                if finding.get("policy_quote"):
                    st.markdown("**Supporting policy clause**")
                    st.info(f"“{finding['policy_quote']}”")
                    st.caption(f"Policy page: {finding.get('policy_page') or 'Not available'} · Clause evidence is checked against the extracted policy text.")
                else:
                    st.markdown(f"**Bill evidence**  \n{finding.get('evidence_quote', 'No exact quote available')}")
                    pages = [p for p in (finding.get("bill_pages") or []) if p is not None]
                    st.caption("Bill page(s): " + (", ".join(str(p) for p in pages) if pages else "Not available"))
                if finding.get("related_items"):
                    st.caption("Related bill item(s): " + ", ".join(finding["related_items"]))
                if finding.get("source"):
                    st.caption("Detection method: " + finding["source"])

    with tab_items:
        if report.get("bill_items"):
            st.dataframe(report["bill_items"], use_container_width=True, hide_index=True)
        else:
            st.write("No bill items extracted.")
        st.caption("Line items are AI-extracted for live audits. Verify them against the original document before relying on the report.")

    with tab_notes:
        for note in report.get("audit_notes", []):
            st.markdown(f"- {note}")
        st.markdown("**Financial interpretation**")
        st.write(report.get("disclaimer", "Potential exposure requires human review."))

    # Download reports include the latest manual review statuses.
    export_report = dict(report)
    export_findings = []
    for f in findings:
        f_out = dict(f)
        f_out["review_status"] = st.session_state.review_status.get(f.get("id", ""), f.get("review_status", "Needs review"))
        export_findings.append(f_out)
    export_report["findings"] = export_findings
    json_bytes = json.dumps(export_report, indent=2, ensure_ascii=False).encode("utf-8")
    csv_output = io.StringIO()
    csv_fields = ["id", "severity", "category", "title", "description", "potential_exposure", "confidence", "review_status", "calculation", "policy_quote", "policy_page", "evidence_quote"]
    writer = csv.DictWriter(csv_output, fieldnames=csv_fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(export_findings)
    st.markdown("---")
    st.subheader("03 · Export report")
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Download full JSON report", data=json_bytes, file_name="claimguard_audit_report.json", mime="application/json", use_container_width=True)
    d2.download_button("⬇️ Download findings CSV", data=csv_output.getvalue().encode("utf-8"), file_name="claimguard_findings.csv", mime="text/csv", use_container_width=True)

st.markdown("---")
st.caption("ClaimGuard AI · Hackathon MVP · Synthetic demo data only · Human review required before any consequential insurance decision.")
