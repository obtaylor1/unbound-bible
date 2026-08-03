from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute('PRAGMA foreign_keys=ON')
    finally:
        cursor.close()


def create_database_engine(settings: Settings) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    database_engine = create_engine(settings.database_url, **options)
    if database_engine.dialect.name == 'sqlite':
        event.listen(database_engine, 'connect', _enable_sqlite_foreign_keys)
    return database_engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


settings = get_settings()
engine = create_database_engine(settings)
SessionLocal = create_session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
