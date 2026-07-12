from app.ai.retrieval import RetrievedSource


def validate_citations(citation_ids: list[str], sources: list[RetrievedSource]) -> tuple[list[str], bool]:
    available = {source.id for source in sources}
    valid = [citation_id for citation_id in citation_ids if citation_id in available]
    return valid, len(valid) == len(citation_ids)
