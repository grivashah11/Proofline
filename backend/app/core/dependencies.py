from typing import Annotated

import httpx
from fastapi import Depends

from app.core.auth import AuthContext, get_auth_context
from app.core.config import Settings, get_settings
from app.core.http_client import get_http_client
from app.core.supabase_gateway import SupabaseGateway

AuthContextDependency = Annotated[
    AuthContext,
    Depends(get_auth_context),
]

SettingsDependency = Annotated[
    Settings,
    Depends(get_settings),
]

HttpClientDependency = Annotated[
    httpx.AsyncClient,
    Depends(get_http_client),
]


def get_supabase_gateway(
    auth: AuthContextDependency,
    settings: SettingsDependency,
    client: HttpClientDependency,
) -> SupabaseGateway:
    return SupabaseGateway(
        client=client,
        settings=settings,
        auth=auth,
    )
