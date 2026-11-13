import pytest
from fastapi import HTTPException

from app.services.ai.openai_client import extract_output_text


def test_extract_output_text_success():
    response = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"claims":[]}',
                    }
                ],
            }
        ],
    }

    assert extract_output_text(response) == '{"claims":[]}'


def test_extract_output_text_rejects_incomplete_response():
    response = {
        "status": "incomplete",
        "output": [],
    }

    with pytest.raises(HTTPException) as error:
        extract_output_text(response)

    assert error.value.status_code == 502


def test_extract_output_text_handles_refusal():
    response = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "status": "completed",
                "content": [
                    {
                        "type": "refusal",
                        "refusal": "Request declined.",
                    }
                ],
            }
        ],
    }

    with pytest.raises(HTTPException) as error:
        extract_output_text(response)

    assert error.value.status_code == 422


def test_extract_output_text_rejects_empty_response():
    response = {
        "status": "completed",
        "output": [],
    }

    with pytest.raises(HTTPException) as error:
        extract_output_text(response)

    assert error.value.status_code == 502


def test_extract_output_text_ignores_non_message_items():
    response = {
        "status": "completed",
        "output": [
            {
                "type": "reasoning",
            },
            {
                "type": "message",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"claims":[]}',
                    }
                ],
            },
        ],
    }

    assert extract_output_text(response) == '{"claims":[]}'
