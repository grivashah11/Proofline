from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Literal

from docx import Document
from docx.document import Document as DocumentObject
from docx.table import Table
from docx.text.paragraph import Paragraph
from fastapi import HTTPException, status
from pypdf import PdfReader
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P

MAX_SOURCE_DOCUMENT_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 250
MAX_SOURCE_SEGMENTS = 2_500
MAX_EXTRACTED_TEXT_CHARACTERS = 1_000_000
MAX_SEGMENT_CHARACTERS = 20_000
MAX_DOCX_ARCHIVE_ENTRIES = 5_000
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 200

PDF_MIME_TYPE = "application/pdf"
DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
ALLOWED_UPLOAD_TYPES = {
    ".pdf": PDF_MIME_TYPE,
    ".docx": DOCX_MIME_TYPE,
}
ALLOWED_DECLARED_TYPES = {
    PDF_MIME_TYPE,
    DOCX_MIME_TYPE,
    "application/octet-stream",
}

LocationType = Literal["page", "section", "table_row"]


@dataclass(frozen=True)
class ExtractedSegment:
    segment_index: int
    location_type: LocationType
    location_label: str
    page_number: int | None
    section_path: str | None
    paragraph_number: int | None
    text_content: str
    sha256_hash: str


@dataclass(frozen=True)
class ExtractedDocument:
    original_filename: str
    mime_type: str
    document_format: Literal["PDF", "DOCX"]
    file_size_bytes: int
    sha256_hash: str
    page_count: int | None
    segment_count: int
    segments: list[ExtractedSegment]
    extraction_warnings: list[str]


