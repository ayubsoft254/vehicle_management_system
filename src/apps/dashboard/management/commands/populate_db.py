"""
Django Management Command to Populate Database with Dummy Data
Usage: python manage.py populate_db [--clear]
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

User = get_user_model()

try:
    from apps.vehicles.models import Vehicle, TrackerAgent, TrackerRecord, ClearingAgent, ClearanceRecord
except ImportError:
    Vehicle = None
    TrackerAgent = None
    TrackerRecord = None
    ClearingAgent = None
    ClearanceRecord = None

try:
    from apps.clients.models import Client, ClientVehicle, VehicleTracker
except ImportError:
    Client = None
    ClientVehicle = None
    VehicleTracker = None

try:
    from apps.payments.models import Payment, PaymentSplit, InstallmentPlan
except ImportError:
    Payment = None
    PaymentSplit = None
    InstallmentPlan = None

try:
    from apps.expenses.models import Expense, ExpenseCategory
except ImportError:
    Expense = None
    ExpenseCategory = None

try:
    from apps.insurance.models import InsurancePolicy, InsuranceClaim, InsuranceAgent
except ImportError:
    InsurancePolicy = None
    InsuranceClaim = None
    InsuranceAgent = None

try:
    from apps.auctions.models import Auction, Bid
except ImportError:
    Auction = None
    Bid = None

try:
    from apps.repossessions.models import Repossession
except ImportError:
    Repossession = None

try:
    from apps.documents.models import Document, DocumentCategory
except ImportError:
    Document = None
    DocumentCategory = None

try:
    from apps.payroll.models import Employee, SalaryStructure, PayrollRun
except ImportError:
    Employee = None
    SalaryStructure = None
    PayrollRun = None


class Command(BaseCommand):
    help = 'Populate database with comprehensive dummy data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before populating',
        )
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of users to create (default: 10)',
        )
        parser.add_argument(
            '--vehicles',
            type=int,
            default=50,
            help='Number of vehicles to create (default: 50)',
        )
        parser.add_argument(
            '--clients',
            type=int,
            default=100,
            help='Number of clients to create (default: 100)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting database population...'))

        if options['clear']:
            self.clear_data()

        try:
            with transaction.atomic():
                self.stdout.write('Creating users...')
                users = self.create_users(options['users'])

                self.stdout.write('Creating clients...')
                clients = self.create_clients(options['clients'])

                self.stdout.write('Creating vehicles...')
                vehicles = self.create_vehicles(options['vehicles'])

                self.stdout.write('Creating agent records (insurance / tracker / clearing)...')
                insurance_agents = self.create_insurance_agents()
                tracker_agents = self.create_tracker_agents()
                clearing_agents = self.create_clearing_agents()

                self.stdout.write('Creating installment plans...')
                installment_plans = self.create_installment_plans(clients, vehicles)

                self.stdout.write('Creating payments...')
                self.create_payments(installment_plans)

                self.stdout.write('Creating expense categories...')
                categories = self.create_expense_categories()

                self.stdout.write('Creating expenses...')
                self.create_expenses(categories, vehicles)

                self.stdout.write('Creating insurance policies...')
                policies = self.create_insurance_policies(vehicles, clients, insurance_agents)

                self.stdout.write('Creating insurance claims...')
                self.create_claims(policies)

                self.stdout.write('Creating vehicle trackers and tracker records...')
                self.create_vehicle_trackers(vehicles, tracker_agents)

                self.stdout.write('Creating clearance records...')
                self.create_clearance_records(vehicles, clearing_agents)

                self.stdout.write('Creating auctions...')
                auctions = self.create_auctions(vehicles)

                self.stdout.write('Creating bids...')
                self.create_bids(auctions, clients)

                self.stdout.write('Creating repossessions...')
                self.create_repossessions(vehicles, clients)

                self.stdout.write('Creating employees...')
                employees = self.create_employees()

                self.stdout.write('Creating salaries...')
                salaries = self.create_salaries(employees)

                self.stdout.write('Creating payslips...')
                self.create_payslips(salaries)

                self.stdout.write('Creating documents...')
                self.create_documents(vehicles, clients)

                self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Database populated successfully!'))
                self.print_summary(users, clients, vehicles)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            raise

    def clear_data(self):
        """Clear existing data from all tables"""
        self.stdout.write(self.style.WARNING('Clearing existing data...'))

        if Document:
            Document.objects.all().delete()
        if PayrollRun:
            PayrollRun.objects.all().delete()
        if SalaryStructure:
            SalaryStructure.objects.all().delete()
        if Employee:
            Employee.objects.all().delete()
        if ClearanceRecord:
            ClearanceRecord.objects.all().delete()
        if ClearingAgent:
            ClearingAgent.objects.all().delete()
        if TrackerRecord:
            TrackerRecord.objects.all().delete()
        if TrackerAgent:
            TrackerAgent.objects.all().delete()
        if ClientVehicle:
            ClientVehicle.objects.all().delete()
        if VehicleTracker:
            VehicleTracker.objects.all().delete()
        if Repossession:
            Repossession.objects.all().delete()
        if Bid:
            Bid.objects.all().delete()
        if Auction:
            Auction.objects.all().delete()
        if InsuranceClaim:
            InsuranceClaim.objects.all().delete()
        if InsurancePolicy:
            InsurancePolicy.objects.all().delete()
        if InsuranceAgent:
            InsuranceAgent.objects.all().delete()
        if Expense:
            Expense.objects.all().delete()
        if ExpenseCategory:
            ExpenseCategory.objects.all().delete()
        if Payment:
            Payment.objects.all().delete()
        if InstallmentPlan:
            InstallmentPlan.objects.all().delete()
        if Vehicle:
            Vehicle.objects.all().delete()
        if Client:
            Client.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

        self.stdout.write(self.style.SUCCESS('Data cleared!'))

    # ------------------------------------------------------------------ #
    #  Agent seed helpers                                                  #
    # ------------------------------------------------------------------ #

    def create_insurance_agents(self):
        if not InsuranceAgent:
            return []
        agents_data = [
            ('Jubilee Insurance Agency', '+254722100001', 'jubilee@agents.co.ke', 'LIC-001'),
            ('APA Insurance Brokers', '+254722100002', 'apa@agents.co.ke', 'LIC-002'),
            ('Britam Direct', '+254722100003', 'britam@agents.co.ke', 'LIC-003'),
            ('CIC Agents Ltd', '+254722100004', 'cic@agents.co.ke', 'LIC-004'),
            ('ICEA Lion Brokers', '+254722100005', 'icea@agents.co.ke', 'LIC-005'),
        ]
        agents = []
        for name, phone, email, id_number in agents_data:
            agent, _ = InsuranceAgent.objects.get_or_create(
                name=name,
                defaults={'phone': phone, 'email': email, 'id_number': id_number, 'is_active': True},
            )
            agents.append(agent)
        self.stdout.write(f'  Created/verified {len(agents)} insurance agents')
        return agents

    def create_tracker_agents(self):
        if not TrackerAgent:
            return []
        agents_data = [
            ('Saudia Tracking Ltd', '+254733200001', 'info@saudia.co.ke'),
            ('Trackmatic Kenya', '+254733200002', 'ops@trackmatic.co.ke'),
            ('AfriCoverage GPS', '+254733200003', 'sales@africoverage.co.ke'),
            ('TrackerSmart Africa', '+254733200004', 'support@trackersmart.co.ke'),
            ('GPS Track Africa', '+254733200005', 'info@gpstrack.co.ke'),
        ]
        agents = []
        for name, phone, email in agents_data:
            agent, _ = TrackerAgent.objects.get_or_create(
                name=name,
                defaults={'phone': phone, 'email': email, 'is_active': True},
            )
            agents.append(agent)
        self.stdout.write(f'  Created/verified {len(agents)} tracker agents')
        return agents

    def create_clearing_agents(self):
        if not ClearingAgent:
            return []
        agents_data = [
            ('Nairobi Clearing House', '+254744300001', 'ops@nch.co.ke'),
            ('Mombasa Port Clearance', '+254744300002', 'info@mpc.co.ke'),
            ('KPA Clearing Agents', '+254744300003', 'kpa@clearance.co.ke'),
            ('Eastlands Customs Bureau', '+254744300004', 'ecb@customs.co.ke'),
        ]
        agents = []
        for name, phone, email in agents_data:
            agent, _ = ClearingAgent.objects.get_or_create(
                name=name,
                defaults={'phone': phone, 'email': email, 'is_active': True},
            )
            agents.append(agent)
        self.stdout.write(f'  Created/verified {len(agents)} clearing agents')
        return agents

    # ------------------------------------------------------------------ #
    #  Core data                                                           #
    # ------------------------------------------------------------------ #

    def create_users(self, count):
        from utils.constants import UserRole

        users = []

        if not User.objects.filter(email='admin@hozainvestments.co.ke').exists():
            admin = User.objects.create_superuser(
                email='admin@hozainvestments.co.ke',
                password='admin123',
                first_name='Admin',
                last_name='User',
                phone='+254784170447',
                is_active=True,
            )
            users.append(admin)
            self.stdout.write('  Created admin: admin@hozainvestments.co.ke / admin123')

        roles = [UserRole.MANAGER, UserRole.SALES, UserRole.ACCOUNTANT, UserRole.CLERK]

        for i in range(1, count + 1):
            email = f'user{i}@hozainvestments.co.ke'
            if not User.objects.filter(email=email).exists():
                user = User.objects.create_user(
                    email=email,
                    password='password123',
                    first_name=f'User{i}',
                    last_name='Staff',
                    phone=f'+25471234{5000 + i}',
                    role=random.choice(roles),
                    is_active=True,
                )
                users.append(user)

        self.stdout.write(f'  Created {len(users)} users')
        return users

    def create_clients(self, count):
        if not Client:
            return []

        clients = []
        first_names = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emma', 'James', 'Olivia',
                       'William', 'Sophia', 'Robert', 'Isabella', 'Daniel', 'Mia', 'Joseph']
        last_names = ['Kamau', 'Wanjiru', 'Ochieng', 'Akinyi', 'Mwangi', 'Njeri', 'Otieno',
                      'Wambui', 'Kiprop', 'Chebet', 'Mutua', 'Nduta', 'Karanja', 'Adhiambo']

        for i in range(count):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)

            client = Client.objects.create(
                first_name=first_name,
                last_name=last_name,
                email=f'{first_name.lower()}.{last_name.lower()}{i}@gmail.com',
                phone_primary=f'+2547{random.randint(10000000, 99999999)}',
                id_number=f'{random.randint(10000000, 99999999)}',
                date_of_birth=datetime.now().date() - timedelta(days=random.randint(7300, 18250)),
                physical_address=f'{random.randint(1, 999)} {random.choice(["Mombasa", "Thika", "Ngong", "Kiambu"])} Road',
                city=random.choice(['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret']),
                county=random.choice(['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Uasin Gishu']),
                status=random.choice(['active', 'active', 'active', 'inactive']),
            )
            clients.append(client)

        self.stdout.write(f'  Created {len(clients)} clients')
        return clients

    def create_vehicles(self, count):
        if not Vehicle:
            return []

        vehicles = []

        makes_models = {
            'Toyota': ['Corolla', 'Camry', 'RAV4', 'Land Cruiser', 'Hilux', 'Prado', 'Vitz', 'Fielder'],
            'Nissan': ['X-Trail', 'Patrol', 'Note', 'Juke', 'Qashqai', 'Navara'],
            'Honda': ['Fit', 'Civic', 'CR-V', 'Accord', 'HR-V'],
            'Mazda': ['Demio', 'CX-5', 'Axela', 'Atenza', 'CX-3'],
            'Subaru': ['Impreza', 'Forester', 'Outback', 'Legacy', 'XV'],
            'Mercedes-Benz': ['C-Class', 'E-Class', 'GLE', 'GLC', 'A-Class'],
            'BMW': ['3 Series', '5 Series', 'X3', 'X5', 'X1'],
            'Mitsubishi': ['Outlander', 'Pajero', 'L200', 'ASX'],
        }

        fuel_types = ['petrol', 'diesel', 'hybrid', 'electric']
        transmission_types = ['automatic', 'manual']
        body_types = ['sedan', 'suv', 'hatchback', 'pickup', 'wagon']
        conditions = ['excellent', 'good', 'fair']
        statuses = ['available', 'sold', 'reserved']

        for i in range(count):
            make = random.choice(list(makes_models.keys()))
            model = random.choice(makes_models[make])
            year = random.randint(2015, 2024)

            base_price = random.randint(800000, 5000000)
            if make in ['Mercedes-Benz', 'BMW']:
                base_price = int(base_price * 1.5)
            if year >= 2022:
                base_price = int(base_price * 1.2)

            purchase_date = datetime.now().date() - timedelta(days=random.randint(30, 730))
            vin = f'VIN{year}{random.randint(1000000, 9999999)}'

            vehicle = Vehicle.objects.create(
                make=make,
                model=model,
                year=year,
                vin=vin,
                registration_number=f'K{random.choice("ABCDEFGH")}{random.randint(100, 999)}{random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}',
                color=random.choice(['White', 'Black', 'Silver', 'Blue', 'Red', 'Gray', 'Pearl']),
                mileage=random.randint(10000, 150000),
                fuel_type=random.choice(fuel_types),
                transmission=random.choice(transmission_types),
                body_type=random.choice(body_types),
                engine_size=f'{random.choice([1.0, 1.3, 1.5, 1.8, 2.0, 2.5, 3.0, 3.5])}L',
                purchase_price=Decimal(base_price) * Decimal('0.8'),
                selling_price=Decimal(base_price),
                clearance_cost=Decimal(random.randint(50000, 300000)),
                condition=random.choice(conditions),
                status=random.choice(statuses),
                location=random.choice(['Main Yard', 'Showroom', 'Service Center', 'Warehouse']),
                purchase_date=purchase_date,
                description=f'{year} {make} {model} in {random.choice(conditions)} condition. Well maintained.',
                features='Air Conditioning, Power Steering, Power Windows, Central Locking, ABS, Airbags',
            )
            vehicles.append(vehicle)

        self.stdout.write(f'  Created {len(vehicles)} vehicles')
        return vehicles

    def create_installment_plans(self, clients, vehicles):
        if not InstallmentPlan or not clients or not vehicles:
            return []

        plans = []
        vehicles_for_plans = random.sample(vehicles, min(len(vehicles), len(clients)))

        for i, vehicle in enumerate(vehicles_for_plans):
            if i >= len(clients):
                break

            client = clients[i]
            down_payment = vehicle.selling_price * Decimal('0.3')
            loan_amount = vehicle.selling_price - down_payment
            duration_months = random.choice([12, 24, 36, 48, 60])
            monthly_payment = round(loan_amount / Decimal(str(duration_months)), 2)
            start_date = datetime.now().date() - timedelta(days=random.randint(30, 365))
            end_date = start_date + timedelta(days=duration_months * 30)

            try:
                client_vehicle = ClientVehicle.objects.create(
                    client=client,
                    vehicle=vehicle,
                    purchase_date=start_date,
                    purchase_price=vehicle.selling_price,
                    deposit_paid=down_payment,
                    total_paid=down_payment,
                    balance=loan_amount,
                    monthly_installment=monthly_payment,
                    installment_months=duration_months,
                    is_active=True,
                    is_paid_off=False,
                )

                plan = InstallmentPlan.objects.create(
                    client_vehicle=client_vehicle,
                    total_amount=vehicle.selling_price,
                    deposit=down_payment,
                    monthly_installment=monthly_payment,
                    number_of_installments=duration_months,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True,
                    is_completed=False,
                    notes=f'Installment plan for {vehicle.make} {vehicle.model}',
                )
                plans.append(plan)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create plan: {e}')

        self.stdout.write(f'  Created {len(plans)} installment plans')
        return plans

    def create_payments(self, installment_plans):
        if not Payment or not installment_plans:
            return []

        payments = []
        today = timezone.now().date()

        for plan in installment_plans:
            client_vehicle = plan.client_vehicle
            months_elapsed = (today - plan.start_date).days // 30
            payments_to_create = min(months_elapsed, plan.number_of_installments)
            missed_months = set()
            if payments_to_create > 2 and random.random() > 0.55:
                missed_count = random.randint(1, min(3, max(1, payments_to_create // 2)))
                missed_months = set(random.sample(range(payments_to_create), missed_count))

            try:
                is_split = random.random() > 0.4
                if is_split and PaymentSplit:
                    split_amount_1 = plan.deposit / Decimal('2')
                    split_amount_2 = plan.deposit - split_amount_1
                    payment = Payment.objects.create(
                        client_vehicle=client_vehicle,
                        amount=plan.deposit,
                        payment_date=plan.start_date,
                        payment_method='mixed',
                        transaction_reference=f'DEP{random.randint(100000, 999999)}',
                        notes='Deposit payment (split)',
                    )
                    PaymentSplit.objects.create(payment=payment, payment_method='cash', amount=split_amount_1,
                                                transaction_reference=f'CASH{random.randint(100000, 999999)}')
                    PaymentSplit.objects.create(payment=payment, payment_method='bank_transfer', amount=split_amount_2,
                                                transaction_reference=f'BT{random.randint(100000, 999999)}')
                else:
                    payment = Payment.objects.create(
                        client_vehicle=client_vehicle,
                        amount=plan.deposit,
                        payment_date=plan.start_date,
                        payment_method=random.choice(['cash', 'bank_transfer', 'mpesa']),
                        transaction_reference=f'DEP{random.randint(100000, 999999)}',
                        notes='Deposit payment',
                    )
                payments.append(payment)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create deposit payment: {e}')

            for i in range(payments_to_create):
                if i in missed_months:
                    continue
                payment_date = plan.start_date + timedelta(days=(i + 1) * 30)
                payment_amount = plan.monthly_installment
                if random.random() > 0.82:
                    payment_amount = round(plan.monthly_installment / Decimal('2'), 2)
                try:
                    is_split_monthly = random.random() > 0.7
                    if is_split_monthly and PaymentSplit:
                        split_amount_1 = payment_amount * Decimal('0.6')
                        split_amount_2 = payment_amount - split_amount_1
                        payment = Payment.objects.create(
                            client_vehicle=client_vehicle,
                            amount=payment_amount,
                            payment_date=payment_date,
                            payment_method='mixed',
                            transaction_reference=f'INST{random.randint(100000, 999999)}',
                            notes=f'Monthly installment {i + 1} of {plan.number_of_installments} (split)',
                        )
                        PaymentSplit.objects.create(payment=payment, payment_method='mpesa', amount=split_amount_1,
                                                    transaction_reference=f'MPESA{random.randint(100000, 999999)}')
                        PaymentSplit.objects.create(payment=payment, payment_method='cash', amount=split_amount_2,
                                                    transaction_reference=f'CASH{random.randint(100000, 999999)}')
                    else:
                        payment = Payment.objects.create(
                            client_vehicle=client_vehicle,
                            amount=payment_amount,
                            payment_date=payment_date,
                            payment_method=random.choice(['bank_transfer', 'mpesa', 'mpesa', 'cash']),
                            transaction_reference=f'INST{random.randint(100000, 999999)}',
                            notes=f'Monthly installment {i + 1} of {plan.number_of_installments}',
                        )
                    payments.append(payment)
                except Exception as e:
                    self.stdout.write(f'    Warning: Could not create monthly payment: {e}')

            try:
                for schedule in plan.payment_schedules.filter(is_paid=False, due_date__lt=today):
                    schedule.update_late_fees()
            except Exception:
                pass

        self.stdout.write(f'  Created {len(payments)} payments')
        return payments

    def create_expense_categories(self):
        if not ExpenseCategory:
            return []

        categories_data = [
            ('Fuel', 'Vehicle fuel expenses', 'FUEL'),
            ('Maintenance', 'Vehicle maintenance and repairs', 'MAINT'),
            ('Insurance', 'Insurance premiums', 'INSUR'),
            ('Salaries', 'Employee salaries', 'SAL'),
            ('Rent', 'Office and yard rent', 'RENT'),
            ('Utilities', 'Electricity, water, internet', 'UTIL'),
            ('Marketing', 'Advertising and promotions', 'MKTG'),
            ('Office Supplies', 'Stationery and supplies', 'OFFIC'),
            ('Transport', 'Transport and logistics', 'TRANS'),
            ('Legal', 'Legal fees and compliance', 'LEGAL'),
        ]

        categories = []
        for name, description, code in categories_data:
            category, _ = ExpenseCategory.objects.get_or_create(
                code=code,
                defaults={'name': name, 'description': description, 'is_active': True},
            )
            categories.append(category)

        self.stdout.write(f'  Created/verified {len(categories)} expense categories')
        return categories

    def create_expenses(self, categories, vehicles):
        if not Expense or not categories:
            return []

        expenses = []
        amount_ranges = {
            'FUEL': (2000, 10000),
            'MAINT': (5000, 50000),
            'INSUR': (10000, 100000),
            'SAL': (30000, 100000),
            'RENT': (50000, 200000),
            'UTIL': (5000, 30000),
            'MKTG': (10000, 100000),
            'OFFIC': (2000, 20000),
            'TRANS': (3000, 15000),
            'LEGAL': (10000, 50000),
        }

        submitter = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not submitter:
            return []

        for _ in range(200):
            category = random.choice(categories)
            related_vehicle = (
                random.choice(vehicles) if vehicles and category.code in ['FUEL', 'MAINT', 'INSUR'] else None
            )
            lo, hi = amount_ranges.get(category.code, (5000, 50000))
            amount = Decimal(random.randint(lo, hi))
            expense_date = datetime.now().date() - timedelta(days=random.randint(1, 365))
            try:
                expense = Expense.objects.create(
                    title=f'{category.name} expense',
                    category=category,
                    related_vehicle=related_vehicle,
                    amount=amount,
                    expense_date=expense_date,
                    payment_method=random.choice(['CASH', 'BANK_TRANSFER', 'MOBILE_MONEY', 'CHECK']),
                    submitted_by=submitter,
                    status=random.choice(['APPROVED', 'PAID', 'PAID']),
                    vendor_name=f'{random.choice(["ABC", "XYZ", "Best", "Top"])} {random.choice(["Services", "Suppliers", "Company"])}',
                    invoice_number=f'INV{random.randint(1000, 9999)}',
                    description=f'{category.name} expense for {expense_date.strftime("%B %Y")}',
                )
                expenses.append(expense)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create expense: {e}')

        self.stdout.write(f'  Created {len(expenses)} expenses')
        return expenses

    def create_insurance_policies(self, vehicles, clients, insurance_agents):
        if not InsurancePolicy or not vehicles:
            return []

        policies = []

        if not insurance_agents:
            insurance_agents = list(InsuranceAgent.objects.filter(is_active=True)) if InsuranceAgent else []

        agent_names_fallback = ['Jane Smith', 'Peter Kipchoge', 'Alice Omondi', 'David Mureithi', 'Grace Karwai']

        for vehicle in random.sample(vehicles, min(len(vehicles), 40)):
            start_date = datetime.now().date() - timedelta(days=random.randint(0, 365))
            linked_cv = None
            if ClientVehicle:
                linked_cv = ClientVehicle.objects.filter(vehicle=vehicle).order_by('-purchase_date').first()

            sold = linked_cv is not None and random.random() > 0.2
            policy_client = linked_cv.client if sold else None

            buying_price = (vehicle.purchase_price if hasattr(vehicle, 'purchase_price') else vehicle.selling_price * Decimal('0.8'))
            selling_price = Decimal(random.randint(15000, 90000))

            if sold:
                payment_state = random.choice(['full', 'partial', 'unpaid'])
                if payment_state == 'full':
                    paid_amount = selling_price
                elif payment_state == 'partial':
                    paid_amount = round(selling_price * Decimal(random.choice(['0.25', '0.5', '0.75'])), 2)
                else:
                    paid_amount = Decimal('0.00')
                balance_amount = selling_price - paid_amount
                has_plan = balance_amount > 0 and random.random() > 0.4
            else:
                paid_amount = Decimal('0.00')
                balance_amount = Decimal('0.00')
                has_plan = False

            insurance_agent = random.choice(insurance_agents) if insurance_agents else None

            policy_data = {
                'vehicle': vehicle,
                'insurance_agent': insurance_agent,
                'policy_number': f'POL{random.randint(100000, 999999)}',
                'policy_type': random.choice(['comprehensive', 'third_party', 'third_party_fire_theft']),
                'premium_amount': Decimal(random.randint(30000, 150000)),
                'sum_insured': vehicle.selling_price,
                'start_date': start_date,
                'end_date': start_date + timedelta(days=365),
                'status': random.choice(['active', 'active', 'expired']),
                'buying_price': buying_price,
                'selling_price': selling_price,
                'client': policy_client,
                'agent_name': insurance_agent.name if insurance_agent else random.choice(agent_names_fallback),
                'agent_id': f'AG{random.randint(10000, 99999)}',
                'has_payment_plan': has_plan,
                'insurance_deposit': paid_amount,
                'insurance_total_paid': paid_amount,
                'insurance_balance': balance_amount,
                'dealer_payment_status': random.choice(['unpaid', 'unpaid', 'paid']),
            }

            if has_plan:
                policy_data.update({
                    'insurance_installment_months': random.choice([6, 12, 24]),
                    'insurance_interest_rate': Decimal(random.choice([0, 5, 10])),
                })

            try:
                policy = InsurancePolicy.objects.create(**policy_data)
                policies.append(policy)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create policy: {e}')

        self.stdout.write(f'  Created {len(policies)} insurance policies')
        return policies

    def create_claims(self, policies):
        if not InsuranceClaim or not policies:
            return []

        claims = []
        for policy in random.sample(policies, min(len(policies), 10)):
            try:
                claim = InsuranceClaim.objects.create(
                    policy=policy,
                    claim_number=f'CLM{random.randint(100000, 999999)}',
                    claim_date=policy.start_date + timedelta(days=random.randint(30, 300)),
                    incident_date=policy.start_date + timedelta(days=random.randint(30, 290)),
                    claim_type=random.choice(['accident', 'theft', 'fire', 'vandalism']),
                    claimed_amount=Decimal(random.randint(50000, 500000)),
                    status=random.choice(['pending', 'approved', 'rejected', 'settled']),
                    incident_description='Claim filed for vehicle incident',
                    incident_location='Nairobi',
                    notes='Claim in process',
                )
                claims.append(claim)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create claim: {e}')

        self.stdout.write(f'  Created {len(claims)} insurance claims')
        return claims

    def create_vehicle_trackers(self, vehicles, tracker_agents):
        if not ClientVehicle:
            return []

        if not tracker_agents:
            tracker_agents = list(TrackerAgent.objects.filter(is_active=True)) if TrackerAgent else []

        trackers = []
        client_vehicles = list(ClientVehicle.objects.filter(is_active=True)[:30])
        if not client_vehicles:
            self.stdout.write('  No sold vehicles found for trackers')
            return []

        for cv in client_vehicles:
            if random.random() > 0.3:
                num_trackers = random.choice([1, 1, 1, 2])
                for i in range(num_trackers):
                    has_plan = random.random() > 0.6
                    selling_price = Decimal(random.randint(8000, 20000))
                    buying_price = Decimal(random.randint(5000, 15000))
                    payment_state = random.choice(['full', 'partial', 'unpaid'])
                    if payment_state == 'full':
                        total_paid = selling_price
                    elif payment_state == 'partial':
                        total_paid = round(selling_price * Decimal(random.choice(['0.3', '0.5', '0.7'])), 2)
                    else:
                        total_paid = Decimal('0.00')

                    agent = random.choice(tracker_agents) if tracker_agents else None
                    agent_name = agent.name if agent else f'Tracker Agent {i+1}'
                    installed_date = datetime.now().date() - timedelta(days=random.randint(30, 365))
                    tracker_name = f'{agent_name} Unit {i+1}'
                    serial_number = f'TRK{random.randint(100000, 999999)}'

                    tracker_data = {
                        'client_vehicle': cv,
                        'tracker_name': tracker_name,
                        'serial_number': serial_number,
                        'provider': agent_name,
                        'buying_price': buying_price,
                        'selling_price': selling_price,
                        'has_payment_plan': has_plan,
                        'installed_date': installed_date,
                        'created_by_id': User.objects.first().id if User.objects.exists() else None,
                        'total_paid': total_paid,
                    }
                    if has_plan:
                        tracker_data.update({
                            'deposit': total_paid,
                            'installment_months': random.choice([6, 12]),
                            'monthly_installment': Decimal(random.randint(500, 2000)),
                        })

                    try:
                        tracker = VehicleTracker.objects.create(**tracker_data)
                        trackers.append(tracker)

                        if agent and TrackerRecord:
                            TrackerRecord.objects.create(
                                vehicle=cv.vehicle,
                                client_vehicle=cv,
                                agent=agent,
                                tracker_name=tracker_name,
                                serial_number=serial_number,
                                buying_price=buying_price,
                                selling_price=selling_price,
                                installation_date=installed_date,
                                dealer_payment_status=random.choice(['unpaid', 'unpaid', 'paid']),
                            )
                    except Exception as e:
                        self.stdout.write(f'    Warning: Could not create tracker: {e}')

        self.stdout.write(f'  Created {len(trackers)} vehicle trackers with tracker records')
        return trackers

    def create_clearance_records(self, vehicles, clearing_agents):
        if not ClearanceRecord or not clearing_agents or not vehicles:
            return []

        records = []
        vehicles_with_clearance = [v for v in vehicles if getattr(v, 'clearance_cost', None) and v.clearance_cost > 0]
        sample = random.sample(vehicles_with_clearance, min(len(vehicles_with_clearance), 35))

        for vehicle in sample:
            agent = random.choice(clearing_agents)
            clearance_date = getattr(vehicle, 'purchase_date', None) or datetime.now().date() - timedelta(days=random.randint(30, 365))
            try:
                record, _ = ClearanceRecord.objects.get_or_create(
                    vehicle=vehicle,
                    agent=agent,
                    defaults={
                        'amount': vehicle.clearance_cost,
                        'date': clearance_date,
                        'payment_status': random.choice(['unpaid', 'unpaid', 'paid']),
                    },
                )
                records.append(record)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create clearance record: {e}')

        self.stdout.write(f'  Created {len(records)} clearance records')
        return records

    def create_auctions(self, vehicles):
        if not Auction or not vehicles:
            return []

        auctions = []
        available_vehicles = [v for v in vehicles if v.status == 'available']

        for vehicle in random.sample(available_vehicles, min(len(available_vehicles), 15)):
            start_date = timezone.now() - timedelta(days=random.randint(1, 30))
            end_date = start_date + timedelta(days=random.randint(7, 30))
            try:
                auction = Auction.objects.create(
                    vehicle=vehicle,
                    title=f'{vehicle.year} {vehicle.make} {vehicle.model} Auction',
                    description=f'Auction for {vehicle.make} {vehicle.model}.',
                    starting_price=vehicle.selling_price * Decimal('0.8'),
                    reserve_price=vehicle.selling_price * Decimal('0.9'),
                    current_bid=vehicle.selling_price * Decimal('0.85'),
                    start_date=start_date,
                    end_date=end_date,
                    status=random.choice(['active', 'active', 'completed', 'cancelled']),
                )
                auctions.append(auction)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create auction: {e}')

        self.stdout.write(f'  Created {len(auctions)} auctions')
        return auctions

    def create_bids(self, auctions, clients):
        if not Bid or not auctions:
            return []

        bids = []
        users = list(User.objects.all())
        if not users:
            return []

        for auction in auctions:
            num_bids = random.randint(2, 8)
            bid_users = random.sample(users, min(num_bids, len(users)))
            for i, user in enumerate(bid_users):
                bid_amount = (
                    auction.starting_price + (auction.reserve_price - auction.starting_price) * Decimal(i / num_bids)
                    if auction.reserve_price else auction.starting_price * Decimal(1 + i * 0.05)
                )
                try:
                    bid = Bid.objects.create(
                        auction=auction,
                        bidder=user,
                        bid_amount=bid_amount,
                        is_active=random.choice([True, True, False]),
                    )
                    bids.append(bid)
                except Exception as e:
                    self.stdout.write(f'    Warning: Could not create bid: {e}')

        self.stdout.write(f'  Created {len(bids)} bids')
        return bids

    def create_repossessions(self, vehicles, clients):
        if not Repossession or not vehicles or not clients:
            return []

        repossessions = []
        defaulted_sales = []
        if ClientVehicle:
            defaulted_sales = list(
                ClientVehicle.objects.select_related('client', 'vehicle').filter(is_paid_off=False).order_by('-purchase_date')[:20]
            )

        if not defaulted_sales:
            sold_vehicles = [v for v in vehicles if v.status == 'sold']
            if not sold_vehicles:
                return []
            defaulted_sales = [
                type('FallbackSale', (), {
                    'vehicle': vehicle,
                    'client': random.choice(clients),
                    'balance': vehicle.selling_price * Decimal('0.35'),
                })()
                for vehicle in random.sample(sold_vehicles, min(len(sold_vehicles), 5))
            ]

        assigned_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

        for sale in random.sample(defaulted_sales, min(len(defaulted_sales), 5)):
            vehicle = sale.vehicle
            client = sale.client
            outstanding_amount = getattr(sale, 'balance', None) or vehicle.selling_price * Decimal('0.35')
            status = random.choice(['PENDING', 'NOTICE_SENT', 'IN_PROGRESS', 'VEHICLE_RECOVERED', 'COMPLETED'])
            recovery_date = None
            completion_date = None
            current_location = ''
            recovery_method = ''
            resolution_type = ''

            if status in ['VEHICLE_RECOVERED', 'COMPLETED']:
                recovery_date = datetime.now().date() - timedelta(days=random.randint(1, 30))
                completion_date = recovery_date + timedelta(days=random.randint(1, 10)) if status == 'COMPLETED' else None
                current_location = f'{random.randint(1, 999)} Industrial Area, Nairobi'
                recovery_method = random.choice(['Tow truck recovery', 'Voluntary surrender', 'Police-assisted recovery'])
                resolution_type = random.choice(['AUCTIONED', 'RETURNED', 'PAID_IN_FULL'])

            try:
                repo = Repossession.objects.create(
                    vehicle=vehicle,
                    client=client,
                    reason=random.choice(['PAYMENT_DEFAULT', 'BREACH_OF_CONTRACT', 'INSURANCE_LAPSE']),
                    status=status,
                    outstanding_amount=Decimal(outstanding_amount),
                    payments_missed=random.randint(2, 8),
                    last_payment_date=datetime.now().date() - timedelta(days=random.randint(30, 180)),
                    initiated_date=datetime.now().date() - timedelta(days=random.randint(1, 90)),
                    notice_sent_date=datetime.now().date() - timedelta(days=random.randint(1, 60)) if status != 'PENDING' else None,
                    recovery_date=recovery_date,
                    completion_date=completion_date,
                    assigned_to=assigned_user,
                    recovery_cost=Decimal(random.randint(10000, 50000)),
                    last_known_location=f'{random.randint(1, 999)} Mombasa Road, Nairobi',
                    current_location=current_location,
                    recovery_method=recovery_method,
                    legal_notice_sent=status != 'PENDING',
                    court_order_obtained=status in ['VEHICLE_RECOVERED', 'COMPLETED'] and random.random() > 0.6,
                    additional_costs=Decimal(random.randint(10000, 40000)),
                    resolution_type=resolution_type,
                    notes='Seeded repossession record for dashboard testing',
                )
                repossessions.append(repo)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create repossession: {e}')

        self.stdout.write(f'  Created {len(repossessions)} repossessions')
        return repossessions

    def create_employees(self):
        if not Employee:
            return []

        from utils.constants import UserRole

        employees = []
        positions = [
            ('Sales Manager', 'FULL_TIME'),
            ('Sales Executive', 'FULL_TIME'),
            ('Accountant', 'FULL_TIME'),
            ('Receptionist', 'FULL_TIME'),
            ('Mechanic', 'FULL_TIME'),
            ('Driver', 'CONTRACT'),
            ('Security Guard', 'CONTRACT'),
            ('Cleaner', 'PART_TIME'),
        ]
        first_names = ['Peter', 'Mary', 'John', 'Grace', 'Paul', 'Faith', 'Joseph', 'Lucy']
        last_names = ['Kamau', 'Wanjiru', 'Otieno', 'Akinyi', 'Kiprop', 'Chebet', 'Mwangi']

        for i, (position, employment_type) in enumerate(positions):
            email = f'employee{i+1}@hozainvestments.co.ke'
            if User.objects.filter(email=email).exists():
                continue
            user = User.objects.create_user(
                email=email,
                password='password123',
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                phone=f'+2547{random.randint(10000000, 99999999)}',
                role=UserRole.CLERK,
                is_active=True,
            )
            try:
                employee = Employee.objects.create(
                    user=user,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    email=email,
                    phone_number=user.phone,
                    national_id=f'{random.randint(10000000, 99999999)}',
                    job_title=position,
                    department=random.choice(['SALES', 'FINANCE', 'OPERATIONS', 'ADMIN']),
                    employment_type=employment_type,
                    date_of_birth=datetime.now().date() - timedelta(days=random.randint(7300, 18250)),
                    hire_date=datetime.now().date() - timedelta(days=random.randint(90, 1095)),
                    status='ACTIVE',
                    bank_name='KCB Bank',
                    bank_account_number=f'{random.randint(1000000000, 9999999999)}',
                    emergency_contact_name=f'{random.choice(first_names)} {random.choice(last_names)}',
                    emergency_contact_phone=f'+2547{random.randint(10000000, 99999999)}',
                    emergency_contact_relationship='Spouse',
                    address_line1=f'{random.randint(1, 999)} Mombasa Road',
                    city=random.choice(['Nairobi', 'Mombasa', 'Kisumu']),
                    country='Kenya',
                )
                employees.append(employee)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create employee: {e}')

        self.stdout.write(f'  Created {len(employees)} employees')
        return employees

    def create_salaries(self, employees):
        self.stdout.write('  Skipping salary creation (model structure unknown)')
        return []

    def create_payslips(self, salaries):
        self.stdout.write('  Skipping payslip creation (model structure unknown)')
        return []

    def create_documents(self, vehicles, clients):
        if not Document or not DocumentCategory:
            return []

        documents = []
        from django.utils.text import slugify

        categories_data = [
            ('Vehicle Documents', 'vehicle-documents', 'Documents related to vehicles'),
            ('Client Documents', 'client-documents', 'Documents related to clients'),
            ('Contracts', 'contracts', 'Contracts and agreements'),
            ('Insurance', 'insurance', 'Insurance related documents'),
            ('Legal', 'legal', 'Legal documents'),
        ]

        categories = []
        for name, slug, desc in categories_data:
            category, _ = DocumentCategory.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'description': desc, 'is_active': True},
            )
            categories.append(category)

        vehicle_category = next((c for c in categories if c.slug == 'vehicle-documents'), categories[0])
        client_category = next((c for c in categories if c.slug == 'client-documents'), categories[0])

        if vehicles and Vehicle:
            from django.contrib.contenttypes.models import ContentType
            vehicle_ct = ContentType.objects.get_for_model(Vehicle)
            for vehicle in random.sample(vehicles, min(len(vehicles), 20)):
                try:
                    doc = Document.objects.create(
                        title=f'{vehicle.make} {vehicle.model} - Logbook',
                        description=f'Logbook for {vehicle.registration_number}',
                        category=vehicle_category,
                        content_type=vehicle_ct,
                        object_id=vehicle.id,
                        document_number=f'LOG{random.randint(100000, 999999)}',
                        issue_date=datetime.now().date() - timedelta(days=random.randint(1, 365)),
                    )
                    documents.append(doc)
                except Exception as e:
                    self.stdout.write(f'    Warning: Could not create vehicle document: {e}')

        if clients and Client:
            from django.contrib.contenttypes.models import ContentType
            client_ct = ContentType.objects.get_for_model(Client)
            for client in random.sample(clients, min(len(clients), 20)):
                try:
                    doc = Document.objects.create(
                        title=f'{client.first_name} {client.last_name} - ID Copy',
                        description='ID document for client',
                        category=client_category,
                        content_type=client_ct,
                        object_id=client.id,
                        document_number=client.id_number,
                        issue_date=datetime.now().date() - timedelta(days=random.randint(1, 365)),
                    )
                    documents.append(doc)
                except Exception as e:
                    self.stdout.write(f'    Warning: Could not create client document: {e}')

        self.stdout.write(f'  Created {len(documents)} documents')
        return documents

    def print_summary(self, users, clients, vehicles):
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('DATABASE POPULATION SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'[USERS]       {User.objects.count()}')
        if Client:
            self.stdout.write(f'[CLIENTS]     {Client.objects.count()}')
        if Vehicle:
            self.stdout.write(f'[VEHICLES]    {Vehicle.objects.count()}')
        if InsuranceAgent:
            self.stdout.write(f'[INS AGENTS]  {InsuranceAgent.objects.count()}')
        if TrackerAgent:
            self.stdout.write(f'[TRK AGENTS]  {TrackerAgent.objects.count()}')
        if ClearingAgent:
            self.stdout.write(f'[CLR AGENTS]  {ClearingAgent.objects.count()}')
        if InstallmentPlan:
            self.stdout.write(f'[PLANS]       {InstallmentPlan.objects.count()}')
        if Payment:
            self.stdout.write(f'[PAYMENTS]    {Payment.objects.count()}')
        if Expense:
            self.stdout.write(f'[EXPENSES]    {Expense.objects.count()}')
        if InsurancePolicy:
            self.stdout.write(f'[POLICIES]    {InsurancePolicy.objects.count()}')
        if TrackerRecord:
            self.stdout.write(f'[TRK RECORDS] {TrackerRecord.objects.count()}')
        if ClearanceRecord:
            self.stdout.write(f'[CLR RECORDS] {ClearanceRecord.objects.count()}')
        if InsuranceClaim:
            self.stdout.write(f'[CLAIMS]      {InsuranceClaim.objects.count()}')
        if Auction:
            self.stdout.write(f'[AUCTIONS]    {Auction.objects.count()}')
        if Bid:
            self.stdout.write(f'[BIDS]        {Bid.objects.count()}')
        if Repossession:
            self.stdout.write(f'[REPOSSESS]   {Repossession.objects.count()}')
        if Employee:
            self.stdout.write(f'[EMPLOYEES]   {Employee.objects.count()}')
        if Document:
            self.stdout.write(f'[DOCUMENTS]   {Document.objects.count()}')
        self.stdout.write('='*60)
        self.stdout.write('\n[ADMIN LOGIN]')
        self.stdout.write('   Email: admin@hozainvestments.co.ke')
        self.stdout.write('   Password: admin123')
        self.stdout.write('\n[STAFF LOGIN]')
        self.stdout.write('   Email: user1@hozainvestments.co.ke')
        self.stdout.write('   Password: password123')
        self.stdout.write('='*60 + '\n')
