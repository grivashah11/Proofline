from uuid import uuid4

from app.services.revision_diff import build_revision_diff


def test_revision_diff_identifies_insert_delete_and_replace_blocks():
    content_id = uuid4()
    from_revision = {
        "id": uuid4(),
        "revision_number": 1,
        "content_text": "Headline\nOld benefit\nFooter",
    }
    to_revision = {
        "id": uuid4(),
        "revision_number": 2,
        "content_text": "Headline\nUpdated benefit\nFooter\nNew disclaimer",
    }

    result = build_revision_diff(
        content_id=content_id,
        from_revision=from_revision,
        to_revision=to_revision,
    )

    assert result.content_id == content_id
    assert result.from_revision_number == 1
    assert result.to_revision_number == 2
    assert result.summary.inserted_lines == 2
    assert result.summary.deleted_lines == 1
    assert result.summary.unchanged_lines == 2
    assert result.summary.changed_blocks == 2
    assert any(item.operation == "replace" for item in result.operations)
    assert any(item.operation == "insert" for item in result.operations)


def test_revision_diff_supports_empty_and_unchanged_revisions():
    revision = {
        "id": uuid4(),
        "revision_number": 1,
        "content_text": "Same content\nSecond line",
    }

    result = build_revision_diff(
        content_id=uuid4(),
        from_revision=revision,
        to_revision=revision,
    )

    assert result.summary.inserted_lines == 0
    assert result.summary.deleted_lines == 0
    assert result.summary.unchanged_lines == 2
    assert result.summary.changed_blocks == 0
    assert [item.operation for item in result.operations] == ["equal"]