def _safe_filename(filename: str | None) -> str:
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A filename is required.",
        )

    # Treat Windows and POSIX separators as path separators, then remove
    # control characters and header-sensitive characters.
    leaf = filename.replace("\\", "/").rsplit("/", 1)[-1]
    leaf = "".join(char for char in leaf if char.isprintable())
    leaf = leaf.strip().strip(".")
    leaf = re.sub(r'[\r\n\x00]', "", leaf)

    if not leaf or len(leaf) > 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The filename is empty or exceeds 255 characters.",
        )

    return leaf


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _split_text(text: str, limit: int = MAX_SEGMENT_CHARACTERS) -> list[str]:
    """Split long source passages without dropping characters."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining.strip())
            break

        split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at < limit // 2:
            split_at = limit

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].strip()

    return chunks


def _validate_docx_package(content: bytes) -> None:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ARCHIVE_ENTRIES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="The DOCX document contains too many internal components.",
                )

            names = {entry.filename for entry in entries}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Only standard DOCX documents are supported.",
                )

            total_uncompressed = 0
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="The DOCX package contains an unsafe internal path.",
                    )
                if entry.flag_bits & 0x1:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Encrypted DOCX packages are not supported.",
                    )

                total_uncompressed += entry.file_size
                if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="The DOCX expands beyond the supported extraction limit.",
                    )

                if entry.compress_size > 0 and (
                    entry.file_size / entry.compress_size > MAX_DOCX_COMPRESSION_RATIO
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="The DOCX compression ratio is not supported.",
                    )
    except HTTPException:
        raise
    except (zipfile.BadZipFile, OSError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded DOCX file is damaged or invalid.",
        ) from None


def _iter_docx_blocks(document: DocumentObject):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _heading_level(paragraph: Paragraph) -> int | None:
    style_name = getattr(paragraph.style, "name", "") or ""
    match = re.fullmatch(r"Heading\s+([1-9])", style_name, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _append_segments(
    segments: list[ExtractedSegment],
    *,
    location_type: LocationType,
    location_label: str,
    page_number: int | None,
    section_path: str | None,
    paragraph_number: int | None,
    text_content: str,
) -> None:
    cleaned = _clean_text(text_content)
    if not cleaned:
        return

    parts = _split_text(cleaned)
    for part_number, part in enumerate(parts, start=1):
        if len(segments) >= MAX_SOURCE_SEGMENTS:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=(
                    "The document contains more than the supported "
                    f"{MAX_SOURCE_SEGMENTS:,} extractable sections."
                ),
            )

        label = location_label
        if len(parts) > 1:
            label = f"{location_label} (part {part_number})"

        digest = hashlib.sha256(part.encode("utf-8")).hexdigest()
        segments.append(
            ExtractedSegment(
                segment_index=len(segments) + 1,
                location_type=location_type,
                location_label=label[:500],
                page_number=page_number,
                section_path=section_path[:1000] if section_path else None,
                paragraph_number=paragraph_number,
                text_content=part,
                sha256_hash=digest,
            )
        )


def _extract_pdf(content: bytes) -> tuple[list[ExtractedSegment], int, list[str]]:
    if b"%PDF-" not in content[:1024]:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The file extension is PDF, but its contents are not a valid PDF file.",
        )

    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password-protected PDFs are not supported. Upload an unlocked PDF.",
            )
        page_count = len(reader.pages)
        if page_count < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The PDF does not contain any pages.",
            )
        if page_count > MAX_PDF_PAGES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"PDFs are limited to {MAX_PDF_PAGES} pages.",
            )

        segments: list[ExtractedSegment] = []
        warnings_list: list[str] = []
        total_characters = 0

        for page_index, page in enumerate(reader.pages, start=1):
            try:
                extracted = _clean_text(page.extract_text())
            except Exception:
                warnings_list.append(f"Text extraction failed on PDF page {page_index}.")
                continue

            if not extracted:
                warnings_list.append(
                    f"No selectable text was found on PDF page {page_index}."
                )
                continue

            total_characters += len(extracted)
            if total_characters > MAX_EXTRACTED_TEXT_CHARACTERS:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="The document exceeds the supported extracted-text limit.",
                )

            _append_segments(
                segments,
                location_type="page",
                location_label=f"Page {page_index}",
                page_number=page_index,
                section_path=None,
                paragraph_number=None,
                text_content=extracted,
            )

        if not segments:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "No selectable text could be extracted from this PDF. "
                    "Scanned or image-only PDFs require OCR and are not supported."
                ),
            )

        return segments, page_count, warnings_list

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded PDF is damaged, malformed, or cannot be read.",
        ) from None


def _extract_docx(content: bytes) -> tuple[list[ExtractedSegment], None, list[str]]:
    _validate_docx_package(content)

    try:
        document = Document(BytesIO(content))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded DOCX file could not be opened.",
        ) from None

    segments: list[ExtractedSegment] = []
    heading_stack: list[str] = []
    paragraph_number = 0
    table_number = 0
    total_characters = 0

    for block in _iter_docx_blocks(document):
        if isinstance(block, Paragraph):
            text = _clean_text(block.text)
            if not text:
                continue

            heading_level = _heading_level(block)
            if heading_level is not None:
                while len(heading_stack) >= heading_level:
                    heading_stack.pop()
                heading_stack.append(text[:300])
                continue

            paragraph_number += 1
            section_path = " > ".join(heading_stack) or None
            location_label = (
                f"{section_path} · Paragraph {paragraph_number}"
                if section_path
                else f"Paragraph {paragraph_number}"
            )
            total_characters += len(text)
            _append_segments(
                segments,
                location_type="section",
                location_label=location_label,
                page_number=None,
                section_path=section_path,
                paragraph_number=paragraph_number,
                text_content=text,
            )

        elif isinstance(block, Table):
            table_number += 1
            section_path = " > ".join(heading_stack) or None
            for row_number, row in enumerate(block.rows, start=1):
                cell_values = [_clean_text(cell.text) for cell in row.cells]
                row_text = " | ".join(value for value in cell_values if value)
                if not row_text:
                    continue

                total_characters += len(row_text)
                location_label = f"Table {table_number}, Row {row_number}"
                if section_path:
                    location_label = f"{section_path} · {location_label}"

                _append_segments(
                    segments,
                    location_type="table_row",
                    location_label=location_label,
                    page_number=None,
                    section_path=section_path,
                    paragraph_number=None,
                    text_content=row_text,
                )

        if total_characters > MAX_EXTRACTED_TEXT_CHARACTERS:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The document exceeds the supported extracted-text limit.",
            )

    if not segments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No extractable text was found in this DOCX document.",
        )

    return segments, None, []


def extract_source_document(
    content: bytes,
    filename: str | None,
    declared_mime_type: str | None = None,
) -> ExtractedDocument:
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded document is empty.",
        )

    if len(content) > MAX_SOURCE_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                "The source document exceeds the 15 MB upload limit. "
                "Compress the document or upload a smaller file."
            ),
        )

    safe_name = _safe_filename(filename)
    extension = PurePosixPath(safe_name).suffix.lower()
    expected_mime = ALLOWED_UPLOAD_TYPES.get(extension)
    if expected_mime is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF and DOCX source documents are supported.",
        )

    declared = (declared_mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if declared not in ALLOWED_DECLARED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded document has an unsupported content type.",
        )
    if declared not in {expected_mime, "application/octet-stream"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The filename extension and declared content type do not match.",
        )

    if extension == ".pdf":
        segments, page_count, extraction_warnings = _extract_pdf(content)
        document_format: Literal["PDF", "DOCX"] = "PDF"
    else:
        segments, page_count, extraction_warnings = _extract_docx(content)
        document_format = "DOCX"

    return ExtractedDocument(
        original_filename=safe_name,
        mime_type=expected_mime,
        document_format=document_format,
        file_size_bytes=len(content),
        sha256_hash=hashlib.sha256(content).hexdigest(),
        page_count=page_count,
        segment_count=len(segments),
        segments=segments,
        extraction_warnings=extraction_warnings,
    )
