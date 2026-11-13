from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, get_auth_context
from app.schemas.auth import AuthenticatedUser

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

AuthContextDependency = Annotated[
    AuthContext,
    Depends(get_auth_context),
]


@router.get(
    "/me",
    response_model=AuthenticatedUser,
    summary="Get the currently authenticated user",
)
async def get_me(
    auth: AuthContextDependency,
) -> AuthenticatedUser:
    return auth.user
