"""Read bills and policies: selectable text where available, page images for scans and photos."""
from __future__ import annotations
import io
from dataclasses import dataclass, field
from pathlib import Path
import fitz

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 30
MAX_IMAGE_PAGES = 8
MAX_TEXT_CHARS = 150_000
MAX_IMAGE_SIDE = 1600
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


class DocumentReadError(ValueError):
    pass


@dataclass
class DocumentContent:
    filename: str
    text: str = ""
    images: list[bytes] = field(default_factory=list)  # PNG pages, sent to Claude as vision input
    truncated: bool = False

    @property
    def is_visual(self) -> bool:
        return bool(self.images)


def _page_png(page: "fitz.Page") -> bytes:
    longest = max(page.rect.width, page.rect.height) or 1
    zoom = min(3.0, MAX_IMAGE_SIDE / longest)
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("png")


def _cap(text: str) -> tuple[str, bool]:
    return text[:MAX_TEXT_CHARS], len(text) > MAX_TEXT_CHARS


def read_document(filename: str, data: bytes, allow_images: bool = True) -> DocumentContent:
    if not data:
        raise DocumentReadError(f"{filename} is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise DocumentReadError(f"{filename} exceeds the 10 MB limit. Use a smaller file.")

    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        text = data.decode("utf-8", errors="replace").strip()
        if not text:
            raise DocumentReadError(f"No readable text was found in {filename}.")
        text, truncated = _cap(text)
        return DocumentContent(filename, text=text, truncated=truncated)

    if suffix in IMAGE_SUFFIXES:
        if not allow_images:
            raise DocumentReadError(f"{filename} is an image. Upload the policy as a text-based PDF or TXT so clause citations can be verified.")
        try:
            with fitz.open(stream=io.BytesIO(data), filetype=suffix.lstrip(".")) as doc:
                return DocumentContent(filename, images=[_page_png(doc[0])])
        except Exception as exc:
            raise DocumentReadError(f"Could not read the image {filename}.") from exc

    if suffix != ".pdf":
        raise DocumentReadError("Please upload a PDF, TXT, PNG, or JPG document.")

    try:
        document = fitz.open(stream=io.BytesIO(data), filetype="pdf")
    except Exception as exc:
        raise DocumentReadError(f"Could not read {filename}. Make sure it is a valid PDF.") from exc
    with document:
        if document.page_count > MAX_PDF_PAGES:
            raise DocumentReadError(f"{filename} has {document.page_count} pages. The limit is {MAX_PDF_PAGES} pages.")
        pages = [f"[PAGE {n}]\n{page.get_text('text').strip()}" for n, page in enumerate(document, start=1)]
        text = "\n\n".join(pages).strip()
        actual_text = "\n".join(line for line in text.splitlines() if not line.startswith("[PAGE ")).strip()
        if len(actual_text) >= 30:
            text, truncated = _cap(text)
            return DocumentContent(filename, text=text, truncated=truncated)

        # Scanned PDF: no selectable text, so fall back to page images for Claude's vision.
        if not allow_images:
            raise DocumentReadError(
                f"No selectable text was found in {filename}. The policy must be text-based so quoted clauses "
                "can be verified against the source; run OCR on it first."
            )
        if document.page_count > MAX_IMAGE_PAGES:
            raise DocumentReadError(f"{filename} is a scanned PDF with {document.page_count} pages. Scanned bills are limited to {MAX_IMAGE_PAGES} pages.")
        return DocumentContent(filename, images=[_page_png(page) for page in document])


def extract_document_text(filename: str, data: bytes) -> str:
    """Text-only reader kept for callers that cannot handle page images."""
    return read_document(filename, data, allow_images=False).text
