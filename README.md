# ClaimGuard AI — Evidence-Based Medical Bill Auditor

A hackathon MVP that compares hospital bill line items with an insurance policy, flags possible discrepancies, cites source policy text, computes potential exposure in deterministic Python code, and exports a review report.

## Features

- Streamlit dashboard and manual review status per finding.
- Synthetic demo mode works without an Anthropic key or API credits.
- PDF/TXT extraction for text-based documents (max 10 MB and 30 PDF pages per file).
- Optional single-call Claude-powered structured extraction.
- Policy quote verification before a policy rule can trigger a financial finding.
- Deterministic checks for exact/near-exact duplicate charges, line-item arithmetic differences, explicit room daily caps, and explicit excluded services.
- Non-overlapping financial exposure allocation.
- JSON and CSV downloads.
- Unit tests for key calculations and evidence verification.

## Quick start (Mac / Linux)

```bash
cd claimguard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Click **Load synthetic demo** to see the expected sample audit without using API credits.

## Enable live Claude audits

1. Copy `.env.example` to `.env`.
2. Add your Anthropic API key to `ANTHROPIC_API_KEY` in `.env`.
3. Restart `streamlit run app.py` if the app was already running.
4. Upload a hospital bill and policy as text-based PDFs or `.txt` files, set the number of covered days, and click **Audit uploaded documents**.

The default model is `claude-sonnet-4-6`; set `CLAUDE_MODEL` in `.env` if your account uses a different available model. Each live audit is designed to make one Claude API request. Use the sample demo while iterating on the UI to conserve credits.

## Tests

```bash
pytest -q
```

## Limitations

- Scanned image-only PDFs are not OCR'd in this two-hour MVP. Use selectable-text PDFs or OCR the document before uploading.
- The app assumes INR for display and financial summaries. Check source currency before interpreting real documents.
- Policy interpretation, duplicate flags, and estimates require human review. This does not determine fraud, coverage, final reimbursement, or guaranteed recovery.
- The app is a local hackathon demonstration, not a production HIPAA/DPDP-compliant system. Use synthetic data only; do not upload real patient records.
- Uploaded files are processed in memory and are not intentionally persisted by the application.

## Structure

```text
claimguard/
├── app.py
├── audit_engine.py
├── claude_auditor.py
├── document_reader.py
├── schemas.py
├── requirements.txt
├── .env.example
├── .gitignore
├── sample_data/
└── tests/test_audit_engine.py
```
