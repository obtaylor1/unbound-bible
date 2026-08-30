"""Explicit comparison normalization with no hidden text transformations."""

from __future__ import annotations

import unicodedata

from app.library.verification.types import ComparisonRules


def normalize_exact(text: str, rules: ComparisonRules) -> str:
    """Apply only Unicode and configured line-ending normalization."""
    normalized = unicodedata.normalize(rules.unicode_form, text)
    if rules.normalize_line_endings:
        normalized = normalized.replace('\r\n', '\n').replace('\r', '\n')
    return normalized


def normalize_formatting(text: str, rules: ComparisonRules) -> str:
    """Apply exact normalization and the explicitly configured whitespace rule."""
    normalized = normalize_exact(text, rules)
    if rules.collapse_whitespace:
        return ' '.join(normalized.split())
    return normalized
