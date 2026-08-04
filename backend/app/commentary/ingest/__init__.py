"""Strict ingestion support for local commentary source bundles."""

from .adapter import load_helloao_bundle
from .types import NormalizedCommentaryEntry, normalize_body

__all__ = ['NormalizedCommentaryEntry', 'load_helloao_bundle', 'normalize_body']
