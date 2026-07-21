"""
Vehicles Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg, Value, DecimalField
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django.db import transaction
from django.http import HttpResponse, JsonResponse, Http404
from django.utils import timezone
from .models import Vehicle, VehiclePhoto, VehicleHistory, TrackerAgent, TrackerRecord, ClearingAgent, ClearanceRecord, Broker, BrokerPayment, JapanSupplier, JapanSupplierRecord, JapanSupplierPayment, BusinessLoan, BusinessLoanRepayment
from apps.clients.models import ClientVehicle, Client
from apps.insurance.models import InsuranceAgent
from django.contrib.contenttypes.models import ContentType
from .forms import (
    VehicleForm, VehiclePhotoForm, VehicleSearchForm,
    VehicleStatusChangeForm, BulkVehicleActionForm, VehicleMoveForm,
    TrackerAgentForm, ClearingAgentForm, BrokerForm, JapanSupplierForm,
)
from utils.decorators import role_required, module_permission_required
from utils.constants import UserRole, VehicleStatus, AccessLevel
from apps.audit.models import AuditLog
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation


def _can_view_vehicle_prices(user):
    """Only administrators should see vehicle pricing data across the app."""
    if not getattr(user, 'is_authenticated', False):
        return False
    return bool(user.is_superuser or user.is_staff or getattr(user, 'role', None) == UserRole.ADMIN)


def _extract_extra_cost_entries(post_data):
    """Extract extra costs from submitted form data and return (entries, total)."""
    entries = []
    total = Decimal('0.00')

    for key in sorted(post_data.keys()):
        if not key.startswith('extra_cost_description_'):
            continue

        index = key.replace('extra_cost_description_', '')
        amount_key = f'extra_cost_amount_{index}'

        description = (post_data.get(key) or '').strip()
        amount_str = (post_data.get(amount_key) or '').strip()

        if not description or not amount_str:
            continue

        try:
            amount = Decimal(amount_str)
        except (InvalidOperation, TypeError):
            continue

        if amount <= 0:
            continue

        entries.append((description, amount))
        total += amount

    return entries, total


def _sync_vehicle_extra_costs(vehicle, entries, user):
    """Sync a vehicle's extra-cost rows to match submitted entries."""
    existing_costs = list(vehicle.extra_costs.order_by('date_added'))

    # Update existing rows in order or create new ones.
    for index, (description, amount) in enumerate(entries):
        if index < len(existing_costs):
            cost = existing_costs[index]
            cost.description = description
            cost.amount = amount
            cost.added_by = user
            cost.save(update_fields=['description', 'amount', 'added_by'])
        else:
            vehicle.extra_costs.create(
                description=description,
                amount=amount,
                added_by=user,
            )

    # Remove any leftover rows not present in the submitted form.
    for cost in existing_costs[len(entries):]:
        cost.delete()


def vehicle_list_view(request):
    """List all vehicles with search and filter - Public and authenticated users"""
    can_view_prices = _can_view_vehicle_prices(request.user)
    show_public_prices = not can_view_prices
    vehicles = Vehicle.objects.all().prefetch_related('photos')
    
    # For authenticated users with permissions, include more details
    if request.user.is_authenticated:
        vehicles = vehicles.select_related('added_by')
    
    # For public users, only show available vehicles
    if not request.user.is_authenticated:
        vehicles = vehicles.filter(status=VehicleStatus.AVAILABLE)
    
    # Search and filter
    form = VehicleSearchForm(request.GET)
    
    if form.is_valid():
        search = form.cleaned_data.get('search')
        status = form.cleaned_data.get('status')
        make = form.cleaned_data.get('make')
        year_from = form.cleaned_data.get('year_from')
        year_to = form.cleaned_data.get('year_to')
        price_from = form.cleaned_data.get('price_from')
        price_to = form.cleaned_data.get('price_to')
        fuel_type = form.cleaned_data.get('fuel_type')
        transmission = form.cleaned_data.get('transmission')
        body_type = form.cleaned_data.get('body_type')
        location = form.cleaned_data.get('location')
        
        if search:
            vehicles = vehicles.filter(
                Q(make__icontains=search) |
                Q(model__icontains=search) |
                Q(vin__icontains=search) |
                Q(registration_number__icontains=search) |
                Q(color__icontains=search)
            )
        
        if status:
            vehicles = vehicles.filter(status=status)
        
        if make:
            vehicles = vehicles.filter(make__icontains=make)
        
        if year_from:
            vehicles = vehicles.filter(year__gte=year_from)
        
        if year_to:
            vehicles = vehicles.filter(year__lte=year_to)
        
        if can_view_prices and price_from:
            vehicles = vehicles.filter(selling_price__gte=price_from)
        
        if can_view_prices and price_to:
            vehicles = vehicles.filter(selling_price__lte=price_to)

        if can_view_prices and request.GET.get('without_purchase_price') in ['1', 'true', 'on', 'yes']:
            vehicles = vehicles.filter(purchase_price=Decimal('0.00'))
        
        if fuel_type:
            vehicles = vehicles.filter(fuel_type=fuel_type)
        
        if transmission:
            vehicles = vehicles.filter(transmission=transmission)
        
        if body_type:
            vehicles = vehicles.filter(body_type=body_type)

        if location:
            vehicles = vehicles.filter(location=location)
    
    # Statistics
    total_vehicles = vehicles.count()
    available_count = vehicles.filter(status=VehicleStatus.AVAILABLE).count()
    sold_count = vehicles.filter(status=VehicleStatus.SOLD).count()
    reserved_count = vehicles.filter(status=VehicleStatus.RESERVED).count()
    
    # Total value
    total_inventory_value = Decimal('0.00')
    if can_view_prices:
        total_inventory_value = vehicles.filter(
            status=VehicleStatus.AVAILABLE
        ).aggregate(total=Sum('selling_price'))['total'] or Decimal('0.00')
    
    # Pagination
    paginator = Paginator(vehicles, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'can_view_prices': can_view_prices,
        'show_public_prices': show_public_prices,
        'total_vehicles': total_vehicles,
        'available_count': available_count,
        'sold_count': sold_count,
        'reserved_count': reserved_count,
        'total_inventory_value': total_inventory_value,
    }
    return render(request, 'vehicles/vehicle_list.html', context)


def vehicle_detail_view(request, pk):
    """
    View vehicle details - Public and authenticated users
    - Public users can only see available vehicles
    - Authenticated users can see all vehicles based on permissions
    """
    can_view_prices = _can_view_vehicle_prices(request.user)
    show_public_prices = not can_view_prices

    # Build base queryset
    queryset = Vehicle.objects.select_related('added_by').prefetch_related('photos', 'history')
    
    # Filter based on authentication
    if not request.user.is_authenticated:
        # Public users only see available vehicles
        vehicle = get_object_or_404(
            queryset,
            pk=pk,
            is_active=True,
            status=VehicleStatus.AVAILABLE
        )
    else:
        # Authenticated users see based on permissions
        vehicle = get_object_or_404(queryset, pk=pk)
    
    # Get history (only for authenticated users)
    history = []
    if request.user.is_authenticated:
        history = vehicle.history.select_related('changed_by').all()[:10]
        
        # Log view action
        try:
            AuditLog.log_read(
                user=request.user,
                obj=vehicle,
                ip_address=request.META.get('REMOTE_ADDR')
            )
        except Exception as e:
            # Silently fail if audit logging fails
            pass

    extra_cost_total = vehicle.extra_costs.aggregate(total=Sum('amount'))['total'] or 0
    extra_costs = vehicle.extra_costs.all().order_by('date_added')
    location_history = vehicle.location_history.all()[:10]
    # Include insurance buying price and tracker-related expenses in totals
    insurance_total = vehicle.insurance_policies.aggregate(total=Sum('buying_price'))['total'] or Decimal('0.00')
    tracker_total = vehicle.expenses.filter(
        Q(category__name__icontains='track') | Q(category__code__icontains='TRACKER')
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_additional_cost = (
        vehicle.duty_cost +
        vehicle.clearance_cost +
        vehicle.commission_cost +
        extra_cost_total +
        insurance_total +
        tracker_total
    )
    total_cost = vehicle.purchase_price + total_additional_cost

    can_view_vin = False
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        can_view_vin = True
    elif request.user.is_authenticated:
        client_profile = getattr(request.user, 'client_profile', None)
        if client_profile:
            can_view_vin = ClientVehicle.objects.filter(
                client=client_profile,
                vehicle=vehicle,
            ).exists()
    
    latest_sale = vehicle.client_purchases.select_related('client').order_by('-purchase_date', '-created_at').first()

    if vehicle.status == VehicleStatus.SOLD and latest_sale:
        display_price = latest_sale.final_selling_price
    else:
        display_price = vehicle.website_display_price

    repossession_history = []
    repossession_cost_total = Decimal('0.00')
    repossession_outstanding_total = Decimal('0.00')
    if request.user.is_authenticated:
        repossession_history = list(
            vehicle.repossessions.select_related('client', 'created_by')
            .prefetch_related('expenses', 'additional_cost_items')
            .order_by('-initiated_date')
        )
        for repo in repossession_history:
            # get_total_additional_costs = total_cost + expense_total
            # additional_cost_items are sub-items of additional_costs (already in total_cost)
            repossession_cost_total += repo.get_total_additional_costs()
            repossession_outstanding_total += repo.outstanding_amount

    if repossession_history:
        total_additional_cost += repossession_cost_total
        total_cost = vehicle.purchase_price + total_additional_cost

    vehicle_profit = display_price - total_cost

    active_reservation = None
    if request.user.is_authenticated:
        active_reservation = vehicle.reservations.filter(
            status__in=('active', 'expired')
        ).select_related('client', 'proforma').order_by('-reserved_at').first()

    context = {
        'vehicle': vehicle,
        'history': history,
        'active_reservation': active_reservation,
        'extra_costs': extra_costs,
        'location_history': location_history,
        'extra_cost_total': extra_cost_total,
        'total_additional_cost': total_additional_cost,
        'total_cost': total_cost,
        'can_view_vin': can_view_vin,
        'can_view_prices': can_view_prices,
        'show_public_prices': show_public_prices,
        'display_price': display_price,
        'latest_sale': latest_sale,
        'vehicle_profit': vehicle_profit,
        'repossession_history': repossession_history,
        'repossession_cost_total': repossession_cost_total,
        'repossession_total_with_outstanding': repossession_outstanding_total + repossession_cost_total,
    }
    return render(request, 'vehicles/vehicle_detail.html', context)


@login_required
def vehicle_detail_pdf(request, pk):
    """Printable spec-sheet PDF for a single vehicle."""
    from utils.report_kit import build_pdf_response, fmt_money, BORDER_GREY, LIGHT_GREY

    can_view_prices = _can_view_vehicle_prices(request.user)
    vehicle = get_object_or_404(
        Vehicle.objects.select_related('added_by'), pk=pk
    )

    def body(elements, styles):
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

        compact = ParagraphStyle('VehicleSpecCompact', parent=styles['Normal'], fontSize=8, leading=10)
        heading = styles['ReportSectionHeading']
        heading.spaceBefore = 6
        heading.spaceAfter = 3

        def field_grid(pairs, col_widths):
            rows, row = [], []
            for label, value in pairs:
                row.append(Paragraph(f'<b>{label}:</b> {value}', compact))
                if len(row) == len(col_widths):
                    rows.append(row)
                    row = []
            if row:
                row += [''] * (len(col_widths) - len(row))
                rows.append(row)
            table = Table(rows, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.4, BORDER_GREY),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, LIGHT_GREY]),
            ]))
            return table

        elements.append(Paragraph('IDENTIFICATION', heading))
        elements.append(field_grid([
            ('Reg No', vehicle.registration_number or '—'),
            ('Chassis No (VIN)', vehicle.vin),
            ('Make / Model', f'{vehicle.make} {vehicle.model}'),
            ('Year', vehicle.year),
            ('Status', vehicle.get_status_display()),
            ('Location', vehicle.get_location_display() if vehicle.location else '—'),
        ], col_widths=[3.25 * inch, 3.25 * inch]))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph('SPECIFICATIONS', heading))
        elements.append(field_grid([
            ('Mileage', f'{vehicle.mileage:,} KM' if vehicle.mileage is not None else '—'),
            ('Fuel Type', vehicle.get_fuel_type_display()),
            ('Transmission', vehicle.get_transmission_display()),
            ('Body Type', vehicle.get_body_type_display() if vehicle.body_type else '—'),
            ('Color', vehicle.color or '—'),
            ('Seats', vehicle.seats or '—'),
            ('Engine Size', vehicle.engine_size or '—'),
            ('Condition', vehicle.get_condition_display() if vehicle.condition else '—'),
        ], col_widths=[3.25 * inch, 3.25 * inch]))
        elements.append(Spacer(1, 6))

        if can_view_prices:
            elements.append(Paragraph('PRICING', heading))
            elements.append(field_grid([
                ('Purchase Price', fmt_money(vehicle.purchase_price)),
                ('Selling Price', fmt_money(vehicle.selling_price)),
                ('Website Price', fmt_money(vehicle.website_price) if vehicle.website_price else '—'),
                ('Deposit Required', fmt_money(vehicle.deposit_required)),
            ], col_widths=[3.25 * inch, 3.25 * inch]))
        else:
            elements.append(Paragraph('PRICING', heading))
            elements.append(field_grid([
                ('Selling Price', fmt_money(vehicle.website_display_price)),
            ], col_widths=[3.25 * inch, 3.25 * inch]))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph('www.hozacars.com', styles['ReportCompanyMeta']))

    try:
        AuditLog.log_read(user=request.user, obj=vehicle, ip_address=request.META.get('REMOTE_ADDR'))
    except Exception:
        pass

    return build_pdf_response(
        f'vehicle-{vehicle.pk}-spec-sheet.pdf', 'Vehicle Spec Sheet',
        subtitle=vehicle.full_name,
        build_body=body,
    )


