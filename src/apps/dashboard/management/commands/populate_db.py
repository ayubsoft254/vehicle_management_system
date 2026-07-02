"""
Django Management Command — Seed full demo data across the whole system
(users, vehicles, clients, sales, payments, expenses, vendors, and the
finance ledger) so every module can be clicked through with realistic data.

Usage:
    python manage.py populate_db            # create/update, safe to re-run
    python manage.py populate_db --clear     # wipe seedable data first, then recreate
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction

from django.core.management.base import BaseCommand

User = get_user_model()

from apps.clients.models import Client, ClientVehicle
from apps.expenses.models import Expense, ExpenseCategory
from apps.finance import services as finance_services
from apps.finance.models import (
    AccountReconciliation, FinancialAccount, InternalTransfer,
    LedgerTransaction, SuspenseTransaction,
)
from apps.insurance.models import InsuranceAgent, InsuranceAgentPayment
from apps.payments.models import InstallmentPlan, Payment
from apps.vehicles.models import (
    Broker, BrokerPayment, ClearingAgent, ClearingAgentPayment,
    JapanSupplier, JapanSupplierPayment, TrackerAgent, TrackerAgentPayment,
    Vehicle,
)
from utils.constants import UserRole

DEMO_PASSWORD = 'Demo@12345'


class Command(BaseCommand):
    help = (
        'Seed the whole system with demo data: role-based test users, vehicles, clients, '
        'vehicle sales, client payments, expenses, vendor payments, and finance ledger '
        'scenarios (pending/approved/rejected/reversed/corrected transactions, an internal '
        'transfer, a suspense allocation, and a reconciliation).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help=(
                'Delete previously seeded vehicles, clients, sales, payments, expenses, '
                'vendor payments, and finance ledger entries before seeding. Accounts and '
                'users are preserved (existing users are updated in place).'
            ),
        )

    def handle(self, *args, **options):
        if options['clear']:
            self._clear()

        with transaction.atomic():
            self.admin = self._create_superuser()
            self.role_users = self._create_role_users()
            self._create_clearing_agents()
            self._create_tracker_agents()
            self._create_insurance_agents()
            self._create_brokers()
            self._create_japan_suppliers()
            self._create_vehicles()
            self._create_clients()
            self.accounts = self._create_finance_accounts()
            self._create_vehicle_purchases()
            self._create_client_payments()
            self._create_expenses()
            self._create_vendor_payments()
            self._create_finance_scenarios()

        self._print_summary()

    # ------------------------------------------------------------------ #
    # Clearing
    # ------------------------------------------------------------------ #

    def _clear(self):
        self.stdout.write(self.style.WARNING('Clearing previously seeded data...'))
        SuspenseTransaction.objects.all().delete()
        AccountReconciliation.objects.all().delete()
        InternalTransfer.objects.all().delete()
        LedgerTransaction.objects.all().delete()
        BrokerPayment.objects.all().delete()
        TrackerAgentPayment.objects.all().delete()
        ClearingAgentPayment.objects.all().delete()
        JapanSupplierPayment.objects.all().delete()
        InsuranceAgentPayment.objects.all().delete()
        Expense.objects.all().delete()
        Payment.objects.all().delete()
        InstallmentPlan.objects.all().delete()
        ClientVehicle.objects.all().delete()
        Vehicle.objects.all().delete()
        Client.objects.all().delete()
        Broker.objects.all().delete()
        JapanSupplier.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Cleared.'))

    # ------------------------------------------------------------------ #
    # Users
    # ------------------------------------------------------------------ #

    def _create_superuser(self):
        email = 'admin@hozainvestments.co.ke'
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create_superuser(
                email=email, password='admin123',
                first_name='Admin', last_name='Hoza',
                phone='+254784170447', is_active=True,
            )
            self.stdout.write(f'  Created superuser: {email} / admin123')
        else:
            self.stdout.write(f'  Superuser already exists: {email}')
        return user

    def _create_role_users(self):
        """One active test user per role, all sharing DEMO_PASSWORD, for testing
        role-based permissions across every module without hand-creating users."""
        role_users = {
            UserRole.MANAGER: ('manager@hozainvestments.co.ke', 'Mary', 'Manager'),
            UserRole.SALES: ('sales@hozainvestments.co.ke', 'Sam', 'Sales'),
            UserRole.ACCOUNTANT: ('accountant@hozainvestments.co.ke', 'Ann', 'Accountant'),
            UserRole.AUCTIONEER: ('auctioneer@hozainvestments.co.ke', 'Tom', 'Auctioneer'),
            UserRole.CLERK: ('clerk@hozainvestments.co.ke', 'Cathy', 'Clerk'),
            UserRole.AUDITOR: ('auditor@hozainvestments.co.ke', 'Alex', 'Auditor'),
        }
        created_users = {}
        for role, (email, first_name, last_name) in role_users.items():
            user = User.objects.filter(email=email).first()
            if not user:
                user = User.objects.create_user(
                    email=email, password=DEMO_PASSWORD,
                    first_name=first_name, last_name=last_name,
                    role=role, is_active=True,
                )
                self.stdout.write(f'  Created {role} user: {email} / {DEMO_PASSWORD}')
            elif user.role != role or not user.is_active:
                user.role = role
                user.is_active = True
                user.save(update_fields=['role', 'is_active'])
                self.stdout.write(f'  Updated {role} user: {email}')
            else:
                self.stdout.write(f'  {role} user already exists: {email}')
            created_users[role] = user
        return created_users

    # ------------------------------------------------------------------ #
    # Vendors / agents
    # ------------------------------------------------------------------ #

    def _create_clearing_agents(self):
        agents = [
            ('Mombasa Port Clearance', '+254744300001', 'info@mpc.co.ke'),
            ('Nairobi Clearing House', '+254744300002', 'ops@nch.co.ke'),
            ('KPA Clearing Agents', '+254744300003', 'kpa@clearance.co.ke'),
        ]
        for name, phone, email in agents:
            _, created = ClearingAgent.objects.get_or_create(
                name=name, defaults={'phone': phone, 'email': email, 'is_active': True},
            )
            self.stdout.write(f'  {"Created" if created else "Exists"} clearing agent: {name}')

    def _create_tracker_agents(self):
        agents = [
            ('Saudia Tracking Ltd', '+254733200001', 'info@saudia.co.ke'),
            ('Trackmatic Kenya', '+254733200002', 'ops@trackmatic.co.ke'),
            ('AfriCoverage GPS', '+254733200003', 'sales@africoverage.co.ke'),
        ]
        for name, phone, email in agents:
            _, created = TrackerAgent.objects.get_or_create(
                name=name, defaults={'phone': phone, 'email': email, 'is_active': True},
            )
            self.stdout.write(f'  {"Created" if created else "Exists"} tracker agent: {name}')

    def _create_insurance_agents(self):
        agents = [
            ('Jubilee Insurance Agency', '+254722100001', 'jubilee@agents.co.ke', 'LIC-001'),
            ('APA Insurance Brokers', '+254722100002', 'apa@agents.co.ke', 'LIC-002'),
            ('Britam Direct', '+254722100003', 'britam@agents.co.ke', 'LIC-003'),
        ]
        for name, phone, email, id_number in agents:
            _, created = InsuranceAgent.objects.get_or_create(
                name=name, defaults={'phone': phone, 'email': email, 'id_number': id_number, 'is_active': True},
            )
            self.stdout.write(f'  {"Created" if created else "Exists"} insurance agent: {name}')

    def _create_brokers(self):
        brokers = [
            ('Peter Mwangi', '+254711100001', 'peter.mwangi.broker@gmail.com', 'BRK-10001'),
            ('Lucy Njeri', '+254711100002', 'lucy.njeri.broker@gmail.com', 'BRK-10002'),
        ]
        for name, phone, email, id_number in brokers:
            _, created = Broker.objects.get_or_create(
                id_number=id_number, defaults={'name': name, 'phone': phone, 'email': email, 'is_active': True},
            )
            self.stdout.write(f'  {"Created" if created else "Exists"} broker: {name}')

    def _create_japan_suppliers(self):
        suppliers = [
            ('Osaka Motors Trading', '+81312345001', 'sales@osakamotors.jp'),
            ('Yokohama Auto Export', '+81312345002', 'export@yokohama-auto.jp'),
        ]
        for name, phone, email in suppliers:
            _, created = JapanSupplier.objects.get_or_create(
                name=name, defaults={'phone': phone, 'email': email, 'country': 'Japan', 'is_active': True},
            )
            self.stdout.write(f'  {"Created" if created else "Exists"} Japan supplier: {name}')

    # ------------------------------------------------------------------ #
    # Vehicles / clients
    # ------------------------------------------------------------------ #

    def _create_vehicles(self):
        vehicles = [
            {
                'make': 'Toyota', 'model': 'Land Cruiser', 'year': 2020,
                'vin': 'VIN20201234567', 'registration_number': 'KDG 123A',
                'color': 'White', 'mileage': 45000,
                'fuel_type': 'diesel', 'transmission': 'automatic',
                'body_type': 'suv', 'engine_size': '4.5L',
                'purchase_price': Decimal('4200000'), 'selling_price': Decimal('5000000'),
                'clearance_cost': Decimal('250000'),
                'condition': 'excellent', 'status': 'available',
                'location': 'Showroom', 'purchase_date': date(2024, 1, 15),
            },
            {
                'make': 'Nissan', 'model': 'X-Trail', 'year': 2019,
                'vin': 'VIN20197654321', 'registration_number': 'KCF 456B',
                'color': 'Silver', 'mileage': 62000,
                'fuel_type': 'petrol', 'transmission': 'automatic',
                'body_type': 'suv', 'engine_size': '2.0L',
                'purchase_price': Decimal('1600000'), 'selling_price': Decimal('2000000'),
                'clearance_cost': Decimal('120000'),
                'condition': 'good', 'status': 'available',
                'location': 'Main Yard', 'purchase_date': date(2024, 2, 10),
            },
            {
                'make': 'Subaru', 'model': 'Forester', 'year': 2021,
                'vin': 'VIN20219871234', 'registration_number': 'KDH 789C',
                'color': 'Blue', 'mileage': 28000,
                'fuel_type': 'petrol', 'transmission': 'automatic',
                'body_type': 'suv', 'engine_size': '2.5L',
                'purchase_price': Decimal('2100000'), 'selling_price': Decimal('2600000'),
                'clearance_cost': Decimal('160000'),
                'condition': 'excellent', 'status': 'available',
                'location': 'Showroom', 'purchase_date': date(2024, 3, 5),
            },
            {
                'make': 'Mazda', 'model': 'CX-5', 'year': 2022,
                'vin': 'VIN20225551212', 'registration_number': 'KDJ 321D',
                'color': 'Red', 'mileage': 12000,
                'fuel_type': 'petrol', 'transmission': 'automatic',
                'body_type': 'suv', 'engine_size': '2.5L',
                'purchase_price': Decimal('2800000'), 'selling_price': Decimal('3400000'),
                'clearance_cost': Decimal('180000'),
                'condition': 'excellent', 'status': 'available',
                'location': 'Showroom', 'purchase_date': date(2024, 5, 20),
            },
        ]
        for data in vehicles:
            data['added_by'] = self.admin
            _, created = Vehicle.objects.get_or_create(vin=data['vin'], defaults=data)
            self.stdout.write(
                f'  {"Created" if created else "Exists"} vehicle: '
                f'{data["year"]} {data["make"]} {data["model"]} ({data["registration_number"]})'
            )

    def _create_clients(self):
        clients = [
            {
                'first_name': 'James', 'last_name': 'Kamau', 'email': 'james.kamau@gmail.com',
                'phone_primary': '+254712345678', 'id_number': '12345678',
                'date_of_birth': date(1985, 4, 20), 'physical_address': '45 Ngong Road',
                'city': 'Nairobi', 'county': 'Nairobi', 'status': 'active',
            },
            {
                'first_name': 'Grace', 'last_name': 'Wanjiru', 'email': 'grace.wanjiru@gmail.com',
                'phone_primary': '+254723456789', 'id_number': '23456789',
                'date_of_birth': date(1990, 8, 14), 'physical_address': '12 Mombasa Road',
                'city': 'Mombasa', 'county': 'Mombasa', 'status': 'active',
            },
            {
                'first_name': 'David', 'last_name': 'Ochieng', 'email': 'david.ochieng@gmail.com',
                'phone_primary': '+254734567890', 'id_number': '34567890',
                'date_of_birth': date(1988, 11, 3), 'physical_address': '78 Thika Road',
                'city': 'Nairobi', 'county': 'Kiambu', 'status': 'active',
            },
        ]
        for data in clients:
            data['registered_by'] = self.admin
            _, created = Client.objects.get_or_create(id_number=data['id_number'], defaults=data)
            self.stdout.write(f'  {"Created" if created else "Exists"} client: {data["first_name"]} {data["last_name"]}')

    # ------------------------------------------------------------------ #
    # Finance accounts
    # ------------------------------------------------------------------ #

    def _create_finance_accounts(self):
        """Safety net: the finance app's own data migration normally creates
        these, but re-assert them here so `populate_db` works even against a
        database where migrations were run without that data migration."""
        defaults = [
            ('EQTY-HOZA', 'Financial Analyst Equity Hoza', 'bank', True),
            ('DIB-HOZA', 'DIB Hoza', 'bank', True),
            ('COOP-HOZA', 'COOP Hoza', 'bank', True),
            ('SUSPENSE-HOZA', 'Suspense Account - Hoza', 'suspense', False),
        ]
        accounts = {}
        for code, name, account_type, is_default in defaults:
            account, created = FinancialAccount.objects.get_or_create(
                code=code,
                defaults={
                    'name': name, 'account_type': account_type, 'currency': 'KES',
                    'opening_balance': Decimal('0.00'), 'opening_balance_date': date(2024, 1, 1),
                    'status': 'active', 'is_default': is_default,
                    'allow_manual_transactions': True, 'require_approval': True,
                    'created_by': self.admin,
                },
            )
            self.stdout.write(f'  {"Created" if created else "Exists"} finance account: {name}')
            accounts[code] = account
        return accounts

    # ------------------------------------------------------------------ #
    # Vehicle sales / installment plans
    # ------------------------------------------------------------------ #

    def _create_vehicle_purchases(self):
        james = Client.objects.get(id_number='12345678')
        grace = Client.objects.get(id_number='23456789')
        david = Client.objects.get(id_number='34567890')

        land_cruiser = Vehicle.objects.get(vin='VIN20201234567')
        xtrail = Vehicle.objects.get(vin='VIN20197654321')
        forester = Vehicle.objects.get(vin='VIN20219871234')

        # James: Land Cruiser on installments, several months already progressed.
        self.james_cv, _ = ClientVehicle.objects.get_or_create(
            client=james, vehicle=land_cruiser,
            defaults=dict(
                purchase_date=date(2024, 6, 1), purchase_price=Decimal('5000000'),
                client_purchase_price=Decimal('5000000'), final_selling_price=Decimal('5000000'),
                deposit_paid=Decimal('1000000'), total_paid=Decimal('1000000'),
                balance=Decimal('4000000'), monthly_installment=Decimal('200000'),
                installment_months=20, payment_type='installment',
                remainder_payment_type='monthly', monthly_payment_date=1, is_active=True,
            ),
        )
        self.james_plan, plan_created = InstallmentPlan.objects.get_or_create(
            client_vehicle=self.james_cv,
            defaults=dict(
                total_amount=Decimal('4000000'), deposit=Decimal('1000000'),
                monthly_installment=Decimal('200000'), number_of_installments=20,
                start_date=date(2024, 7, 1), created_by=self.admin,
            ),
        )
        if plan_created:
            self.james_plan.generate_payment_schedule()

        # Grace: X-Trail, straight cash sale (no installment plan).
        self.grace_cv, _ = ClientVehicle.objects.get_or_create(
            client=grace, vehicle=xtrail,
            defaults=dict(
                purchase_date=date(2024, 8, 15), purchase_price=Decimal('2000000'),
                client_purchase_price=Decimal('2000000'), final_selling_price=Decimal('2000000'),
                deposit_paid=Decimal('0'), total_paid=Decimal('0'), balance=Decimal('2000000'),
                monthly_installment=Decimal('0'), installment_months=0, payment_type='full',
                is_active=True,
            ),
        )

        # David: Forester on installments, only just started (mostly unpaid) —
        # gives us a defaulter-style / early-progress record to look at too.
        self.david_cv, _ = ClientVehicle.objects.get_or_create(
            client=david, vehicle=forester,
            defaults=dict(
                purchase_date=date(2025, 3, 1), purchase_price=Decimal('2600000'),
                client_purchase_price=Decimal('2600000'), final_selling_price=Decimal('2600000'),
                deposit_paid=Decimal('500000'), total_paid=Decimal('500000'),
                balance=Decimal('2100000'), monthly_installment=Decimal('150000'),
                installment_months=14, payment_type='installment',
                remainder_payment_type='monthly', monthly_payment_date=5, is_active=True,
            ),
        )
        self.david_plan, plan_created = InstallmentPlan.objects.get_or_create(
            client_vehicle=self.david_cv,
            defaults=dict(
                total_amount=Decimal('2100000'), deposit=Decimal('500000'),
                monthly_installment=Decimal('150000'), number_of_installments=14,
                start_date=date(2025, 4, 5), created_by=self.admin,
            ),
        )
        if plan_created:
            self.david_plan.generate_payment_schedule()

        # Mark the sold vehicles/clients accordingly.
        for vehicle in (land_cruiser, xtrail, forester):
            if vehicle.status != 'sold':
                vehicle.status = 'sold'
                vehicle.date_sold = vehicle.date_sold or date.today()
                vehicle.save(update_fields=['status', 'date_sold'])

        self.stdout.write('  Vehicle purchases: James/Land Cruiser (installment), '
                           'Grace/X-Trail (cash), David/Forester (installment)')

    # ------------------------------------------------------------------ #
    # Client payments (through the real integration, posting to the ledger)
    # ------------------------------------------------------------------ #

    def _record_client_payment(self, client_vehicle, amount, account, payment_date,
                                payment_method='bank_transfer', approve=True, reference=''):
        payment = Payment.objects.create(
            client_vehicle=client_vehicle, amount=amount, payment_date=payment_date,
            payment_method=payment_method, transaction_reference=reference,
            account=account, recorded_by=self.admin,
        )
        # Reuses apps/payments/views.py::_record_finance_ledger_entry — the
        # exact same helper the real payment-recording views use, so seeded
        # data matches how a real payment actually flows through the system.
        from apps.payments.views import _record_finance_ledger_entry
        ledger_txn = _record_finance_ledger_entry(payment, client_vehicle)
        if ledger_txn and approve:
            finance_services.approve_transaction(ledger_txn, self.admin, comments='Seeded as approved for demo purposes')
        return payment, ledger_txn

    def _create_client_payments(self):
        from apps.payments.views import _snapshot_pending_schedule_amounts, _allocate_ledger_transaction_to_schedules

        dib = self.accounts['DIB-HOZA']
        coop = self.accounts['COOP-HOZA']
        eqty = self.accounts['EQTY-HOZA']

        if not Payment.objects.filter(client_vehicle=self.james_cv).exists():
            # James: 2 approved monthly instalments + 1 still pending approval,
            # so the finance module has a live "awaiting approval" example
            # tied to a real client payment, not just a manual demo entry.
            for i, (amount, pay_date, approve) in enumerate([
                (Decimal('200000'), date(2024, 7, 3), True),
                (Decimal('200000'), date(2024, 8, 2), True),
                (Decimal('200000'), date(2024, 9, 4), False),
            ]):
                pre_amounts = _snapshot_pending_schedule_amounts(self.james_cv)
                payment, ledger_txn = self._record_client_payment(
                    self.james_cv, amount, dib, pay_date,
                    reference=f'JK-INSTALMENT-{i+1}', approve=approve,
                )
                if ledger_txn:
                    _allocate_ledger_transaction_to_schedules(ledger_txn, self.james_cv, pre_amounts)
            self.stdout.write('  Recorded James Kamau instalment payments (2 approved, 1 pending)')

        if not Payment.objects.filter(client_vehicle=self.grace_cv).exists():
            payment, ledger_txn = self._record_client_payment(
                self.grace_cv, Decimal('2000000'), coop, date(2024, 8, 15),
                payment_method='bank_transfer', reference='GW-FULL-PAYMENT', approve=True,
            )
            self.grace_cv.refresh_from_db()
            self.stdout.write('  Recorded Grace Wanjiru full cash payment (vehicle paid off)')

        if not Payment.objects.filter(client_vehicle=self.david_cv).exists():
            pre_amounts = _snapshot_pending_schedule_amounts(self.david_cv)
            payment, ledger_txn = self._record_client_payment(
                self.david_cv, Decimal('150000'), eqty, date(2025, 4, 6),
                reference='DO-INSTALMENT-1', approve=True,
            )
            if ledger_txn:
                _allocate_ledger_transaction_to_schedules(ledger_txn, self.david_cv, pre_amounts)
            self.stdout.write('  Recorded David Ochieng first instalment payment')

    # ------------------------------------------------------------------ #
    # Expenses
    # ------------------------------------------------------------------ #

    def _create_expenses(self):
        categories = [
            ('Fuel', 'FUEL'), ('Maintenance & Repairs', 'MAINT'),
            ('Office Rent', 'RENT'), ('Legal Fees', 'LEGAL'), ('Marketing', 'MKTG'),
        ]
        cat_objs = {}
        for name, code in categories:
            cat, created = ExpenseCategory.objects.get_or_create(name=name, defaults={'code': code})
            cat_objs[code] = cat
            if created:
                self.stdout.write(f'  Created expense category: {name}')

        if Expense.objects.exists():
            return

        dib = self.accounts['DIB-HOZA']
        coop = self.accounts['COOP-HOZA']

        # Draft — not yet submitted for approval.
        Expense.objects.create(
            title='Fuel for yard vehicles', category=cat_objs['FUEL'],
            amount=Decimal('8500'), currency='KES', tax_amount=Decimal('0'),
            expense_date=date.today() - timedelta(days=2),
            payment_method='CASH', vendor_name='Total Energies Station',
            submitted_by=self.admin, status='DRAFT',
        )

        # Approved but not yet paid — no ledger entry yet.
        Expense.objects.create(
            title='Legal consultation - sale agreements', category=cat_objs['LEGAL'],
            amount=Decimal('45000'), currency='KES', tax_amount=Decimal('0'),
            expense_date=date.today() - timedelta(days=10),
            payment_method='BANK_TRANSFER', vendor_name='Mwangi & Associates Advocates',
            submitted_by=self.admin, status='APPROVED',
            approved_by=self.admin, account=dib,
        )

        # Approved and marked PAID -> posts a real debit ledger transaction.
        paid_rent = Expense.objects.create(
            title='Office rent - Q3', category=cat_objs['RENT'],
            amount=Decimal('150000'), currency='KES', tax_amount=Decimal('0'),
            expense_date=date.today() - timedelta(days=20),
            payment_method='BANK_TRANSFER', vendor_name='Westlands Business Park Ltd',
            submitted_by=self.admin, status='APPROVED',
            approved_by=self.admin, account=coop,
        )
        if paid_rent.mark_as_paid():
            ledger_txn = finance_services.create_transaction(
                coop, direction='debit', transaction_type='staff_expense',
                amount=paid_rent.total_amount, created_by=self.admin,
                transaction_date=paid_rent.expense_date, source_module='expenses',
                description=f'Expense: {paid_rent.title} ({paid_rent.category.name})',
            )
            finance_services.approve_transaction(ledger_txn, self.admin, comments='Seeded as approved for demo purposes')

        self.stdout.write('  Created sample expenses (draft, approved-unpaid, approved-paid)')

    # ------------------------------------------------------------------ #
    # Vendor payments
    # ------------------------------------------------------------------ #

    def _create_vendor_payments(self):
        if BrokerPayment.objects.exists():
            return

        dib = self.accounts['DIB-HOZA']
        coop = self.accounts['COOP-HOZA']
        eqty = self.accounts['EQTY-HOZA']

        def pay_vendor(model, fk_field, vendor, amount, pay_date, account, transaction_type, source_module, description):
            payment = model.objects.create(**{
                fk_field: vendor, 'amount': amount, 'payment_date': pay_date,
                'payment_method': 'bank_transfer', 'recorded_by': self.admin, 'account': account,
            })
            ledger_txn = finance_services.create_transaction(
                account, direction='debit', transaction_type=transaction_type,
                amount=amount, created_by=self.admin, transaction_date=pay_date,
                source_module=source_module, related_party=vendor,
                related_party_label=vendor.name, payment_method='bank_transfer',
                description=description,
            )
            finance_services.approve_transaction(ledger_txn, self.admin, comments='Seeded as approved for demo purposes')
            return payment

        broker = Broker.objects.first()
        pay_vendor(BrokerPayment, 'broker', broker, Decimal('50000'), date.today() - timedelta(days=15),
                   dib, 'broker_commission', 'vehicles', f'Broker payment - {broker.name}')

        tracker_agent = TrackerAgent.objects.first()
        pay_vendor(TrackerAgentPayment, 'agent', tracker_agent, Decimal('12000'), date.today() - timedelta(days=12),
                   dib, 'tracker_vendor_payment', 'vehicles', f'Tracker agent payment - {tracker_agent.name}')

        clearing_agent = ClearingAgent.objects.first()
        pay_vendor(ClearingAgentPayment, 'agent', clearing_agent, Decimal('180000'), date.today() - timedelta(days=25),
                   coop, 'clearing_charges', 'vehicles', f'Clearing agent payment - {clearing_agent.name}')

        japan_supplier = JapanSupplier.objects.first()
        pay_vendor(JapanSupplierPayment, 'supplier', japan_supplier, Decimal('2500000'), date.today() - timedelta(days=40),
                   eqty, 'supplier_payment', 'vehicles', f'Japan supplier payment - {japan_supplier.name}')

        insurance_agent = InsuranceAgent.objects.first()
        pay_vendor(InsuranceAgentPayment, 'agent', insurance_agent, Decimal('35000'), date.today() - timedelta(days=8),
                   coop, 'insurance_company_payment', 'insurance', f'Insurance agent payment - {insurance_agent.name}')

        self.stdout.write('  Recorded vendor payments: broker, tracker agent, clearing agent, Japan supplier, insurance agent')

    # ------------------------------------------------------------------ #
    # Finance ledger scenarios: approvals, reversal, correction, transfer,
    # suspense allocation, reconciliation.
    # ------------------------------------------------------------------ #

    def _create_finance_scenarios(self):
        if LedgerTransaction.objects.filter(source_module='manual').exists():
            self.stdout.write('  Finance ledger scenarios already seeded, skipping')
            return

        dib = self.accounts['DIB-HOZA']
        coop = self.accounts['COOP-HOZA']
        eqty = self.accounts['EQTY-HOZA']
        suspense = self.accounts['SUSPENSE-HOZA']
        accountant = self.role_users[UserRole.ACCOUNTANT]
        clerk = self.role_users[UserRole.CLERK]

        # 1. Pending approval — recorded by the clerk, awaiting an approver.
        finance_services.create_transaction(
            dib, direction='credit', transaction_type='bank_deposit', amount=Decimal('75000'),
            created_by=clerk, transaction_date=date.today() - timedelta(days=1),
            source_module='manual', payment_method='bank_transfer',
            description='Bank deposit awaiting approval (seed demo)',
        )

        # 2. Approved.
        approved_txn = finance_services.create_transaction(
            coop, direction='credit', transaction_type='cash_deposit', amount=Decimal('30000'),
            created_by=clerk, transaction_date=date.today() - timedelta(days=5),
            source_module='manual', payment_method='cash',
            description='Cash deposit (seed demo)',
        )
        finance_services.approve_transaction(approved_txn, accountant, comments='Approved for demo')

        # 3. Rejected.
        rejected_txn = finance_services.create_transaction(
            dib, direction='debit', transaction_type='bank_charge', amount=Decimal('500'),
            created_by=clerk, transaction_date=date.today() - timedelta(days=4),
            source_module='manual', payment_method='bank_transfer',
            description='Disputed bank charge (seed demo)',
        )
        finance_services.reject_transaction(rejected_txn, accountant, comments='Charge disputed with bank, rejected pending refund')

        # 4. Reversed — approved, then reversed to demonstrate the reversal trail.
        to_reverse = finance_services.create_transaction(
            eqty, direction='debit', transaction_type='cash_withdrawal', amount=Decimal('20000'),
            created_by=clerk, transaction_date=date.today() - timedelta(days=7),
            source_module='manual', payment_method='cash',
            description='Cash withdrawal later found to be a duplicate (seed demo)',
        )
        finance_services.approve_transaction(to_reverse, accountant, comments='Approved for demo')
        finance_services.reverse_transaction(to_reverse, self.admin, 'Duplicate withdrawal entry — reversed (seed demo)')

        # 5. Corrected — spec's own worked example (wrong amount, then fixed).
        to_correct = finance_services.create_transaction(
            coop, direction='debit', transaction_type='cash_withdrawal', amount=Decimal('300000'),
            created_by=clerk, transaction_date=date.today() - timedelta(days=9),
            source_module='manual', payment_method='cash',
            description='Cash withdrawal (seed demo — will be corrected)',
        )
        finance_services.approve_transaction(to_correct, accountant, comments='Approved for demo')
        finance_services.correct_transaction(
            to_correct, self.admin, Decimal('30000'),
            'Typo: entered KES 300,000 instead of KES 30,000 (seed demo)',
        )

        # 6. Internal transfer, approved.
        transfer = finance_services.create_internal_transfer(
            from_account=dib, to_account=coop, amount=Decimal('100000'),
            created_by=self.admin, transfer_date=date.today() - timedelta(days=3),
            notes='Rebalancing funds between accounts (seed demo)',
        )
        finance_services.approve_internal_transfer(transfer, self.admin, comments='Approved for demo')

        # 7. Suspense: one unresolved unmatched payment, one already allocated.
        # SuspenseTransaction rows are created automatically by create_transaction()
        # for any credit posted to a suspense-type account — see services.py.
        finance_services.create_transaction(
            suspense, direction='credit', transaction_type='suspense_allocation', amount=Decimal('15000'),
            created_by=clerk, transaction_date=date.today() - timedelta(days=2),
            source_module='manual', payment_method='mpesa',
            description='Unidentified M-Pesa payment, reference unclear (seed demo)',
        )

        matched = finance_services.create_transaction(
            suspense, direction='credit', transaction_type='suspense_allocation', amount=Decimal('9000'),
            created_by=clerk, transaction_date=date.today() - timedelta(days=14),
            source_module='manual', payment_method='mpesa',
            description='M-Pesa payment later identified as David Ochieng (seed demo)',
        )
        matched_suspense = SuspenseTransaction.objects.get(transaction=matched)
        finance_services.allocate_suspense_transaction(
            matched_suspense, self.admin, client_vehicle=self.david_cv,
            notes='Confirmed with client via phone call (seed demo)',
        )

        # 8. Reconciliation: one completed reconciliation against DIB Hoza.
        dib_recon = AccountReconciliation.objects.create(
            account=dib, reconciliation_date=date.today() - timedelta(days=1),
            statement_balance=dib.current_balance, book_balance=dib.current_balance,
            notes='Matches bank statement (seed demo)',
        )
        finance_services.complete_reconciliation(dib_recon, accountant)

        self.stdout.write(
            '  Finance ledger scenarios: 1 pending, 1 approved, 1 rejected, 1 reversed, '
            '1 corrected, 1 internal transfer, 1 suspense unallocated, 1 suspense allocated, '
            '1 completed reconciliation'
        )

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #

    def _print_summary(self):
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('SEED COMPLETE'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'  Users               : {User.objects.filter(is_active=True).count()}')
        self.stdout.write(f'  Vehicles            : {Vehicle.objects.count()}')
        self.stdout.write(f'  Clients             : {Client.objects.count()}')
        self.stdout.write(f'  Vehicle purchases   : {ClientVehicle.objects.count()}')
        self.stdout.write(f'  Payments            : {Payment.objects.count()}')
        self.stdout.write(f'  Expenses            : {Expense.objects.count()}')
        self.stdout.write(f'  Brokers             : {Broker.objects.count()}')
        self.stdout.write(f'  Japan suppliers     : {JapanSupplier.objects.count()}')
        self.stdout.write(f'  Clearing agents     : {ClearingAgent.objects.count()}')
        self.stdout.write(f'  Tracker agents      : {TrackerAgent.objects.count()}')
        self.stdout.write(f'  Insurance agents    : {InsuranceAgent.objects.count()}')
        self.stdout.write(f'  Finance accounts    : {FinancialAccount.objects.count()}')
        self.stdout.write(f'  Ledger transactions : {LedgerTransaction.objects.count()}')
        self.stdout.write(f'  Internal transfers  : {InternalTransfer.objects.count()}')
        self.stdout.write(f'  Suspense entries    : {SuspenseTransaction.objects.count()}')
        self.stdout.write(f'  Reconciliations     : {AccountReconciliation.objects.count()}')
        self.stdout.write('=' * 70)
        self.stdout.write('  LOGIN CREDENTIALS')
        self.stdout.write('  ' + '-' * 66)
        self.stdout.write('  Super Admin  : admin@hozainvestments.co.ke / admin123')
        for role, user in self.role_users.items():
            self.stdout.write(f'  {role.capitalize():<12} : {user.email} / {DEMO_PASSWORD}')
        self.stdout.write('=' * 70 + '\n')
