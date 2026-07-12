from pydantic import BaseModel


class SearchResult(BaseModel):
    group: str
    id: str
    title: str
    excerpt: str
    url: str


class SearchResponse(BaseModel):
    query: str
    limit: int
    results: list[SearchResult]
