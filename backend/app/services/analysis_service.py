from app.schemas.analysis import (
    AnalysisFindingSeverity,
)
from app.schemas.claim_extraction import (
    ClaimAssessment,
    PassportMatchStatus,
)
from app.schemas.rule_engine import RuleCheckResponse

CLAIM_TITLES = {
    PassportMatchStatus.SUPPORTED: "Claim supported by active Passport",
    PassportMatchStatus.CONFLICT: "Claim conflicts with active Passport",
    PassportMatchStatus.REVIEW_DUE: "Claim Passport requires review",
    PassportMatchStatus.NEEDS_VERIFICATION: "Claim needs verification",
}


def _claim_severity(
    outcome: PassportMatchStatus,
) -> AnalysisFindingSeverity:
    if outcome == PassportMatchStatus.CONFLICT:
        return AnalysisFindingSeverity.ERROR

    if outcome in {
        PassportMatchStatus.REVIEW_DUE,
        PassportMatchStatus.NEEDS_VERIFICATION,
    }:
        return AnalysisFindingSeverity.WARNING

    return AnalysisFindingSeverity.INFO


def build_analysis_findings(
    rule_result: RuleCheckResponse,
    assessments: list[ClaimAssessment],
) -> list[dict]:
    findings: list[dict] = []

    for finding in rule_result.findings:
        findings.append(
            {
                "source": finding.source.value,
                "source_id": str(finding.source_id),
                "category": finding.category.value,
                "outcome": finding.outcome.value,
                "severity": finding.severity.value,
                "title": finding.title,
                "message": finding.message,
                "recommended_action": finding.recommended_action,
                "start_index": finding.start_index,
                "end_index": finding.end_index,
                "matched_text": finding.matched_text,
                "source_span_verified": (
                    finding.start_index is not None and finding.end_index is not None
                ),
                "candidate_claim": None,
                "passport_id": None,
                "passport_version_id": None,
                "passport_version_number": None,
                "approved_wording": None,
                "evidence_source_title": None,
                "evidence_source_url": None,
                "evidence_reference": None,
                "evidence_excerpt": None,
            }
        )

    for assessment in assessments:
        passport_id = assessment.passport_id

        findings.append(
            {
                "source": ("claim_passport" if passport_id else "ai_claim"),
                "source_id": str(passport_id) if passport_id else None,
                "category": "claim",
                "outcome": assessment.status.value,
                "severity": _claim_severity(assessment.status).value,
                "title": CLAIM_TITLES[assessment.status],
                "message": assessment.explanation,
                "recommended_action": assessment.recommended_action,
                "start_index": assessment.start_index,
                "end_index": assessment.end_index,
                "matched_text": assessment.candidate.exact_text,
                "source_span_verified": assessment.source_span_verified,
                "candidate_claim": assessment.candidate.model_dump(mode="json"),
                "passport_id": (
                    str(assessment.passport_id) if assessment.passport_id else None
                ),
                "passport_version_id": (
                    str(assessment.passport_version_id)
                    if assessment.passport_version_id
                    else None
                ),
                "passport_version_number": assessment.passport_version_number,
                "approved_wording": assessment.approved_wording,
                "evidence_source_title": assessment.evidence_source_title,
                "evidence_source_url": assessment.evidence_source_url,
                "evidence_reference": assessment.evidence_reference,
                "evidence_excerpt": assessment.evidence_excerpt,
            }
        )

    return findings
