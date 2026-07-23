"""
Assistant App - Views

A canned-question "assistant": free text in, fuzzy-matched against a
fixed registry of questions (questions.py), answered from the same
aggregation functions the dashboard already uses. No LLM involved.
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.permissions.templatetags.permission_tags import can_access

from .matching import match
from .questions import QUESTIONS, DEFAULT_SUGGESTIONS

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 300


def _can_use_assistant(user) -> bool:
    return user.is_superuser or can_access(user, 'dashboard')


@login_required
@require_POST
def ask(request):
    if not _can_use_assistant(request.user):
        return JsonResponse({'error': 'Not available for this account.'}, status=403)

    try:
        payload = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid request.'}, status=400)

    text = str(payload.get('question', '')).strip()[:MAX_QUESTION_LENGTH]
    if not text:
        return JsonResponse({'error': 'Ask me something first.'}, status=400)

    question, suggestions, score = match(text, QUESTIONS)

    if question is None:
        options = suggestions or DEFAULT_SUGGESTIONS
        return JsonResponse({
            'matched': False,
            'answer': "I'm not sure about that one. Try one of these:",
            'suggestions': [{'id': q.id, 'prompt': q.prompt} for q in options],
        })

    try:
        answer = question.handler(text)
    except Exception:
        logger.exception("Assistant handler failed for question_id=%s", question.id)
        answer = "I ran into a problem pulling that up — try again in a moment."

    return JsonResponse({
        'matched': True,
        'question_id': question.id,
        'answer': answer,
    })


@login_required
def suggestions(request):
    """Starter prompts shown when the chat widget first opens."""
    if not _can_use_assistant(request.user):
        return JsonResponse({'error': 'Not available for this account.'}, status=403)

    return JsonResponse({
        'suggestions': [{'id': q.id, 'prompt': q.prompt} for q in QUESTIONS],
    })
