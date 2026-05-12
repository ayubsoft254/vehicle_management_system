from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch

from .models import Notification, NotificationPreference


User = get_user_model()


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='owner@example.com',
            first_name='Owner',
            last_name='User',
            password='password123'
        )

    def test_user_creation_creates_notification_preference(self):
        another_user = User.objects.create_user(
            email='newuser@example.com',
            first_name='New',
            last_name='User',
            password='password123'
        )

        self.assertTrue(
            NotificationPreference.objects.filter(user=another_user).exists()
        )

    @patch('apps.notifications.signals.deliver_notification')
    def test_mark_as_read_sets_timestamp(self, mock_deliver):
        mock_deliver.return_value = {'in_app': True, 'email': False, 'sms': False, 'push': False}
        notification = Notification.objects.create(
            user=self.user,
            title='Test',
            message='Message'
        )

        notification.mark_as_read()
        notification.refresh_from_db()

        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    @patch('apps.notifications.signals.deliver_notification')
    def test_mark_as_unread_clears_timestamp(self, mock_deliver):
        mock_deliver.return_value = {'in_app': True, 'email': False, 'sms': False, 'push': False}
        notification = Notification.objects.create(
            user=self.user,
            title='Test',
            message='Message',
            is_read=True
        )
        notification.read_at = notification.created_at
        notification.save(update_fields=['read_at'])

        notification.mark_as_unread()
        notification.refresh_from_db()

        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

    @patch('apps.notifications.signals.deliver_notification')
    def test_manager_mark_as_read_updates_all_unread(self, mock_deliver):
        mock_deliver.return_value = {'in_app': True, 'email': False, 'sms': False, 'push': False}
        Notification.objects.create(user=self.user, title='N1', message='M1')
        Notification.objects.create(user=self.user, title='N2', message='M2')

        updated = Notification.objects.mark_as_read(self.user)

        self.assertEqual(updated, 2)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=False).count(),
            0
        )
