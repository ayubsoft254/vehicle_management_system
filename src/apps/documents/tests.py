from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.authentication.models import User
from apps.documents.models import Document, DocumentCategory


class RequestSignatureViewTests(TestCase):
	def setUp(self):
		self.owner = User.objects.create_user(email='owner@example.com', password='pass12345')
		self.other_user = User.objects.create_user(email='other@example.com', password='pass12345')
		self.category = DocumentCategory.objects.create(name='Agreements', slug='agreements')

		self.document = Document.objects.create(
			title='Vehicle Sale Agreement',
			category=self.category,
			file=SimpleUploadedFile('agreement.pdf', b'%PDF-1.4 test', content_type='application/pdf'),
			uploaded_by=self.owner,
		)

	@patch('apps.documents.views.create_signature_request')
	def test_owner_can_request_signature(self, mock_create_signature_request):
		mock_create_signature_request.return_value = {
			'submission_id': '12345',
			'slug': 'abc123',
			'signing_link': 'https://docuseal.example.com/s/abc123',
			'raw_response': {},
		}

		self.client.force_login(self.owner)
		response = self.client.post(
			reverse('documents:request_signature', args=[self.document.pk]),
			{
				'signer_name': 'John Doe',
				'signer_email': 'john@example.com',
			},
			follow=False,
		)

		self.assertEqual(response.status_code, 302)
		self.document.refresh_from_db()
		self.assertEqual(self.document.esign_provider, 'docuseal')
		self.assertEqual(self.document.esign_submission_id, '12345')
		self.assertEqual(self.document.esign_signer_name, 'John Doe')
		self.assertEqual(self.document.esign_signer_email, 'john@example.com')
		self.assertEqual(self.document.esign_signing_link, 'https://docuseal.example.com/s/abc123')
		self.assertEqual(self.document.esign_status, 'pending')

	@patch('apps.documents.views.create_signature_request')
	def test_non_owner_cannot_request_signature(self, mock_create_signature_request):
		self.client.force_login(self.other_user)
		response = self.client.post(
			reverse('documents:request_signature', args=[self.document.pk]),
			{
				'signer_name': 'John Doe',
				'signer_email': 'john@example.com',
			},
			follow=False,
		)

		self.assertEqual(response.status_code, 302)
		mock_create_signature_request.assert_not_called()
		self.document.refresh_from_db()
		self.assertEqual(self.document.esign_status, '')

	@patch('apps.documents.views.create_signature_request')
	def test_missing_signer_details_does_not_call_service(self, mock_create_signature_request):
		self.client.force_login(self.owner)
		response = self.client.post(
			reverse('documents:request_signature', args=[self.document.pk]),
			{
				'signer_name': '',
				'signer_email': '',
			},
			follow=False,
		)

		self.assertEqual(response.status_code, 302)
		mock_create_signature_request.assert_not_called()
		self.document.refresh_from_db()
		self.assertEqual(self.document.esign_status, '')
