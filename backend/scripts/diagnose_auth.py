import sys
from getpass import getpass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings

API_URL = "http://127.0.0.1:8000"


def response_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return "Non-JSON response received."

    if isinstance(data, dict):
        detail = (
            data.get("detail")
            or data.get("msg")
            or data.get("message")
            or data.get("error_description")
            or data.get("error")
        )
        return str(detail or "No error detail returned.")[:500]

    return "Unexpected response format."


def main() -> None:
    settings = Settings()

    print("\n--- BACKEND CONFIGURATION ---")

    print("Supabase URL configured:", bool(settings.supabase_url))
    print(
        "Supabase host:",
        urlsplit(settings.supabase_url).netloc if settings.supabase_url else "MISSING",
    )
    print(
        "Publishable key configured:",
        bool(settings.supabase_publishable_key),
    )

    if not settings.supabase_url or not settings.supabase_publishable_key:
        print("\nFAILED: Backend Supabase configuration is missing.")
        raise SystemExit(1)

    email = input("\nSupabase email: ").strip()
    password = getpass("Supabase password: ")

    api_key = settings.supabase_publishable_key.get_secret_value()

    headers = {
        "apikey": api_key,
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            print("\n--- STEP 1: SUPABASE LOGIN ---")

            login = client.post(
                f"{settings.supabase_url}/auth/v1/token",
                params={"grant_type": "password"},
                headers=headers,
                json={
                    "email": email,
                    "password": password,
                },
            )

            password = ""

            print("HTTP status:", login.status_code)

            if login.status_code != 200:
                print("Response:", response_detail(login))
                raise SystemExit(1)

            token = login.json().get("access_token")

            if not token:
                print("FAILED: Access token missing.")
                raise SystemExit(1)

            print("PASS: Login succeeded.")

            auth_headers = {
                **headers,
                "Authorization": f"Bearer {token}",
            }

            print("\n--- STEP 2: DIRECT SUPABASE TOKEN VERIFICATION ---")

            direct = client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers=auth_headers,
            )

            print("HTTP status:", direct.status_code)

            if direct.status_code != 200:
                print("Response:", response_detail(direct))
            else:
                print("PASS: Supabase verified the access token.")

            print("\n--- STEP 3: FASTAPI TOKEN VERIFICATION ---")

            backend = client.get(
                f"{API_URL}/api/v1/auth/me",
                headers=auth_headers,
            )

            print("HTTP status:", backend.status_code)

            if backend.status_code != 200:
                print("Response:", response_detail(backend))
            else:
                print("PASS: FastAPI authenticated the user.")
                print("Authenticated user ID:", backend.json()["id"])

            token = ""

    except httpx.RequestError as exc:
        print("\nCONNECTION ERROR:", type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
