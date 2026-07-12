from fastapi import APIRouter, Request
from app.auth.router import router as auth_router
from app.studies.router import router as studies_router
from app.ai.factory import provider_diagnostics
from app.ai.router import router as ai_router
from app.sharing.router import router as sharing_router
from app.search.router import router as search_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(studies_router)
api_router.include_router(ai_router)
api_router.include_router(sharing_router)
api_router.include_router(search_router)


@api_router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "unbound-bible"}


@api_router.get("/health/providers", tags=["system"])
def provider_health(request: Request) -> dict:
    return {"status": "healthy", "providers": provider_diagnostics(request.app.state.settings)}
