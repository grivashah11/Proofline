import re
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.auth import AuthContext
from app.core.config import Settings

RESOURCE_PATTERN = re.compile(r"^(?:[a-z][a-z0-9_]*|rpc/[a-z][a-z0-9_]*)$")


class SupabaseGateway:
    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: Settings,
        auth: AuthContext,
    ) -> None:

        if settings.supabase_url is None or settings.supabase_publishable_key is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service is not configured.",
            )

        self.client = client
        self.base_url = settings.supabase_url.rstrip("/")
        self.publishable_key = settings.supabase_publishable_key.get_secret_value()
        self.access_token = auth.access_token

    async def request(
        self,
        method: str,
        resource: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> Any:

        if not RESOURCE_PATTERN.fullmatch(resource):
            raise ValueError("Invalid database resource.")

        headers = {
            "apikey": self.publishable_key,
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

        if payload is not None:
            headers["Content-Type"] = "application/json"

        if prefer:
            headers["Prefer"] = prefer

        url = f"{self.base_url}/rest/v1/{resource}"

        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=payload,
                headers=headers,
            )

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database request timed out.",
            ) from None

        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service is unavailable.",
            ) from None

        if response.is_error:
            error_code = None

            try:
                error_data = response.json()

                if isinstance(error_data, dict):
                    error_code = error_data.get("code")

            except ValueError:
                pass

            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Database authentication failed.",
                )

            if response.status_code == 403 or error_code == "42501":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to perform this action.",
                )

            if response.status_code == 404 or error_code == "P0002":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Requested database record was not found.",
                )

            if response.status_code == 409 or error_code in {
                "23505",
                "23503",
                "P0001",
            }:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The operation conflicts with existing data or workspace rules."
                    ),
                )

            if response.status_code == 400 or error_code in {
                "23514",
                "22P02",
                "22023",
            }:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="The database rejected the supplied data.",
                )

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database operation failed.",
            )

        if response.status_code == 204 or not response.content:
            return []

        try:
            return response.json()

        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Database service returned an invalid response.",
            ) from None

    async def rpc(
        self,
        function_name: str,
        payload: dict[str, Any],
    ) -> Any:

        if not re.fullmatch(r"[a-z][a-z0-9_]*", function_name):
            raise ValueError("Invalid database function name.")

        return await self.request(
            "POST",
            f"rpc/{function_name}",
            payload=payload,
        )
