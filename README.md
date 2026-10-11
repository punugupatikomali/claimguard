# ClaimGuard AI — Evidence-Based Medical Bill Auditor

A hackathon MVP that compares hospital bill line items with an insurance policy, flags possible discrepancies, cites source policy text, computes potential exposure in deterministic Python code, and exports a review report.

## Features

- Dark audit dashboard: claim details, rule-engine findings with evidence, and a verdict card with recommended action.
- Five synthetic demo scenarios (room-cap breach, duplicate billing, excluded services, inflated line items, clean claim) that run without an API key.
- PDF/TXT extraction for text-based documents (max 10 MB and 30 PDF pages per file).
- Scanned PDFs and photos of bills (PNG/JPG) are read with Claude vision.
- Single-call Claude extraction of line items, policy clauses, claim header, and AI observations the rules don't cover.
- Policy quote verification before a policy rule can trigger a financial finding.
- Deterministic checks for exact/near-exact duplicate charges, line-item arithmetic differences, printed bill total vs. line-item sum, explicit room daily caps, and explicit excluded services.
- Stay length detected from admission/discharge dates for room-cap math (or entered by the reviewer).
- Non-overlapping financial exposure allocation.
- JSON and CSV downloads.
- Unit tests for key calculations and evidence verification.

## Quick start (Mac / Linux)

```bash
cd claimguard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The same dashboard also ships as a FastAPI web app (used for Vercel):

```bash
uvicorn web.server:app --port 8000   # then open http://localhost:8000
```

Pick a demo scenario and click **Analyze Claim** to see an audit without using API credits.

## Enable live Claude audits

1. Copy `.env.example` to `.env`.
2. Add your Anthropic API key to `ANTHROPIC_API_KEY` in `.env`.
3. Set `ANTHROPIC_BASE_URL` too if your key comes from an API gateway rather than Anthropic.
4. Restart the app if it was already running.
5. Choose **Upload Your Documents**, add a hospital bill (PDF, TXT, PNG, or JPG) and a text-based policy (PDF or TXT), and click **Analyze Claim**. Leave covered days at 0 to detect the stay from the bill.

The default model is `claude-sonnet-5-5`; set `CLAUDE_MODEL` in `.env` if your account uses a different available model. Each live audit is designed to make one Claude API request. Use the sample demo while iterating on the UI to conserve credits.

## Deploy on Vercel

1. Import the GitHub repo at vercel.com/new and leave the build settings at their defaults. `pyproject.toml` points Vercel at `web.server:app`.
2. Add environment variables `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, and (for gateway keys) `ANTHROPIC_BASE_URL`.
3. Deploy. Vercel limits uploads to 4.5 MB per request, so keep the bill and policy under 4 MB combined.

## Tests

```bash
pytest -q
```

## Limitations

- Scanned bills are limited to 8 pages. Policies must be text-based so quoted clauses can be verified against the source.
- The app assumes INR for display and financial summaries. Check source currency before interpreting real documents.
- Policy interpretation, duplicate flags, and estimates require human review. This does not determine fraud, coverage, final reimbursement, or guaranteed recovery.
- The app is a local hackathon demonstration, not a production HIPAA/DPDP-compliant system. Use synthetic data only; do not upload real patient records.
- Uploaded files are processed in memory and are not intentionally persisted by the application.

## Structure

```text
claimguard/
├── streamlit_app.py      # Streamlit dashboard (local / Streamlit Cloud)
├── web/                  # FastAPI + HTML dashboard (Vercel)
├── pipeline.py
├── audit_engine.py
├── claude_auditor.py
├── document_reader.py
├── scenarios.py
├── schemas.py
├── requirements.txt
├── pyproject.toml        # Vercel entrypoint and web dependencies
├── .streamlit/config.toml
├── .env.example
├── .gitignore
├── sample_data/
└── tests/
```
