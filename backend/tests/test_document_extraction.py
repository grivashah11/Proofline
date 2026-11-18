from io import BytesIO

import pytest
from docx import Document
from fastapi import HTTPException
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.services.document_extraction import (
    MAX_SEGMENT_CHARACTERS,
    MAX_SOURCE_DOCUMENT_BYTES,
    extract_source_document,
)


def make_pdf_bytes(text: str = "Proofline evidence passage.") -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    pdf.drawString(72, 720, text)
    pdf.save()
    return output.getvalue()


def make_docx_bytes() -> bytes:
    document = Document()
    document.add_heading("Product Specifications", level=1)
    document.add_paragraph("Battery life is up to 30 hours under the stated test conditions.")
    document.add_heading("Display", level=2)
    document.add_paragraph("The display reaches 700 nits at peak brightness.")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Model"
    table.rows[0].cells[1].text = "Proofline Sample"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def test_extract_pdf_retains_page_number_and_excerpt():
    extracted = extract_source_document(
        make_pdf_bytes("Battery life is up to 30 hours."),
        "report.pdf",
        "application/pdf",
    )

    assert extracted.document_format == "PDF"
    assert extracted.mime_type == "application/pdf"
    assert extracted.page_count == 1
    assert extracted.segment_count == 1
    assert extracted.segments[0].location_type == "page"
    assert extracted.segments[0].page_number == 1
    assert extracted.segments[0].location_label == "Page 1"
    assert "up to 30 hours" in extracted.segments[0].text_content


def test_extract_docx_preserves_heading_paragraph_and_table_locations():
    extracted = extract_source_document(
        make_docx_bytes(),
        "specifications.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert extracted.document_format == "DOCX"
    assert extracted.page_count is None
    assert any(
        segment.location_type == "section"
        and segment.section_path == "Product Specifications"
        and "up to 30 hours" in segment.text_content
        for segment in extracted.segments
    )
    assert any(
        segment.location_type == "section"
        and segment.section_path == "Product Specifications > Display"
        and "700 nits" in segment.text_content
        for segment in extracted.segments
    )
    assert any(
        segment.location_type == "table_row"
        and "Proofline Sample" in segment.text_content
        for segment in extracted.segments
    )


def test_extract_source_document_sanitizes_windows_filename():
    extracted = extract_source_document(
        make_pdf_bytes(),
        r"C:\\Users\\Private\\report.pdf",
        "application/pdf",
    )
    assert extracted.original_filename == "report.pdf"


def test_rejects_empty_document():
    with pytest.raises(HTTPException) as error:
        extract_source_document(b"", "report.pdf", "application/pdf")
    assert error.value.status_code == 422


def test_rejects_document_over_15_mb():
    with pytest.raises(HTTPException) as error:
        extract_source_document(
            b"x" * (MAX_SOURCE_DOCUMENT_BYTES + 1),
            "report.pdf",
            "application/pdf",
        )
    assert error.value.status_code == 413


def test_rejects_unsupported_extension():
    with pytest.raises(HTTPException) as error:
        extract_source_document(b"anything", "report.doc", "application/msword")
    assert error.value.status_code == 415


def test_rejects_content_type_extension_mismatch():
    with pytest.raises(HTTPException) as error:
        extract_source_document(make_pdf_bytes(), "report.pdf", "text/plain")
    assert error.value.status_code == 415


def test_rejects_invalid_pdf_bytes():
    with pytest.raises(HTTPException) as error:
        extract_source_document(b"not a pdf file", "report.pdf", "application/pdf")
    assert error.value.status_code == 415


def test_rejects_docx_named_file_that_is_not_a_docx_package():
    with pytest.raises(HTTPException) as error:
        extract_source_document(b"not a zip file", "report.docx", "application/octet-stream")
    assert error.value.status_code == 422


def test_long_pdf_page_is_split_without_exceeding_segment_limit():
    long_text = "Evidence " * (MAX_SEGMENT_CHARACTERS // 8 + 200)
    extracted = extract_source_document(
        make_pdf_bytes(long_text),
        "long.pdf",
        "application/pdf",
    )
    assert len(extracted.segments) >= 1
    assert all(
        len(segment.text_content) <= MAX_SEGMENT_CHARACTERS
        for segment in extracted.segments
    )


def test_rejects_image_only_or_blank_pdf_without_ocr():
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    pdf.showPage()
    pdf.save()

    with pytest.raises(HTTPException) as error:
        extract_source_document(output.getvalue(), "scan.pdf", "application/pdf")

    assert error.value.status_code == 422
    assert "OCR" in error.value.detail
