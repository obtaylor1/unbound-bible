"""Seed the immutable Ethiopian Orthodox Tewahedo 81-book catalog."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys
from collections.abc import Sequence

from sqlalchemy import delete, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import create_database_engine, create_session_factory
from app.library.canon import (
    ALIASES,
    ETHIOPIAN_CANON,
    SUPPLEMENTAL_LIBRARY_WORKS,
    WORKS,
    validate_canon,
)
from app.library.models import CanonEntry, CanonEntryWork, LibraryWork, LibraryWorkAlias


CANON_CODE = 'ETHIO81'
REQUIRED_TABLES = frozenset({
    'library_works',
    'library_work_aliases',
    'canon_entries',
    'canon_entry_works',
})


@dataclass(frozen=True)
class EthiopianCanonSeedResult:
    old_testament_count: int
    new_testament_count: int
    entry_count: int
    navigation_work_count: int


def _sync_navigation(session: Session) -> None:
    works_by_id = {
        work.id: work for work in (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS)
    }
    existing_works = {
        work.id: work
        for work in session.scalars(select(LibraryWork).where(LibraryWork.id.in_(works_by_id)))
    }
    for work_id, work in works_by_id.items():
        stored_work = existing_works.get(work_id)
        if stored_work is None:
            session.add(LibraryWork(id=work.id, title=work.name))
        elif stored_work.title != work.name:
            stored_work.title = work.name
    session.flush()

    canonical_work_ids = set(works_by_id)
    aliases = {
        alias: work_id
        for alias, work_id in ALIASES.items()
        if work_id in canonical_work_ids
    }
    existing_aliases = {
        stored_alias.alias: stored_alias
        for stored_alias in session.scalars(
            select(LibraryWorkAlias).where(LibraryWorkAlias.alias.in_(aliases))
        )
    }
    for alias, work_id in aliases.items():
        stored_alias = existing_aliases.get(alias)
        if stored_alias is None:
            session.add(LibraryWorkAlias(alias=alias, work_id=work_id))
        elif stored_alias.work_id != work_id:
            stored_alias.work_id = work_id


def _sync_entries(session: Session) -> None:
    entries_by_key = {
        (entry.testament, entry.order): entry
        for entry in ETHIOPIAN_CANON
    }
    stored_entries = session.scalars(
        select(CanonEntry).where(CanonEntry.canon_code == CANON_CODE)
    ).all()
    current_by_key = {
        (entry.testament, entry.canonical_order): entry
        for entry in stored_entries
    }

    stale_entry_ids = [
        entry.id for entry in stored_entries
        if (entry.testament, entry.canonical_order) not in entries_by_key
    ]
    if stale_entry_ids:
        session.execute(
            delete(CanonEntryWork).where(CanonEntryWork.canon_entry_id.in_(stale_entry_ids))
        )
        session.execute(delete(CanonEntry).where(CanonEntry.id.in_(stale_entry_ids)))

    desired_stored_entries: dict[tuple[str, int], CanonEntry] = {}
    for key, entry in entries_by_key.items():
        stored_entry = current_by_key.get(key)
        if stored_entry is None:
            stored_entry = CanonEntry(
                canon_code=CANON_CODE,
                testament=entry.testament,
                canonical_order=entry.order,
                title=entry.name,
            )
            session.add(stored_entry)
        elif stored_entry.title != entry.name:
            stored_entry.title = entry.name
        desired_stored_entries[key] = stored_entry
    session.flush()

    entry_ids = [entry.id for entry in desired_stored_entries.values()]
    stored_work_ids_by_entry_id: dict[int, set[str]] = {entry_id: set() for entry_id in entry_ids}
    for row in session.execute(
        select(CanonEntryWork.canon_entry_id, CanonEntryWork.work_id).where(
            CanonEntryWork.canon_entry_id.in_(entry_ids)
        )
    ):
        stored_work_ids_by_entry_id[row.canon_entry_id].add(row.work_id)

    for key, entry in entries_by_key.items():
        stored_entry = desired_stored_entries[key]
        expected_work_ids = set(entry.work_ids)
        current_work_ids = stored_work_ids_by_entry_id[stored_entry.id]
        stale_work_ids = current_work_ids - expected_work_ids
        if stale_work_ids:
            session.execute(
                delete(CanonEntryWork).where(
                    CanonEntryWork.canon_entry_id == stored_entry.id,
                    CanonEntryWork.work_id.in_(stale_work_ids),
                )
            )
        for work_id in entry.work_ids:
            if work_id not in current_work_ids:
                session.add(CanonEntryWork(canon_entry_id=stored_entry.id, work_id=work_id))


def seed_ethiopian_canon(session: Session) -> EthiopianCanonSeedResult:
    """Upsert the Ethiopian catalog and commit it as one transaction."""
    try:
        validate_canon()
        _sync_navigation(session)
        _sync_entries(session)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return EthiopianCanonSeedResult(
        old_testament_count=46,
        new_testament_count=35,
        entry_count=81,
        navigation_work_count=len(WORKS),
    )


def _require_seed_schema(engine: Engine) -> None:
    available_tables = set(inspect(engine).get_table_names())
    missing_tables = sorted(REQUIRED_TABLES - available_tables)
    if missing_tables:
        missing = ', '.join(missing_tables)
        raise RuntimeError(
            f'Database schema is missing required library tables: {missing}. '
            'Run Alembic migrations before seeding.'
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Seed the Ethiopian Orthodox 81-book catalog.')
    parser.add_argument('--database-url', required=True, help='Database URL for an already migrated database.')
    args = parser.parse_args(argv)

    engine = create_database_engine(Settings(database_url=args.database_url))
    try:
        _require_seed_schema(engine)
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            result = seed_ethiopian_canon(session)
    except Exception as exc:
        print(f'Unable to seed Ethiopian canon: {exc}', file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print(
        'OT: {old}; NT: {new}; entries: {entries}; navigation works: {works}'.format(
            old=result.old_testament_count,
            new=result.new_testament_count,
            entries=result.entry_count,
            works=result.navigation_work_count,
        )
    )
    expected = (46, 35, 81)
    actual = (result.old_testament_count, result.new_testament_count, result.entry_count)
    return 0 if actual == expected else 1


if __name__ == '__main__':
    raise SystemExit(main())
