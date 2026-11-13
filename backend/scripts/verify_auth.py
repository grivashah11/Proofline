import sys
from getpass import getpass
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings

API_URL = "http://127.0.0.1:8000"
DEMO_WORKSPACE_SLUG = "proofline-demo"


def stop(message: str) -> None:
    print(f"\nFAILED: {message}")
    raise SystemExit(1)


def main() -> None:
    settings = Settings()

    if not settings.supabase_url or not settings.supabase_publishable_key:
        stop("Supabase configuration is missing from backend/.env")

    email = input("Supabase user email: ").strip()
    password = getpass("Supabase user password: ")

    if not email or not password:
        stop("Email and password are required.")

    headers = {
        "apikey": settings.supabase_publishable_key.get_secret_value(),
        "Accept": "application/json",
    }

    print("\n[1/5] Checking protected API access...")

    try:
        with httpx.Client(timeout=20.0) as client:
            unauthenticated = client.get(f"{API_URL}/api/v1/auth/me")

            if unauthenticated.status_code != 401:
                stop("Unauthenticated requests were not rejected with HTTP 401.")

            print("PASS: Unauthenticated access correctly rejected.")

            print("\n[2/5] Authenticating with Supabase...")

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

            if login.status_code != 200:
                try:
                    error_data = login.json()
                    error_message = (
                        error_data.get("msg")
                        or error_data.get("message")
                        or error_data.get("error_description")
                        or "Authentication failed."
                    )
                except ValueError:
                    error_message = "Authentication failed."

                stop(
                    f"Supabase login failed (HTTP {login.status_code}): {error_message}"
                )

            token = login.json().get("access_token")

            if not token:
                stop("Supabase did not return an access token.")

            print("PASS: Supabase login successful.")

            auth_headers = {
                **headers,
                "Authorization": f"Bearer {token}",
            }

            print("\n[3/5] Verifying FastAPI authentication...")

            me = client.get(
                f"{API_URL}/api/v1/auth/me",
                headers=auth_headers,
            )

            if me.status_code != 200:
                stop(f"FastAPI authentication failed: HTTP {me.status_code}")

            user = me.json()
            user_id = user.get("id")

            if not user_id:
                stop("Authenticated user ID is missing.")

            print(f"PASS: User verified: {user.get('email')}")
            print(f"User ID: {user_id}")

            print("\n[4/5] Checking workspace access...")

            workspaces_response = client.get(
                f"{API_URL}/api/v1/workspaces",
                headers=auth_headers,
            )

            if workspaces_response.status_code != 200:
                stop(
                    f"Workspace listing failed: HTTP {workspaces_response.status_code}"
                )

            workspaces = workspaces_response.json()

            demo_workspace = next(
                (
                    item
                    for item in workspaces
                    if item.get("workspace", {}).get("slug") == DEMO_WORKSPACE_SLUG
                ),
                None,
            )

            if demo_workspace is None:
                stop(
                    "Demo workspace was not found. "
                    "Check seed.sql and workspace membership."
                )

            role = demo_workspace.get("role")

            if role != "brand_owner":
                stop(f"Expected brand_owner role, received: {role}")

            workspace = demo_workspace["workspace"]
            workspace_id = workspace["id"]

            print("PASS: Demo workspace accessible.")
            print(f"Workspace: {workspace['name']}")
            print(f"Role: {role}")

            print("\n[5/5] Checking workspace membership...")

            members_response = client.get(
                f"{API_URL}/api/v1/workspaces/{workspace_id}/members",
                headers=auth_headers,
            )

            if members_response.status_code != 200:
                stop(
                    "Workspace membership verification failed: "
                    f"HTTP {members_response.status_code}"
                )

            members = members_response.json()

            own_membership = next(
                (member for member in members if member.get("user_id") == user_id),
                None,
            )

            if own_membership is None:
                stop("Current user membership was not found.")

            print("PASS: Workspace membership verified.")

            token = ""

    except httpx.RequestError as exc:
        stop(
            "Could not connect to Supabase or FastAPI. "
            f"Check that the services are available. {type(exc).__name__}"
        )

    print("\n" + "=" * 48)
    print("PROOFLINE AUTHENTICATION VERIFICATION PASSED")
    print("=" * 48)
    print("Supabase login:       PASS")
    print("JWT verification:     PASS")
    print("Workspace access:     PASS")
    print("Brand Owner role:     PASS")
    print("Membership check:     PASS")
    print("\nNo workspace data was modified.")


if __name__ == "__main__":
    main()
