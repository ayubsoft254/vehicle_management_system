from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import User
from apps.clients.models import Client, ClientVehicle
from apps.dashboard.models import MetricCache
from apps.dashboard.utils import get_dashboard_overview_data
from apps.payments.models import Payment
from apps.vehicles.models import Vehicle
from utils.constants import UserRole, VehicleStatus


class PaymentSignalsIntegrationTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email='signals@example.com',
			password='StrongPass123!',
			first_name='Signal',
			last_name='Tester',
			role=UserRole.ACCOUNTANT,
			is_staff=True,
		)

		self.client_profile = Client.objects.create(
			first_name='Jane',
			last_name='Doe',
			id_number='ID-TEST-1001',
			phone_primary='+254712345678',
			physical_address='Nairobi',
			registered_by=self.user,
		)

		self.vehicle = Vehicle.objects.create(
			make='Toyota',
			model='Corolla',
			year=2021,
			vin='JTDBR32E720123456',
			registration_number='KDA123A',
			color='White',
			mileage=15000,
			fuel_type='petrol',
			transmission='automatic',
			condition='good',
			purchase_price=Decimal('1000000.00'),
			selling_price=Decimal('1200000.00'),
			deposit_required=Decimal('100000.00'),
			status=VehicleStatus.SOLD,
			purchase_date=timezone.now().date(),
			added_by=self.user,
		)

		self.client_vehicle = ClientVehicle.objects.create(
			client=self.client_profile,
			vehicle=self.vehicle,
			purchase_date=timezone.now().date(),
			purchase_price=Decimal('1200000.00'),
			deposit_paid=Decimal('0.00'),
			total_paid=Decimal('0.00'),
			balance=Decimal('1200000.00'),
			payment_type='installment',
			created_by=self.user,
		)

	def test_payment_creation_updates_balance_and_dashboard_metrics(self):
		overview_before = get_dashboard_overview_data(self.user)
		outstanding_before = Decimal(str(overview_before['outstanding']['total']))
		revenue_before = Decimal(str(overview_before['payments']['all_time']))

		Payment.objects.create(
			client_vehicle=self.client_vehicle,
			amount=Decimal('150000.00'),
			payment_date=timezone.now().date(),
			payment_method='cash',
			recorded_by=self.user,
		)

		self.client_vehicle.refresh_from_db()

		self.assertEqual(self.client_vehicle.total_paid, Decimal('150000.00'))
		self.assertEqual(self.client_vehicle.balance, Decimal('1050000.00'))
		self.assertFalse(self.client_vehicle.is_paid_off)

		overview_after = get_dashboard_overview_data(self.user)
		outstanding_after = Decimal(str(overview_after['outstanding']['total']))
		revenue_after = Decimal(str(overview_after['payments']['all_time']))

		self.assertEqual(revenue_after, revenue_before + Decimal('150000.00'))
		self.assertEqual(outstanding_after, outstanding_before - Decimal('150000.00'))

	def test_payment_change_clears_dashboard_widget_cache(self):
		MetricCache.objects.create(
			metric_key='widget_data_test',
			metric_name='Test Widget Cache',
			value={'value': 123},
			expires_at=timezone.now() + timezone.timedelta(minutes=5),
		)

		self.assertTrue(MetricCache.objects.filter(metric_key='widget_data_test').exists())

		payment = Payment.objects.create(
			client_vehicle=self.client_vehicle,
			amount=Decimal('50000.00'),
			payment_date=timezone.now().date(),
			payment_method='cash',
			recorded_by=self.user,
		)

		self.assertFalse(MetricCache.objects.filter(metric_key='widget_data_test').exists())

		MetricCache.objects.create(
			metric_key='widget_data_test_2',
			metric_name='Test Widget Cache 2',
			value={'value': 456},
			expires_at=timezone.now() + timezone.timedelta(minutes=5),
		)

		payment.delete()
		self.assertFalse(MetricCache.objects.filter(metric_key='widget_data_test_2').exists())
