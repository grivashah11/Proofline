from difflib import SequenceMatcher

from app.schemas.governance import (
    RevisionDiffOperation,
    RevisionDiffResponse,
    RevisionDiffSummary,
)


def build_revision_diff(
    *,
    content_id,
    from_revision: dict,
    to_revision: dict,
) -> RevisionDiffResponse:
    """Build a line-oriented diff between two immutable revisions."""
    old_lines = str(from_revision.get("content_text") or "").splitlines()
    new_lines = str(to_revision.get("content_text") or "").splitlines()
    matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=True)

    operations: list[RevisionDiffOperation] = []
    summary = RevisionDiffSummary()

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_slice = old_lines[i1:i2]
        new_slice = new_lines[j1:j2]

        if tag == "equal":
            summary.unchanged_lines += len(old_slice)
        elif tag == "insert":
            summary.inserted_lines += len(new_slice)
            summary.changed_blocks += 1
        elif tag == "delete":
            summary.deleted_lines += len(old_slice)
            summary.changed_blocks += 1
        elif tag == "replace":
            summary.deleted_lines += len(old_slice)
            summary.inserted_lines += len(new_slice)
            summary.changed_blocks += 1

        operations.append(
            RevisionDiffOperation(
                operation=tag,
                from_start_line=i1 + 1,
                from_end_line=i2,
                to_start_line=j1 + 1,
                to_end_line=j2,
                from_lines=old_slice,
                to_lines=new_slice,
            )
        )

    return RevisionDiffResponse(
        content_id=content_id,
        from_revision_id=from_revision["id"],
        from_revision_number=from_revision["revision_number"],
        to_revision_id=to_revision["id"],
        to_revision_number=to_revision["revision_number"],
        summary=summary,
        operations=operations,
    )
