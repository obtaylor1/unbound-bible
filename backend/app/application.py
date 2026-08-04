from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.application_state import wire_application_state
from app.config import Settings, get_settings
from app.database import Base, create_database_engine
from app.auth import models as auth_models  # noqa: F401
from app.studies import models as study_models  # noqa: F401
from app.sharing import models as sharing_models  # noqa: F401
from app.notifications import models as notification_models  # noqa: F401
from app.community import models as community_models  # noqa: F401
from app.library import models as library_models  # noqa: F401
from app.library.ingest import models as ingest_models  # noqa: F401
from app.commentary import models as commentary_models  # noqa: F401
from app.library.seed import seed_ethiopian_canon
from app.library.router import compatibility_router
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
    engine = create_database_engine(settings)
    wire_application_state(application, settings, engine)
    configure_logging()
    if settings.environment == "test":
        Base.metadata.create_all(engine)
        with application.state.session_factory() as session:
            seed_ethiopian_canon(session)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(api_router, prefix="/api/v1")
    application.include_router(compatibility_router)
    return application


app = create_application()
