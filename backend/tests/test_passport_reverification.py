from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.auth import AuthContext, get_auth_context
from app.core.dependencies import get_supabase_gateway
from app.main import app
from app.schemas.auth import AuthenticatedUser


class ReverificationGateway:
    def __init__(self, user_id):
        self.user_id = user_id
        self.workspace_id = uuid4()
        self.overdue_id = uuid4()
        self.expired_id = uuid4()
        self.upcoming_id = uuid4()

    async def request(self, method, resource, *, params=None, payload=None, prefer=None):
        if resource == "workspace_members":
            return [{"role": "brand_owner"}]

        if resource == "claim_passport_versions":
            today = date.today()
            return [
                {
                    "id": str(uuid4()),
                    "claim_passport_id": str(self.overdue_id),
                    "version_number": 1,
                    "review_by": (today - timedelta(days=2)).isoformat(),
                    "valid_until": None,
                    "status": "active",
                },
                {
                    "id": str(uuid4()),
                    "claim_passport_id": str(self.expired_id),
                    "version_number": 3,
                    "review_by": (today + timedelta(days=10)).isoformat(),
                    "valid_until": (today - timedelta(days=1)).isoformat(),
                    "status": "active",
                },
                {
                    "id": str(uuid4()),
                    "claim_passport_id": str(self.upcoming_id),
                    "version_number": 2,
                    "review_by": (today + timedelta(days=5)).isoformat(),
                    "valid_until": (today + timedelta(days=30)).isoformat(),
                    "status": "active",
                },
            ]

        if resource == "claim_passports":
            return [
                {
                    "id": str(self.overdue_id),
                    "passport_code": "PFL-OVERDUE",
                    "subject": "Overdue product",
                },
                {
                    "id": str(self.expired_id),
                    "passport_code": "PFL-EXPIRED",
                    "subject": "Expired product",
                },
                {
                    "id": str(self.upcoming_id),
                    "passport_code": "PFL-UPCOMING",
                    "subject": "Upcoming product",
                },
            ]

        raise AssertionError(f"Unexpected database request: {resource}")


def test_reverification_endpoint_reports_due_overdue_and_expired_versions():
    user_id = uuid4()
    gateway = ReverificationGateway(user_id)

    def override_auth():
        return AuthContext(
            user=AuthenticatedUser(id=user_id, email="reverification@example.com"),
            access_token="test-token",
        )

    previous_auth = app.dependency_overrides.get(get_auth_context)
    previous_gateway = app.dependency_overrides.get(get_supabase_gateway)
    app.dependency_overrides[get_auth_context] = override_auth
    app.dependency_overrides[get_supabase_gateway] = lambda: gateway

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/workspaces/{gateway.workspace_id}/claim-passports/"
                "reverification-reminders?within_days=30"
            )

        assert response.status_code == 200, response.text
        reminders = {item["passport_code"]: item for item in response.json()}
        assert reminders["PFL-OVERDUE"]["status"] == "overdue"
        assert reminders["PFL-EXPIRED"]["status"] == "expired"
        assert reminders["PFL-UPCOMING"]["status"] == "due_soon"
    finally:
        if previous_auth is None:
            app.dependency_overrides.pop(get_auth_context, None)
        else:
            app.dependency_overrides[get_auth_context] = previous_auth
        if previous_gateway is None:
            app.dependency_overrides.pop(get_supabase_gateway, None)
        else:
            app.dependency_overrides[get_supabase_gateway] = previous_gateway
