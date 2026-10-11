import fitz
import pytest
from document_reader import read_document, DocumentReadError


def _pdf(text: str = "") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_text_pdf_returns_text_with_page_markers():
    content = read_document("bill.pdf", _pdf("Room Charges 15000 Laboratory Tests 8000"))
    assert content.text.startswith("[PAGE 1]") and not content.is_visual


def test_scanned_bill_falls_back_to_page_images():
    content = read_document("bill.pdf", _pdf())
    assert content.is_visual and content.images[0].startswith(b"\x89PNG")


def test_scanned_policy_is_rejected():
    with pytest.raises(DocumentReadError):
        read_document("policy.pdf", _pdf(), allow_images=False)
