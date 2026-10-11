"""Extract text from text-based PDFs or plain text documents."""
from __future__ import annotations
import io
from pathlib import Path
import fitz

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 30
MAX_TEXT_CHARS = 35_000


class DocumentReadError(ValueError):
    pass


def extract_document_text(filename: str, data: bytes) -> str:
    if not data:
        raise DocumentReadError(f"{filename} is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise DocumentReadError(f"{filename} exceeds the 10 MB limit. Use a smaller file.")

    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        text = data.decode("utf-8", errors="replace").strip()
        if not text:
            raise DocumentReadError(f"No readable text was found in {filename}.")
        return text[:MAX_TEXT_CHARS]

    if suffix != ".pdf":
        raise DocumentReadError("Please upload a PDF or plain-text (.txt) document.")

    try:
        document = fitz.open(stream=io.BytesIO(data), filetype="pdf")
        if document.page_count > MAX_PDF_PAGES:
            raise DocumentReadError(
                f"{filename} has {document.page_count} pages. The MVP limit is {MAX_PDF_PAGES} pages."
            )
        pages: list[str] = []
        for page_number, page in enumerate(document, start=1):
            page_text = page.get_text("text").strip()
            pages.append(f"[PAGE {page_number}]\n{page_text}")
        document.close()
        text = "\n\n".join(pages).strip()
    except DocumentReadError:
        raise
    except Exception as exc:
        raise DocumentReadError(f"Could not read {filename}. Make sure it is a valid PDF.") from exc

    actual_text = "\n".join(line for line in text.splitlines() if not line.startswith("[PAGE ")).strip()
    if len(actual_text) < 30:
        raise DocumentReadError(
            f"No selectable text was found in {filename}. This MVP supports text-based PDFs; "
            "scanned image-only PDFs need OCR first. Try the built-in synthetic demo."
        )
    return text[:MAX_TEXT_CHARS]
