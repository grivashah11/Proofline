from urllib.parse import quote

import httpx
from fastapi import HTTPException, status

from app.core.auth import AuthContext
from app.core.config import Settings

BRAND_IMAGE_BUCKET = "proofline-workspace-images"
SOURCE_DOCUMENT_BUCKET = "proofline-source-documents"
ALLOWED_STORAGE_BUCKETS = {
    BRAND_IMAGE_BUCKET,
    SOURCE_DOCUMENT_BUCKET,
}


class SupabaseStorageGateway:
    """User-scoped access to approved private Supabase Storage buckets."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: Settings,
        auth: AuthContext,
    ) -> None:
        if settings.supabase_url is None or settings.supabase_publishable_key is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File storage is not configured.",
            )

        self.client = client
        self.base_url = settings.supabase_url.rstrip("/")
        self.publishable_key = settings.supabase_publishable_key.get_secret_value()
        self.access_token = auth.access_token

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.publishable_key,
            "Authorization": f"Bearer {self.access_token}",
        }

    @staticmethod
    def _validate_bucket(bucket: str) -> str:
        if bucket not in ALLOWED_STORAGE_BUCKETS:
            raise ValueError("Storage bucket is not permitted by this application.")
        return bucket

    def _object_url(
        self,
        path: str,
        *,
        bucket: str = BRAND_IMAGE_BUCKET,
        authenticated_download: bool = False,
    ) -> str:
        bucket = self._validate_bucket(bucket)
        encoded_path = quote(path, safe="/")
        endpoint = "/authenticated" if authenticated_download else ""
        return (
            f"{self.base_url}/storage/v1/object{endpoint}/"
            f"{quote(bucket, safe='')}/{encoded_path}"
        )

    async def upload(
        self,
        path: str,
        content: bytes,
        mime_type: str,
        *,
        bucket: str = BRAND_IMAGE_BUCKET,
    ) -> None:
        headers = self._headers()
        headers.update(
            {
                "Content-Type": mime_type,
                "x-upsert": "false",
                "cache-control": "3600",
            }
        )

        try:
            response = await self.client.post(
                self._object_url(path, bucket=bucket),
                content=content,
                headers=headers,
            )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File storage upload timed out.",
            ) from None
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File storage is unavailable.",
            ) from None

        self._raise_storage_error(response, operation="upload")

    async def download(
        self,
        path: str,
        *,
        bucket: str = BRAND_IMAGE_BUCKET,
    ) -> bytes:
        try:
            response = await self.client.get(
                self._object_url(
                    path,
                    bucket=bucket,
                    authenticated_download=True,
                ),
                headers=self._headers(),
            )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File storage download timed out.",
            ) from None
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File storage is unavailable.",
            ) from None

        self._raise_storage_error(response, operation="download")
        return response.content

    async def remove(
        self,
        path: str,
        *,
        bucket: str = BRAND_IMAGE_BUCKET,
    ) -> None:
        """Best-effort rollback for an object whose database insert failed."""
        bucket = self._validate_bucket(bucket)
        url = (
            f"{self.base_url}/storage/v1/object/"
            f"{quote(bucket, safe='')}"
        )
        try:
            response = await self.client.request(
                "DELETE",
                url,
                json={"prefixes": [path]},
                headers={**self._headers(), "Content-Type": "application/json"},
            )
        except httpx.RequestError:
            return

        # Rollback is intentionally best-effort; never mask the original failure.
        if response.is_error:
            return

    @staticmethod
    def _raise_storage_error(response: httpx.Response, *, operation: str) -> None:
        if not response.is_error:
            return

        if response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="File storage authentication failed.",
            )
        if response.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this file.",
            )
        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The stored file was not found.",
            )
        if response.status_code == 409:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A file already exists at this storage path.",
            )
        if response.status_code == 413:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The file exceeds the storage upload limit.",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"File storage {operation} failed.",
        )
