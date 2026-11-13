import sys
from getpass import getpass
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings

API_URL = "http://127.0.0.1:8000"
DEMO_WORKSPACE_SLUG = "proofline-demo"


def fail(message: str) -> None:
    print(f"\nFAILED: {message}")
    raise SystemExit(1)


def main() -> None:
    settings = Settings()

    if not settings.supabase_is_configured:
        fail("Supabase configuration is missing.")

    if not settings.openai_is_configured:
        fail("OPENAI_API_KEY is missing from backend/.env.")

    email = input("Supabase email: ").strip()
    password = getpass("Supabase password: ")

    headers = {
        "apikey": settings.supabase_publishable_key.get_secret_value(),
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=90.0) as client:
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
                fail("Supabase authentication failed.")

            token = login.json().get("access_token")

            if not token:
                fail("Supabase did not issue an access token.")

            auth_headers = {
                **headers,
                "Authorization": f"Bearer {token}",
            }

            workspaces_response = client.get(
                f"{API_URL}/api/v1/workspaces",
                headers=auth_headers,
            )

            if workspaces_response.status_code != 200:
                fail("Unable to retrieve workspace information.")

            workspaces = workspaces_response.json()

            demo = next(
                (
                    item
                    for item in workspaces
                    if item["workspace"]["slug"] == DEMO_WORKSPACE_SLUG
                ),
                None,
            )

            if demo is None:
                fail("Proofline demo workspace was not found.")

            workspace_id = demo["workspace"]["id"]

            # Fictional hackathon data. Not a real product claim.

            draft = (
                "Meet the HydraLite Bottle. "
                "It keeps beverages cold for up to 24 hours "
                "under the stated test conditions. "
                "Terms and conditions apply."
            )

            print("\nSending one draft to the AI extraction service...")

            response = client.post(
                f"{API_URL}/api/v1/workspaces/{workspace_id}/claim-extraction",
                headers=auth_headers,
                json={
                    "content": draft,
                    "channel": "social",
                    "market": "demo market",
                },
            )

            if response.status_code != 200:
                print("HTTP status:", response.status_code)

                try:
                    print("Error:", response.json().get("detail"))
                except ValueError:
                    pass

                fail("Claim extraction request failed.")

            result = response.json()

            print("\n" + "=" * 48)
            print("PROOFLINE AI EXTRACTION RESPONSE")
            print("=" * 48)

            print("Model:", result["model"])
            print("Extracted claims:", result["extracted_claim_count"])
            print("Supported:", result["supported_count"])
            print("Conflict:", result["conflict_count"])
            print("Review due:", result["review_due_count"])
            print("Needs verification:", result["needs_verification_count"])

            for index, assessment in enumerate(
                result["assessments"],
                start=1,
            ):
                print(f"\nClaim {index}")
                print("Text:", assessment["candidate"]["exact_text"])
                print("Status:", assessment["status"])
                print("Passport:", assessment["passport_code"])
                print("Explanation:", assessment["explanation"])

            if not result["human_approval_required"]:
                fail("Human approval requirement was not preserved.")

            print("\nAI EXTRACTION TEST PASSED")
            print("Human approval remains mandatory.")
            print("The draft was not saved to the database.")

            token = ""

    except httpx.RequestError as exc:
        fail(f"Connection error: {type(exc).__name__}")


if __name__ == "__main__":
    main()
