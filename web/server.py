"""Web API + single-page dashboard for hosts that can't run Streamlit (e.g. Vercel)."""
from __future__ import annotations
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from audit_engine import assess_report
from claude_auditor import ClaudeAuditError, model_name
from document_reader import DocumentReadError
from pipeline import audit_documents
from scenarios import SCENARIOS, run_scenario

load_dotenv(ROOT / ".env")
logger = logging.getLogger("claimguard")
INDEX = Path(__file__).resolve().parent / "static" / "index.html"

app = FastAPI(title="ClaimGuard AI", docs_url=None, redoc_url=None)


def _with_verdict(report: dict) -> dict:
    return {"report": report, "verdict": assess_report(report)}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(INDEX, media_type="text/html")


@app.get("/api/status")
def status() -> dict:
    return {"ai_ready": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()), "model": model_name()}


@app.get("/api/scenarios")
def scenarios() -> list[dict]:
    return [{"key": key, "title": s["title"], "subtitle": s["subtitle"]} for key, s in SCENARIOS.items()]


@app.get("/api/scenarios/{key}")
def scenario(key: str) -> dict:
    if key not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Unknown scenario.")
    return _with_verdict(run_scenario(key))


@app.post("/api/audit")
def audit(bill: UploadFile = File(...), policy: UploadFile = File(...), covered_days: int = Form(0)) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured on the server.")
    try:
        report = audit_documents(bill.filename or "bill", bill.file.read(), policy.filename or "policy",
                                 policy.file.read(), max(0, min(365, covered_days)))
    except DocumentReadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ClaudeAuditError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # surface the real cause instead of a bare 500
        logger.exception("Audit failed")
        raise HTTPException(status_code=500, detail=f"Unexpected error ({type(exc).__name__}): {str(exc)[:300]}") from exc
    return _with_verdict(report)