@login_required
@module_permission_required('vehicles', AccessLevel.READ_WRITE)
def vehicle_create_view(request):
    """Create new vehicle"""
    can_view_prices = _can_view_vehicle_prices(request.user)
    if request.method == 'POST':
        print("\n" + "="*50)
        print("POST REQUEST RECEIVED")
        print("="*50)
        print("POST Data:", request.POST)
        print("FILES:", request.FILES)
        print("-"*50)
        
        form = VehicleForm(request.POST, request.FILES, can_view_prices=can_view_prices)
        print("Form created, checking validity...")
        
        if form.is_valid():
            print("✓ Form is VALID!")
            extra_cost_entries, extra_cost_total = _extract_extra_cost_entries(request.POST)

            vehicle = form.save(commit=False)
            vehicle.duty_cost = vehicle.duty_cost or Decimal('0.00')
            vehicle.clearance_cost = vehicle.clearance_cost or Decimal('0.00')
            # Commission is no longer entered during vehicle creation; assignment-level commission is handled in client assignment.
            vehicle.commission_cost = vehicle.commission_cost or Decimal('0.00')
            if can_view_prices:
                vehicle.selling_price = (
                    vehicle.purchase_price +
                    vehicle.duty_cost +
                    vehicle.clearance_cost +
                    extra_cost_total
                )
            else:
                vehicle.selling_price = Decimal('0.00')
                vehicle.deposit_required = Decimal('0.00')
            vehicle.added_by = request.user
            vehicle.save()

            # Handle extra costs
            _sync_vehicle_extra_costs(vehicle, extra_cost_entries, request.user)
            for description, amount in extra_cost_entries:
                print(f"✓ Created extra cost: {description} - {amount}")

            # Link clearance cost to a clearing agent ledger record
            clearing_agent_id = request.POST.get('clearing_agent_id')
            if clearing_agent_id and vehicle.clearance_cost:
                try:
                    clearing_agent = ClearingAgent.objects.get(pk=clearing_agent_id)
                    ClearanceRecord.objects.update_or_create(
                        vehicle=vehicle,
                        agent=clearing_agent,
                        defaults={'amount': vehicle.clearance_cost, 'date': vehicle.date_added.date()},
                    )
                except ClearingAgent.DoesNotExist:
                    pass

            # Link purchase price (USD) to a Japan supplier ledger record
            japan_supplier_id = request.POST.get('japan_supplier_id')
            japan_supplier_price_usd_str = request.POST.get('japan_supplier_price_usd', '').strip()
            if japan_supplier_id and japan_supplier_price_usd_str:
                try:
                    japan_supplier_price_usd = Decimal(japan_supplier_price_usd_str)
                    japan_supplier = JapanSupplier.objects.get(pk=japan_supplier_id)
                    JapanSupplierRecord.objects.update_or_create(
                        vehicle=vehicle,
                        defaults={
                            'supplier': japan_supplier,
                            'purchase_price': japan_supplier_price_usd,
                            'date': vehicle.date_added.date(),
                        },
                    )
                except (JapanSupplier.DoesNotExist, Exception):
                    pass

            # Log creation
            AuditLog.log_create(
                user=request.user,
                obj=vehicle,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f'Vehicle {vehicle.full_name} created successfully!')
            print(f"✓ Vehicle saved: {vehicle.pk} - {vehicle.full_name}")
            print("="*50 + "\n")
            return redirect('vehicles:detail', pk=vehicle.pk)
        else:
            # Debug: Print form errors to console
            print("✗ Form is INVALID!")
            print("\nForm Errors:")
            for field, errors in form.errors.items():
                print(f"  - {field}: {errors}")
            
            print("\nCleaned Data (partial):")
            for field, value in form.cleaned_data.items():
                print(f"  - {field}: {value}")
            
            print("="*50 + "\n")
            messages.error(request, 'Please correct the errors below.')
    else:
        form = VehicleForm(can_view_prices=can_view_prices)
    
    extra_cost_entries = []
    if request.method == 'POST':
        parsed_entries, _ = _extract_extra_cost_entries(request.POST)
        extra_cost_entries = [
            {'description': description, 'amount': amount}
            for description, amount in parsed_entries
        ]

    _post_supplier_id = request.POST.get('japan_supplier_id') if request.method == 'POST' else None
    context = {
        'form': form,
        'title': 'Add New Vehicle',
        'can_view_prices': can_view_prices,
        'extra_cost_entries': extra_cost_entries,
        'clearing_agents': ClearingAgent.objects.filter(is_active=True).order_by('name'),
        'existing_clearing_agent_id': None,
        'japan_suppliers': JapanSupplier.objects.filter(is_active=True).order_by('name'),
        'existing_japan_supplier_id': int(_post_supplier_id) if _post_supplier_id else None,
        'existing_japan_supplier_price_usd': request.POST.get('japan_supplier_price_usd', '') if request.method == 'POST' else '',
    }
    return render(request, 'vehicles/vehicle_form.html', context)


@login_required
@module_permission_required('vehicles', AccessLevel.READ_WRITE)
def vehicle_update_view(request, pk):
    """Update vehicle information"""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    can_view_prices = _can_view_vehicle_prices(request.user)
    
    # Store old values for audit
    old_values = {
        'make': vehicle.make,
        'model': vehicle.model,
        'status': vehicle.status,
        'selling_price': str(vehicle.selling_price),
    }
    
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=vehicle, can_view_prices=can_view_prices)
        if form.is_valid():
            extra_cost_entries, extra_cost_total = _extract_extra_cost_entries(request.POST)

            vehicle = form.save(commit=False)
            vehicle.duty_cost = vehicle.duty_cost or Decimal('0.00')
            vehicle.clearance_cost = vehicle.clearance_cost or Decimal('0.00')
            vehicle.commission_cost = vehicle.commission_cost or Decimal('0.00')
            if can_view_prices:
                vehicle.selling_price = (
                    vehicle.purchase_price +
                    vehicle.duty_cost +
                    vehicle.clearance_cost +
                    extra_cost_total
                )
            vehicle.save()

            # Handle extra costs
            _sync_vehicle_extra_costs(vehicle, extra_cost_entries, request.user)

            # Link clearance cost to a clearing agent ledger record
            clearing_agent_id = request.POST.get('clearing_agent_id')
            if clearing_agent_id and vehicle.clearance_cost:
                try:
                    clearing_agent = ClearingAgent.objects.get(pk=clearing_agent_id)
                    ClearanceRecord.objects.update_or_create(
                        vehicle=vehicle,
                        agent=clearing_agent,
                        defaults={
                            'amount': vehicle.clearance_cost,
                            'date': vehicle.purchase_date or timezone.now().date(),
                        },
                    )
                except ClearingAgent.DoesNotExist:
                    pass

            # Link purchase price (USD) to a Japan supplier ledger record
            japan_supplier_id = request.POST.get('japan_supplier_id')
            japan_supplier_price_usd_str = request.POST.get('japan_supplier_price_usd', '').strip()
            if japan_supplier_id and japan_supplier_price_usd_str:
                try:
                    japan_supplier_price_usd = Decimal(japan_supplier_price_usd_str)
                    japan_supplier = JapanSupplier.objects.get(pk=japan_supplier_id)
                    JapanSupplierRecord.objects.update_or_create(
                        vehicle=vehicle,
                        defaults={
                            'supplier': japan_supplier,
                            'purchase_price': japan_supplier_price_usd,
                            'date': vehicle.purchase_date or timezone.now().date(),
                        },
                    )
                except (JapanSupplier.DoesNotExist, Exception):
                    pass

            # Detect changes
            changes = {}
            if old_values['status'] != vehicle.status:
                changes['status'] = {'old': old_values['status'], 'new': vehicle.status}
            if old_values['selling_price'] != str(vehicle.selling_price):
                changes['selling_price'] = {'old': old_values['selling_price'], 'new': str(vehicle.selling_price)}
            
            # Log update
            AuditLog.log_update(
                user=request.user,
                obj=vehicle,
                changes=changes,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f'Vehicle {vehicle.full_name} updated successfully!')
            return redirect('vehicles:detail', pk=vehicle.pk)
    else:
        form = VehicleForm(instance=vehicle, can_view_prices=can_view_prices)

    if request.method == 'POST':
        parsed_entries, _ = _extract_extra_cost_entries(request.POST)
        extra_cost_entries = [
            {'description': description, 'amount': amount}
            for description, amount in parsed_entries
        ]
    else:
        extra_cost_entries = list(vehicle.extra_costs.values('description', 'amount'))
    
    existing_clearance = vehicle.clearance_records.select_related('agent').first()
    try:
        existing_supplier_record = vehicle.japan_supplier_record
    except Exception:
        existing_supplier_record = None

    if request.method == 'POST':
        _post_supplier_id = request.POST.get('japan_supplier_id')
        _existing_japan_supplier_id = int(_post_supplier_id) if _post_supplier_id else None
        _existing_japan_supplier_price_usd = request.POST.get('japan_supplier_price_usd', '')
    else:
        _existing_japan_supplier_id = existing_supplier_record.supplier_id if existing_supplier_record else None
        # Convert Decimal to plain string so Django template won't add thousand separators
        _price = existing_supplier_record.purchase_price if existing_supplier_record else None
        _existing_japan_supplier_price_usd = str(_price) if _price is not None else ''

    context = {
        'form': form,
        'vehicle': vehicle,
        'can_view_prices': can_view_prices,
        'title': f'Edit Vehicle: {vehicle.full_name}',
        'extra_cost_entries': extra_cost_entries,
        'clearing_agents': ClearingAgent.objects.filter(is_active=True).order_by('name'),
        'existing_clearing_agent_id': existing_clearance.agent_id if existing_clearance else None,
        'japan_suppliers': JapanSupplier.objects.filter(is_active=True).order_by('name'),
        'existing_japan_supplier_id': _existing_japan_supplier_id,
        'existing_japan_supplier_price_usd': _existing_japan_supplier_price_usd,
    }
    return render(request, 'vehicles/vehicle_form.html', context)


@login_required
@module_permission_required('vehicles', AccessLevel.READ_WRITE)
def vehicle_move_view(request, pk):
    """Move a vehicle to a new location using a dedicated movement form."""
    vehicle = get_object_or_404(Vehicle, pk=pk)

    old_values = {
        'location': vehicle.location,
        'location_moved_date': vehicle.location_moved_date.isoformat() if vehicle.location_moved_date else '',
        'location_driver_name': vehicle.location_driver_name,
        'location_driver_phone': vehicle.location_driver_phone,
        'location_driver_id_number': vehicle.location_driver_id_number,
    }

    if request.method == 'POST':
        form = VehicleMoveForm(request.POST, vehicle=vehicle)
        if form.is_valid():
            vehicle.location = form.cleaned_data['location']
            vehicle.location_moved_date = form.cleaned_data['location_moved_date']
            vehicle.location_driver_name = form.cleaned_data['location_driver_name']
            vehicle.location_driver_phone = form.cleaned_data['location_driver_phone']
            vehicle.location_driver_id_number = form.cleaned_data['location_driver_id_number']
            vehicle._location_move_notes = form.cleaned_data['notes']
            vehicle.save()

            changes = {
                'location': {'old': old_values['location'], 'new': vehicle.location},
                'location_moved_date': {'old': old_values['location_moved_date'], 'new': vehicle.location_moved_date.isoformat() if vehicle.location_moved_date else ''},
                'location_driver_name': {'old': old_values['location_driver_name'], 'new': vehicle.location_driver_name},
                'location_driver_phone': {'old': old_values['location_driver_phone'], 'new': vehicle.location_driver_phone},
                'location_driver_id_number': {'old': old_values['location_driver_id_number'], 'new': vehicle.location_driver_id_number},
                'location_move_notes': {'old': '', 'new': form.cleaned_data['notes']},
            }

            AuditLog.log_update(
                user=request.user,
                obj=vehicle,
                changes=changes,
                description='Vehicle moved using dedicated move form',
                ip_address=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, f'Location updated for {vehicle.full_name}.')
            return redirect('vehicles:detail', pk=vehicle.pk)
    else:
        form = VehicleMoveForm(vehicle=vehicle)

    context = {
        'form': form,
        'vehicle': vehicle,
    }
    return render(request, 'vehicles/move_vehicle_form.html', context)


@login_required
@module_permission_required('vehicles', AccessLevel.FULL_ACCESS)
def vehicle_delete_view(request, pk):
    """Delete vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    # Prevent deletion if vehicle is sold or has clients
    if vehicle.status == VehicleStatus.SOLD:
        messages.error(request, 'Cannot delete a sold vehicle.')
        return redirect('vehicles:detail', pk=vehicle.pk)
    
    if request.method == 'POST':
        vehicle_name = vehicle.full_name

        try:
            vehicle.delete()
        except ProtectedError as e:
            related = e.protected_objects
            labels = ', '.join(str(obj) for obj in related)
            messages.error(
                request,
                f'Cannot delete {vehicle_name} because it is referenced by: {labels}. '
                'Remove or reassign those records first.'
            )
            return redirect('vehicles:detail', pk=vehicle.pk)

        AuditLog.log_delete(
            user=request.user,
            obj=vehicle,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        messages.success(request, f'Vehicle {vehicle_name} deleted successfully!')
        return redirect('vehicles:list')
    
    context = {
        'vehicle': vehicle,
        'can_view_prices': _can_view_vehicle_prices(request.user),
    }
    return render(request, 'vehicles/vehicle_confirm_delete.html', context)


@login_required
@module_permission_required('vehicles', AccessLevel.READ_WRITE)
def vehicle_status_change_view(request, pk):
    """Change vehicle status"""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    if request.method == 'POST':
        form = VehicleStatusChangeForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data['new_status']
            notes = form.cleaned_data['notes']
            
            vehicle.change_status(new_status, request.user, notes)
            
            messages.success(request, f'Vehicle status changed to {vehicle.get_status_display()}')
            return redirect('vehicles:detail', pk=vehicle.pk)
    else:
        form = VehicleStatusChangeForm(initial={'new_status': vehicle.status})
    
    context = {
        'form': form,
        'vehicle': vehicle,
        'can_view_prices': _can_view_vehicle_prices(request.user),
    }
    return render(request, 'vehicles/status_change_form.html', context)


@login_required
@module_permission_required('vehicles', AccessLevel.READ_WRITE)
def vehicle_photo_upload_view(request, pk):
    """Upload photos for a vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    if request.method == 'POST':
        form = VehiclePhotoForm(request.POST, request.FILES)
        if form.is_valid():
            from .photo_utils import compress_uploaded_photo
            from apps.audit.utils import log_audit

            try:
                files = request.FILES.getlist('image')
                caption = form.cleaned_data.get('caption') or ''
                is_primary = form.cleaned_data.get('is_primary') or False
                is_public = form.cleaned_data.get('is_public')
                if is_public is None:
                    is_public = True
                base_order = form.cleaned_data.get('order') or 0

                created = 0
                for index, uploaded in enumerate(files):
                    VehiclePhoto.objects.create(
                        vehicle=vehicle,
                        image=compress_uploaded_photo(uploaded),
                        caption=caption,
                        # Only the first file of a batch can be primary
                        is_primary=is_primary and index == 0,
                        is_public=is_public,
                        order=base_order + index,
                        uploaded_by=request.user,
                    )
                    created += 1

                log_audit(
                    request.user, 'create', 'VehiclePhoto',
                    f'Uploaded {created} photo(s) for {vehicle.full_name} '
                    f'({"public" if is_public else "internal"})',
                    object_id=str(vehicle.pk),
                )
                messages.success(
                    request,
                    f'{created} photo(s) uploaded successfully! '
                    f'{vehicle.photos.count()} photo(s) total.'
                )
                return redirect('vehicles:detail', pk=vehicle.pk)
            except Exception as e:
                messages.error(request, f'Error saving photo: {str(e)}')
        else:
            # Add form errors to messages for debugging
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f'{error}')
                    else:
                        messages.error(request, f'{field}: {error}')
    else:
        form = VehiclePhotoForm()
    
    context = {
        'form': form,
        'vehicle': vehicle,
    }
    return render(request, 'vehicles/photo_upload.html', context)


