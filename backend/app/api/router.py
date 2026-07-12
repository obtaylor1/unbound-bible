from fastapi import APIRouter
from app.auth.router import router as auth_router


api_router = APIRouter()
api_router.include_router(auth_router)


@api_router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "unbound-bible"}
