"""Session timeout middleware."""
from datetime import datetime

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone


class SessionTimeoutMiddleware:
    """Log authenticated users out after a period of inactivity."""

    SESSION_KEY = 'last_activity'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_skip(request):
            return self.get_response(request)

        if self._has_expired(request):
            logout(request)
            if not request.path.startswith(settings.LOGIN_URL):
                return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")
            return self.get_response(request)

        request.session[self.SESSION_KEY] = timezone.now().isoformat()
        return self.get_response(request)

    def _should_skip(self, request):
        user = getattr(request, 'user', None)
        if not getattr(user, 'is_authenticated', False):
            return True

        return request.path.startswith(('/static/', '/media/', '/favicon.ico'))

    def _has_expired(self, request):
        last_activity = request.session.get(self.SESSION_KEY)
        if not last_activity:
            return False

        try:
            last_activity_at = datetime.fromisoformat(last_activity)
        except ValueError:
            return False

        timeout_seconds = getattr(settings, 'SESSION_IDLE_TIMEOUT_SECONDS', 3600)
        elapsed = timezone.now() - last_activity_at
        return elapsed.total_seconds() >= timeout_seconds