@login_required
@module_permission_required('vehicles', AccessLevel.FULL_ACCESS)
def vehicle_photo_delete_view(request, pk, photo_pk):
    """Delete a vehicle photo"""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    photo = get_object_or_404(VehiclePhoto, pk=photo_pk, vehicle=vehicle)
    
    if request.method == 'POST':
        photo.delete()
        messages.success(request, 'Photo deleted successfully!')
        return redirect('vehicles:detail', pk=vehicle.pk)
    
    context = {
        'vehicle': vehicle,
        'photo': photo,
    }
    return render(request, 'vehicles/photo_confirm_delete.html', context)


@login_required
@module_permission_required('vehicles', AccessLevel.READ_WRITE)
def vehicle_photo_update_view(request, pk, photo_pk):
    """
    Manage a single photo: set as main/cover, toggle public/internal,
    update caption or display order.
    """
    from apps.audit.utils import log_audit

    if request.method != 'POST':
        return redirect('vehicles:detail', pk=pk)

    vehicle = get_object_or_404(Vehicle, pk=pk)
    photo = get_object_or_404(VehiclePhoto, pk=photo_pk, vehicle=vehicle)
    action = request.POST.get('action', '')

    if action == 'set_primary':
        photo.is_primary = True
        photo.save()
        messages.success(request, 'Cover photo updated.')
    elif action == 'toggle_public':
        photo.is_public = not photo.is_public
        if not photo.is_public and photo.is_primary:
            # An internal photo cannot be the website cover
            replacement = vehicle.photos.filter(
                is_public=True).exclude(pk=photo.pk).first()
            if replacement:
                replacement.is_primary = True
                replacement.save()
            photo.is_primary = False
        photo.save()
        messages.success(
            request,
            f'Photo marked as {"Public" if photo.is_public else "Internal"}.'
        )
    elif action == 'update_details':
        photo.caption = request.POST.get('caption', photo.caption or '').strip()
        try:
            photo.order = int(request.POST.get('order', photo.order))
        except (TypeError, ValueError):
            pass
        photo.save()
        messages.success(request, 'Photo details updated.')
    elif action == 'replace':
        from .photo_utils import compress_uploaded_photo
        uploaded = request.FILES.get('image')
        if uploaded:
            import os
            old_path = photo.image.path if photo.image else None
            photo.image = compress_uploaded_photo(uploaded)
            photo.save()
            if old_path and os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass
            messages.success(request, 'Photo replaced.')
        else:
            messages.error(request, 'Choose a replacement image.')
    else:
        messages.error(request, 'Unknown photo action.')
        return redirect('vehicles:detail', pk=pk)

    log_audit(
        request.user, 'update', 'VehiclePhoto',
        f'Photo {photo.pk} on {vehicle.full_name}: {action}',
        object_id=str(vehicle.pk),
    )
    return redirect('vehicles:detail', pk=pk)


@login_required
@module_permission_required('vehicles', AccessLevel.READ_WRITE)
def vehicle_toggle_photo_downloads_view(request, pk):
    """Enable/disable public photo downloads for a vehicle."""
    from apps.audit.utils import log_audit

    if request.method != 'POST':
        return redirect('vehicles:detail', pk=pk)

    vehicle = get_object_or_404(Vehicle, pk=pk)
    vehicle.allow_photo_downloads = not vehicle.allow_photo_downloads
    vehicle.save(update_fields=['allow_photo_downloads', 'last_updated'])

    state = 'enabled' if vehicle.allow_photo_downloads else 'disabled'
    log_audit(
        request.user, 'update', 'Vehicle',
        f'Public photo downloads {state} for {vehicle.full_name}',
        object_id=str(vehicle.pk),
    )
    messages.success(request, f'Public photo downloads {state} for this vehicle.')
    return redirect('vehicles:detail', pk=pk)


@login_required
@module_permission_required('vehicles', AccessLevel.READ_WRITE)
def vehicle_toggle_featured_view(request, pk):
    """Toggle vehicle featured status"""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    vehicle.is_featured = not vehicle.is_featured
    vehicle.save()
    
    status = 'featured' if vehicle.is_featured else 'unfeatured'
    messages.success(request, f'Vehicle marked as {status}.')
    
    return redirect('vehicles:detail', pk=vehicle.pk)


@login_required
@module_permission_required('vehicles', AccessLevel.FULL_ACCESS)
def bulk_vehicle_action_view(request):
    """Perform bulk actions on vehicles"""
    if request.method == 'POST':
        form = BulkVehicleActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            vehicle_ids = form.cleaned_data['vehicle_ids'].split(',')
            new_status = form.cleaned_data.get('new_status')
            
            vehicles = Vehicle.objects.filter(pk__in=vehicle_ids)
            count = vehicles.count()
            
            if action == 'activate':
                vehicles.update(is_active=True)
                messages.success(request, f'{count} vehicles activated.')
            
            elif action == 'deactivate':
                vehicles.update(is_active=False)
                messages.success(request, f'{count} vehicles deactivated.')
            
            elif action == 'feature':
                vehicles.update(is_featured=True)
                messages.success(request, f'{count} vehicles marked as featured.')
            
            elif action == 'unfeature':
                vehicles.update(is_featured=False)
                messages.success(request, f'{count} vehicles unmarked as featured.')
            
            elif action == 'change_status' and new_status:
                for vehicle in vehicles:
                    vehicle.change_status(new_status, request.user, 'Bulk status change')
                messages.success(request, f'{count} vehicles status changed to {new_status}.')
            
            return redirect('vehicles:list')
    
    return redirect('vehicles:list')


