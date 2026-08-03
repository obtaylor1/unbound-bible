from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import Settings, get_settings
from app.database import Base, create_database_engine, create_session_factory
from app.auth import models as auth_models  # noqa: F401
from app.studies import models as study_models  # noqa: F401
from app.sharing import models as sharing_models  # noqa: F401
from app.notifications import models as notification_models  # noqa: F401
from app.community import models as community_models  # noqa: F401
from app.library import models as library_models  # noqa: F401
from app.security.rate_limits import InMemoryRateLimiter
from app.observability.logging import configure_logging


def create_application(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    application = FastAPI(
        title="Unbound Bible API",
        version="1.0.0",
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
    )
    application.state.settings = settings
    engine = create_database_engine(settings)
    application.state.database_engine = engine
    application.state.session_factory = create_session_factory(engine)
    application.state.rate_limiter = InMemoryRateLimiter()
    configure_logging()
    if settings.environment == "test":
        Base.metadata.create_all(engine)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_application()
