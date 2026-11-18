from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.claim_passports import PassportVersionCreate
from app.schemas.source_documents import (
    PassportReverificationReminder,
    ReverificationStatus,
    SourceDocumentRecord,
)


def _version_payload() -> dict:
    return {
        "approved_wording": "Battery life is up to 30 hours.",
        "subject": "Proofline Sample",
        "attribute": "Battery life",
        "review_by": date(2027, 1, 1),
    }


def test_passport_version_allows_manual_source_reference_without_document_link():
    version = PassportVersionCreate(
        **_version_payload(),
        evidence_source_title="Test report",
        evidence_reference="Section 2",
        evidence_excerpt="Battery life is up to 30 hours.",
    )
    assert version.evidence_source_title == "Test report"


def test_passport_version_requires_all_document_link_fields_together():
    with pytest.raises(ValidationError):
        PassportVersionCreate(
            **_version_payload(),
            source_document_id=uuid4(),
        )


def test_passport_version_accepts_complete_document_link():
    version = PassportVersionCreate(
        **_version_payload(),
        source_document_id=uuid4(),
        source_document_segment_id=uuid4(),
        source_excerpt="Battery life is up to 30 hours.",
    )
    assert version.source_document_id is not None
    assert version.source_excerpt == "Battery life is up to 30 hours."


def test_source_document_record_requires_valid_hash_and_segment_count():
    with pytest.raises(ValidationError):
        SourceDocumentRecord.model_validate(
            {
                "id": str(uuid4()),
                "workspace_id": str(uuid4()),
                "title": "Test report",
                "original_filename": "report.pdf",
                "mime_type": "application/pdf",
                "document_format": "PDF",
                "file_size_bytes": 100,
                "sha256_hash": "not-a-hash",
                "page_count": 1,
                "segment_count": 1,
                "uploaded_by": str(uuid4()),
                "created_at": "2026-11-18T10:00:00Z",
            }
        )


def test_reverification_reminder_has_explicit_status():
    reminder = PassportReverificationReminder(
        passport_id=uuid4(),
        passport_code="PFL-001",
        subject="Proofline Sample",
        version_id=uuid4(),
        version_number=2,
        review_by=date(2026, 11, 20),
        status=ReverificationStatus.DUE_SOON,
        days_until_action=2,
    )
    assert reminder.status == ReverificationStatus.DUE_SOON
