from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

from .middleware import SessionTimeoutMiddleware


class SessionTimeoutMiddlewareTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.user = get_user_model().objects.create_user(
			email='tester@example.com',
			password='password123'
		)

	def _build_request(self, path='/dashboard/'):
		request = self.factory.get(path)
		SessionMiddleware(lambda req: HttpResponse()).process_request(request)
		request.session.save()
		request.user = self.user
		return request

	def test_authenticated_request_refreshes_last_activity(self):
		request = self._build_request()
		middleware = SessionTimeoutMiddleware(lambda req: HttpResponse('ok'))

		response = middleware(request)

		self.assertEqual(response.status_code, 200)
		self.assertIn('last_activity', request.session)

	def test_expired_session_redirects_to_login(self):
		request = self._build_request('/dashboard/')
		request.session['last_activity'] = (timezone.now() - timedelta(hours=2)).isoformat()
		middleware = SessionTimeoutMiddleware(lambda req: HttpResponse('ok'))

		response = middleware(request)

		self.assertEqual(response.status_code, 302)
		self.assertTrue(response.url.startswith('/accounts/login/'))
		self.assertFalse(request.user.is_authenticated)
