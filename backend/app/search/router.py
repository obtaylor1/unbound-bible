from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.auth.dependencies import get_optional_user, get_session
from app.auth.models import User
from app.search.schemas import SearchResponse
from app.search.service import global_search


router = APIRouter(prefix='/search', tags=['search'])


@router.get('', response_model=SearchResponse)
def search(q: str = Query(min_length=2, max_length=200), limit: int = Query(default=30, ge=1), user: User | None = Depends(get_optional_user), session: Session = Depends(get_session)):
    bounded_limit = min(limit, 50)
    return SearchResponse(query=q.strip(), limit=bounded_limit, results=global_search(session, q, user.id if user else None, bounded_limit))