@login_required
@module_permission_required('vehicles', AccessLevel.READ_ONLY)
def vehicle_export_view(request):
    """Export vehicles to CSV"""
    if not _can_view_vehicle_prices(request.user):
        messages.error(request, 'Only administrators can export vehicle pricing data.')
        return redirect('vehicles:list')

    vehicles = Vehicle.objects.all().select_related('added_by')
    
    # Apply filters from GET parameters
    form = VehicleSearchForm(request.GET)
    if form.is_valid():
        # Apply same filters as list view
        search = form.cleaned_data.get('search')
        status = form.cleaned_data.get('status')
        
        if search:
            vehicles = vehicles.filter(
                Q(make__icontains=search) | Q(model__icontains=search)
            )
        if status:
            vehicles = vehicles.filter(status=status)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="vehicles_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Make', 'Model', 'Year', 'VIN', 'Registration', 'Color',
        'Mileage', 'Fuel Type', 'Transmission', 'Status',
        'Purchase Price', 'Selling Price', 'Profit', 'Date Added'
    ])
    
    for vehicle in vehicles:
        writer.writerow([
            vehicle.make,
            vehicle.model,
            vehicle.year,
            vehicle.vin,
            vehicle.registration_number or '',
            vehicle.color,
            vehicle.mileage,
            vehicle.get_fuel_type_display(),
            vehicle.get_transmission_display(),
            vehicle.get_status_display(),
            vehicle.purchase_price,
            vehicle.selling_price,
            vehicle.profit,
            vehicle.date_added.strftime('%Y-%m-%d'),
        ])
    
    # Log export
    AuditLog.log_export(
        user=request.user,
        model_name='Vehicle',
        description=f'Exported {vehicles.count()} vehicles',
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return response


@login_required
@module_permission_required('vehicles', AccessLevel.READ_ONLY)
def vehicle_stats_view(request):
    """Get vehicle statistics (AJAX)"""
    can_view_prices = _can_view_vehicle_prices(request.user)
    stats = {
        'total': Vehicle.objects.count(),
        'available': Vehicle.objects.filter(status=VehicleStatus.AVAILABLE).count(),
        'sold': Vehicle.objects.filter(status=VehicleStatus.SOLD).count(),
        'reserved': Vehicle.objects.filter(status=VehicleStatus.RESERVED).count(),
        'repossessed': Vehicle.objects.filter(status=VehicleStatus.REPOSSESSED).count(),
        'total_value': float(
            Vehicle.objects.filter(status=VehicleStatus.AVAILABLE).aggregate(
                total=Sum('selling_price')
            )['total'] or 0
        ) if can_view_prices else 0.0,
        'avg_price': float(
            Vehicle.objects.filter(status=VehicleStatus.AVAILABLE).aggregate(
                avg=Avg('selling_price')
            )['avg'] or 0
        ) if can_view_prices else 0.0,
        'by_make': list(
            Vehicle.objects.values('make').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
        ),
    }
    
    return JsonResponse(stats)


@login_required
@module_permission_required('vehicles')
def search_clients_api(request):
    """
    API endpoint for searching clients
    Used by vehicle sell feature for quick client lookup
    """
    search_term = request.GET.get('q', '').strip()
    
    if len(search_term) < 2:
        return JsonResponse({'results': []})
    
    # Search clients by name or ID number
    clients = Client.objects.filter(
        Q(first_name__icontains=search_term) |
        Q(last_name__icontains=search_term) |
        Q(id_number__icontains=search_term) |
        Q(phone_primary__icontains=search_term),
        status='active'
    ).select_related('user').values('id', 'first_name', 'last_name', 'id_number', 'phone_primary')[:20]
    
    results = [
        {
            'id': client['id'],
            'text': f"{client['first_name']} {client['last_name']} ({client['id_number']})",
            'full_name': f"{client['first_name']} {client['last_name']}",
            'id_number': client['id_number'],
            'phone': client['phone_primary'],
        }
        for client in clients
    ]
    
    return JsonResponse({'results': results})


@login_required
@module_permission_required('vehicles')
def sell_vehicle(request, pk):
    """
    Initiate selling a vehicle to a client
    Handles modal submission and redirects to assign_vehicle form
    """
    from django.urls import reverse
    
    vehicle = get_object_or_404(Vehicle, pk=pk, status=VehicleStatus.AVAILABLE)
    
    if request.method == 'POST':
        # Get selected client ID from POST data
        client_id = request.POST.get('client_id', '').strip()
        if client_id:
            try:
                # Verify client exists and is active
                client = Client.objects.get(pk=client_id, status='active')
                # Redirect to assign vehicle form with the client and vehicle pre-selected
                url = reverse('clients:assign_vehicle', kwargs={'client_pk': client_id})
                return redirect(f'{url}?vehicle_id={pk}')
            except Client.DoesNotExist:
                messages.error(request, 'Selected client not found or is inactive')
                return redirect('vehicles:detail', pk=pk)
        else:
            messages.error(request, 'Please select a client')
            return redirect('vehicles:detail', pk=pk)
    
    # GET requests should redirect back to vehicle detail
    return redirect('vehicles:detail', pk=pk)


@login_required
def vehicle_pricing_api(request, pk):
    """Lightweight pricing lookup used by the proforma form to auto-fill.

    Deliberately uses the raw website_price (not website_display_price) —
    a proforma should be pre-filled from the price quoted to the public,
    never silently fall back to the internal vehicle cost when no website
    price has been set.
    """
    vehicle = get_object_or_404(Vehicle, pk=pk)
    return JsonResponse({
        'selling_price': float(vehicle.website_price or 0),
        'deposit_required': float(vehicle.deposit_required or 0),
        'registration_number': vehicle.registration_number or '',
        'vin': vehicle.vin,
        'status': vehicle.status,
    })


@login_required
@role_required(UserRole.ADMIN)
def vehicle_purchase_price_assignment_view(request):
    """Admin-only module to assign/edit vehicle purchase price and recalculate selling price."""
    from django.urls import reverse

    selected_vehicle_id = (request.GET.get('vehicle') or '').strip()

    vehicles = Vehicle.objects.all().prefetch_related('photos', 'extra_costs').annotate(
        extra_cost_total=Coalesce(
            Sum('extra_costs__amount'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    ).order_by('-date_added')

    if selected_vehicle_id:
        vehicles = vehicles.filter(pk=selected_vehicle_id)

    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    without_purchase_price = request.GET.get('without_purchase_price', '').strip().lower() in ['1', 'true', 'on', 'yes']

    if search:
        vehicles = vehicles.filter(
            Q(make__icontains=search)
            | Q(model__icontains=search)
            | Q(vin__icontains=search)
            | Q(registration_number__icontains=search)
        )

    if status:
        vehicles = vehicles.filter(status=status)

    if without_purchase_price:
        vehicles = vehicles.filter(purchase_price=Decimal('0.00'))

    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle_id')
        purchase_price_raw = (request.POST.get('purchase_price') or '').strip()
        try:
            purchase_price = Decimal(purchase_price_raw)
            if purchase_price < 0:
                raise InvalidOperation
        except Exception:
            messages.error(request, 'Please enter a valid non-negative purchase price.')
            if selected_vehicle_id:
                return redirect(f"{reverse('vehicles:purchase_price_assignment')}?vehicle={selected_vehicle_id}")
            return redirect('vehicles:purchase_price_assignment')

        vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
        extra_total = vehicle.extra_costs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        vehicle.purchase_price = purchase_price.quantize(Decimal('0.01'))
        vehicle.selling_price = (
            vehicle.purchase_price
            + (vehicle.duty_cost or Decimal('0.00'))
            + (vehicle.clearance_cost or Decimal('0.00'))
            + extra_total
        ).quantize(Decimal('0.01'))

        usd_price_raw = (request.POST.get('purchase_price_usd') or '').strip()
        usd_rate_raw = (request.POST.get('purchase_usd_rate') or '').strip()
        try:
            vehicle.purchase_price_usd = Decimal(usd_price_raw).quantize(Decimal('0.01')) if usd_price_raw else None
        except Exception:
            vehicle.purchase_price_usd = None
        try:
            vehicle.purchase_usd_rate = Decimal(usd_rate_raw).quantize(Decimal('0.0001')) if usd_rate_raw else None
        except Exception:
            vehicle.purchase_usd_rate = None

        vehicle.save(update_fields=['purchase_price', 'selling_price', 'purchase_price_usd', 'purchase_usd_rate', 'last_updated'])

        messages.success(request, f'Updated purchase price for {vehicle.full_name}.')
        if selected_vehicle_id:
            return redirect(f"{reverse('vehicles:purchase_price_assignment')}?vehicle={selected_vehicle_id}")
        return redirect('vehicles:purchase_price_assignment')

    paginator = Paginator(vehicles, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'without_purchase_price': without_purchase_price,
        'selected_vehicle_id': selected_vehicle_id,
        'status_choices': VehicleStatus.CHOICES,
        'can_view_prices': True,
    }
    return render(request, 'vehicles/vehicle_purchase_price_assignment.html', context)

# ==================== TRACKER AGENT LEDGER VIEWS ====================

@login_required
@role_required('admin', 'manager', 'sales', 'accountant', 'auctioneer')
def tracker_agent_ledger_list(request):
    """List all tracker agents with totals and outstanding balances."""
    from django.db.models import Q, Sum, Value, DecimalField
    from django.db.models.functions import Coalesce
    from django.contrib import messages

    if request.method == 'POST':
        form = TrackerAgentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tracker agent added successfully.')
            return redirect('vehicles:tracker_agent_ledger_list')
    else:
        form = TrackerAgentForm()

    agents = TrackerAgent.objects.filter(is_active=True).prefetch_related('tracker_records').order_by('name')
    totals = TrackerRecord.objects.aggregate(
        grand_buying=Coalesce(Sum('buying_price'), Value(0, output_field=DecimalField())),
        grand_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
        grand_owed=Coalesce(
            Sum('buying_price', filter=Q(dealer_payment_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
    )
    context = {
        'agents': agents,
        'grand_buying': totals['grand_buying'],
        'grand_selling': totals['grand_selling'],
        'grand_owed': totals['grand_owed'],
        'form': form,
    }
    return render(request, 'vehicles/tracker_agent_ledger_list.html', context)


def _tracker_agent_statement(agent, date_from, date_to):
    """Shared by the on-screen detail view and its PDF export so they never disagree."""
    from utils.ledger import make_entry, build_statement

    records = agent.tracker_records.select_related('vehicle', 'client_vehicle__client').order_by('-created_at')
    payments = agent.payments.select_related('recorded_by').order_by('-payment_date')

    entries = [
        make_entry(
            (r.installation_date or r.created_at.date()),
            f'Tracker supplied: {r.tracker_name}',
            credit=r.buying_price,
            reference=r.serial_number or f'TRK-{r.pk}',
            related=str(r.vehicle),
            status=r.get_dealer_payment_status_display(),
            sort_key=r.created_at,
        )
        for r in records
    ] + [
        make_entry(
            p.payment_date,
            'Payment to agent',
            debit=p.amount,
            reference=p.reference_number or f'PAY-{p.pk}',
            method=p.get_payment_method_display(),
            created_by=p.recorded_by,
            status='Paid',
            notes=p.notes,
            sort_key=p.created_at,
        )
        for p in payments
    ]
    if date_from:
        entries = [e for e in entries if e['date'] >= date_from]
    if date_to:
        entries = [e for e in entries if e['date'] <= date_to]
    statement_rows, statement_summary = build_statement(entries, balance_from='credit')
    return records, payments, statement_rows, statement_summary


@login_required
def tracker_agent_ledger_detail(request, pk):
    """Show all tracker records for an agent and allow marking them paid."""
    from utils.ledger import parse_date_range

    date_from, date_to = parse_date_range(request)
    agent = get_object_or_404(TrackerAgent, pk=pk)
    records, payments, statement_rows, statement_summary = _tracker_agent_statement(agent, date_from, date_to)

    context = {
        'agent': agent,
        'records': records,
        'payments': payments,
        'statement_rows': statement_rows,
        'statement_summary': statement_summary,
        'debit_hint': 'payment made to agent',
        'credit_hint': 'tracker billed by agent',
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'vehicles/tracker_agent_ledger_detail.html', context)


@login_required
def tracker_agent_ledger_pdf(request, pk):
    """Printable PDF statement for a single tracker agent."""
    from utils.ledger import parse_date_range
    from utils.report_kit import ledger_statement_pdf_response

    date_from, date_to = parse_date_range(request)
    agent = get_object_or_404(TrackerAgent, pk=pk)
    _, _, statement_rows, statement_summary = _tracker_agent_statement(agent, date_from, date_to)

    subtitle = agent.name
    if date_from or date_to:
        subtitle += f" — {date_from or 'the beginning'} to {date_to or 'today'}"

    return ledger_statement_pdf_response(
        f'tracker-agent-{agent.pk}-statement.pdf', 'Tracker Agent Statement', subtitle,
        statement_rows, statement_summary,
        debit_hint='payment made to agent', credit_hint='tracker billed by agent',
    )


@login_required
def tracker_record_mark_paid(request, pk):
    """Mark a single tracker record as paid to the agent."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    record = get_object_or_404(TrackerRecord, pk=pk)
    record.dealer_payment_status = 'paid'
    record.save(update_fields=['dealer_payment_status'])
    return JsonResponse({'status': 'paid', 'record_id': pk})


@login_required
def tracker_agent_mark_all_paid(request, agent_pk):
    """Mark all unpaid tracker records for an agent as paid."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    agent = get_object_or_404(TrackerAgent, pk=agent_pk)
    updated = agent.tracker_records.filter(dealer_payment_status='unpaid').update(dealer_payment_status='paid')
    return JsonResponse({'status': 'ok', 'updated': updated})


# ==================== CLEARING AGENT LEDGER VIEWS ====================

@login_required
@role_required('admin', 'manager', 'sales', 'accountant', 'auctioneer')
def clearing_agent_ledger_list(request):
    """List all clearing agents with totals and outstanding balances."""
    from django.db.models import Q, Sum, Value, DecimalField
    from django.db.models.functions import Coalesce
    from django.contrib import messages

    if request.method == 'POST':
        form = ClearingAgentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Clearing agent added successfully.')
            return redirect('vehicles:clearing_agent_ledger_list')
    else:
        form = ClearingAgentForm()

    agents = ClearingAgent.objects.filter(is_active=True).prefetch_related('clearance_records').order_by('name')
    totals = ClearanceRecord.objects.aggregate(
        grand_billed=Coalesce(Sum('amount'), Value(0, output_field=DecimalField())),
        grand_owed=Coalesce(
            Sum('amount', filter=Q(payment_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
        grand_settled=Coalesce(
            Sum('amount', filter=Q(payment_status='paid')),
            Value(0, output_field=DecimalField()),
        ),
    )
    context = {
        'agents': agents,
        'grand_billed': totals['grand_billed'],
        'grand_owed': totals['grand_owed'],
        'grand_settled': totals['grand_settled'],
        'form': form,
    }
    return render(request, 'vehicles/clearing_agent_ledger_list.html', context)


def _clearing_agent_statement(agent, date_from, date_to):
    """Shared by the on-screen detail view and its PDF export so they never disagree."""
    from utils.ledger import make_entry, build_statement

    records = agent.clearance_records.select_related('vehicle').order_by('-date')
    payments = agent.payments.select_related('recorded_by').order_by('-payment_date')

    entries = [
        make_entry(
            r.date,
            'Clearance charges',
            credit=r.amount,
            reference=f'CLR-{r.pk}',
            related=str(r.vehicle),
            status=r.get_payment_status_display(),
            notes=r.notes,
            sort_key=r.created_at,
        )
        for r in records
    ] + [
        make_entry(
            p.payment_date,
            'Payment to agent',
            debit=p.amount,
            reference=p.reference_number or f'PAY-{p.pk}',
            method=p.get_payment_method_display(),
            created_by=p.recorded_by,
            status='Paid',
            notes=p.notes,
            sort_key=p.created_at,
        )
        for p in payments
    ]
    if date_from:
        entries = [e for e in entries if e['date'] >= date_from]
    if date_to:
        entries = [e for e in entries if e['date'] <= date_to]
    statement_rows, statement_summary = build_statement(entries, balance_from='credit')
    return records, payments, statement_rows, statement_summary


@login_required
def clearing_agent_ledger_detail(request, pk):
    """Show all clearance records for an agent and allow marking them paid."""
    from utils.ledger import parse_date_range

    date_from, date_to = parse_date_range(request)
    agent = get_object_or_404(ClearingAgent, pk=pk)
    records, payments, statement_rows, statement_summary = _clearing_agent_statement(agent, date_from, date_to)

    context = {
        'agent': agent,
        'records': records,
        'payments': payments,
        'statement_rows': statement_rows,
        'statement_summary': statement_summary,
        'debit_hint': 'payment made to agent',
        'credit_hint': 'clearance billed by agent',
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'vehicles/clearing_agent_ledger_detail.html', context)


@login_required
def clearing_agent_ledger_pdf(request, pk):
    """Printable PDF statement for a single clearing agent."""
    from utils.ledger import parse_date_range
    from utils.report_kit import ledger_statement_pdf_response

    date_from, date_to = parse_date_range(request)
    agent = get_object_or_404(ClearingAgent, pk=pk)
    _, _, statement_rows, statement_summary = _clearing_agent_statement(agent, date_from, date_to)

    subtitle = agent.name
    if date_from or date_to:
        subtitle += f" — {date_from or 'the beginning'} to {date_to or 'today'}"

    return ledger_statement_pdf_response(
        f'clearing-agent-{agent.pk}-statement.pdf', 'Clearing Agent Statement', subtitle,
        statement_rows, statement_summary,
        debit_hint='payment made to agent', credit_hint='clearance billed by agent',
    )


@login_required
def clearance_record_mark_paid(request, pk):
    """Mark a single clearance record as paid to the agent."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    record = get_object_or_404(ClearanceRecord, pk=pk)
    record.payment_status = 'paid'
    record.save(update_fields=['payment_status'])
    return JsonResponse({'status': 'paid', 'record_id': pk})


@login_required
def clearing_agent_mark_all_paid(request, agent_pk):
    """Mark all unpaid clearance records for an agent as paid."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    agent = get_object_or_404(ClearingAgent, pk=agent_pk)
    updated = agent.clearance_records.filter(payment_status='unpaid').update(payment_status='paid')
    return JsonResponse({'status': 'ok', 'updated': updated})


@login_required
def record_tracker_agent_payment(request, agent_pk):
    """Record a lump-sum payment to a tracker agent."""
    if request.method != 'POST':
        messages.error(request, 'Method not allowed.')
        return redirect('vehicles:tracker_agent_ledger_detail', pk=agent_pk)
    agent = get_object_or_404(TrackerAgent, pk=agent_pk)
    from .models import TrackerAgentPayment
    amount_str = request.POST.get('amount', '').strip()
    payment_method = request.POST.get('payment_method', 'bank_transfer')
    reference_number = request.POST.get('reference_number', '').strip()
    notes = request.POST.get('notes', '').strip()
    payment_date_str = request.POST.get('payment_date', '').strip()
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError
    except Exception:
        messages.error(request, 'Invalid payment amount.')
        return redirect('vehicles:tracker_agent_ledger_detail', pk=agent_pk)
    from datetime import date as date_type, datetime as datetime_type
    payment_date = date_type.today()
    if payment_date_str:
        try:
            payment_date = datetime_type.strptime(payment_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    with transaction.atomic():
        TrackerAgentPayment.objects.create(
            agent=agent,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
            payment_date=payment_date,
            recorded_by=request.user,
        )

        # Mark unpaid tracker records as paid (oldest first) until payment is exhausted
        remaining = amount
        unpaid_records = agent.tracker_records.filter(
            dealer_payment_status='unpaid'
        ).order_by('created_at')

        records_cleared = 0
        for record in unpaid_records:
            if remaining >= record.buying_price:
                remaining -= record.buying_price
                record.dealer_payment_status = 'paid'
                record.save(update_fields=['dealer_payment_status'])
                records_cleared += 1
            else:
                break

    if records_cleared:
        messages.success(
            request,
            f'Payment of KES {amount:,.2f} recorded for {agent.name}. '
            f'{records_cleared} tracker record(s) marked as settled.'
        )
    else:
        messages.success(request, f'Payment of KES {amount:,.2f} recorded for {agent.name}.')
    return redirect('vehicles:tracker_agent_ledger_detail', pk=agent_pk)


@login_required
def record_clearing_agent_payment(request, agent_pk):
    """Record a lump-sum payment to a clearing agent."""
    if request.method != 'POST':
        messages.error(request, 'Method not allowed.')
        return redirect('vehicles:clearing_agent_ledger_detail', pk=agent_pk)
    agent = get_object_or_404(ClearingAgent, pk=agent_pk)
    from .models import ClearingAgentPayment
    amount_str = request.POST.get('amount', '').strip()
    payment_method = request.POST.get('payment_method', 'bank_transfer')
    reference_number = request.POST.get('reference_number', '').strip()
    notes = request.POST.get('notes', '').strip()
    payment_date_str = request.POST.get('payment_date', '').strip()
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError
    except Exception:
        messages.error(request, 'Invalid payment amount.')
        return redirect('vehicles:clearing_agent_ledger_detail', pk=agent_pk)
    from datetime import date as date_type, datetime as datetime_type
    payment_date = date_type.today()
    if payment_date_str:
        try:
            payment_date = datetime_type.strptime(payment_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    with transaction.atomic():
        ClearingAgentPayment.objects.create(
            agent=agent,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
            payment_date=payment_date,
            recorded_by=request.user,
        )

        # Mark unpaid clearance records as paid (oldest first) until payment is exhausted
        remaining = amount
        unpaid_records = agent.clearance_records.filter(
            payment_status='unpaid'
        ).order_by('date', 'id')

        records_cleared = 0
        for record in unpaid_records:
            if remaining >= record.amount:
                remaining -= record.amount
                record.payment_status = 'paid'
                record.save(update_fields=['payment_status'])
                records_cleared += 1
            else:
                break

    if records_cleared:
        messages.success(
            request,
            f'Payment of KES {amount:,.2f} recorded for {agent.name}. '
            f'{records_cleared} clearance record(s) marked as settled.'
        )
    else:
        messages.success(request, f'Payment of KES {amount:,.2f} recorded for {agent.name}.')
    return redirect('vehicles:clearing_agent_ledger_detail', pk=agent_pk)


# ==================== JAPAN SUPPLIER LEDGER VIEWS ====================

@login_required
@role_required('admin', 'manager', 'sales', 'accountant', 'auctioneer')
def japan_supplier_ledger_list(request):
    """List all Japan suppliers with totals and outstanding balances."""
    from django.db.models import Q, Sum, Value, DecimalField
    from django.db.models.functions import Coalesce

    if request.method == 'POST':
        form = JapanSupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Japan supplier added successfully.')
            return redirect('vehicles:japan_supplier_ledger_list')
    else:
        form = JapanSupplierForm()

    suppliers = JapanSupplier.objects.filter(is_active=True).prefetch_related('supplier_records').order_by('name')
    totals = JapanSupplierRecord.objects.aggregate(
        grand_total=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
        grand_owed=Coalesce(
            Sum('purchase_price', filter=Q(payment_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
        grand_settled=Coalesce(
            Sum('purchase_price', filter=Q(payment_status='paid')),
            Value(0, output_field=DecimalField()),
        ),
    )
    context = {
        'suppliers': suppliers,
        'grand_total': totals['grand_total'],
        'grand_owed': totals['grand_owed'],
        'grand_settled': totals['grand_settled'],
        'form': form,
    }
    return render(request, 'vehicles/japan_supplier_ledger_list.html', context)


def _japan_supplier_statement(supplier, date_from, date_to, vehicle_search=''):
    """Shared by the on-screen detail view and its PDF export so they never disagree."""
    from utils.ledger import make_entry, build_statement

    records = supplier.supplier_records.select_related('vehicle').order_by('-date')
    payments = supplier.payments.select_related('recorded_by').order_by('-payment_date')

    if vehicle_search:
        records = records.filter(
            Q(vehicle__vin__icontains=vehicle_search) |
            Q(vehicle__registration_number__icontains=vehicle_search)
        )

    entries = [
        make_entry(
            r.date,
            'Vehicle purchased from supplier',
            credit=r.purchase_price,
            reference=f'SUP-{r.pk}',
            related=str(r.vehicle),
            status=r.get_payment_status_display(),
            notes=r.notes,
            sort_key=r.created_at,
        )
        for r in records
    ] + [
        make_entry(
            p.payment_date,
            'Payment to supplier',
            debit=p.amount,
            reference=p.reference_number or f'PAY-{p.pk}',
            method=p.get_payment_method_display(),
            created_by=p.recorded_by,
            status='Paid',
            notes=p.notes,
            sort_key=p.created_at,
        )
        for p in payments
    ]
    if date_from:
        entries = [e for e in entries if e['date'] >= date_from]
    if date_to:
        entries = [e for e in entries if e['date'] <= date_to]
    statement_rows, statement_summary = build_statement(entries, balance_from='credit')
    return records, payments, statement_rows, statement_summary


@login_required
def japan_supplier_ledger_detail(request, pk):
    """Show all purchase records for a supplier and payment history."""
    from utils.ledger import parse_date_range

    date_from, date_to = parse_date_range(request)
    supplier = get_object_or_404(JapanSupplier, pk=pk)
    vehicle_search = request.GET.get('vehicle_search', '').strip()
    records, payments, statement_rows, statement_summary = _japan_supplier_statement(
        supplier, date_from, date_to, vehicle_search
    )

    context = {
        'supplier': supplier,
        'records': records,
        'payments': payments,
        'vehicle_search': vehicle_search,
        'statement_rows': statement_rows,
        'statement_summary': statement_summary,
        'debit_hint': 'payment made to supplier',
        'credit_hint': 'vehicle billed by supplier',
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'vehicles/japan_supplier_ledger_detail.html', context)


@login_required
def japan_supplier_ledger_pdf(request, pk):
    """Printable PDF statement for a single Japan supplier."""
    from utils.ledger import parse_date_range
    from utils.report_kit import ledger_statement_pdf_response

    date_from, date_to = parse_date_range(request)
    supplier = get_object_or_404(JapanSupplier, pk=pk)
    vehicle_search = request.GET.get('vehicle_search', '').strip()
    _, _, statement_rows, statement_summary = _japan_supplier_statement(
        supplier, date_from, date_to, vehicle_search
    )

    subtitle = supplier.name
    if date_from or date_to:
        subtitle += f" — {date_from or 'the beginning'} to {date_to or 'today'}"

    return ledger_statement_pdf_response(
        f'japan-supplier-{supplier.pk}-statement.pdf', 'Japan Supplier Statement', subtitle,
        statement_rows, statement_summary,
        debit_hint='payment made to supplier', credit_hint='vehicle billed by supplier',
    )


@login_required
def japan_supplier_record_mark_paid(request, pk):
    """Mark a single supplier record as paid."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    record = get_object_or_404(JapanSupplierRecord, pk=pk)
    record.payment_status = 'paid'
    record.save(update_fields=['payment_status'])
    return JsonResponse({'status': 'paid', 'record_id': pk})


@login_required
def japan_supplier_mark_all_paid(request, supplier_pk):
    """Mark all unpaid records for a supplier as paid."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    supplier = get_object_or_404(JapanSupplier, pk=supplier_pk)
    updated = supplier.supplier_records.filter(payment_status='unpaid').update(payment_status='paid')
    return JsonResponse({'status': 'ok', 'updated': updated})


@login_required
def record_japan_supplier_payment(request, supplier_pk):
    """Record a lump-sum payment to a Japan supplier."""
    if request.method != 'POST':
        messages.error(request, 'Method not allowed.')
        return redirect('vehicles:japan_supplier_ledger_detail', pk=supplier_pk)
    supplier = get_object_or_404(JapanSupplier, pk=supplier_pk)
    amount_str = request.POST.get('amount', '').strip()
    payment_method = request.POST.get('payment_method', 'bank_transfer')
    reference_number = request.POST.get('reference_number', '').strip()
    notes = request.POST.get('notes', '').strip()
    payment_date_str = request.POST.get('payment_date', '').strip()
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError
    except Exception:
        messages.error(request, 'Invalid payment amount.')
        return redirect('vehicles:japan_supplier_ledger_detail', pk=supplier_pk)
    from datetime import date as date_type, datetime as datetime_type
    payment_date = date_type.today()
    if payment_date_str:
        try:
            payment_date = datetime_type.strptime(payment_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    with transaction.atomic():
        JapanSupplierPayment.objects.create(
            supplier=supplier,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
            payment_date=payment_date,
            recorded_by=request.user,
        )

        # Mark unpaid records as paid (oldest first) until payment is exhausted
        remaining = amount
        unpaid_records = supplier.supplier_records.filter(
            payment_status='unpaid'
        ).order_by('date', 'id')

        records_cleared = 0
        for record in unpaid_records:
            if remaining >= record.purchase_price:
                remaining -= record.purchase_price
                record.payment_status = 'paid'
                record.save(update_fields=['payment_status'])
                records_cleared += 1
            else:
                break

    if records_cleared:
        messages.success(
            request,
            f'Payment of KES {amount:,.2f} recorded for {supplier.name}. '
            f'{records_cleared} vehicle(s) marked as settled.'
        )
    else:
        messages.success(request, f'Payment of KES {amount:,.2f} recorded for {supplier.name}.')
    return redirect('vehicles:japan_supplier_ledger_detail', pk=supplier_pk)


@login_required
def delete_japan_supplier(request, pk):
    """Delete a Japan supplier and all related records."""
    if request.method != 'POST':
        return redirect('vehicles:japan_supplier_ledger_detail', pk=pk)
    supplier = get_object_or_404(JapanSupplier, pk=pk)
    name = supplier.name
    supplier.delete()
    messages.success(request, f'Supplier "{name}" has been deleted.')
    return redirect('vehicles:japan_supplier_ledger_list')


# ==================== VEHICLE REPORTS ====================

@login_required
def vehicle_reports(request):
    """Comprehensive vehicle inventory and financial analytics."""
    from django.db.models import Min, Max
    from datetime import date
    from utils.ledger import parse_date_range

    can_see_prices = _can_view_vehicle_prices(request.user)
    date_from, date_to = parse_date_range(request)
    vehicles = Vehicle.objects.all()
    if date_from:
        vehicles = vehicles.filter(date_added__date__gte=date_from)
    if date_to:
        vehicles = vehicles.filter(date_added__date__lte=date_to)
    today = date.today()

    # ── Status breakdown ─────────────────────────────────────────────────────
    status_breakdown = []
    total_count = vehicles.count()
    for val, label in VehicleStatus.CHOICES:
        count = vehicles.filter(status=val).count()
        status_breakdown.append({'status': label, 'value': val, 'count': count})

    available_qs = vehicles.filter(status=VehicleStatus.AVAILABLE)
    sold_qs = vehicles.filter(status=VehicleStatus.SOLD)

    # ── Inventory value (available stock) ────────────────────────────────────
    if can_see_prices:
        inv_agg = available_qs.aggregate(
            total_purchase=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
            total_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
            avg_purchase=Coalesce(Avg('purchase_price'), Value(0, output_field=DecimalField())),
            avg_selling=Coalesce(Avg('selling_price'), Value(0, output_field=DecimalField())),
            min_price=Min('selling_price'),
            max_price=Max('selling_price'),
        )
        sold_agg = sold_qs.aggregate(
            total_purchase=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
            total_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
        )
        all_agg = vehicles.aggregate(
            total_purchase=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
            total_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
            avg_mileage=Coalesce(Avg('mileage'), Value(0.0)),
        )
    else:
        inv_agg = sold_agg = all_agg = {
            'total_purchase': 0, 'total_selling': 0,
            'avg_purchase': 0, 'avg_selling': 0,
            'min_price': 0, 'max_price': 0, 'avg_mileage': 0,
        }

    # ── Make breakdown (top 10) ──────────────────────────────────────────────
    by_make = list(
        vehicles.values('make').annotate(
            count=Count('id'),
            available=Count('id', filter=Q(status=VehicleStatus.AVAILABLE)),
            sold=Count('id', filter=Q(status=VehicleStatus.SOLD)),
        ).order_by('-count')[:10]
    )

    # ── Fuel type breakdown ──────────────────────────────────────────────────
    fuel_choices = [('petrol', 'Petrol'), ('diesel', 'Diesel'), ('electric', 'Electric'),
                    ('hybrid', 'Hybrid'), ('other', 'Other')]
    by_fuel = [
        {'label': label, 'count': vehicles.filter(fuel_type=val).count()}
        for val, label in fuel_choices
    ]

    # ── Body type breakdown ──────────────────────────────────────────────────
    body_choices = [('sedan', 'Sedan'), ('suv', 'SUV'), ('hatchback', 'Hatchback'),
                    ('pickup', 'Pickup Truck'), ('van', 'Van'), ('coupe', 'Coupe'),
                    ('wagon', 'Station Wagon'), ('other', 'Other')]
    by_body = [
        {'label': label, 'count': vehicles.filter(body_type=val).count()}
        for val, label in body_choices if vehicles.filter(body_type=val).exists()
    ]

    # ── Location breakdown ───────────────────────────────────────────────────
    from utils.constants import VehicleLocation
    by_location = [
        {'label': label, 'count': vehicles.filter(location=val).count()}
        for val, label in VehicleLocation.CHOICES
        if vehicles.filter(location=val).exists()
    ]
    unlocated = vehicles.filter(location='').count()
    if unlocated:
        by_location.append({'label': 'Unassigned', 'count': unlocated})

    # ── Year breakdown (last 10 model years) ─────────────────────────────────
    current_year = today.year
    by_year = list(
        vehicles.filter(year__gte=current_year - 9)
        .values('year').annotate(count=Count('id'))
        .order_by('-year')
    )

    # ── Condition breakdown ──────────────────────────────────────────────────
    cond_choices = [('excellent', 'Excellent'), ('good', 'Good'), ('fair', 'Fair'), ('poor', 'Poor')]
    by_condition = [
        {'label': label, 'count': vehicles.filter(condition=val).count()}
        for val, label in cond_choices
    ]

    # ── This month additions ─────────────────────────────────────────────────
    added_this_month = vehicles.filter(
        date_added__year=today.year, date_added__month=today.month
    ).count()
    sold_this_month = sold_qs.filter(
        date_sold__year=today.year, date_sold__month=today.month
    ).count() if hasattr(Vehicle, 'date_sold') else 0

    context = {
        'can_see_prices': can_see_prices,
        'date_from': date_from,
        'date_to': date_to,
        'total_count': total_count,
        'status_breakdown': status_breakdown,
        'available_count': available_qs.count(),
        'sold_count': sold_qs.count(),
        'featured_count': vehicles.filter(is_featured=True).count(),
        'added_this_month': added_this_month,
        'inv_agg': inv_agg,
        'sold_agg': sold_agg,
        'all_agg': all_agg,
        'by_make': by_make,
        'by_fuel': by_fuel,
        'by_body': by_body,
        'by_location': by_location,
        'by_year': by_year,
        'by_condition': by_condition,
    }
    return render(request, 'vehicles/vehicle_reports.html', context)


@login_required
def vehicle_reports_pdf(request):
    """PDF version of the vehicle inventory and financial analytics report."""
    from utils.report_kit import build_pdf_response, fmt_money, kpi_table, styled_table
    from utils.ledger import parse_date_range
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Spacer
    import datetime as dt

    can_see_prices = _can_view_vehicle_prices(request.user)
    date_from, date_to = parse_date_range(request)
    vehicles = Vehicle.objects.all()
    if date_from:
        vehicles = vehicles.filter(date_added__date__gte=date_from)
    if date_to:
        vehicles = vehicles.filter(date_added__date__lte=date_to)
    today = dt.date.today()

    status_breakdown = []
    total_count = vehicles.count()
    for val, label in VehicleStatus.CHOICES:
        count = vehicles.filter(status=val).count()
        status_breakdown.append({'status': label, 'value': val, 'count': count})

    available_qs = vehicles.filter(status=VehicleStatus.AVAILABLE)
    sold_qs = vehicles.filter(status=VehicleStatus.SOLD)

    if can_see_prices:
        inv_agg = available_qs.aggregate(
            total_purchase=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
            total_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
        )
        sold_agg = sold_qs.aggregate(
            total_purchase=Coalesce(Sum('purchase_price'), Value(0, output_field=DecimalField())),
            total_selling=Coalesce(Sum('selling_price'), Value(0, output_field=DecimalField())),
        )
    else:
        inv_agg = sold_agg = {'total_purchase': 0, 'total_selling': 0}

    by_make = list(
        vehicles.values('make').annotate(count=Count('id')).order_by('-count')[:10]
    )
    fuel_choices = [('petrol', 'Petrol'), ('diesel', 'Diesel'), ('electric', 'Electric'),
                    ('hybrid', 'Hybrid'), ('other', 'Other')]
    by_fuel = [{'label': label, 'count': vehicles.filter(fuel_type=val).count()} for val, label in fuel_choices]
    body_choices = [('sedan', 'Sedan'), ('suv', 'SUV'), ('hatchback', 'Hatchback'),
                    ('pickup', 'Pickup Truck'), ('van', 'Van'), ('coupe', 'Coupe'),
                    ('wagon', 'Station Wagon'), ('other', 'Other')]
    by_body = [
        {'label': label, 'count': vehicles.filter(body_type=val).count()}
        for val, label in body_choices if vehicles.filter(body_type=val).exists()
    ]

    def body(elements, styles):
        heading = styles['ReportSectionHeading']
        heading.spaceBefore = 8
        heading.spaceAfter = 4

        kpi_pairs = [
            ('Total Vehicles', str(total_count)),
            ('Available', str(available_qs.count())),
            ('Sold', str(sold_qs.count())),
        ]
        if can_see_prices:
            kpi_pairs += [
                ('Available Inventory Value', fmt_money(inv_agg['total_selling'])),
                ('Sold Value', fmt_money(sold_agg['total_selling'])),
            ]
        elements.append(kpi_table(kpi_pairs, col_widths=[3 * inch, 3 * inch]))
        elements.append(Spacer(1, 10))

        elements.append(Paragraph('STATUS BREAKDOWN', heading))
        elements.append(styled_table(
            [['Status', 'Count']] + [[s['status'], str(s['count'])] for s in status_breakdown],
            align_right_from=1,
        ))
        elements.append(Spacer(1, 10))

        elements.append(Paragraph('TOP MAKES', heading))
        elements.append(styled_table(
            [['Make', 'Count']] + [[m['make'] or '—', str(m['count'])] for m in by_make],
            align_right_from=1,
        ))
        elements.append(Spacer(1, 10))

        elements.append(Paragraph('FUEL TYPE', heading))
        elements.append(styled_table(
            [['Fuel Type', 'Count']] + [[f['label'], str(f['count'])] for f in by_fuel],
            align_right_from=1,
        ))
        elements.append(Spacer(1, 10))

        if by_body:
            elements.append(Paragraph('BODY TYPE', heading))
            elements.append(styled_table(
                [['Body Type', 'Count']] + [[b['label'], str(b['count'])] for b in by_body],
                align_right_from=1,
            ))

    if date_from or date_to:
        subtitle = f"Added {date_from or 'the beginning'} to {date_to or 'today'}"
    else:
        subtitle = f'Generated {today.strftime("%d %B %Y")}'

    return build_pdf_response(
        'vehicle-reports.pdf', 'Vehicle Inventory & Financial Report',
        subtitle=subtitle,
        build_body=body,
    )


# ==================== BROKER LEDGER VIEWS ====================

@login_required
@role_required('admin', 'manager', 'sales', 'accountant', 'auctioneer')
def broker_ledger_list(request):
    """List all brokers with commission totals and outstanding balances."""
    if request.method == 'POST':
        form = BrokerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Broker added successfully.')
            return redirect('vehicles:broker_ledger_list')
    else:
        form = BrokerForm()

    brokers = Broker.objects.filter(is_active=True).order_by('name')
    totals = ClientVehicle.objects.filter(broker__isnull=False).aggregate(
        grand_commission=Coalesce(Sum('commission_amount'), Value(0, output_field=DecimalField())),
        grand_owed=Coalesce(
            Sum('commission_amount', filter=Q(broker_commission_status='unpaid')),
            Value(0, output_field=DecimalField()),
        ),
        grand_paid=Coalesce(
            Sum('commission_amount', filter=Q(broker_commission_status='paid')),
            Value(0, output_field=DecimalField()),
        ),
    )
    context = {
        'brokers': brokers,
        'grand_commission': totals['grand_commission'],
        'grand_owed': totals['grand_owed'],
        'grand_paid': totals['grand_paid'],
        'form': form,
    }
    return render(request, 'vehicles/broker_ledger_list.html', context)


def _broker_statement(broker, date_from, date_to):
    """Shared by the on-screen detail view and its PDF export so they never disagree."""
    from utils.ledger import make_entry, build_statement

    sales = broker.sales.select_related('vehicle', 'client').order_by('-purchase_date')
    payments = broker.payments.select_related('recorded_by').order_by('-payment_date')

    entries = [
        make_entry(
            s.purchase_date,
            f'Commission earned — sale to {s.client.get_full_name()}',
            credit=s.commission_amount,
            reference=f'CV-{s.pk}',
            related=str(s.vehicle),
            status=s.get_broker_commission_status_display(),
            sort_key=s.created_at,
        )
        for s in sales if s.commission_amount and s.commission_amount > 0
    ] + [
        make_entry(
            p.payment_date,
            'Commission payment (voucher)',
            debit=p.amount,
            reference=p.voucher_number or p.reference_number or f'PAY-{p.pk}',
            method=p.get_payment_method_display(),
            created_by=p.recorded_by,
            status='Paid',
            notes=p.notes,
            sort_key=p.created_at,
        )
        for p in payments
    ]
    if date_from:
        entries = [e for e in entries if e['date'] >= date_from]
    if date_to:
        entries = [e for e in entries if e['date'] <= date_to]
    statement_rows, statement_summary = build_statement(entries, balance_from='credit')
    return sales, payments, statement_rows, statement_summary


@login_required
def broker_ledger_detail(request, pk):
    """Show all sales for a broker and allow marking commissions paid."""
    from utils.ledger import parse_date_range

    date_from, date_to = parse_date_range(request)
    broker = get_object_or_404(Broker, pk=pk)
    sales, payments, statement_rows, statement_summary = _broker_statement(broker, date_from, date_to)

    context = {
        'broker': broker,
        'sales': sales,
        'payments': payments,
        'statement_rows': statement_rows,
        'statement_summary': statement_summary,
        'debit_hint': 'commission paid to broker',
        'credit_hint': 'commission earned by broker',
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'vehicles/broker_ledger_detail.html', context)


@login_required
def broker_ledger_pdf(request, pk):
    """Printable PDF statement for a single broker."""
    from utils.ledger import parse_date_range
    from utils.report_kit import ledger_statement_pdf_response

    date_from, date_to = parse_date_range(request)
    broker = get_object_or_404(Broker, pk=pk)
    _, _, statement_rows, statement_summary = _broker_statement(broker, date_from, date_to)

    subtitle = broker.name
    if date_from or date_to:
        subtitle += f" — {date_from or 'the beginning'} to {date_to or 'today'}"

    return ledger_statement_pdf_response(
        f'broker-{broker.pk}-statement.pdf', 'Broker Statement', subtitle,
        statement_rows, statement_summary,
        debit_hint='commission paid to broker', credit_hint='commission earned by broker',
    )


@login_required
def broker_commission_mark_paid(request, pk):
    """Mark a single sale's broker commission as paid."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    sale = get_object_or_404(ClientVehicle, pk=pk)
    sale.broker_commission_status = 'paid'
    sale.save(update_fields=['broker_commission_status'])
    return JsonResponse({'status': 'paid', 'sale_id': pk})


@login_required
def broker_mark_all_paid(request, broker_pk):
    """Mark all unpaid commissions for a broker as paid."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    broker = get_object_or_404(Broker, pk=broker_pk)
    updated = broker.sales.filter(broker_commission_status='unpaid').update(
        broker_commission_status='paid'
    )
    return JsonResponse({'status': 'ok', 'updated': updated})


@login_required
def record_broker_payment(request, broker_pk):
    """Record a lump-sum payment (voucher) to a broker."""
    if request.method != 'POST':
        messages.error(request, 'Method not allowed.')
        return redirect('vehicles:broker_ledger_detail', pk=broker_pk)
    broker = get_object_or_404(Broker, pk=broker_pk)
    amount_str = request.POST.get('amount', '').strip()
    payment_method = request.POST.get('payment_method', 'bank_transfer')
    reference_number = request.POST.get('reference_number', '').strip()
    notes = request.POST.get('notes', '').strip()
    payment_date_str = request.POST.get('payment_date', '').strip()
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError
    except Exception:
        messages.error(request, 'Invalid payment amount.')
        return redirect('vehicles:broker_ledger_detail', pk=broker_pk)
    from datetime import date as date_type, datetime as datetime_type
    payment_date = date_type.today()
    if payment_date_str:
        try:
            payment_date = datetime_type.strptime(payment_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    with transaction.atomic():
        payment = BrokerPayment.objects.create(
            broker=broker,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
            payment_date=payment_date,
            recorded_by=request.user,
        )

        # Mark unpaid commission records as paid (oldest first) until exhausted
        remaining = amount
        unpaid_sales = broker.sales.filter(
            broker_commission_status='unpaid'
        ).order_by('purchase_date', 'id')

        sales_cleared = 0
        for sale in unpaid_sales:
            if remaining >= sale.commission_amount:
                remaining -= sale.commission_amount
                sale.broker_commission_status = 'paid'
                sale.save(update_fields=['broker_commission_status'])
                sales_cleared += 1
            else:
                break

    msg = f'Payment voucher {payment.voucher_number} (KES {amount:,.2f}) recorded for {broker.name}.'
    if sales_cleared:
        msg += f' {sales_cleared} commission record(s) marked as settled.'
    messages.success(request, msg)
    return redirect('vehicles:broker_ledger_detail', pk=broker_pk)


@login_required
def broker_voucher_print(request, payment_pk):
    """Printable voucher for a broker payment."""
    payment = get_object_or_404(BrokerPayment, pk=payment_pk)
    return render(request, 'vehicles/broker_voucher_print.html', {'payment': payment})


@login_required
def broker_voucher_pdf(request, payment_pk):
    """PDF version of the broker payment voucher."""
    from utils.report_kit import build_pdf_response, fmt_money, kpi_table

    payment = get_object_or_404(BrokerPayment.objects.select_related('broker', 'recorded_by'), pk=payment_pk)

    def body(elements, styles):
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, Spacer

        pairs = [
            ('Amount Paid', fmt_money(payment.amount)),
            ('Paid To (Broker)', payment.broker.name),
            ('Payment Date', payment.payment_date.strftime('%d %B %Y')),
            ('Payment Method', payment.get_payment_method_display()),
            ('Reference / Receipt No.', payment.reference_number or '—'),
            ('Recorded By', payment.recorded_by.get_full_name() if payment.recorded_by else '—'),
            ('Date Recorded', payment.created_at.strftime('%d %B %Y, %H:%M')),
        ]
        elements.append(kpi_table(pairs, col_widths=[2.6 * inch, 2.6 * inch]))
        elements.append(Spacer(1, 8))

        if payment.notes:
            elements.append(Paragraph(f'<b>Notes:</b> {payment.notes}', styles['Normal']))
            elements.append(Spacer(1, 8))

        elements.append(Paragraph(
            'Authorised By: ______________________  &nbsp;&nbsp;&nbsp;&nbsp;  '
            f'Received By ({payment.broker.name}): ______________________',
            styles['Normal'],
        ))

    return build_pdf_response(
        f'voucher-{payment.voucher_number}.pdf', 'Payment Voucher',
        subtitle=f'Voucher No: {payment.voucher_number} — Broker Commission Payment',
        build_body=body,
    )


# ==================== PARTNER LEDGER EXPORTS ====================
# Broker, Tracker Agent, Clearing Agent and Japan Supplier ledgers all share
# the same "party with billed/paid/owed totals" shape, so one parametrized
# view covers PDF/Excel/CSV export for all four instead of four near-copies.

_PARTY_LEDGER_EXPORT_CONFIG = {
    'broker': {
        'queryset': lambda: Broker.objects.filter(is_active=True).order_by('name'),
        'title': 'Broker Ledger',
        'billed_attr': 'total_commission',
        'billed_label': 'Total Commission',
    },
    'tracker_agent': {
        'queryset': lambda: TrackerAgent.objects.filter(is_active=True).order_by('name'),
        'title': 'Tracker Agent Ledger',
        'billed_attr': 'total_selling_price',
        'billed_label': 'Total Billed',
    },
    'clearing_agent': {
        'queryset': lambda: ClearingAgent.objects.filter(is_active=True).order_by('name'),
        'title': 'Clearing Agent Ledger',
        'billed_attr': 'total_billed',
        'billed_label': 'Total Billed',
    },
    'japan_supplier': {
        'queryset': lambda: JapanSupplier.objects.filter(is_active=True).order_by('name'),
        'title': 'Japan Supplier Ledger',
        'billed_attr': 'total_purchase_value',
        'billed_label': 'Total Purchase Value',
    },
}


@login_required
def party_ledger_export(request, kind, fmt):
    """Export the Broker/Tracker Agent/Clearing Agent/Japan Supplier ledger list as PDF/Excel/CSV."""
    from utils.report_kit import export_rows

    config = _PARTY_LEDGER_EXPORT_CONFIG.get(kind)
    if not config:
        raise Http404('Unknown ledger type.')

    parties = config['queryset']()
    headers = ['Name', 'Phone', 'Email', config['billed_label'], 'Paid', 'Outstanding']
    rows = [
        [
            p.name, p.phone or '', getattr(p, 'email', '') or '',
            float(getattr(p, config['billed_attr'])), float(p.total_payments_made), float(p.total_owed),
        ]
        for p in parties
    ]
    return export_rows(fmt, f'{kind}_ledger', config['title'], headers, rows, currency_cols={4, 5, 6})


# ==================== BUSINESS LOANS (MONEY LOANED OUT) ====================

_LOAN_BORROWER_MODELS = {
    'client': ('clients', 'client'),
    'broker': ('vehicles', 'broker'),
    'tracker_agent': ('vehicles', 'trackeragent'),
    'clearing_agent': ('vehicles', 'clearingagent'),
    'japan_supplier': ('vehicles', 'japansupplier'),
    'insurance_agent': ('insurance', 'insuranceagent'),
}


def _borrower_display_name(obj):
    if hasattr(obj, 'get_full_name'):
        return obj.get_full_name()
    return getattr(obj, 'name', str(obj))


@login_required
@role_required('admin', 'manager', 'sales', 'accountant', 'auctioneer')
def business_loan_list(request):
    """List all money the business has loaned out, with repayment status."""
    if request.method == 'POST':
        borrower_type = request.POST.get('borrower_type', 'other')
        borrower_id = request.POST.get('borrower_id', '').strip()
        borrower_name = request.POST.get('borrower_name', '').strip()
        principal_amount_str = request.POST.get('principal_amount', '').strip()
        date_issued_str = request.POST.get('date_issued', '').strip()
        expected_repayment_date_str = request.POST.get('expected_repayment_date', '').strip()
        purpose = request.POST.get('purpose', '').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []
        try:
            principal_amount = Decimal(principal_amount_str)
            if principal_amount <= 0:
                raise ValueError
        except Exception:
            errors.append('Principal amount must be a positive number.')
            principal_amount = None

        date_issued = timezone.now().date()
        if date_issued_str:
            try:
                date_issued = datetime.strptime(date_issued_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Invalid date issued.')

        expected_repayment_date = None
        if expected_repayment_date_str:
            try:
                expected_repayment_date = datetime.strptime(expected_repayment_date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Invalid expected repayment date.')

        borrower_ct = None
        borrower_obj = None
        if borrower_type in _LOAN_BORROWER_MODELS and borrower_id:
            app_label, model_name = _LOAN_BORROWER_MODELS[borrower_type]
            try:
                borrower_ct = ContentType.objects.get(app_label=app_label, model=model_name)
                borrower_obj = borrower_ct.model_class().objects.get(pk=borrower_id)
            except Exception:
                errors.append('Selected borrower could not be found.')
                borrower_ct = None

        if borrower_obj is not None:
            borrower_name = _borrower_display_name(borrower_obj)
        elif not borrower_name:
            errors.append('Borrower name is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            loan = BusinessLoan.objects.create(
                borrower_name=borrower_name,
                borrower_content_type=borrower_ct,
                borrower_object_id=borrower_obj.pk if borrower_obj else None,
                principal_amount=principal_amount,
                date_issued=date_issued,
                expected_repayment_date=expected_repayment_date,
                purpose=purpose,
                notes=notes,
                recorded_by=request.user,
            )
            messages.success(request, f'Loan of KES {principal_amount:,.2f} to {borrower_name} recorded.')
            return redirect('vehicles:business_loan_list')

    loans = BusinessLoan.objects.select_related('recorded_by', 'borrower_content_type').all()

    ZERO = Decimal('0.00')
    grand_principal = loans.aggregate(t=Sum('principal_amount'))['t'] or ZERO
    grand_repaid = BusinessLoanRepayment.objects.filter(loan__in=loans).aggregate(t=Sum('amount'))['t'] or ZERO
    grand_outstanding = grand_principal - grand_repaid

    context = {
        'loans': loans,
        'grand_principal': grand_principal,
        'grand_repaid': grand_repaid,
        'grand_outstanding': grand_outstanding,
        'today_str': timezone.now().date().isoformat(),
        'clients': Client.objects.filter(is_active=True).order_by('first_name', 'last_name'),
        'brokers': Broker.objects.filter(is_active=True).order_by('name'),
        'tracker_agents': TrackerAgent.objects.filter(is_active=True).order_by('name'),
        'clearing_agents': ClearingAgent.objects.filter(is_active=True).order_by('name'),
        'japan_suppliers': JapanSupplier.objects.filter(is_active=True).order_by('name'),
        'insurance_agents': InsuranceAgent.objects.filter(is_active=True).order_by('name'),
    }
    return render(request, 'vehicles/business_loan_list.html', context)


@login_required
def business_loan_export(request, fmt):
    """Export the Business Loans list as PDF/Excel/CSV."""
    from utils.report_kit import export_rows
    loans = BusinessLoan.objects.select_related('recorded_by').order_by('-date_issued')
    headers = ['Borrower', 'Date Issued', 'Principal', 'Repaid', 'Outstanding', 'Status']
    rows = [
        [
            loan.borrower_name, loan.date_issued.strftime('%Y-%m-%d'),
            float(loan.principal_amount), float(loan.total_repaid), float(loan.balance),
            loan.get_status_display(),
        ]
        for loan in loans
    ]
    return export_rows(fmt, 'business_loans', 'Business Loans', headers, rows, currency_cols={3, 4, 5})


@login_required
def business_loan_detail(request, pk):
    """Show a business loan's repayment history."""
    loan = get_object_or_404(BusinessLoan, pk=pk)
    repayments = loan.repayments.select_related('recorded_by').order_by('-payment_date', '-created_at')
    context = {
        'loan': loan,
        'repayments': repayments,
    }
    return render(request, 'vehicles/business_loan_detail.html', context)


@login_required
def record_loan_repayment(request, loan_pk):
    """Record a repayment received against a business loan."""
    if request.method != 'POST':
        messages.error(request, 'Method not allowed.')
        return redirect('vehicles:business_loan_detail', pk=loan_pk)
    loan = get_object_or_404(BusinessLoan, pk=loan_pk)
    amount_str = request.POST.get('amount', '').strip()
    payment_method = request.POST.get('payment_method', 'bank_transfer')
    reference_number = request.POST.get('reference_number', '').strip()
    notes = request.POST.get('notes', '').strip()
    payment_date_str = request.POST.get('payment_date', '').strip()
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError
    except Exception:
        messages.error(request, 'Invalid repayment amount.')
        return redirect('vehicles:business_loan_detail', pk=loan_pk)

    payment_date = timezone.now().date()
    if payment_date_str:
        try:
            payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    BusinessLoanRepayment.objects.create(
        loan=loan,
        amount=amount,
        payment_method=payment_method,
        reference_number=reference_number,
        notes=notes,
        payment_date=payment_date,
        recorded_by=request.user,
    )
    messages.success(request, f'Repayment of KES {amount:,.2f} recorded for {loan.borrower_name}.')
    return redirect('vehicles:business_loan_detail', pk=loan_pk)


@login_required
def business_loan_write_off(request, pk):
    """Mark a business loan as written off (uncollectable)."""
    if request.method != 'POST':
        messages.error(request, 'Method not allowed.')
        return redirect('vehicles:business_loan_detail', pk=pk)
    loan = get_object_or_404(BusinessLoan, pk=pk)
    loan.status = 'written_off'
    loan.save(update_fields=['status'])
    messages.success(request, f'Loan to {loan.borrower_name} marked as written off.')
    return redirect('vehicles:business_loan_detail', pk=pk)


@login_required
@role_required('admin', 'manager', 'sales', 'accountant', 'auctioneer')
def main_ledger_view(request):
    """Combined main ledger aggregating all financial activity."""
    from apps.payments.models import Payment
    from apps.insurance.models import InsuranceAgentPayment
    from apps.expenses.models import Expense
    from .models import (
        TrackerAgentPayment as _TrackerAgentPayment,
        ClearingAgentPayment as _ClearingAgentPayment,
        ManualLedgerEntry,
        BusinessLoan as _BusinessLoan,
        BusinessLoanRepayment as _BusinessLoanRepayment,
    )
    import datetime as dt

    today = dt.date.today()

    # --- Handle POST: record a manual ledger entry ---
    if request.method == 'POST':
        raw_date = request.POST.get('entry_date', '').strip()
        description = request.POST.get('entry_description', '').strip()
        raw_amount = request.POST.get('entry_amount', '').strip()
        direction = request.POST.get('entry_direction', '').strip()
        reference = request.POST.get('entry_reference', '').strip()

        errors = []
        if not description:
            errors.append('Description is required.')
        if not raw_date:
            errors.append('Date is required.')
        if direction not in ('in', 'out'):
            errors.append('Direction must be Debit or Credit.')
        amount = None
        try:
            amount = Decimal(raw_amount)
            if amount <= 0:
                raise ValueError
        except Exception:
            errors.append('Amount must be a positive number.')

        entry_date = None
        try:
            entry_date = dt.date.fromisoformat(raw_date)
        except Exception:
            errors.append('Invalid date.')

        if not errors:
            ManualLedgerEntry.objects.create(
                date=entry_date,
                description=description,
                amount=amount,
                direction=direction,
                reference=reference,
                recorded_by=request.user,
            )
            messages.success(request, f'Entry recorded: {description}')
        else:
            for e in errors:
                messages.error(request, e)

        # Redirect back to main ledger preserving filters
        redirect_url = request.POST.get('next', request.get_full_path())
        return redirect(redirect_url.split('?')[0] + '?' + request.POST.get('filter_qs', ''))

    # --- Handle DELETE: remove a manual entry ---
    if request.method == 'GET' and request.GET.get('delete_entry'):
        entry_id = request.GET.get('delete_entry')
        try:
            entry = ManualLedgerEntry.objects.get(pk=entry_id)
            entry.delete()
            messages.success(request, 'Entry deleted.')
        except ManualLedgerEntry.DoesNotExist:
            pass
        # Redirect without the delete param
        import urllib.parse
        params = {k: v for k, v in request.GET.items() if k != 'delete_entry'}
        qs = urllib.parse.urlencode(params)
        return redirect(f"{request.path}?{qs}" if qs else request.path)

    context = _compute_main_ledger_context(request)
    return render(request, 'vehicles/main_ledger.html', context)


def _compute_main_ledger_context(request):
    """Filter + aggregate the combined main ledger — shared by the on-screen
    view and its PDF/Excel/CSV exports so all four always match."""
    from apps.payments.models import Payment
    from apps.insurance.models import InsuranceAgentPayment
    from apps.expenses.models import Expense
    from .models import (
        TrackerAgentPayment as _TrackerAgentPayment,
        ClearingAgentPayment as _ClearingAgentPayment,
        ManualLedgerEntry,
        BusinessLoan as _BusinessLoan,
        BusinessLoanRepayment as _BusinessLoanRepayment,
    )
    import datetime as dt

    today = dt.date.today()

    # --- Filters ---
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    category_filter = request.GET.get('category', '')
    search = request.GET.get('q', '').strip()

    try:
        date_from = dt.date.fromisoformat(date_from_str) if date_from_str else today.replace(day=1)
    except ValueError:
        date_from = today.replace(day=1)

    try:
        date_to = dt.date.fromisoformat(date_to_str) if date_to_str else today
    except ValueError:
        date_to = today

    ZERO = Decimal('0')

    def date_range(qs, field):
        return qs.filter(**{f'{field}__gte': date_from, f'{field}__lte': date_to})

    # --- Base querysets ---
    payments_qs = date_range(
        Payment.objects.select_related('client_vehicle__client', 'client_vehicle__vehicle'),
        'payment_date',
    )
    supplier_payments_qs = date_range(
        JapanSupplierPayment.objects.select_related('supplier'), 'payment_date'
    )
    clearing_payments_qs = date_range(
        _ClearingAgentPayment.objects.select_related('agent'), 'payment_date'
    )
    tracker_payments_qs = date_range(
        _TrackerAgentPayment.objects.select_related('agent'), 'payment_date'
    )
    broker_payments_qs = date_range(
        BrokerPayment.objects.select_related('broker'), 'payment_date'
    )
    insurance_payments_qs = date_range(
        InsuranceAgentPayment.objects.select_related('agent'), 'payment_date'
    )
    expenses_qs = date_range(
        Expense.objects.filter(status__in=['APPROVED', 'PAID']).select_related('category'),
        'expense_date',
    )
    manual_qs = date_range(ManualLedgerEntry.objects.select_related('recorded_by'), 'date')
    loans_qs = date_range(_BusinessLoan.objects.all(), 'date_issued')
    loan_repayments_qs = date_range(
        _BusinessLoanRepayment.objects.select_related('loan'), 'payment_date'
    )

    # Search
    if search:
        payments_qs = payments_qs.filter(
            Q(client_vehicle__client__first_name__icontains=search)
            | Q(client_vehicle__client__last_name__icontains=search)
            | Q(receipt_number__icontains=search)
            | Q(transaction_reference__icontains=search)
        )
        expenses_qs = expenses_qs.filter(
            Q(title__icontains=search) | Q(vendor_name__icontains=search)
        )
        manual_qs = manual_qs.filter(
            Q(description__icontains=search) | Q(reference__icontains=search)
        )
        loans_qs = loans_qs.filter(
            Q(borrower_name__icontains=search) | Q(purpose__icontains=search)
        )
        loan_repayments_qs = loan_repayments_qs.filter(
            Q(loan__borrower_name__icontains=search) | Q(reference_number__icontains=search)
        )

    # Category filter
    _ALL = {
        'client_payment', 'supplier', 'clearing', 'tracker', 'broker', 'insurance',
        'expense', 'manual', 'loan_disbursed', 'loan_repayment',
    }
    if category_filter and category_filter in _ALL:
        if category_filter != 'client_payment':
            payments_qs = payments_qs.none()
        if category_filter != 'supplier':
            supplier_payments_qs = supplier_payments_qs.none()
        if category_filter != 'clearing':
            clearing_payments_qs = clearing_payments_qs.none()
        if category_filter != 'tracker':
            tracker_payments_qs = tracker_payments_qs.none()
        if category_filter != 'broker':
            broker_payments_qs = broker_payments_qs.none()
        if category_filter != 'insurance':
            insurance_payments_qs = insurance_payments_qs.none()
        if category_filter != 'expense':
            expenses_qs = expenses_qs.none()
        if category_filter != 'manual':
            manual_qs = manual_qs.none()
        if category_filter != 'loan_disbursed':
            loans_qs = loans_qs.none()
        if category_filter != 'loan_repayment':
            loan_repayments_qs = loan_repayments_qs.none()

    # --- Totals ---
    total_in = payments_qs.aggregate(t=Sum('amount'))['t'] or ZERO
    total_supplier = supplier_payments_qs.aggregate(t=Sum('amount'))['t'] or ZERO
    total_clearing = clearing_payments_qs.aggregate(t=Sum('amount'))['t'] or ZERO
    total_tracker = tracker_payments_qs.aggregate(t=Sum('amount'))['t'] or ZERO
    total_broker = broker_payments_qs.aggregate(t=Sum('amount'))['t'] or ZERO
    total_insurance = insurance_payments_qs.aggregate(t=Sum('amount'))['t'] or ZERO
    total_expenses = expenses_qs.aggregate(t=Sum('total_amount'))['t'] or ZERO
    total_loans_disbursed = loans_qs.aggregate(t=Sum('principal_amount'))['t'] or ZERO
    total_loan_repayments = loan_repayments_qs.aggregate(t=Sum('amount'))['t'] or ZERO

    manual_in = manual_qs.filter(direction='in').aggregate(t=Sum('amount'))['t'] or ZERO
    manual_out = manual_qs.filter(direction='out').aggregate(t=Sum('amount'))['t'] or ZERO

    total_out = (
        total_supplier + total_clearing + total_tracker + total_broker + total_insurance
        + total_expenses + manual_out + total_loans_disbursed
    )
    net = (total_in + manual_in + total_loan_repayments) - total_out

    # --- Build transaction rows ---
    transactions = []

    for p in payments_qs:
        client = p.client_vehicle.client
        transactions.append({
            'date': p.payment_date,
            'ref': p.receipt_number or p.transaction_reference or f'PMT-{p.pk}',
            'description': f"{client.first_name} {client.last_name}",
            'detail': p.client_vehicle.vehicle.full_name,
            'category': 'client_payment',
            'category_label': 'Client Payment',
            'category_color': 'green',
            'method': p.get_payment_method_display(),
            'money_in': p.amount,
            'money_out': ZERO,
            'manual_id': None,
        })

    for p in supplier_payments_qs:
        transactions.append({
            'date': p.payment_date,
            'ref': p.reference_number or f'SUP-{p.pk}',
            'description': p.supplier.name,
            'detail': 'Japan Supplier',
            'category': 'supplier',
            'category_label': 'Japan Supplier',
            'category_color': 'red',
            'method': p.get_payment_method_display(),
            'money_in': ZERO,
            'money_out': p.amount,
            'manual_id': None,
        })

    for p in clearing_payments_qs:
        transactions.append({
            'date': p.payment_date,
            'ref': p.reference_number or f'CLR-{p.pk}',
            'description': p.agent.name,
            'detail': 'Clearing Agent',
            'category': 'clearing',
            'category_label': 'Clearing Agent',
            'category_color': 'teal',
            'method': p.get_payment_method_display(),
            'money_in': ZERO,
            'money_out': p.amount,
            'manual_id': None,
        })

    for p in tracker_payments_qs:
        transactions.append({
            'date': p.payment_date,
            'ref': p.reference_number or f'TRK-{p.pk}',
            'description': p.agent.name,
            'detail': 'Tracker Agent',
            'category': 'tracker',
            'category_label': 'Tracker Agent',
            'category_color': 'purple',
            'method': p.get_payment_method_display(),
            'money_in': ZERO,
            'money_out': p.amount,
            'manual_id': None,
        })

    for p in broker_payments_qs:
        transactions.append({
            'date': p.payment_date,
            'ref': p.voucher_number or p.reference_number or f'BRK-{p.pk}',
            'description': p.broker.name,
            'detail': 'Broker Commission',
            'category': 'broker',
            'category_label': 'Broker',
            'category_color': 'amber',
            'method': p.get_payment_method_display(),
            'money_in': ZERO,
            'money_out': p.amount,
            'manual_id': None,
        })

    for p in insurance_payments_qs:
        transactions.append({
            'date': p.payment_date,
            'ref': p.reference_number or f'INS-{p.pk}',
            'description': p.agent.name,
            'detail': 'Insurance Agent',
            'category': 'insurance',
            'category_label': 'Insurance Agent',
            'category_color': 'blue',
            'method': p.get_payment_method_display(),
            'money_in': ZERO,
            'money_out': p.amount,
            'manual_id': None,
        })

    for e in expenses_qs:
        transactions.append({
            'date': e.expense_date,
            'ref': e.invoice_number or f'EXP-{e.pk}',
            'description': e.title,
            'detail': e.vendor_name or e.category.name,
            'category': 'expense',
            'category_label': e.category.name,
            'category_color': 'gray',
            'method': e.get_payment_method_display(),
            'money_in': ZERO,
            'money_out': e.total_amount,
            'manual_id': None,
        })

    for e in manual_qs:
        transactions.append({
            'date': e.date,
            'ref': e.reference or f'MAN-{e.pk}',
            'description': e.description,
            'detail': f"Recorded by {e.recorded_by.get_full_name() if e.recorded_by else '—'}",
            'category': 'manual',
            'category_label': 'Manual Entry',
            'category_color': 'orange',
            'method': '—',
            'money_in': e.amount if e.direction == 'in' else ZERO,
            'money_out': e.amount if e.direction == 'out' else ZERO,
            'manual_id': e.pk,
        })

    for loan in loans_qs:
        transactions.append({
            'date': loan.date_issued,
            'ref': f'LOAN-{loan.pk}',
            'description': loan.borrower_name,
            'detail': loan.purpose or 'Loan Disbursed',
            'category': 'loan_disbursed',
            'category_label': 'Loan Disbursed',
            'category_color': 'rose',
            'method': '—',
            'money_in': ZERO,
            'money_out': loan.principal_amount,
            'manual_id': None,
        })

    for r in loan_repayments_qs:
        transactions.append({
            'date': r.payment_date,
            'ref': r.reference_number or f'LR-{r.pk}',
            'description': r.loan.borrower_name,
            'detail': 'Loan Repayment',
            'category': 'loan_repayment',
            'category_label': 'Loan Repayment',
            'category_color': 'emerald',
            'method': r.get_payment_method_display(),
            'money_in': r.amount,
            'money_out': ZERO,
            'manual_id': None,
        })

    # Compute running balance ascending, then reverse for display
    transactions.sort(key=lambda x: x['date'])
    running = ZERO
    for t in transactions:
        running += t['money_in'] - t['money_out']
        t['running_balance'] = running
    transactions = list(reversed(transactions))

    category_summary = [
        {'label': 'Client Payments', 'key': 'client_payment', 'color': 'green', 'money_in': total_in, 'money_out': ZERO},
        {'label': 'Japan Suppliers', 'key': 'supplier', 'color': 'red', 'money_in': ZERO, 'money_out': total_supplier},
        {'label': 'Clearing Agents', 'key': 'clearing', 'color': 'teal', 'money_in': ZERO, 'money_out': total_clearing},
        {'label': 'Tracker Agents', 'key': 'tracker', 'color': 'purple', 'money_in': ZERO, 'money_out': total_tracker},
        {'label': 'Broker Commissions', 'key': 'broker', 'color': 'amber', 'money_in': ZERO, 'money_out': total_broker},
        {'label': 'Insurance Agents', 'key': 'insurance', 'color': 'blue', 'money_in': ZERO, 'money_out': total_insurance},
        {'label': 'General Expenses', 'key': 'expense', 'color': 'gray', 'money_in': ZERO, 'money_out': total_expenses},
        {'label': 'Manual Entries', 'key': 'manual', 'color': 'orange', 'money_in': manual_in, 'money_out': manual_out},
        {'label': 'Loans Disbursed', 'key': 'loan_disbursed', 'color': 'rose', 'money_in': ZERO, 'money_out': total_loans_disbursed},
        {'label': 'Loan Repayments', 'key': 'loan_repayment', 'color': 'emerald', 'money_in': total_loan_repayments, 'money_out': ZERO},
    ]

    # Build filter querystring for POST redirect
    import urllib.parse
    filter_qs = urllib.parse.urlencode({
        k: v for k, v in {
            'date_from': date_from_str,
            'date_to': date_to_str,
            'category': category_filter,
            'q': search,
        }.items() if v
    })

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'date_from_str': date_from.isoformat(),
        'date_to_str': date_to.isoformat(),
        'category_filter': category_filter,
        'search': search,
        'total_in': total_in + manual_in + total_loan_repayments,
        'total_out': total_out,
        'net': net,
        'category_summary': category_summary,
        'transactions': transactions,
        'filter_qs': filter_qs,
        'today_str': today.isoformat(),
    }
    return context


def _main_ledger_export_rows(ctx):
    headers = ['Date', 'Reference', 'Description', 'Category', 'Method', 'Debit', 'Credit', 'Balance']
    rows = [
        [
            t['date'].strftime('%Y-%m-%d'), t['ref'], t['description'], t['category_label'], t['method'],
            float(t['money_in']), float(t['money_out']), float(t['running_balance']),
        ]
        for t in ctx['transactions']
    ]
    return headers, rows


@login_required
@role_required('admin', 'manager', 'sales', 'accountant', 'auctioneer')
def main_ledger_export(request, fmt):
    """Export the Main Ledger (filtered the same way as the on-screen view) as PDF/Excel/CSV."""
    from utils.report_kit import export_rows
    ctx = _compute_main_ledger_context(request)
    headers, rows = _main_ledger_export_rows(ctx)
    subtitle = f"{ctx['date_from']} to {ctx['date_to']}"
    return export_rows(fmt, 'main_ledger', 'Main Ledger', headers, rows, currency_cols={6, 7, 8}, subtitle=subtitle)


# ==================== SALES LEDGER ====================
# Every completed sale (a ClientVehicle against a sold Vehicle) with its
# actual revenue, total cost and profit/loss, filterable by sale date so a
# specific date or date range shows whether the business made a profit or a
# loss on the vehicles sold in that window.

def _sales_ledger_queryset(date_from, date_to, search=''):
    sales = ClientVehicle.objects.filter(vehicle__status=VehicleStatus.SOLD).select_related(
        'client', 'vehicle', 'broker'
    ).prefetch_related(
        'vehicle__extra_costs',
        'vehicle__insurance_policies',
        'vehicle__expenses__category',
        'vehicle__repossessions__expenses',
        'vehicle__repossessions__additional_cost_items',
    ).order_by('-purchase_date', '-created_at')

    if date_from:
        sales = sales.filter(purchase_date__gte=date_from)
    if date_to:
        sales = sales.filter(purchase_date__lte=date_to)
    if search:
        sales = sales.filter(
            Q(vehicle__registration_number__icontains=search) |
            Q(vehicle__vin__icontains=search)
        )
    return sales


def _sales_ledger_rows(date_from, date_to, search=''):
    from .utils import compute_sale_profit

    rows = []
    for cv in _sales_ledger_queryset(date_from, date_to, search):
        result = compute_sale_profit(cv)
        rows.append({
            'client_vehicle': cv,
            'vehicle': cv.vehicle,
            'client': cv.client,
            'sale_date': cv.purchase_date,
            **result,
        })
    return rows


@login_required
@role_required('admin', 'manager', 'sales', 'accountant', 'auctioneer')
def sales_ledger(request):
    """Every completed vehicle sale with revenue, total cost and actual profit/loss."""
    import urllib.parse
    from utils.ledger import parse_date_range
    from .utils import bulk_sale_totals

    date_from, date_to = parse_date_range(request)
    search = request.GET.get('search', '').strip()
    rows = _sales_ledger_rows(date_from, date_to, search)

    # Summary totals come from bulk_sale_totals() (shared with the dashboard),
    # not by summing each row's compute_sale_profit() - if the same vehicle
    # was sold more than once (repossessed and resold), each row correctly
    # carries that vehicle's full cost for reading in isolation, but summing
    # rows would then double-count that shared cost in the total.
    total_revenue, total_cost = bulk_sale_totals(_sales_ledger_queryset(date_from, date_to, search))
    total_profit = total_revenue - total_cost
    profitable_count = sum(1 for r in rows if r['profit'] > 0)
    loss_count = sum(1 for r in rows if r['profit'] < 0)

    qs_params = {}
    if date_from:
        qs_params['date_from'] = date_from.isoformat()
    if date_to:
        qs_params['date_to'] = date_to.isoformat()
    if search:
        qs_params['search'] = search
    filter_qs = urllib.parse.urlencode(qs_params)

    context = {
        'rows': rows,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
        'filter_qs': filter_qs,
        'sale_count': len(rows),
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'total_profit': total_profit,
        'is_profit_overall': total_profit >= 0,
        'profitable_count': profitable_count,
        'loss_count': loss_count,
        'breakeven_count': len(rows) - profitable_count - loss_count,
    }
    return render(request, 'vehicles/sales_ledger.html', context)


@login_required
@role_required('admin', 'manager', 'sales', 'accountant', 'auctioneer')
def sales_ledger_export(request, fmt):
    """Export the Sales Ledger (same date filters as the on-screen view) as PDF/Excel/CSV."""
    from utils.report_kit import export_rows
    from utils.ledger import parse_date_range

    date_from, date_to = parse_date_range(request)
    search = request.GET.get('search', '').strip()
    rows = _sales_ledger_rows(date_from, date_to, search)

    headers = ['Sale Date', 'Vehicle', 'Reg. No.', 'VIN', 'Client', 'Revenue', 'Total Cost', 'Profit / (Loss)', 'Result']
    export_data = [
        [
            r['sale_date'], r['vehicle'].full_name, r['vehicle'].registration_number or '', r['vehicle'].vin,
            r['client'].get_full_name(), float(r['revenue']), float(r['total_cost']),
            float(r['profit']), 'Profit' if r['profit'] >= 0 else 'Loss',
        ]
        for r in rows
    ]
    subtitle = f"{date_from or 'the beginning'} to {date_to or 'today'}"
    if search:
        subtitle += f' — search: "{search}"'
    return export_rows(
        fmt, 'sales_ledger', 'Sales Ledger', headers, export_data,
        currency_cols={6, 7, 8}, subtitle=subtitle,
    )
