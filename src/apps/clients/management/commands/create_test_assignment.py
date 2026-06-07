"""
Management command: create_test_assignment

Creates one client, one vehicle (or reuses an existing available one), assigns the
vehicle to the client, attaches an insurance policy and a GPS tracker, then prints
the URLs you can visit to test the agreement + online-signing flows.

Usage:
    python manage.py create_test_assignment
    python manage.py create_test_assignment --email admin@example.com
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Seed one test client-vehicle assignment with insurance and tracker"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default=None,
            help="Email of the staff user to use as 'created_by' (defaults to first superuser)",
        )

    def handle(self, *args, **options):
        from apps.authentication.models import User
        from apps.vehicles.models import Vehicle
        from apps.clients.models import Client, ClientVehicle, VehicleTracker
        from apps.insurance.models import InsuranceProvider, InsurancePolicy

        # ── 1. Resolve acting user ──────────────────────────────────────────
        email = options.get("email")
        if email:
            actor = User.objects.filter(email=email).first()
            if not actor:
                self.stderr.write(self.style.ERROR(f"No user found with email '{email}'"))
                return
        else:
            actor = (
                User.objects.filter(is_superuser=True).first()
                or User.objects.filter(is_staff=True).first()
                or User.objects.first()
            )

        if not actor:
            self.stderr.write(self.style.ERROR(
                "No users exist in the database. Create a superuser first."
            ))
            return

        self.stdout.write(f"Acting user: {actor.get_full_name()} ({actor.email})")

        # ── 2. Resolve / create test vehicle ───────────────────────────────
        ts = timezone.now().strftime("%Y%m%d%H%M%S")

        vehicle = Vehicle.objects.filter(status="available", is_active=True).first()
        if vehicle:
            self.stdout.write(f"Reusing existing available vehicle: {vehicle}")
        else:
            vehicle = Vehicle.objects.create(
                make="Toyota",
                model="Corolla",
                year=2021,
                vin=f"TEST-VIN-{ts}",
                registration_number=f"KZ{ts[-6:]}T",
                color="White",
                body_type="sedan",
                fuel_type="petrol",
                transmission="automatic",
                seats=5,
                mileage=Decimal("18000.00"),
                purchase_price=Decimal("1850000.00"),
                selling_price=Decimal("2200000.00"),
                status="available",
                is_active=True,
                added_by=actor,
            )
            self.stdout.write(self.style.SUCCESS(f"Created vehicle: {vehicle}"))

        # ── 3. Create test client ───────────────────────────────────────────
        client = Client.objects.create(
            first_name="Agreement",
            last_name="TestClient",
            id_type="national_id",
            id_number=f"TC{ts}",
            phone_primary="+254700000001",
            physical_address="123 Test Street, Nairobi",
            city="Nairobi",
            county="Nairobi",
            registered_by=actor,
            status="active",
        )
        self.stdout.write(self.style.SUCCESS(
            f"Created client: {client.get_full_name()} (ID: {client.pk})"
        ))

        # ── 4. Assign vehicle to client ────────────────────────────────────
        now = timezone.now()
        selling_price = Decimal(str(vehicle.selling_price))
        deposit = Decimal("500000.00")

        cv = ClientVehicle.objects.create(
            client=client,
            vehicle=vehicle,
            purchase_date=now.date(),
            purchase_price=selling_price,
            client_purchase_price=selling_price,
            final_selling_price=selling_price,
            deposit_paid=deposit,
            total_paid=deposit,
            balance=selling_price - deposit,
            payment_type="installment",
            remainder_payment_type="monthly",
            monthly_payment_date=5,
            installment_months=18,
            monthly_installment=((selling_price - deposit) / 18).quantize(Decimal("0.01")),
            notes="Auto-created by create_test_assignment management command",
            created_by=actor,
        )

        # Mark vehicle as sold
        vehicle.status = "sold"
        vehicle.save(update_fields=["status"])

        self.stdout.write(self.style.SUCCESS(
            f"Created ClientVehicle (ID: {cv.pk}): "
            f"{client.get_full_name()} ← {vehicle}"
        ))

        # ── 5. Add insurance policy ────────────────────────────────────────
        provider, _ = InsuranceProvider.objects.get_or_create(
            name="Jubilee Insurance Co.",
            defaults={"is_active": True, "created_by": actor},
        )

        policy = InsurancePolicy.objects.create(
            vehicle=vehicle,
            client=client,
            provider=provider,
            policy_number=f"POL-{ts}",
            policy_type="comprehensive",
            vehicle_usage="private",
            start_date=now.date(),
            end_date=(now + timezone.timedelta(days=365)).date(),
            premium_amount=Decimal("85000.00"),
            sum_insured=selling_price,
            buying_price=Decimal("65000.00"),
            selling_price=Decimal("85000.00"),
            agent_name="Test Agent",
            agent_id="AG001",
            payment_type="full",
            has_payment_plan=False,
            insurance_deposit=Decimal("85000.00"),
            insurance_total_paid=Decimal("85000.00"),
            insurance_balance=Decimal("0.00"),
            insurance_interest_rate=Decimal("0.00"),
            status="active",
            created_by=actor,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Created insurance policy: {policy.policy_number} ({provider.name})"
        ))

        # ── 6. Add GPS tracker ─────────────────────────────────────────────
        tracker = VehicleTracker.objects.create(
            client_vehicle=cv,
            tracker_name="Teltonika FMB920",
            serial_number=f"IMEI-{ts}",
            certificate_number=f"CERT-{ts}",
            provider="Hoza Trackers Ltd",
            buying_price=Decimal("9500.00"),
            selling_price=Decimal("15000.00"),
            payment_type="full",
            has_payment_plan=False,
            deposit=Decimal("15000.00"),
            total_paid=Decimal("15000.00"),
            balance=Decimal("0.00"),
            installed_date=now.date(),
            notes="GPS tracker — installed on delivery",
            created_by=actor,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Created tracker: {tracker.tracker_name} "
            f"(serial: {tracker.serial_number}, provider: {tracker.provider})"
        ))

        # ── 7. Verify agreement PDF can be generated ───────────────────────
        try:
            from apps.documents.sales_agreement_pdf import generate_sales_agreement_pdf
            buf = generate_sales_agreement_pdf(cv)
            size = buf.getbuffer().nbytes
            self.stdout.write(self.style.SUCCESS(
                f"Agreement PDF generated OK ({size:,} bytes)"
            ))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"PDF generation raised an error (non-fatal): {exc}"
            ))

        # ── 8. Print useful URLs ───────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("== Useful URLs =="))
        self.stdout.write(f"  Client detail    : /clients/{client.pk}/")
        self.stdout.write(f"  Vehicle purchase : /clients/vehicle/{cv.pk}/")
        self.stdout.write(f"  Print agreement  : /clients/vehicle/{cv.pk}/agreement/")
        self.stdout.write(f"  Sign online      : /clients/vehicle/{cv.pk}/sign/")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Done. Open the URLs above to test."))
