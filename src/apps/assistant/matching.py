"""
Assistant App - Free-text to canned-question matcher

Fuzzy-matches free text against the Question registry using only the
standard library (difflib) - no LLM, no external dependencies.
"""

import difflib
from typing import List, Optional, Tuple

from .questions import Question
from .text_utils import STOPWORDS, normalize

MATCH_THRESHOLD = 0.4
SUGGESTION_THRESHOLD = 0.12
TOKEN_FUZZ_THRESHOLD = 0.82


def _content_tokens(tokens: set) -> set:
    filtered = tokens - STOPWORDS
    return filtered or tokens  # an all-stopword phrase still needs something to compare


def _tokens_match(a: str, b: str) -> bool:
    if a == b:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= TOKEN_FUZZ_THRESHOLD


def _phrase_score(text_tokens: set, phrase_tokens: set) -> float:
    """
    Fraction of the combined vocabulary (phrase tokens ∪ text tokens) that
    the phrase's tokens account for, matching word-by-word with typo
    tolerance. Both token sets have stopwords stripped first so the
    generic scaffolding words common to every question here don't drown
    out the one content word that actually identifies the intent.

    This deliberately penalizes text tokens the phrase doesn't account
    for - fine for the fixed-template questions in this registry, but
    wrong for open-ended identifiers (plate numbers, client names). Those
    are handled separately in questions.try_entity_lookup(), which runs
    before this matcher.
    """
    if not phrase_tokens or not text_tokens:
        return 0.0
    matched = sum(
        1 for pt in phrase_tokens
        if any(_tokens_match(pt, tt) for tt in text_tokens)
    )
    union_size = len(phrase_tokens | text_tokens)
    return matched / union_size if union_size else 0.0


def _score(norm_text: str, question: Question) -> float:
    text_tokens = _content_tokens(set(norm_text.split()))
    best = 0.0
    for phrase in question.keywords:
        phrase_tokens = _content_tokens(set(normalize(phrase).split()))
        best = max(best, _phrase_score(text_tokens, phrase_tokens))
    return best


def match(text: str, questions: List[Question]) -> Tuple[Optional[Question], List[Question], float]:
    """
    Match free text against the question registry.

    Returns (matched_question_or_None, suggestions, best_score). When no
    question clears MATCH_THRESHOLD, `suggestions` holds up to 3 closest
    candidates above SUGGESTION_THRESHOLD for a "did you mean" fallback.
    """
    norm_text = normalize(text)
    if not norm_text:
        return None, [], 0.0

    scored = sorted(
        ((q, _score(norm_text, q)) for q in questions),
        key=lambda pair: pair[1],
        reverse=True,
    )

    best_question, best_score = scored[0]
    if best_score >= MATCH_THRESHOLD:
        return best_question, [], best_score

    suggestions = [q for q, s in scored[:3] if s >= SUGGESTION_THRESHOLD]
    return None, suggestions, best_score
