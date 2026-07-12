import uuid
from sqlalchemy import inspect, or_, select, text
from sqlalchemy.orm import Session

from app.search.schemas import SearchResult
from app.sharing.models import SharedStudy
from app.studies.models import StudySession, UserNote
from app.community.models import CommunityPost


def global_search(session: Session, query: str, user_id: uuid.UUID | None, limit: int) -> list[SearchResult]:
    term, pattern = query.strip(), f"%{query.strip()}%"
    per_group = max(1, min(10, limit // 4 or 1))
    results: list[SearchResult] = []
    if inspect(session.bind).has_table('biblical_texts'):
        rows = session.execute(text("SELECT id, book, chapter, verse, text, translation FROM biblical_texts WHERE lower(text) LIKE lower(:pattern) OR lower(book) LIKE lower(:pattern) LIMIT :limit"), {'pattern': pattern, 'limit': per_group}).mappings()
        results.extend(SearchResult(group='scripture', id=str(row['id']), title=f"{row['book']} {row['chapter']}:{row['verse']}", excerpt=row['text'][:240], url=f"/#scriptures?book={row['book']}&chapter={row['chapter']}&verse={row['verse']}") for row in rows)
    shares = session.scalars(select(SharedStudy).where(SharedStudy.visibility == 'public', SharedStudy.revoked_at.is_(None), SharedStudy.title.ilike(pattern)).limit(per_group)).all()
    results.extend(SearchResult(group='shared_studies', id=str(item.id), title=item.title, excerpt='Public shared study', url=f"/share/{item.public_id}") for item in shares)
    community = session.scalars(select(CommunityPost).where(or_(CommunityPost.title.ilike(pattern), CommunityPost.content.ilike(pattern))).limit(per_group)).all()
    results.extend(SearchResult(group='community', id=str(item.id), title=item.title, excerpt=item.content[:240], url='/#community') for item in community)
    if inspect(session.bind).has_table('factbook_entries'):
        rows = session.execute(text("SELECT id, title, summary FROM factbook_entries WHERE lower(title) LIKE lower(:pattern) OR lower(summary) LIKE lower(:pattern) LIMIT :limit"), {'pattern': pattern, 'limit': per_group}).mappings()
        results.extend(SearchResult(group='factbook', id=str(row['id']), title=row['title'], excerpt=(row['summary'] or '')[:240], url='/#factbook') for row in rows)
    if inspect(session.bind).has_table('geographical_locations'):
        rows = session.execute(text("SELECT id, name, description FROM geographical_locations WHERE lower(name) LIKE lower(:pattern) OR lower(description) LIKE lower(:pattern) LIMIT :limit"), {'pattern': pattern, 'limit': per_group}).mappings()
        results.extend(SearchResult(group='locations', id=str(row['id']), title=row['name'], excerpt=(row['description'] or '')[:240], url='/#map') for row in rows)
    if user_id:
        notes = session.scalars(select(UserNote).where(UserNote.owner_id == user_id, or_(UserNote.content.ilike(pattern), UserNote.passage_reference.ilike(pattern))).limit(per_group)).all()
        results.extend(SearchResult(group='my_notes', id=str(item.id), title=item.passage_reference or 'General note', excerpt=item.content[:240], url='/#library') for item in notes)
        studies = session.scalars(select(StudySession).where(StudySession.owner_id == user_id, StudySession.title.ilike(pattern)).limit(per_group)).all()
        results.extend(SearchResult(group='my_studies', id=str(item.id), title=item.title, excerpt='Private study', url='/#library') for item in studies)
    return results[:limit]
