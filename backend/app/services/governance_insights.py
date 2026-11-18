from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from app.schemas.governance import (
    EvidenceGapCandidate,
    FindingResolutionSummary,
    GovernanceInsightsResponse,
    GuidelineGapCandidate,
    RecurringIssuePattern,
)

GUIDELINE_SUGGESTIONS = {
    "messaging": (
        "Consider adding concrete required message elements, approved examples, "
        "and wording boundaries to this guideline."
    ),
    "brand_voice": (
        "Consider adding observable tone criteria and positive/negative examples "
        "so creators and reviewers can apply this guidance consistently."
    ),
    "channel_guidance": (
        "Consider clarifying the channel-specific requirement with an example "
        "and a measurable acceptance criterion."
    ),
}


def _as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def build_governance_insights(
    *,
    workspace_id: UUID,
    records: list[dict],
    window_start: datetime,
    window_days: int,
    min_distinct_submissions: int,
    limit: int,
) -> GovernanceInsightsResponse:
    """Aggregate workspace-level issue patterns from per-content lifecycle rows."""
    current_rows: list[dict] = []
    for row in records:
        last_seen = _as_datetime(row["last_seen_at"])
        # Keep unresolved issues visible even if their last observation is older
        # than the requested reporting window.
        if last_seen >= window_start or row.get("status") == "open":
            copied = dict(row)
            copied["_last_seen"] = last_seen
            current_rows.append(copied)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in current_rows:
        grouped[str(row["fingerprint"])].append(row)

    recurring: list[RecurringIssuePattern] = []
    guideline_gaps: list[GuidelineGapCandidate] = []
    evidence_gaps: list[EvidenceGapCandidate] = []

    for fingerprint, rows in grouped.items():
        distinct_submissions = len({str(row["content_id"]) for row in rows})
        total_occurrences = sum(int(row.get("occurrence_count") or 0) for row in rows)
        open_submissions = sum(row.get("status") == "open" for row in rows)
        resolved_submissions = sum(row.get("status") == "resolved" for row in rows)
        reappeared_submissions = sum(int(row.get("reappeared_count") or 0) > 0 for row in rows)
        latest = max(rows, key=lambda row: row["_last_seen"])

        if distinct_submissions >= min_distinct_submissions:
            recurring.append(
                RecurringIssuePattern(
                    fingerprint=fingerprint,
                    source=latest["source"],
                    category=latest["category"],
                    source_id=latest.get("source_id"),
                    title=latest["issue_title"],
                    distinct_submissions=distinct_submissions,
                    total_occurrences=total_occurrences,
                    open_submissions=open_submissions,
                    resolved_submissions=resolved_submissions,
                    reappeared_submissions=reappeared_submissions,
                    last_seen_at=latest["_last_seen"],
                )
            )

        if (
            distinct_submissions >= min_distinct_submissions
            and latest["source"] == "brand_rule"
            and latest["category"] in GUIDELINE_SUGGESTIONS
            and any(row.get("last_outcome") == "needs_review" for row in rows)
        ):
            guideline_gaps.append(
                GuidelineGapCandidate(
                    fingerprint=fingerprint,
                    rule_id=latest.get("source_id"),
                    category=latest["category"],
                    current_guideline_title=latest["issue_title"],
                    distinct_submissions=distinct_submissions,
                    total_occurrences=total_occurrences,
                    suggested_clarification=GUIDELINE_SUGGESTIONS[latest["category"]],
                    requires_owner_confirmation=True,
                )
            )

        if (
            distinct_submissions >= min_distinct_submissions
            and latest["source"] in {"ai_claim", "claim_passport"}
            and latest["category"] == "claim"
            and any(row.get("last_outcome") == "needs_verification" for row in rows)
        ):
            evidence_gaps.append(
                EvidenceGapCandidate(
                    fingerprint=fingerprint,
                    subject=latest.get("claim_subject"),
                    attribute=latest.get("claim_attribute"),
                    distinct_submissions=distinct_submissions,
                    total_occurrences=total_occurrences,
                    suggested_action=(
                        "Ask the Brand Owner to confirm whether an approved Claim Passport "
                        "and supporting source should be registered for this recurring claim."
                    ),
                    requires_owner_confirmation=True,
                )
            )

    recurring.sort(key=lambda item: (item.distinct_submissions, item.total_occurrences), reverse=True)
    guideline_gaps.sort(key=lambda item: (item.distinct_submissions, item.total_occurrences), reverse=True)
    evidence_gaps.sort(key=lambda item: (item.distinct_submissions, item.total_occurrences), reverse=True)

    resolution = FindingResolutionSummary(
        open_threads=sum(row.get("status") == "open" for row in current_rows),
        resolved_threads=sum(row.get("status") == "resolved" for row in current_rows),
        reappeared_threads=sum(int(row.get("reappeared_count") or 0) > 0 for row in current_rows),
    )

    return GovernanceInsightsResponse(
        workspace_id=workspace_id,
        window_days=window_days,
        generated_at=datetime.now(timezone.utc),
        min_distinct_submissions=min_distinct_submissions,
        resolution_summary=resolution,
        recurring_issues=recurring[:limit],
        candidate_guideline_gaps=guideline_gaps[:limit],
        evidence_gaps=evidence_gaps[:limit],
    )
