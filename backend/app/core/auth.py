from dataclasses import dataclass, field
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.http_client import get_http_client
from app.schemas.auth import AuthenticatedUser, SupabaseAuthUser

bearer_scheme = HTTPBearer(auto_error=False)

CredentialsDependency = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]

SettingsDependency = Annotated[
    Settings,
    Depends(get_settings),
]

HttpClientDependency = Annotated[
    httpx.AsyncClient,
    Depends(get_http_client),
]


@dataclass(frozen=True)
class AuthContext:
    user: AuthenticatedUser
    access_token: str = field(repr=False)


async def get_auth_context(
    credentials: CredentialsDependency,
    settings: SettingsDependency,
    client: HttpClientDependency,
) -> AuthContext:

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if not token or len(token) > 8192:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.supabase_url is None or settings.supabase_publishable_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured.",
        )

    auth_url = f"{settings.supabase_url}/auth/v1/user"

    headers = {
        "apikey": settings.supabase_publishable_key.get_secret_value(),
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        response = await client.get(
            auth_url,
            headers=headers,
        )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service timed out.",
        ) from None

    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from None

    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify authentication.",
        )

    try:
        auth_user = SupabaseAuthUser.model_validate(response.json())

    except (ValidationError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication service returned an invalid response.",
        ) from None

    return AuthContext(
        user=AuthenticatedUser(
            id=auth_user.id,
            email=auth_user.email,
        ),
        access_token=token,
    )
