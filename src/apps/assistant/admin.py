"""
Assistant App - Admin

Read-only view over tracked assistant queries: what staff ask, which
keywords come up, and which questions went unanswered.
"""

from django.contrib import admin

from .models import AssistantQuery


@admin.register(AssistantQuery)
class AssistantQueryAdmin(admin.ModelAdmin):
    list_display = ('text', 'keywords', 'matched', 'question_id', 'user', 'created_at')
    list_filter = ('matched', 'question_id', 'created_at')
    search_fields = ('text', 'keywords')
    readonly_fields = ('user', 'text', 'keywords', 'matched', 'question_id', 'score', 'created_at')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
