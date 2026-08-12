"""Start an isolated, minimally seeded backend for local Playwright runs."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from sqlalchemy import text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    return parser


@contextmanager
def isolated_database():
    if os.environ.get("ENVIRONMENT") != "test":
        raise RuntimeError("Playwright backend requires ENVIRONMENT=test")

    original_database_url = os.environ.get("DATABASE_URL")
    with TemporaryDirectory(prefix="unbound-bible-e2e-") as directory:
        database_path = Path(directory) / "playwright.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{database_path}"
        try:
            yield database_path
        finally:
            if original_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = original_database_url


def _seed_verified_reference(application) -> None:
    with application.state.database_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS biblical_texts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book VARCHAR(50) NOT NULL,
                    chapter INTEGER NOT NULL,
                    verse INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    translation VARCHAR(50) NOT NULL,
                    UNIQUE (book, chapter, verse, translation)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT OR IGNORE INTO biblical_texts
                    (book, chapter, verse, text, translation)
                VALUES
                    ('Genesis', 1, 1,
                     'In the beginning God created the heaven and the earth.',
                     'KJV')
                """
            )
        )


def main() -> None:
    arguments = _parser().parse_args()
    with isolated_database():
        from app.application import app

        _seed_verified_reference(app)
        try:
            uvicorn.run(app, host="127.0.0.1", port=arguments.port)
        finally:
            app.state.database_engine.dispose()


if __name__ == "__main__":
    main()
