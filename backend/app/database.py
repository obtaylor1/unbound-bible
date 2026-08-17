from collections.abc import Generator, Iterable

from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


class ImmutableRecordError(RuntimeError):
    """Raised when an application session attempts to mutate an immutable record."""


class ApplicationSession(Session):
    """Application session with guards for marker-declared immutable models."""

    @staticmethod
    def _raise_if_immutable_model(mapper) -> None:
        mapped_class = getattr(mapper, 'class_', mapper)
        if not getattr(mapped_class, '__immutable_record__', False):
            return
        error_type = getattr(
            mapped_class, '__immutable_record_error__', ImmutableRecordError
        )
        raise error_type(f'{mapped_class.__name__} records are immutable')

    def bulk_update_mappings(self, mapper, mappings) -> None:
        self._raise_if_immutable_model(mapper)
        super().bulk_update_mappings(mapper, mappings)

    def bulk_save_objects(
        self,
        objects: Iterable[object],
        return_defaults: bool = False,
        update_changed_only: bool = True,
        preserve_order: bool = True,
    ) -> None:
        records = list(objects)
        for record in records:
            if (
                getattr(type(record), '__immutable_record__', False)
                and inspect(record).key is not None
            ):
                self._raise_if_immutable_model(type(record))
        super().bulk_save_objects(
            records,
            return_defaults=return_defaults,
            update_changed_only=update_changed_only,
            preserve_order=preserve_order,
        )

    # Session guards cannot intercept raw SQL executed on a Connection. Database
    # migrations must install UPDATE/DELETE triggers for immutable tables.


def _enable_sqlite_foreign_keys(dbapi_connection, *_args) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute('PRAGMA foreign_keys=ON')
    finally:
        cursor.close()


def ensure_sqlite_foreign_keys(database_engine: Engine) -> None:
    """Enable SQLite foreign keys on every checkout, including pooled connections."""
    if database_engine.dialect.name != 'sqlite':
        return
    if not event.contains(database_engine, 'checkout', _enable_sqlite_foreign_keys):
        event.listen(database_engine, 'checkout', _enable_sqlite_foreign_keys)


def create_database_engine(settings: Settings) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    database_engine = create_engine(settings.database_url, **options)
    ensure_sqlite_foreign_keys(database_engine)
    return database_engine


def create_session_factory(engine: Engine) -> sessionmaker[ApplicationSession]:
    return sessionmaker(
        bind=engine,
        class_=ApplicationSession,
        autoflush=False,
        expire_on_commit=False,
    )


settings = get_settings()
engine = create_database_engine(settings)
SessionLocal = create_session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
