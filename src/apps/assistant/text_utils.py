"""
Assistant App - Shared text-normalization helpers

Used by both matching.py (fuzzy question matching) and questions.py
(free-form name/identifier extraction for entity lookups) - kept in its
own module so neither imports the other.
"""

import re

# Generic filler words that carry no distinguishing signal for this app's
# question templates ("how many X do we have", "what does X owe", ...).
# Stripping them keeps scoring focused on the words that actually name
# the topic (vehicles vs. clients, expenses vs. revenue) instead of
# letting shared scaffolding words dominate.
STOPWORDS = {
    'a', 'an', 'the', 'is', 'are', 'do', 'does', 'did', 'have', 'has', 'had',
    'how', 'many', 'much', 'what', 'whats', 's', 'we', 'us', 'our', 'i',
    'me', 'my', 'you', 'your', 'give', 'show', 'tell', 'please', 'want',
    'know', 'of', 'in', 'on', 'to', 'for', 'this', 'that', 'it', 'who',
}


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def content_tokens(text: str, extra_stopwords=frozenset()) -> set:
    """Normalized, whitespace-tokenized words with stopwords removed."""
    tokens = set(normalize(text).split())
    return tokens - STOPWORDS - set(extra_stopwords)
