from fastapi import APIRouter

from app.api.v1.endpoints import (
    analyses,
    auth,
    brand_rules,
    claim_extraction,
    claim_passports,
    contents,
    health,
    images,
    reviews,
    rule_checks,
    terminology,
    workspaces,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(workspaces.router)
api_router.include_router(brand_rules.router)
api_router.include_router(terminology.router)
api_router.include_router(claim_passports.router)
api_router.include_router(rule_checks.router)
api_router.include_router(claim_extraction.router)
api_router.include_router(contents.router)
api_router.include_router(analyses.router)
api_router.include_router(reviews.router)
api_router.include_router(images.router)
