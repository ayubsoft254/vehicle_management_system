"""
Assistant App - Models

Keyword tracking for the chat widget: every question asked is logged with
the normalized content keywords it contained, so admins can see what staff
actually search for and which questions the registry fails to answer
(candidates for new canned questions).
"""

from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class AssistantQuery(models.Model):
    """One free-text question asked through the assistant widget."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assistant_queries',
    )

    text = models.CharField(
        'Question Text',
        max_length=300,
        help_text='The raw question as typed by the user',
    )

    keywords = models.CharField(
        'Tracked Keywords',
        max_length=300,
        blank=True,
        help_text='Space-separated content keywords extracted from the question',
    )

    matched = models.BooleanField(
        'Matched',
        default=False,
        help_text='Whether the assistant found an answer for this question',
    )

    question_id = models.CharField(
        'Matched Question ID',
        max_length=50,
        blank=True,
        help_text='Registry id of the question that answered this query',
    )

    score = models.FloatField(
        'Match Score',
        default=0.0,
    )

    created_at = models.DateTimeField(
        'Asked At',
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        db_table = 'assistant_queries'
        verbose_name = 'Assistant Query'
        verbose_name_plural = 'Assistant Queries'
        ordering = ['-created_at']

    def __str__(self):
        state = self.question_id if self.matched else 'unmatched'
        return f"{self.text[:50]} ({state})"

    @classmethod
    def top_keywords(cls, days=30, limit=10, unmatched_only=False):
        """Most frequent tracked keywords over the last `days`, as
        (keyword, count) pairs — the raw material for deciding which new
        canned questions are worth adding."""
        queryset = cls.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=days)
        )
        if unmatched_only:
            queryset = queryset.filter(matched=False)

        counter = Counter()
        for keywords in queryset.values_list('keywords', flat=True):
            counter.update(word for word in keywords.split() if word)
        return counter.most_common(limit)
