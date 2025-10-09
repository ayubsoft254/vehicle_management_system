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

# Import all models
from apps.authentication.models import User
from apps.vehicles.models import Vehicle
from apps.clients.models import Client
from apps.payments.models import Payment, InstallmentPlan
from apps.expenses.models import Expense, ExpenseCategory
from apps.insurance.models import InsurancePolicy, Claim
from apps.auctions.models import Auction, Bid
from apps.repossessions.models import Repossession
from apps.documents.models import Document
from apps.payroll.models import Employee, Salary, Payslip

User = get_user_model()


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
        Document.objects.all().delete()
        Payslip.objects.all().delete()
        Salary.objects.all().delete()
        Employee.objects.all().delete()
        Repossession.objects.all().delete()
        Bid.objects.all().delete()
        Auction.objects.all().delete()
        Claim.objects.all().delete()
        InsurancePolicy.objects.all().delete()
        Expense.objects.all().delete()
        ExpenseCategory.objects.all().delete()
        Payment.objects.all().delete()
        InstallmentPlan.objects.all().delete()
        Vehicle.objects.all().delete()
        Client.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        
        self.stdout.write(self.style.SUCCESS('Data cleared!'))

    def create_users(self, count):
        """Create user accounts"""
        users = []
        
        # Create admin user
        if not User.objects.filter(email='admin@hozainvestments.co.ke').exists():
            admin = User.objects.create_superuser(
                email='admin@hozainvestments.co.ke',
                password='admin123',
                first_name='Admin',
                last_name='User',
                phone_number='+254712345678',
                role='ADMIN',
                is_active=True
            )
            users.append(admin)
            self.stdout.write(f'  Created admin: admin@hozainvestments.co.ke / admin123')
        
        # Create staff users
        roles = ['MANAGER', 'SALES', 'ACCOUNTANT', 'SUPPORT']
        
        for i in range(1, count + 1):
            email = f'user{i}@hozainvestments.co.ke'
            if not User.objects.filter(email=email).exists():
                user = User.objects.create_user(
                    email=email,
                    password='password123',
                    first_name=f'User{i}',
                    last_name='Staff',
                    phone_number=f'+25471234{5000 + i}',
                    role=random.choice(roles),
                    is_active=True
                )
                users.append(user)
        
        self.stdout.write(f'  Created {len(users)} users')
        return users

    def create_clients(self, count):
        """Create client records"""
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
                phone_number=f'+2547{random.randint(10000000, 99999999)}',
                id_number=f'{random.randint(10000000, 99999999)}',
                date_of_birth=datetime.now().date() - timedelta(days=random.randint(7300, 18250)),
                address=f'{random.randint(1, 999)} {random.choice(["Mombasa", "Thika", "Ngong", "Kiambu"])} Road',
                city=random.choice(['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret']),
                county=random.choice(['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Uasin Gishu']),
                status=random.choice(['ACTIVE', 'ACTIVE', 'ACTIVE', 'INACTIVE']),
                credit_score=random.randint(500, 850),
                notes=f'Client created on {datetime.now().strftime("%Y-%m-%d")}'
            )
            clients.append(client)
        
        self.stdout.write(f'  Created {len(clients)} clients')
        return clients

    def create_vehicles(self, count):
        """Create vehicle records"""
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
        
        fuel_types = ['PETROL', 'DIESEL', 'HYBRID', 'ELECTRIC']
        transmission_types = ['AUTOMATIC', 'MANUAL']
        body_types = ['SEDAN', 'SUV', 'HATCHBACK', 'PICKUP', 'WAGON']
        conditions = ['EXCELLENT', 'GOOD', 'FAIR']
        statuses = ['AVAILABLE', 'SOLD', 'RESERVED', 'IN_TRANSIT']
        
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
                description=f'{year} {make} {model} in {random.choice(conditions).lower()} condition. Well maintained.',
                features='Air Conditioning, Power Steering, Power Windows, Central Locking, ABS, Airbags',
                notes=f'Added to inventory on {datetime.now().strftime("%Y-%m-%d")}'
            )
            vehicles.append(vehicle)
        
        self.stdout.write(f'  Created {len(vehicles)} vehicles')
        return vehicles

    def create_installment_plans(self, clients, vehicles):
        """Create installment plans for clients"""
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
            
            plan = InstallmentPlan.objects.create(
                vehicle=vehicle,
                client=client,
                total_amount=vehicle.selling_price,
                down_payment=down_payment,
                loan_amount=loan_amount,
                interest_rate=interest_rate,
                duration_months=duration_months,
                monthly_payment=monthly_payment,
                start_date=start_date,
                end_date=start_date + timedelta(days=duration_months * 30),
                status=random.choice(['ACTIVE', 'ACTIVE', 'COMPLETED', 'DEFAULTED']),
                notes=f'Installment plan for {vehicle.make} {vehicle.model}'
            )
            plans.append(plan)
        
        self.stdout.write(f'  Created {len(plans)} installment plans')
        return plans

    def create_payments(self, installment_plans):
        """Create payment records"""
        payments = []
        
        for plan in installment_plans:
            # Create down payment
            down_payment = Payment.objects.create(
                installment_plan=plan,
                amount=plan.down_payment,
                payment_date=plan.start_date,
                payment_method=random.choice(['CASH', 'BANK_TRANSFER', 'MPESA']),
                reference_number=f'DP{random.randint(100000, 999999)}',
                status='COMPLETED',
                notes='Down payment'
            )
            payments.append(down_payment)
            
            # Create monthly payments
            months_elapsed = (datetime.now().date() - plan.start_date).days // 30
            payments_to_create = min(months_elapsed, plan.duration_months)
            
            for i in range(payments_to_create):
                payment_date = plan.start_date + timedelta(days=(i + 1) * 30)
                
                payment = Payment.objects.create(
                    installment_plan=plan,
                    amount=plan.monthly_payment,
                    payment_date=payment_date,
                    payment_method=random.choice(['BANK_TRANSFER', 'MPESA', 'MPESA', 'CASH']),
                    reference_number=f'PAY{random.randint(100000, 999999)}',
                    status=random.choice(['COMPLETED', 'COMPLETED', 'COMPLETED', 'PENDING']),
                    notes=f'Monthly payment {i + 1} of {plan.duration_months}'
                )
                payments.append(payment)
        
        self.stdout.write(f'  Created {len(payments)} payments')
        return payments

    def create_expense_categories(self):
        """Create expense categories"""
        categories_data = [
            ('Fuel', 'Vehicle fuel expenses'),
            ('Maintenance', 'Vehicle maintenance and repairs'),
            ('Insurance', 'Insurance premiums'),
            ('Salaries', 'Employee salaries'),
            ('Rent', 'Office and yard rent'),
            ('Utilities', 'Electricity, water, internet'),
            ('Marketing', 'Advertising and promotions'),
            ('Office Supplies', 'Stationery and supplies'),
            ('Transport', 'Transport and logistics'),
            ('Legal', 'Legal fees and compliance'),
        ]
        
        categories = []
        for name, description in categories_data:
            category, created = ExpenseCategory.objects.get_or_create(
                name=name,
                defaults={'description': description, 'is_active': True}
            )
            categories.append(category)
        
        self.stdout.write(f'  Created/verified {len(categories)} expense categories')
        return categories

    def create_expenses(self, categories, vehicles):
        """Create expense records"""
        expenses = []
        
        for i in range(200):
            category = random.choice(categories)
            
            # Some expenses are vehicle-specific
            vehicle = random.choice(vehicles) if category.name in ['Fuel', 'Maintenance', 'Insurance'] else None
            
            # Generate amount based on category
            amount_ranges = {
                'Fuel': (2000, 10000),
                'Maintenance': (5000, 50000),
                'Insurance': (10000, 100000),
                'Salaries': (30000, 100000),
                'Rent': (50000, 200000),
                'Utilities': (5000, 30000),
                'Marketing': (10000, 100000),
                'Office Supplies': (2000, 20000),
                'Transport': (3000, 15000),
                'Legal': (10000, 50000),
            }
            
            amount_range = amount_ranges.get(category.name, (5000, 50000))
            amount = Decimal(random.randint(amount_range[0], amount_range[1]))
            
            expense_date = datetime.now().date() - timedelta(days=random.randint(1, 365))
            
            expense = Expense.objects.create(
                category=category,
                vehicle=vehicle,
                amount=amount,
                expense_date=expense_date,
                payment_method=random.choice(['CASH', 'BANK_TRANSFER', 'MPESA', 'CHEQUE']),
                reference_number=f'EXP{random.randint(100000, 999999)}',
                description=f'{category.name} expense',
                notes=f'Recorded on {datetime.now().strftime("%Y-%m-%d")}'
            )
            expenses.append(expense)
        
        self.stdout.write(f'  Created {len(expenses)} expenses')
        return expenses

    def create_insurance_policies(self, vehicles):
        """Create insurance policies"""
        policies = []
        insurance_companies = [
            'Jubilee Insurance', 'APA Insurance', 'Britam', 'CIC Insurance', 
            'GA Insurance', 'ICEA Lion', 'Cooperative Insurance', 'Madison Insurance'
        ]
        
        for vehicle in random.sample(vehicles, min(len(vehicles), 40)):
            start_date = datetime.now().date() - timedelta(days=random.randint(0, 365))
            
            policy = InsurancePolicy.objects.create(
                vehicle=vehicle,
                policy_number=f'POL{random.randint(100000, 999999)}',
                insurance_company=random.choice(insurance_companies),
                policy_type=random.choice(['COMPREHENSIVE', 'THIRD_PARTY', 'THIRD_PARTY_FIRE_THEFT']),
                premium_amount=Decimal(random.randint(30000, 150000)),
                coverage_amount=vehicle.selling_price,
                start_date=start_date,
                end_date=start_date + timedelta(days=365),
                status=random.choice(['ACTIVE', 'ACTIVE', 'EXPIRED']),
                notes=f'Policy for {vehicle.registration_number}'
            )
            policies.append(policy)
        
        self.stdout.write(f'  Created {len(policies)} insurance policies')
        return policies

    def create_claims(self, policies):
        """Create insurance claims"""
        claims = []
        
        for policy in random.sample(policies, min(len(policies), 10)):
            claim = Claim.objects.create(
                policy=policy,
                claim_number=f'CLM{random.randint(100000, 999999)}',
                claim_date=policy.start_date + timedelta(days=random.randint(30, 300)),
                incident_date=policy.start_date + timedelta(days=random.randint(30, 290)),
                claim_type=random.choice(['ACCIDENT', 'THEFT', 'FIRE', 'VANDALISM']),
                claim_amount=Decimal(random.randint(50000, 500000)),
                status=random.choice(['PENDING', 'APPROVED', 'REJECTED', 'SETTLED']),
                description='Claim filed for vehicle incident',
                notes='Claim in process'
            )
            claims.append(claim)
        
        self.stdout.write(f'  Created {len(claims)} insurance claims')
        return claims

    def create_auctions(self, vehicles):
        """Create auction records"""
        auctions = []
        available_vehicles = [v for v in vehicles if v.status == 'AVAILABLE']
        
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
                status=random.choice(['ACTIVE', 'ACTIVE', 'CLOSED', 'CANCELLED']),
                terms_conditions='Standard auction terms apply'
            )
            auctions.append(auction)
        
        self.stdout.write(f'  Created {len(auctions)} auctions')
        return auctions

    def create_bids(self, auctions, clients):
        """Create bid records"""
        bids = []
        
        for auction in auctions:
            num_bids = random.randint(2, 8)
            bid_clients = random.sample(clients, min(num_bids, len(clients)))
            
            for i, client in enumerate(bid_clients):
                bid_amount = auction.starting_price + (auction.reserve_price - auction.starting_price) * Decimal(i / num_bids)
                
                bid = Bid.objects.create(
                    auction=auction,
                    bidder=client,
                    amount=bid_amount,
                    status=random.choice(['ACTIVE', 'ACTIVE', 'WITHDRAWN']),
                    notes=f'Bid {i + 1} for auction'
                )
                bids.append(bid)
        
        self.stdout.write(f'  Created {len(bids)} bids')
        return bids

    def create_repossessions(self, vehicles, clients):
        """Create repossession records"""
        repossessions = []
        sold_vehicles = [v for v in vehicles if v.status == 'SOLD']
        
        for vehicle in random.sample(sold_vehicles, min(len(sold_vehicles), 8)):
            client = random.choice(clients)
            
            repossession = Repossession.objects.create(
                vehicle=vehicle,
                client=client,
                reason=random.choice(['DEFAULT', 'BREACH_OF_CONTRACT', 'REQUEST']),
                scheduled_date=datetime.now().date() + timedelta(days=random.randint(1, 30)),
                status=random.choice(['PENDING', 'IN_PROGRESS', 'COMPLETED']),
                recovery_cost=Decimal(random.randint(10000, 50000)),
                notes='Repossession initiated due to payment default'
            )
            repossessions.append(repossession)
        
        self.stdout.write(f'  Created {len(repossessions)} repossessions')
        return repossessions

    def create_employees(self):
        """Create employee records"""
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
            employee = Employee.objects.create(
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                email=f'employee{i+1}@hozainvestments.co.ke',
                phone_number=f'+2547{random.randint(10000000, 99999999)}',
                id_number=f'{random.randint(10000000, 99999999)}',
                position=position,
                department=random.choice(['SALES', 'FINANCE', 'OPERATIONS', 'ADMIN']),
                employment_type=employment_type,
                date_hired=datetime.now().date() - timedelta(days=random.randint(90, 1095)),
                status='ACTIVE',
                bank_name='KCB Bank',
                bank_account=f'{random.randint(1000000000, 9999999999)}',
                nssf_number=f'{random.randint(100000, 999999)}',
                nhif_number=f'{random.randint(100000, 999999)}',
                kra_pin=f'A{random.randint(100000000, 999999999)}X'
            )
            employees.append(employee)
        
        self.stdout.write(f'  Created {len(employees)} employees')
        return employees

    def create_salaries(self, employees):
        """Create salary records"""
        salaries = []
        
        salary_ranges = {
            'Sales Manager': (80000, 120000),
            'Sales Executive': (40000, 60000),
            'Accountant': (50000, 80000),
            'Receptionist': (30000, 40000),
            'Mechanic': (35000, 50000),
            'Driver': (25000, 35000),
            'Security Guard': (20000, 30000),
            'Cleaner': (15000, 25000),
        }
        
        for employee in employees:
            salary_range = salary_ranges.get(employee.position, (30000, 50000))
            basic_salary = Decimal(random.randint(salary_range[0], salary_range[1]))
            
            salary = Salary.objects.create(
                employee=employee,
                basic_salary=basic_salary,
                housing_allowance=basic_salary * Decimal('0.15'),
                transport_allowance=basic_salary * Decimal('0.10'),
                effective_date=employee.date_hired,
                status='ACTIVE'
            )
            salaries.append(salary)
        
        self.stdout.write(f'  Created {len(salaries)} salary records')
        return salaries

    def create_payslips(self, salaries):
        """Create payslip records"""
        payslips = []
        
        for salary in salaries:
            # Create payslips for the last 6 months
            for i in range(6):
                month_date = datetime.now().date() - timedelta(days=i * 30)
                
                gross_salary = salary.basic_salary + salary.housing_allowance + salary.transport_allowance
                nssf_deduction = Decimal('200')
                nhif_deduction = Decimal('1700')
                paye = gross_salary * Decimal('0.15')
                total_deductions = nssf_deduction + nhif_deduction + paye
                net_salary = gross_salary - total_deductions
                
                payslip = Payslip.objects.create(
                    employee=salary.employee,
                    salary=salary,
                    month=month_date.month,
                    year=month_date.year,
                    gross_salary=gross_salary,
                    nssf_deduction=nssf_deduction,
                    nhif_deduction=nhif_deduction,
                    paye=paye,
                    other_deductions=Decimal('0'),
                    total_deductions=total_deductions,
                    net_salary=net_salary,
                    payment_date=month_date,
                    status='PAID'
                )
                payslips.append(payslip)
        
        self.stdout.write(f'  Created {len(payslips)} payslips')
        return payslips

    def create_documents(self, vehicles, clients):
        """Create document records"""
        documents = []
        
        document_types = [
            ('LOGBOOK', 'Vehicle'),
            ('INSURANCE', 'Vehicle'),
            ('INSPECTION', 'Vehicle'),
            ('ID_CARD', 'Client'),
            ('CONTRACT', 'Client'),
            ('AGREEMENT', 'Client'),
        ]
        
        # Create documents for vehicles
        for vehicle in random.sample(vehicles, min(len(vehicles), 30)):
            for doc_type, _ in [dt for dt in document_types if dt[1] == 'Vehicle']:
                document = Document.objects.create(
                    title=f'{vehicle.make} {vehicle.model} - {doc_type}',
                    document_type=doc_type,
                    vehicle=vehicle,
                    description=f'{doc_type} document for {vehicle.registration_number}',
                    expiry_date=datetime.now().date() + timedelta(days=random.randint(180, 730)),
                    status='ACTIVE'
                )
                documents.append(document)
        
        # Create documents for clients
        for client in random.sample(clients, min(len(clients), 30)):
            for doc_type, _ in [dt for dt in document_types if dt[1] == 'Client']:
                document = Document.objects.create(
                    title=f'{client.first_name} {client.last_name} - {doc_type}',
                    document_type=doc_type,
                    client=client,
                    description=f'{doc_type} document for client',
                    status='ACTIVE'
                )
                documents.append(document)
        
        self.stdout.write(f'  Created {len(documents)} documents')
        return documents

    def print_summary(self, users, clients, vehicles):
        """Print summary of created data"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('DATABASE POPULATION SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'👥 Users: {User.objects.count()}')
        self.stdout.write(f'👤 Clients: {Client.objects.count()}')
        self.stdout.write(f'🚗 Vehicles: {Vehicle.objects.count()}')
        self.stdout.write(f'📝 Installment Plans: {InstallmentPlan.objects.count()}')
        self.stdout.write(f'💰 Payments: {Payment.objects.count()}')
        self.stdout.write(f'💸 Expenses: {Expense.objects.count()}')
        self.stdout.write(f'🛡️ Insurance Policies: {InsurancePolicy.objects.count()}')
        self.stdout.write(f'📋 Insurance Claims: {Claim.objects.count()}')
        self.stdout.write(f'🔨 Auctions: {Auction.objects.count()}')
        self.stdout.write(f'💵 Bids: {Bid.objects.count()}')
        self.stdout.write(f'🚛 Repossessions: {Repossession.objects.count()}')
        self.stdout.write(f'👔 Employees: {Employee.objects.count()}')
        self.stdout.write(f'💼 Salaries: {Salary.objects.count()}')
        self.stdout.write(f'📄 Payslips: {Payslip.objects.count()}')
        self.stdout.write(f'📁 Documents: {Document.objects.count()}')
        self.stdout.write('='*60)
        self.stdout.write('\n🔑 Admin Login:')
        self.stdout.write('   Email: admin@hozainvestments.co.ke')
        self.stdout.write('   Password: admin123')
        self.stdout.write('\n📧 Staff Login (any):')
        self.stdout.write('   Email: user1@hozainvestments.co.ke (or user2, user3, etc.)')
        self.stdout.write('   Password: password123')
        self.stdout.write('='*60 + '\n')
