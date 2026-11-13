import httpx
from fastapi import HTTPException, Request, status


def get_http_client(request: Request) -> httpx.AsyncClient:
    client = getattr(
        request.app.state,
        "http_client",
        None,
    )

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HTTP client is unavailable.",
        )

    return client


def get_ai_http_client(request: Request) -> httpx.AsyncClient:
    client = getattr(
        request.app.state,
        "ai_http_client",
        None,
    )

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI HTTP client is unavailable.",
        )

    return client
