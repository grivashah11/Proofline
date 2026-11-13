from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(application: FastAPI):

    database_timeout = httpx.Timeout(
        15.0,
        connect=5.0,
    )

    ai_timeout = httpx.Timeout(
        60.0,
        connect=10.0,
    )

    database_limits = httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
    )

    ai_limits = httpx.Limits(
        max_connections=20,
        max_keepalive_connections=10,
    )

    async with (
        httpx.AsyncClient(
            timeout=database_timeout,
            limits=database_limits,
            follow_redirects=False,
        ) as database_client,
        httpx.AsyncClient(
            timeout=ai_timeout,
            limits=ai_limits,
            follow_redirects=False,
        ) as ai_client,
    ):
        application.state.http_client = database_client
        application.state.ai_http_client = ai_client

        yield

        application.state.http_client = None
        application.state.ai_http_client = None


def create_app() -> FastAPI:
    settings = get_settings()

    documentation_enabled = settings.app_env != "production"

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Proofline is an evidence-led brand-governance and content-review platform."
        ),
        docs_url="/docs" if documentation_enabled else None,
        redoc_url="/redoc" if documentation_enabled else None,
        openapi_url=(
            f"{settings.api_v1_prefix}/openapi.json" if documentation_enabled else None
        ),
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=[
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "apikey",
        ],
        expose_headers=["X-Request-ID"],
    )

    @application.middleware("http")
    async def request_id_middleware(request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id

        return response

    @application.middleware("http")
    async def security_headers_middleware(request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        return response

    application.include_router(
        api_router,
        prefix=settings.api_v1_prefix,
    )

    @application.get("/", include_in_schema=False)
    async def root():
        return {
            "service": settings.app_name,
            "status": "running",
            "health": f"{settings.api_v1_prefix}/health",
        }

    return application


app = create_app()
