"""
Django Management Command to Populate Database with Dummy Data
Usage: python manage.py populate_db
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

User = get_user_model()

# Try to import all models (some might not exist or have different names)
try:
    from apps.vehicles.models import Vehicle
except ImportError:
    Vehicle = None

try:
    from apps.clients.models import Client
except ImportError:
    Client = None

try:
    from apps.payments.models import Payment, InstallmentPlan
except ImportError:
    Payment = None
    InstallmentPlan = None

try:
    from apps.expenses.models import Expense, ExpenseCategory
except ImportError:
    Expense = None
    ExpenseCategory = None

try:
    from apps.insurance.models import InsurancePolicy, InsuranceClaim, InsuranceProvider
except ImportError:
    InsurancePolicy = None
    InsuranceClaim = None
    InsuranceProvider = None

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
                # Create data in order of dependencies
                self.stdout.write('Creating users...')
                users = self.create_users(options['users'])
                
                self.stdout.write('Creating clients...')
                clients = self.create_clients(options['clients'])
                
                self.stdout.write('Creating vehicles...')
                vehicles = self.create_vehicles(options['vehicles'])
                
                self.stdout.write('Creating installment plans...')
                installment_plans = self.create_installment_plans(clients, vehicles)
                
                self.stdout.write('Creating payments...')
                self.create_payments(installment_plans)
                
                self.stdout.write('Creating expense categories...')
                categories = self.create_expense_categories()
                
                self.stdout.write('Creating expenses...')
                self.create_expenses(categories, vehicles)
                
                self.stdout.write('Creating insurance policies...')
                policies = self.create_insurance_policies(vehicles)
                
                self.stdout.write('Creating insurance claims...')
                self.create_claims(policies)
                
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
                
                self.stdout.write(self.style.SUCCESS('\n✅ Database populated successfully!'))
                self.print_summary(users, clients, vehicles)
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            raise

    def clear_data(self):
        """Clear existing data from all tables"""
        self.stdout.write(self.style.WARNING('Clearing existing data...'))
        
        # Clear in reverse order of dependencies
        if Document:
            Document.objects.all().delete()
        if PayrollRun:
            PayrollRun.objects.all().delete()
        if SalaryStructure:
            SalaryStructure.objects.all().delete()
        if Employee:
            Employee.objects.all().delete()
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
        if InsuranceProvider:
            InsuranceProvider.objects.all().delete()
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

    def create_users(self, count):
        """Create user accounts"""
        from utils.constants import UserRole
        
        users = []
        
        # Create admin user
        if not User.objects.filter(email='admin@hozainvestments.co.ke').exists():
            admin = User.objects.create_superuser(
                email='admin@hozainvestments.co.ke',
                password='admin123',
                first_name='Admin',
                last_name='User',
                phone='+254712345678',
                is_active=True
            )
            users.append(admin)
            self.stdout.write(f'  Created admin: admin@hozainvestments.co.ke / admin123')
        
        # Create staff users
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
                    is_active=True
                )
                users.append(user)
        
        self.stdout.write(f'  Created {len(users)} users')
        return users

    def create_clients(self, count):
        """Create client records"""
        if not Client:
            self.stdout.write('  Skipping (Client model not available)')
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
                notes=f'Client created on {datetime.now().strftime("%Y-%m-%d")}'
            )
            clients.append(client)
        
        self.stdout.write(f'  Created {len(clients)} clients')
        return clients

    def create_vehicles(self, count):
        """Create vehicle records"""
        if not Vehicle:
            self.stdout.write('  Skipping (Vehicle model not available)')
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
            
            # Determine price based on year and make
            base_price = random.randint(800000, 5000000)
            if make in ['Mercedes-Benz', 'BMW']:
                base_price *= 1.5
            if year >= 2022:
                base_price *= 1.2
            
            purchase_date = datetime.now().date() - timedelta(days=random.randint(30, 730))
            
            vehicle = Vehicle.objects.create(
                make=make,
                model=model,
                year=year,
                vin=f'VIN{year}{random.randint(1000000, 9999999)}',
                registration_number=f'K{random.choice("ABCDEFGH")}{random.randint(100, 999)}{random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}',
                color=random.choice(['White', 'Black', 'Silver', 'Blue', 'Red', 'Gray', 'Pearl']),
                mileage=random.randint(10000, 150000),
                fuel_type=random.choice(fuel_types),
                transmission=random.choice(transmission_types),
                body_type=random.choice(body_types),
                engine_size=f'{random.choice([1.0, 1.3, 1.5, 1.8, 2.0, 2.5, 3.0, 3.5])}L',
                purchase_price=Decimal(base_price * 0.8),
                selling_price=Decimal(base_price),
                condition=random.choice(conditions),
                status=random.choice(statuses),
                location=random.choice(['Main Yard', 'Showroom', 'Service Center', 'Warehouse']),
                purchase_date=purchase_date,
                description=f'{year} {make} {model} in {random.choice(conditions).lower()} condition. Well maintained.',
                features='Air Conditioning, Power Steering, Power Windows, Central Locking, ABS, Airbags'
            )
            vehicles.append(vehicle)
        
        self.stdout.write(f'  Created {len(vehicles)} vehicles')
        return vehicles

    def create_installment_plans(self, clients, vehicles):
        """Create installment plans for clients"""
        if not InstallmentPlan or not clients or not vehicles:
            self.stdout.write('  Skipping (InstallmentPlan model not available or no data)')
            return []
        
        plans = []
        sold_vehicles = [v for v in vehicles if v.status == 'SOLD'][:len(clients)//2]
        
        for i, vehicle in enumerate(sold_vehicles):
            if i >= len(clients):
                break
                
            client = clients[i]
            
            # Calculate installment details
            down_payment = vehicle.selling_price * Decimal('0.3')  # 30% down payment
            loan_amount = vehicle.selling_price - down_payment
            interest_rate = Decimal(random.choice([10.0, 12.0, 15.0]))
            duration_months = random.choice([12, 24, 36, 48, 60])
            
            # Calculate monthly payment
            monthly_rate = interest_rate / Decimal('100') / Decimal('12')
            monthly_payment = loan_amount * monthly_rate / (Decimal('1') - (Decimal('1') + monthly_rate) ** -duration_months)
            
            start_date = datetime.now().date() - timedelta(days=random.randint(30, 365))
            end_date = start_date + timedelta(days=duration_months * 30)
            
            # First create ClientVehicle
            try:
                from apps.clients.models import ClientVehicle
                
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
                    interest_rate=interest_rate,
                    is_active=True,
                    is_paid_off=False
                )
                
                plan = InstallmentPlan.objects.create(
                    client_vehicle=client_vehicle,
                    total_amount=vehicle.selling_price,
                    deposit=down_payment,
                    monthly_installment=monthly_payment,
                    number_of_installments=duration_months,
                    interest_rate=interest_rate,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True,
                    is_completed=False,
                    notes=f'Installment plan for {vehicle.make} {vehicle.model}'
                )
                plans.append(plan)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create plan: {e}')
        
        self.stdout.write(f'  Created {len(plans)} installment plans')
        return plans

    def create_payments(self, installment_plans):
        """Create payment records"""
        if not Payment or not installment_plans:
            self.stdout.write('  Skipping (Payment model not available or no plans)')
            return []
        
        payments = []
        
        for plan in installment_plans:
            # Get the client_vehicle from the plan
            client_vehicle = plan.client_vehicle
            
            # Create deposit payment
            try:
                down_payment = Payment.objects.create(
                    client_vehicle=client_vehicle,
                    amount=plan.deposit,
                    payment_date=plan.start_date,
                    payment_method=random.choice(['cash', 'bank_transfer', 'mpesa']),
                    transaction_reference=f'DP{random.randint(100000, 999999)}',
                    notes='Deposit payment'
                )
                payments.append(down_payment)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create payment: {e}')
            
            # Create monthly payments
            months_elapsed = (datetime.now().date() - plan.start_date).days // 30
            payments_to_create = min(months_elapsed, plan.number_of_installments)
            
            for i in range(payments_to_create):
                payment_date = plan.start_date + timedelta(days=(i + 1) * 30)
                
                try:
                    payment = Payment.objects.create(
                        client_vehicle=client_vehicle,
                        amount=plan.monthly_installment,
                        payment_date=payment_date,
                        payment_method=random.choice(['bank_transfer', 'mpesa', 'mpesa', 'cash']),
                        transaction_reference=f'PAY{random.randint(100000, 999999)}',
                        notes=f'Monthly installment {i + 1} of {plan.number_of_installments}'
                    )
                    payments.append(payment)
                except Exception as e:
                    self.stdout.write(f'    Warning: Could not create payment: {e}')
        
        self.stdout.write(f'  Created {len(payments)} payments')
        return payments

    def create_expense_categories(self):
        """Create expense categories"""
        if not ExpenseCategory:
            self.stdout.write('  Skipping (ExpenseCategory model not available)')
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
            category, created = ExpenseCategory.objects.get_or_create(
                code=code,
                defaults={'name': name, 'description': description, 'is_active': True}
            )
            categories.append(category)
        
        self.stdout.write(f'  Created/verified {len(categories)} expense categories')
        return categories

    def create_expenses(self, categories, vehicles):
        """Create expense records"""
        if not Expense or not categories:
            self.stdout.write('  Skipping (Expense model not available or no categories)')
            return []
        
        expenses = []
        
        for i in range(200):
            category = random.choice(categories)
            
            # Some expenses are vehicle-specific
            related_vehicle = random.choice(vehicles) if category.code in ['fuel', 'maintenance', 'insurance'] and vehicles else None
            
            # Generate amount based on category
            amount_ranges = {
                'fuel': (2000, 10000),
                'maintenance': (5000, 50000),
                'insurance': (10000, 100000),
                'salary': (30000, 100000),
                'rent': (50000, 200000),
                'utilities': (5000, 30000),
                'marketing': (10000, 100000),
                'supplies': (2000, 20000),
                'transport': (3000, 15000),
                'legal': (10000, 50000),
            }
            
            amount_range = amount_ranges.get(category.code, (5000, 50000))
            amount = Decimal(random.randint(amount_range[0], amount_range[1]))
            
            expense_date = datetime.now().date() - timedelta(days=random.randint(1, 365))
            
            # Get a user to be the submitter
            users = User.objects.all()
            submitter = users.first() if users.exists() else None
            
            if not submitter:
                continue
            
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
                notes=f'Recorded on {datetime.now().strftime("%Y-%m-%d")}'
            )
            expenses.append(expense)
        
        self.stdout.write(f'  Created {len(expenses)} expenses')
        return expenses

    def create_insurance_policies(self, vehicles):
        """Create insurance policies"""
        if not InsurancePolicy or not InsuranceProvider or not vehicles:
            return []
        
        policies = []
        
        # First create insurance providers if they don't exist
        insurance_companies = [
            'Jubilee Insurance', 'APA Insurance', 'Britam', 'CIC Insurance', 
            'GA Insurance', 'ICEA Lion', 'Cooperative Insurance', 'Madison Insurance'
        ]
        
        providers = []
        for company_name in insurance_companies:
            provider, created = InsuranceProvider.objects.get_or_create(
                name=company_name,
                defaults={
                    'phone_primary': f'+2547{random.randint(10000000, 99999999)}',
                    'physical_address': f'{random.randint(1, 999)} {random.choice(["Kimathi", "Kenyatta", "Moi"])} Avenue, Nairobi',
                    'is_active': True
                }
            )
            providers.append(provider)
        
        for vehicle in random.sample(vehicles, min(len(vehicles), 40)):
            start_date = datetime.now().date() - timedelta(days=random.randint(0, 365))
            
            policy = InsurancePolicy.objects.create(
                vehicle=vehicle,
                provider=random.choice(providers),
                policy_number=f'POL{random.randint(100000, 999999)}',
                policy_type=random.choice(['comprehensive', 'third_party', 'third_party_fire_theft']),
                premium_amount=Decimal(random.randint(30000, 150000)),
                sum_insured=vehicle.selling_price,
                start_date=start_date,
                end_date=start_date + timedelta(days=365),
                status=random.choice(['active', 'active', 'expired']),
                notes=f'Policy for {vehicle.registration_number}'
            )
            policies.append(policy)
        
        self.stdout.write(f'  Created {len(policies)} insurance policies')
        return policies

    def create_claims(self, policies):
        """Create insurance claims"""
        if not InsuranceClaim or not policies:
            return []
        
        claims = []
        
        for policy in random.sample(policies, min(len(policies), 10)):
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
                notes='Claim in process'
            )
            claims.append(claim)
        
        self.stdout.write(f'  Created {len(claims)} insurance claims')
        return claims

    def create_auctions(self, vehicles):
        """Create auction records"""
        if not Auction or not vehicles:
            self.stdout.write('  Skipping (Auction model not available or no vehicles)')
            return []
        
        auctions = []
        available_vehicles = [v for v in vehicles if v.status == 'available']
        
        if not available_vehicles:
            self.stdout.write('  No available vehicles for auction')
            return []
        
        for vehicle in random.sample(available_vehicles, min(len(available_vehicles), 15)):
            start_date = timezone.now() - timedelta(days=random.randint(1, 30))
            end_date = start_date + timedelta(days=random.randint(7, 30))
            
            auction = Auction.objects.create(
                vehicle=vehicle,
                title=f'{vehicle.year} {vehicle.make} {vehicle.model} Auction',
                description=f'Auction for {vehicle.make} {vehicle.model}. {vehicle.description}',
                starting_price=vehicle.selling_price * Decimal('0.8'),
                reserve_price=vehicle.selling_price * Decimal('0.9'),
                current_bid=vehicle.selling_price * Decimal('0.85'),
                start_date=start_date,
                end_date=end_date,
                status=random.choice(['active', 'active', 'completed', 'cancelled'])
            )
            auctions.append(auction)
        
        self.stdout.write(f'  Created {len(auctions)} auctions')
        return auctions

    def create_bids(self, auctions, clients):
        """Create bid records"""
        if not Bid or not auctions:
            self.stdout.write('  Skipping (Bid model not available or no auctions)')
            return []
        
        bids = []
        
        # Get users to act as bidders
        users = User.objects.all()
        if not users.exists():
            self.stdout.write('  No users available for bidding')
            return []
        
        for auction in auctions:
            num_bids = random.randint(2, 8)
            bid_users = random.sample(list(users), min(num_bids, users.count()))
            
            for i, user in enumerate(bid_users):
                bid_amount = auction.starting_price + (auction.reserve_price - auction.starting_price) * Decimal(i / num_bids) if auction.reserve_price else auction.starting_price * Decimal(1 + i * 0.05)
                
                try:
                    bid = Bid.objects.create(
                        auction=auction,
                        bidder=user,
                        bid_amount=bid_amount,
                        is_active=random.choice([True, True, False])
                    )
                    bids.append(bid)
                except Exception as e:
                    self.stdout.write(f'    Warning: Could not create bid: {e}')
        
        self.stdout.write(f'  Created {len(bids)} bids')
        return bids

    def create_repossessions(self, vehicles, clients):
        """Create repossession records"""
        if not Repossession or not vehicles or not clients:
            self.stdout.write('  Skipping (Repossession model not available or no data)')
            return []
        
        repossessions = []
        sold_vehicles = [v for v in vehicles if v.status == 'sold']
        
        if not sold_vehicles:
            self.stdout.write('  No sold vehicles for repossession')
            return []
        
        for vehicle in random.sample(sold_vehicles, min(len(sold_vehicles), 5)):
            client = random.choice(clients)
            
            try:
                repossession = Repossession.objects.create(
                    vehicle=vehicle,
                    client=client,
                    reason=random.choice(['PAYMENT_DEFAULT', 'BREACH_OF_CONTRACT', 'INSURANCE_LAPSE']),
                    status=random.choice(['PENDING', 'NOTICE_SENT', 'IN_PROGRESS']),
                    outstanding_amount=Decimal(random.randint(100000, 500000)),
                    payments_missed=random.randint(2, 6),
                    initiated_date=datetime.now().date() - timedelta(days=random.randint(1, 90)),
                    recovery_cost=Decimal(random.randint(10000, 50000)),
                    last_known_location=f'{random.randint(1, 999)} {random.choice(["Mombasa", "Thika", "Ngong"])} Road, {random.choice(["Nairobi", "Mombasa", "Kisumu"])}'
                )
                repossessions.append(repossession)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create repossession: {e}')
        
        self.stdout.write(f'  Created {len(repossessions)} repossessions')
        return repossessions

    def create_employees(self):
        """Create employee records"""
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
            # Create a user for this employee
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
                is_active=True
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
                    address_line1=f'{random.randint(1, 999)} {random.choice(["Mombasa", "Thika", "Ngong"])} Road',
                    city=random.choice(['Nairobi', 'Mombasa', 'Kisumu']),
                    country='Kenya'
                )
                employees.append(employee)
            except Exception as e:
                self.stdout.write(f'    Warning: Could not create employee: {e}')
        
        self.stdout.write(f'  Created {len(employees)} employees')
        return employees

    def create_salaries(self, employees):
        """Create salary records"""
        if not SalaryStructure or not employees:
            return []
        
        # This is just a placeholder - adjust based on actual SalaryStructure model
        self.stdout.write('  Skipping salary creation (model structure unknown)')
        return []

    def create_payslips(self, salaries):
        """Create payslip records"""
        if not PayrollRun:
            return []
        
        # This is just a placeholder - adjust based on actual PayrollRun model
        self.stdout.write('  Skipping payslip creation (model structure unknown)')
        return []

    def create_documents(self, vehicles, clients):
        """Create document records"""
        if not Document or not DocumentCategory:
            return []
        
        documents = []
        
        # Create document categories with slugs
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
            category, created = DocumentCategory.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'description': desc, 'is_active': True}
            )
            categories.append(category)
        
        vehicle_category = next((c for c in categories if c.slug == 'vehicle-documents'), categories[0])
        client_category = next((c for c in categories if c.slug == 'client-documents'), categories[0])
        
        # Create documents for vehicles
        if vehicles and Vehicle:
            from django.contrib.contenttypes.models import ContentType
            vehicle_ct = ContentType.objects.get_for_model(Vehicle)
            
            for vehicle in random.sample(vehicles, min(len(vehicles), 20)):
                try:
                    document = Document.objects.create(
                        title=f'{vehicle.make} {vehicle.model} - Logbook',
                        description=f'Logbook for {vehicle.registration_number}',
                        category=vehicle_category,
                        content_type=vehicle_ct,
                        object_id=vehicle.id,
                        document_number=f'LOG{random.randint(100000, 999999)}',
                        issue_date=datetime.now().date() - timedelta(days=random.randint(1, 365))
                    )
                    documents.append(document)
                except Exception as e:
                    self.stdout.write(f'    Warning: Could not create document: {e}')
        
        # Create documents for clients  
        if clients and Client:
            from django.contrib.contenttypes.models import ContentType
            client_ct = ContentType.objects.get_for_model(Client)
            
            for client in random.sample(clients, min(len(clients), 20)):
                try:
                    document = Document.objects.create(
                        title=f'{client.first_name} {client.last_name} - ID Copy',
                        description=f'ID document for client',
                        category=client_category,
                        content_type=client_ct,
                        object_id=client.id,
                        document_number=client.id_number,
                        issue_date=datetime.now().date() - timedelta(days=random.randint(1, 365))
                    )
                    documents.append(document)
                except Exception as e:
                    self.stdout.write(f'    Warning: Could not create document: {e}')
        
        self.stdout.write(f'  Created {len(documents)} documents')
        return documents

    def print_summary(self, users, clients, vehicles):
        """Print summary of created data"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('DATABASE POPULATION SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'👥 Users: {User.objects.count()}')
        
        if Client:
            self.stdout.write(f'👤 Clients: {Client.objects.count()}')
        if Vehicle:
            self.stdout.write(f'🚗 Vehicles: {Vehicle.objects.count()}')
        if InstallmentPlan:
            self.stdout.write(f'📝 Installment Plans: {InstallmentPlan.objects.count()}')
        if Payment:
            self.stdout.write(f'💰 Payments: {Payment.objects.count()}')
        if Expense:
            self.stdout.write(f'💸 Expenses: {Expense.objects.count()}')
        if InsurancePolicy:
            self.stdout.write(f'🛡️ Insurance Policies: {InsurancePolicy.objects.count()}')
        if InsuranceClaim:
            self.stdout.write(f'📋 Insurance Claims: {InsuranceClaim.objects.count()}')
        if Auction:
            self.stdout.write(f'🔨 Auctions: {Auction.objects.count()}')
        if Bid:
            self.stdout.write(f'💵 Bids: {Bid.objects.count()}')
        if Repossession:
            self.stdout.write(f'🚛 Repossessions: {Repossession.objects.count()}')
        if Employee:
            self.stdout.write(f'� Employees: {Employee.objects.count()}')
        if Document:
            self.stdout.write(f'📁 Documents: {Document.objects.count()}')
            
        self.stdout.write('='*60)
        self.stdout.write('\n🔑 Admin Login:')
        self.stdout.write('   Email: admin@hozainvestments.co.ke')
        self.stdout.write('   Password: admin123')
        self.stdout.write('\n📧 Staff Login (any):')
        self.stdout.write('   Email: user1@hozainvestments.co.ke (or user2, user3, etc.)')
        self.stdout.write('   Password: password123')
        self.stdout.write('='*60 + '\n')
