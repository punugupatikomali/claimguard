from __future__ import annotations
import base64
import csv
import html
import io
import json
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from audit_engine import assess_report
from document_reader import DocumentReadError
from claude_auditor import model_name, ClaudeAuditError
from pipeline import audit_documents
from scenarios import SCENARIOS, run_scenario

load_dotenv()
st.set_page_config(page_title="ClaimGuard AI", page_icon="🛡️", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.stApp { background: radial-gradient(1200px 600px at 10% -10%, #10233f 0%, transparent 60%), radial-gradient(900px 500px at 100% 0%, #1e1b4b 0%, transparent 55%), #070d1a; }
.block-container { padding-top: 1.4rem; max-width: 1500px; }
header[data-testid="stHeader"] { background: transparent; }
.cg-header { display:flex; align-items:center; justify-content:space-between; padding: .2rem 0 1rem 0; }
.cg-brand { display:flex; align-items:center; gap:14px; }
.cg-title { font-size: 2rem; font-weight: 800; letter-spacing: -.02em; color:#f1f5f9; line-height:1.1; }
.cg-title span { background: linear-gradient(90deg,#22d3ee,#38bdf8); -webkit-background-clip:text; background-clip:text; color:transparent; }
.cg-sub { color:#8b9bb4; font-size:.98rem; margin-top:4px; }
.cg-badge { border-radius:999px; padding:.45rem 1rem; font-weight:700; font-size:.92rem; }
.cg-badge.rule { background: rgba(161,98,7,.25); color:#fbbf24; border:1px solid rgba(251,191,36,.35); }
.cg-badge.ai { background: rgba(6,95,70,.3); color:#34d399; border:1px solid rgba(52,211,153,.35); }
div[data-baseweb="tab-list"] { gap: 1.6rem; border-bottom: 1px solid rgba(148,163,184,.15); }
button[data-baseweb="tab"] { padding: .7rem .2rem; }
button[data-baseweb="tab"] p { font-size: 1rem; font-weight: 600; color:#94a3b8; }
button[data-baseweb="tab"][aria-selected="true"] p { color:#22d3ee; }
div[data-baseweb="tab-highlight"] { background-color:#22d3ee; }
.cg-section { font-size:1.25rem; font-weight:700; color:#f1f5f9; margin: .4rem 0 .9rem 0; }
div[role="radiogroup"] { gap: 12px; width: 100%; }
div[role="radiogroup"] > div { width:100%; border:1px solid rgba(148,163,184,.16); border-radius:14px; padding:16px 18px; background: rgba(15,23,42,.6); transition: all .15s; }
div[role="radiogroup"] > div:hover { border-color: rgba(34,211,238,.45); }
div[role="radiogroup"] > div[data-selected="true"] { border-color:#22d3ee; background: rgba(8,51,68,.45); box-shadow: 0 0 0 1px rgba(34,211,238,.25); }
div[role="radiogroup"] label[data-testid="stRadioOption"] { width:100%; }
div[role="radiogroup"] label[data-testid="stRadioOption"] > div > div:first-child { display:none; }
div[role="radiogroup"] label[data-testid="stRadioOption"] p { font-size: 1.05rem; font-weight: 700; color:#f1f5f9; }
div[role="radiogroup"] [data-testid="stRadioCaption"] { padding-left: 0; margin-left: 0; }
div[role="radiogroup"] [data-testid="stRadioCaption"] p { color:#94a3b8; font-size:.92rem; }
div.stButton > button[kind="primary"] { background: linear-gradient(90deg,#22d3ee,#8b5cf6); border:0; color:white; font-weight:700; font-size:1.05rem; padding:.7rem 0; border-radius:12px; }
div.stButton > button[kind="primary"]:disabled { opacity:.45; }
div.stButton > button[kind="primary"] p { font-size:1.08rem; font-weight:700; }
.cg-card { background: rgba(15,23,42,.72); border:1px solid rgba(148,163,184,.14); border-radius:16px; padding:22px 26px; margin-bottom:18px; }
.cg-card h3 { margin:0 0 14px 0; font-size:1.3rem; color:#f1f5f9; display:flex; align-items:center; justify-content:space-between; gap:10px; }
.cg-card.sev-high { background: linear-gradient(135deg, rgba(124,45,18,.55), rgba(41,20,10,.6)); border-color: rgba(251,146,60,.45); }
.cg-card.sev-medium { background: linear-gradient(135deg, rgba(113,63,18,.45), rgba(30,22,10,.6)); border-color: rgba(251,191,36,.4); }
.cg-card.sev-clear { background: linear-gradient(135deg, rgba(6,78,59,.45), rgba(8,25,22,.6)); border-color: rgba(52,211,153,.4); }
.cg-card.ai { background: linear-gradient(135deg, rgba(49,46,129,.45), rgba(15,23,42,.85)); border-color: rgba(129,140,248,.3); }
.cg-grid { display:grid; grid-template-columns: 1fr 1fr; gap: 14px 40px; }
.cg-label { color:#8b9bb4; font-size:.92rem; margin-bottom:6px; }
.cg-value { color:#f1f5f9; font-weight:600; }
.cg-mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.cg-amount { color:#34d399; font-weight:700; }
.cg-chips { display:flex; flex-wrap:wrap; gap:8px; margin: 4px 0 14px 0; }
.cg-chip { font-family: ui-monospace, Menlo, monospace; font-size:.82rem; padding:5px 10px; border-radius:8px; background: rgba(148,163,184,.12); color:#cbd5e1; }
.cg-chip.purple { background: rgba(99,102,241,.22); color:#c7d2fe; }
.cg-chip.flag { background: rgba(234,88,12,.22); color:#fdba74; }
.cg-finding { background: rgba(2,6,23,.45); border-radius:10px; padding:14px 16px; margin-top:10px; }
.cg-frow { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:6px; }
.cg-tag { font-family: ui-monospace, Menlo, monospace; font-size:.78rem; padding:3px 8px; border-radius:6px; background: rgba(234,88,12,.3); color:#fdba74; font-weight:700; }
.cg-sev { font-size:.8rem; font-weight:700; color:#94a3b8; }
.cg-sev.High { color:#f87171; } .cg-sev.Medium { color:#fbbf24; } .cg-sev.Low { color:#34d399; }
.cg-exp { margin-left:auto; color:#fca5a5; font-weight:700; font-family: ui-monospace, Menlo, monospace; }
.cg-desc { color:#e2e8f0; }
.cg-desc b { color:#fff; }
details { margin-top:8px; } summary { cursor:pointer; color:#7dd3fc; font-size:.88rem; }
.cg-ev { margin-top:8px; font-size:.9rem; color:#cbd5e1; }
.cg-ev code { background: rgba(148,163,184,.12); color:#e2e8f0; padding:2px 6px; border-radius:5px; }
.cg-quote { border-left:3px solid #22d3ee; padding:6px 12px; margin:8px 0; color:#e0f2fe; background: rgba(8,51,68,.35); border-radius:0 8px 8px 0; }
.cg-risk { font-weight:800; font-size:1rem; }
.cg-risk.HIGH { color:#f87171; } .cg-risk.MEDIUM { color:#fbbf24; } .cg-risk.LOW, .cg-risk.CLEAR { color:#34d399; }
.cg-pill { font-size:.88rem; padding:5px 12px; border-radius:999px; background: rgba(148,163,184,.14); color:#e2e8f0; font-weight:600; }
.cg-action { display:inline-block; font-weight:800; padding:8px 16px; border-radius:8px; letter-spacing:.02em; margin:2px 0 14px 0; }
.cg-action.LOW { background: rgba(6,95,70,.45); color:#6ee7b7; } .cg-action.MEDIUM { background: rgba(113,63,18,.55); color:#fcd34d; } .cg-action.HIGH { background: rgba(127,29,29,.55); color:#fca5a5; }
.cg-p { color:#f1f5f9; font-size:1.02rem; line-height:1.55; margin-bottom:14px; }
.cg-stats { display:grid; grid-template-columns: repeat(4, 1fr); gap:14px; margin-bottom:18px; }
.cg-stat { background: rgba(15,23,42,.72); border:1px solid rgba(148,163,184,.14); border-radius:14px; padding:14px 18px; }
.cg-stat .n { font-size:1.45rem; font-weight:800; color:#f1f5f9; margin-top:2px; }
.cg-stat .n.red { color:#fca5a5; } .cg-stat .n.green { color:#34d399; }
.cg-empty { text-align:center; padding:70px 20px; color:#8b9bb4; }
.cg-empty .big { font-size:2.6rem; }
.cg-headright { display:flex; align-items:center; gap:12px; }
</style>
""", unsafe_allow_html=True)

CATEGORY_TAGS = {
    "arithmetic": "ARITHMETIC_MISMATCH", "duplicate": "DUPLICATE_CHARGE", "room_limit": "ROOM_RENT_CAP",
    "excluded_service": "EXCLUDED_SERVICE", "total_mismatch": "BILL_TOTAL_MISMATCH",
}
REVIEW_STATUSES = ["Needs review", "Confirmed by auditor", "Dismissed by auditor", "Needs more evidence"]
_SHIELD_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" stroke-width="1.7" '
               'stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v6c0 4.5-3 7.7-7 9-4-1.3-7-4.5-7-9V6l7-3z"/><path d="M9 12l2 2 4-4"/></svg>')
# st.html sanitises inline SVG away, so the logo goes in as an image data URI.
SHIELD = f'<img alt="" width="46" height="46" src="data:image/svg+xml;base64,{base64.b64encode(_SHIELD_SVG.encode()).decode()}">'


def e(value) -> str:
    """Escape document-derived text before it goes into HTML; '$' would otherwise trigger LaTeX."""
    text = "—" if value is None or value == "" else str(value)
    return html.escape(text).replace("$", "&#36;")


def inr(amount) -> str:
    return f"₹{float(amount or 0):,.2f}"


if "report" not in st.session_state:
    st.session_state.report = None
    st.session_state.live = False

key_present = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
report = st.session_state.report
live = st.session_state.live
if report is not None and live:
    badge = f'<span class="cg-badge ai">● Claude AI Mode · {e(model_name())}</span>'
elif report is not None or not key_present:
    badge = '<span class="cg-badge rule">● Rule-Based Mode</span>'
else:
    badge = '<span class="cg-badge ai">● Claude Ready</span>'
st.html(f"""<div class="cg-header"><div class="cg-brand">{SHIELD}<div>
<div class="cg-title"><span>ClaimGuard</span> AI Insurance Auditor</div>
<div class="cg-sub">Healthcare Claim Audit System • Powered by Claude</div></div></div>
<div class="cg-headright">{badge}</div></div>""")

tab_claim, tab_items, tab_policy, tab_report = st.tabs(["🧾 Single Claim", "📋 Line Items", "📜 Policy Evidence", "📤 Report & Export"])


# ---------- Rendering helpers ----------
def render_claim_details(r: dict) -> None:
    info = r.get("claim_info", {})
    stay = f"{e(info.get('admission_date'))} → {e(info.get('discharge_date'))}" if info.get("admission_date") else e(info.get("bill_date"))
    categories = sorted({i["category"] for i in r["bill_items"]})
    item_chips = "".join(f'<span class="cg-chip purple">{e(i["description"])}</span>' for i in r["bill_items"][:12])
    more = f'<span class="cg-chip">+{len(r["bill_items"]) - 12} more</span>' if len(r["bill_items"]) > 12 else ""
    st.html(f"""<div class="cg-card"><h3>Claim Details</h3>
<div class="cg-grid">
<div><span class="cg-label">Claim ID:</span> <span class="cg-value cg-mono">{e(info.get('invoice_number'))}</span></div>
<div><span class="cg-label">Provider:</span> <span class="cg-value">{e(info.get('provider'))}</span></div>
<div><span class="cg-label">Stay:</span> <span class="cg-value">{stay}</span></div>
<div><span class="cg-label">Billed:</span> <span class="cg-amount">{inr(r['total_billed'])}</span></div>
<div><span class="cg-label">Covered days:</span> <span class="cg-value">{r['covered_days_assumed']}</span> <span class="cg-label">({e(r.get('covered_days_source'))})</span></div>
<div><span class="cg-label">Policy:</span> <span class="cg-value">{e(info.get('policy_name'))}</span></div>
</div>
<div class="cg-label" style="margin-top:16px">Service categories:</div>
<div class="cg-chips">{''.join(f'<span class="cg-chip">{e(c)}</span>' for c in categories)}</div>
<div class="cg-label">Line items ({len(r['bill_items'])}):</div>
<div class="cg-chips">{item_chips}{more}</div></div>""")


def render_rule_engine(r: dict) -> None:
    findings = r.get("findings", [])
    if not findings:
        st.html("""<div class="cg-card sev-clear"><h3><span>✅ Rule Engine Analysis</span><span class="cg-risk CLEAR">CLEAR</span></h3>
<div class="cg-desc">No duplicates, arithmetic errors, bill-total mismatch, room-cap breaches, or excluded services were detected.</div></div>""")
        return
    overall = "High" if any(f["severity"] == "High" for f in findings) else "Medium" if any(f["severity"] == "Medium" for f in findings) else "Low"
    rows = []
    for f in findings:
        evidence = f'<div class="cg-ev"><b>Calculation</b> <code>{e(f.get("calculation"))}</code></div>'
        if f.get("policy_quote"):
            evidence += f'<div class="cg-ev"><b>Policy clause</b> (page {e(f.get("policy_page"))})<div class="cg-quote">“{e(f["policy_quote"])}”</div></div>'
        else:
            pages = ", ".join(str(p) for p in (f.get("bill_pages") or []) if p is not None)
            evidence += f'<div class="cg-ev"><b>Bill evidence</b> {e(f.get("evidence_quote"))} <span class="cg-label">· bill page {e(pages or None)}</span></div>'
        if f.get("related_items"):
            evidence += f'<div class="cg-ev"><b>Related lines</b> {e(", ".join(f["related_items"]))}</div>'
        evidence += f'<div class="cg-ev"><b>Method</b> {e(f.get("source"))} · <b>Confidence</b> {e(f.get("confidence"))}</div>'
        rows.append(f"""<div class="cg-finding"><div class="cg-frow"><span class="cg-tag">{CATEGORY_TAGS.get(f['category'], f['category'].upper())}</span>
<span class="cg-sev {e(f['severity'])}">{e(f['severity']).upper()}</span><span class="cg-label">{e(f['id'])}</span><span class="cg-exp">{inr(f['potential_exposure'])}</span></div>
<div class="cg-desc"><b>{e(f['title'])}.</b> {e(f['description'])}</div>
<details><summary>Evidence &amp; calculation</summary>{evidence}</details></div>""")
    st.html(f"""<div class="cg-card sev-{overall.lower() if overall != 'Low' else 'medium'}"><h3><span>⚠️ Rule Engine Analysis · {len(findings)} issue{'s' if len(findings) != 1 else ''}</span>
<span class="cg-risk {overall.upper()}">{overall.upper()}</span></h3>{''.join(rows)}</div>""")


def render_stats(r: dict, verdict: dict) -> None:
    st.html(f"""<div class="cg-stats">
<div class="cg-stat"><div class="cg-label">Total billed</div><div class="n">{inr(r['total_billed'])}</div></div>
<div class="cg-stat"><div class="cg-label">Issues found</div><div class="n">{r['finding_count']}</div></div>
<div class="cg-stat"><div class="cg-label">Potential overpayment</div><div class="n red">{inr(r['potential_exposure'])}</div></div>
<div class="cg-stat"><div class="cg-label">Recommended payable</div><div class="n green">{inr(verdict['recommended_payable'])}</div></div></div>""")


def render_verdict(r: dict, verdict: dict, is_live: bool) -> None:
    risk = verdict["risk_level"]
    title = "🧠 Claude AI Analysis" if is_live else "🧠 Audit Verdict"
    body = f"""<div class="cg-label">Recommended Action</div><div class="cg-action {risk}">{e(verdict['recommended_action'])}</div>
<div class="cg-label">Audit Reasoning</div><div class="cg-p">{e(verdict['reasoning'])}</div>"""
    if is_live and r.get("reviewer_summary"):
        body += f'<div class="cg-label">Claude\'s Read of the Documents</div><div class="cg-p">{e(r["reviewer_summary"])}</div>'
    if verdict["citations"]:
        quotes = "".join(f'<div class="cg-quote">“{e(c["quote"])}” <span class="cg-label">— policy page {e(c["page"])}</span></div>' for c in verdict["citations"])
        body += f'<div class="cg-label">Supporting Policy Clauses</div>{quotes}'
    observations = r.get("observations", [])
    if observations:
        items = "".join(
            f"""<div class="cg-finding"><div class="cg-frow"><span class="cg-tag" style="background:rgba(99,102,241,.3);color:#c7d2fe">AI_OBSERVATION</span>
<span class="cg-sev {e(str(o.get('severity', 'low')).title())}">{e(str(o.get('severity', 'low')).upper())}</span></div>
<div class="cg-desc"><b>{e(o.get('title'))}.</b> {e(o.get('detail'))}</div></div>""" for o in observations)
        body += f'<div class="cg-label" style="margin-top:14px">AI-Flagged Observations (unverified, not priced)</div>{items}'
    if not is_live:
        body += '<div class="cg-label" style="margin-top:12px">Rule-based verdict. Upload documents to add Claude\'s extraction, summary, and observations.</div>'
    st.html(f"""<div class="cg-card ai"><h3><span>{title}</span><span style="display:flex;gap:12px;align-items:center">
<span class="cg-risk {risk}">{risk}</span><span class="cg-pill">{verdict['overpayment_share']:.0%} of bill flagged</span></span></h3>{body}</div>""")


def run_live_audit(bill_file, policy_file, covered_days: int) -> None:
    with st.status("Auditing claim…", expanded=True) as status:
        try:
            result = audit_documents(bill_file.name, bill_file.getvalue(), policy_file.name, policy_file.getvalue(),
                                     covered_days, progress=st.write)
            st.session_state.report, st.session_state.live = result, True
            status.update(label=f"Audit complete: {result['finding_count']} issue(s) found", state="complete", expanded=False)
        except (DocumentReadError, ClaudeAuditError) as exc:
            status.update(label="Audit failed", state="error")
            st.error(str(exc))
            return
    st.rerun()


# ---------- Single claim ----------
with tab_claim:
    left, right = st.columns([1, 2.05], gap="large")
    with left:
        st.html('<div class="cg-section">⚡ Select Scenario</div>')
        options = list(SCENARIOS) + ["upload"]
        captions = [SCENARIOS[k]["subtitle"] for k in SCENARIOS] + ["Audit your own hospital bill (PDF, TXT, or photo) against your policy with Claude"]
        choice = st.radio("Scenario", options, format_func=lambda k: "📄 Upload Your Documents" if k == "upload" else SCENARIOS[k]["title"],
                          captions=captions, label_visibility="collapsed", key="scenario")
        disabled = False
        if choice == "upload":
            bill_file = st.file_uploader("Hospital bill", type=["pdf", "txt", "png", "jpg", "jpeg"], help="Text PDF, scanned PDF, TXT, or a photo of the bill. Max 10 MB.")
            policy_file = st.file_uploader("Insurance policy", type=["pdf", "txt"], help="Text-based PDF or TXT, so quoted clauses can be verified. Max 10 MB.")
            covered_days = st.number_input("Covered inpatient days", min_value=0, max_value=365, value=0, step=1,
                                           help="Leave at 0 to detect the stay from the admission and discharge dates on the bill.")
            if not key_present:
                st.warning("Add ANTHROPIC_API_KEY to .env to audit uploaded documents.")
            disabled = not (bill_file and policy_file and key_present)
        if st.button("▷  Analyze Claim", type="primary", width="stretch", disabled=disabled):
            if choice == "upload":
                run_live_audit(bill_file, policy_file, int(covered_days))
            else:
                st.session_state.report, st.session_state.live = run_scenario(choice), False
                st.rerun()

    with right:
        if report is None:
            st.html("""<div class="cg-card cg-empty"><div class="big">🛡️</div><div class="cg-value" style="font-size:1.15rem;margin:8px 0">No claim analysed yet</div>
<div>Pick a demo scenario or upload a hospital bill and policy, then click <b>Analyze Claim</b>.<br>
ClaimGuard flags duplicates, arithmetic errors, padded totals, room-rent cap breaches, and excluded services, and cites the policy clause behind each one.</div></div>""")
        else:
            verdict = assess_report(report)
            render_claim_details(report)
            render_rule_engine(report)
            render_stats(report, verdict)
            render_verdict(report, verdict, live)
            st.caption(f"{report['source_mode']} · Generated {report['created_at'][:19].replace('T', ' ')} UTC · Findings are review leads, not determinations of fraud or coverage.")


# ---------- Line items ----------
with tab_items:
    if report is None:
        st.info("Run an analysis to see the extracted bill line items.")
    else:
        flags: dict[int, list[str]] = {}
        for f in report["findings"]:
            for i in f.get("related_indices", []):
                flags.setdefault(i, []).append(f"{f['id']} {CATEGORY_TAGS.get(f['category'], f['category'])}")
        df = pd.DataFrame([{
            "#": n + 1, "Description": it["description"], "Date": it.get("service_date"), "Qty": it["quantity"],
            "Unit price (₹)": it["unit_price"], "Total (₹)": it["total"], "Category": it["category"],
            "Page": it.get("page"), "Flags": ", ".join(flags.get(n, [])),
        } for n, it in enumerate(report["bill_items"])])
        styled = df.style.apply(lambda row: ["background-color: rgba(234,88,12,.18)" if row["Flags"] else "" for _ in row], axis=1) \
            .format({"Unit price (₹)": "{:,.2f}", "Total (₹)": "{:,.2f}", "Qty": "{:g}"})
        st.dataframe(styled, width="stretch", hide_index=True)
        st.caption(f"{len(df)} line items · {len(flags)} flagged (highlighted). Live audits use AI-extracted lines; verify them against the original bill.")


# ---------- Policy evidence ----------
with tab_policy:
    if report is None:
        st.info("Run an analysis to see the policy clauses used.")
    else:
        rules = report.get("policy_rules_used", [])
        if rules:
            st.markdown("**Verified policy clauses applied by the rule engine**")
            for rule in rules:
                limit = f" · limit {inr(rule['amount_limit'])}/day" if rule.get("amount_limit") else ""
                st.html(f"""<div class="cg-card" style="padding:16px 20px"><div class="cg-frow"><span class="cg-tag" style="background:rgba(34,211,238,.18);color:#67e8f9">{e(str(rule.get('rule_type')).upper())}</span>
<span class="cg-label">page {e(rule.get('page'))}{e(limit)} · confidence {e(rule.get('confidence'))}</span></div>
<div class="cg-desc">{e(rule.get('description'))}</div><div class="cg-quote">“{e(rule.get('quote'))}”</div></div>""")
        else:
            st.warning("No verifiable room-cap or exclusion clauses were found in the policy, so only bill-internal checks ran.")
        st.markdown("**Audit notes**")
        for note in report.get("audit_notes", []):
            st.markdown(f"- {note}")


# ---------- Report & export ----------
with tab_report:
    if report is None:
        st.info("Run an analysis to review findings and export the report.")
    else:
        findings = report["findings"]
        statuses: dict[str, str] = {}
        if findings:
            st.markdown("**Reviewer decisions**: set a status for each finding before exporting.")
            table = pd.DataFrame([{
                "ID": f["id"], "Severity": f["severity"], "Type": CATEGORY_TAGS.get(f["category"], f["category"]),
                "Finding": f["title"], "Exposure (₹)": f["potential_exposure"], "Status": f.get("review_status", "Needs review"),
            } for f in findings])
            # Keyed per report so edits persist across reruns and reset when a new claim is analysed.
            edited = st.data_editor(table, key=f"review_{report['created_at']}", hide_index=True, width="stretch",
                                    disabled=["ID", "Severity", "Type", "Finding", "Exposure (₹)"],
                                    column_config={"Status": st.column_config.SelectboxColumn(options=REVIEW_STATUSES, required=True),
                                                   "Exposure (₹)": st.column_config.NumberColumn(format="%.2f")})
            statuses = dict(zip(edited["ID"], edited["Status"]))
        else:
            st.success("No findings to review.")

        export_findings = []
        for f in findings:
            f_out = {k: v for k, v in f.items() if k != "related_indices"}
            f_out["review_status"] = statuses.get(f["id"], f.get("review_status", "Needs review"))
            export_findings.append(f_out)
        export_report = dict(report, findings=export_findings, verdict=assess_report(report))
        csv_output = io.StringIO()
        writer = csv.DictWriter(csv_output, extrasaction="ignore", fieldnames=[
            "id", "severity", "category", "title", "description", "potential_exposure", "confidence", "review_status",
            "calculation", "policy_quote", "policy_page", "evidence_quote"])
        writer.writeheader()
        writer.writerows(export_findings)
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ Download full JSON report", data=json.dumps(export_report, indent=2, ensure_ascii=False).encode("utf-8"),
                           file_name="claimguard_audit_report.json", mime="application/json", width="stretch")
        d2.download_button("⬇️ Download findings CSV", data=csv_output.getvalue().encode("utf-8"),
                           file_name="claimguard_findings.csv", mime="text/csv", width="stretch")
        st.caption(report.get("disclaimer", ""))
