from dataclasses import asdict, dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.references import ScriptureReference


@dataclass(frozen=True)
class RetrievedSource:
    id: str
    reference: str
    text: str
    translation: str
    kind: str = "scripture"

    def to_dict(self) -> dict:
        return asdict(self)


def retrieve_exact_reference(session: Session, reference: ScriptureReference) -> list[RetrievedSource]:
    statement = text("""SELECT id, book, chapter, verse, text, translation FROM biblical_texts
        WHERE lower(book) = lower(:book) AND chapter = :chapter AND verse BETWEEN :start AND :end
        AND (:translation IS NULL OR upper(translation) = upper(:translation)) ORDER BY verse""")
    try:
        rows = session.execute(statement, {"book": reference.book, "chapter": reference.chapter, "start": reference.verse_start, "end": reference.verse_end, "translation": reference.translation}).mappings()
        return [RetrievedSource(id=f"scripture:{row['id']}", reference=f"{row['book']} {row['chapter']}:{row['verse']}", text=row["text"], translation=row["translation"] or "Unknown") for row in rows]
    except SQLAlchemyError:
        session.rollback()
        return []
