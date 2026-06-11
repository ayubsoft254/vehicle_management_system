"""
Vehicles Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .models import Vehicle, VehiclePhoto, VehicleHistory
from apps.clients.models import ClientVehicle, Client
from .forms import (
    VehicleForm, VehiclePhotoForm, VehicleSearchForm,
    VehicleStatusChangeForm, BulkVehicleActionForm, VehicleMoveForm
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

    context = {
        'vehicle': vehicle,
        'history': history,
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
    }
    return render(request, 'vehicles/vehicle_detail.html', context)


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

    context = {
        'form': form,
        'title': 'Add New Vehicle',
        'can_view_prices': can_view_prices,
        'extra_cost_entries': extra_cost_entries,
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
    
    context = {
        'form': form,
        'vehicle': vehicle,
        'can_view_prices': can_view_prices,
        'title': f'Edit Vehicle: {vehicle.full_name}',
        'extra_cost_entries': extra_cost_entries,
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
        
        # Log deletion
        AuditLog.log_delete(
            user=request.user,
            obj=vehicle,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        vehicle.delete()
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
            try:
                photo = form.save(commit=False)
                # Set required foreign key relationships
                photo.vehicle = vehicle
                photo.uploaded_by = request.user
                
                # Ensure order has a valid value if not set
                if photo.order is None:
                    photo.order = 0
                
                # Save the photo
                photo.save()
                
                messages.success(request, f'Photo uploaded successfully! {vehicle.photos.count()} photo(s) total.')
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
        vehicle.save(update_fields=['purchase_price', 'selling_price', 'last_updated'])

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