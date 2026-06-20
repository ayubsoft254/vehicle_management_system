"""
Django Management Command — Seed minimal demo data.
Usage: python manage.py populate_db [--clear]
"""

from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

from apps.vehicles.models import Vehicle, TrackerAgent, ClearingAgent
from apps.clients.models import Client
from apps.insurance.models import InsuranceAgent


class Command(BaseCommand):
    help = 'Seed database with a superuser, agents, vehicles, and clients'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all vehicles and clients before seeding (users and agents are preserved)',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing vehicles and clients...'))
            Vehicle.objects.all().delete()
            Client.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared.'))

        with transaction.atomic():
            self._create_superuser()
            self._create_clearing_agents()
            self._create_tracker_agents()
            self._create_insurance_agents()
            self._create_vehicles()
            self._create_clients()

        self._print_summary()

    # ------------------------------------------------------------------ #

    def _create_superuser(self):
        email = 'admin@hozainvestments.co.ke'
        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(
                email=email,
                password='admin123',
                first_name='Admin',
                last_name='Hoza',
                phone='+254784170447',
                is_active=True,
            )
            self.stdout.write(f'  Created superuser: {email} / admin123')
        else:
            self.stdout.write(f'  Superuser already exists: {email}')

    def _create_clearing_agents(self):
        agents = [
            ('Mombasa Port Clearance', '+254744300001', 'info@mpc.co.ke'),
            ('Nairobi Clearing House', '+254744300002', 'ops@nch.co.ke'),
            ('KPA Clearing Agents',    '+254744300003', 'kpa@clearance.co.ke'),
        ]
        for name, phone, email in agents:
            _, created = ClearingAgent.objects.get_or_create(
                name=name,
                defaults={'phone': phone, 'email': email, 'is_active': True},
            )
            self.stdout.write(f'  {"Created" if created else "Exists"} clearing agent: {name}')

    def _create_tracker_agents(self):
        agents = [
            ('Saudia Tracking Ltd',  '+254733200001', 'info@saudia.co.ke'),
            ('Trackmatic Kenya',     '+254733200002', 'ops@trackmatic.co.ke'),
            ('AfriCoverage GPS',     '+254733200003', 'sales@africoverage.co.ke'),
        ]
        for name, phone, email in agents:
            _, created = TrackerAgent.objects.get_or_create(
                name=name,
                defaults={'phone': phone, 'email': email, 'is_active': True},
            )
            self.stdout.write(f'  {"Created" if created else "Exists"} tracker agent: {name}')

    def _create_insurance_agents(self):
        agents = [
            ('Jubilee Insurance Agency', '+254722100001', 'jubilee@agents.co.ke', 'LIC-001'),
            ('APA Insurance Brokers',    '+254722100002', 'apa@agents.co.ke',      'LIC-002'),
            ('Britam Direct',            '+254722100003', 'britam@agents.co.ke',   'LIC-003'),
        ]
        for name, phone, email, id_number in agents:
            _, created = InsuranceAgent.objects.get_or_create(
                name=name,
                defaults={'phone': phone, 'email': email, 'id_number': id_number, 'is_active': True},
            )
            self.stdout.write(f'  {"Created" if created else "Exists"} insurance agent: {name}')

    def _create_vehicles(self):
        vehicles = [
            {
                'make': 'Toyota', 'model': 'Land Cruiser', 'year': 2020,
                'vin': 'VIN20201234567',
                'registration_number': 'KDG 123A',
                'color': 'White', 'mileage': 45000,
                'fuel_type': 'diesel', 'transmission': 'automatic',
                'body_type': 'suv', 'engine_size': '4.5L',
                'purchase_price': Decimal('4200000'), 'selling_price': Decimal('5000000'),
                'clearance_cost': Decimal('250000'),
                'condition': 'excellent', 'status': 'available',
                'location': 'Showroom',
                'purchase_date': date(2024, 1, 15),
            },
            {
                'make': 'Nissan', 'model': 'X-Trail', 'year': 2019,
                'vin': 'VIN20197654321',
                'registration_number': 'KCF 456B',
                'color': 'Silver', 'mileage': 62000,
                'fuel_type': 'petrol', 'transmission': 'automatic',
                'body_type': 'suv', 'engine_size': '2.0L',
                'purchase_price': Decimal('1600000'), 'selling_price': Decimal('2000000'),
                'clearance_cost': Decimal('120000'),
                'condition': 'good', 'status': 'available',
                'location': 'Main Yard',
                'purchase_date': date(2024, 2, 10),
            },
            {
                'make': 'Subaru', 'model': 'Forester', 'year': 2021,
                'vin': 'VIN20219871234',
                'registration_number': 'KDH 789C',
                'color': 'Blue', 'mileage': 28000,
                'fuel_type': 'petrol', 'transmission': 'automatic',
                'body_type': 'suv', 'engine_size': '2.5L',
                'purchase_price': Decimal('2100000'), 'selling_price': Decimal('2600000'),
                'clearance_cost': Decimal('160000'),
                'condition': 'excellent', 'status': 'available',
                'location': 'Showroom',
                'purchase_date': date(2024, 3, 5),
            },
        ]
        for data in vehicles:
            _, created = Vehicle.objects.get_or_create(
                vin=data['vin'],
                defaults=data,
            )
            self.stdout.write(
                f'  {"Created" if created else "Exists"} vehicle: '
                f'{data["year"]} {data["make"]} {data["model"]} ({data["registration_number"]})'
            )

    def _create_clients(self):
        clients = [
            {
                'first_name': 'James', 'last_name': 'Kamau',
                'email': 'james.kamau@gmail.com',
                'phone_primary': '+254712345678',
                'id_number': '12345678',
                'date_of_birth': date(1985, 4, 20),
                'physical_address': '45 Ngong Road',
                'city': 'Nairobi', 'county': 'Nairobi',
                'status': 'active',
            },
            {
                'first_name': 'Grace', 'last_name': 'Wanjiru',
                'email': 'grace.wanjiru@gmail.com',
                'phone_primary': '+254723456789',
                'id_number': '23456789',
                'date_of_birth': date(1990, 8, 14),
                'physical_address': '12 Mombasa Road',
                'city': 'Mombasa', 'county': 'Mombasa',
                'status': 'active',
            },
            {
                'first_name': 'David', 'last_name': 'Ochieng',
                'email': 'david.ochieng@gmail.com',
                'phone_primary': '+254734567890',
                'id_number': '34567890',
                'date_of_birth': date(1988, 11, 3),
                'physical_address': '78 Thika Road',
                'city': 'Nairobi', 'county': 'Kiambu',
                'status': 'active',
            },
        ]
        for data in clients:
            _, created = Client.objects.get_or_create(
                id_number=data['id_number'],
                defaults=data,
            )
            self.stdout.write(
                f'  {"Created" if created else "Exists"} client: '
                f'{data["first_name"]} {data["last_name"]}'
            )

    def _print_summary(self):
        self.stdout.write('\n' + '=' * 55)
        self.stdout.write(self.style.SUCCESS('SEED COMPLETE'))
        self.stdout.write('=' * 55)
        self.stdout.write(f'  Superusers      : {User.objects.filter(is_superuser=True).count()}')
        self.stdout.write(f'  Clearing agents : {ClearingAgent.objects.count()}')
        self.stdout.write(f'  Tracker agents  : {TrackerAgent.objects.count()}')
        self.stdout.write(f'  Insurance agents: {InsuranceAgent.objects.count()}')
        self.stdout.write(f'  Vehicles        : {Vehicle.objects.count()}')
        self.stdout.write(f'  Clients         : {Client.objects.count()}')
        self.stdout.write('=' * 55)
        self.stdout.write('  Admin login: admin@hozainvestments.co.ke / admin123')
        self.stdout.write('=' * 55 + '\n')
