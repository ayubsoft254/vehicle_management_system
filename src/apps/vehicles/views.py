"""
Vehicles Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .models import Vehicle, VehiclePhoto, VehicleHistory
from .forms import (
    VehicleForm, VehiclePhotoForm, VehicleSearchForm,
    VehicleStatusChangeForm, BulkVehicleActionForm
)
from utils.decorators import role_required, module_permission_required
from utils.constants import UserRole, VehicleStatus, AccessLevel
from apps.audit.models import AuditLog
import csv
from datetime import datetime


def vehicle_list_view(request):
    """List all vehicles with search and filter - Public and authenticated users"""
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
        
        if price_from:
            vehicles = vehicles.filter(selling_price__gte=price_from)
        
        if price_to:
            vehicles = vehicles.filter(selling_price__lte=price_to)
        
        if fuel_type:
            vehicles = vehicles.filter(fuel_type=fuel_type)
        
        if transmission:
            vehicles = vehicles.filter(transmission=transmission)
        
        if body_type:
            vehicles = vehicles.filter(body_type=body_type)
    
    # Statistics
    total_vehicles = vehicles.count()
    available_count = vehicles.filter(status=VehicleStatus.AVAILABLE).count()
    sold_count = vehicles.filter(status=VehicleStatus.SOLD).count()
    reserved_count = vehicles.filter(status=VehicleStatus.RESERVED).count()
    
    # Total value
    total_inventory_value = vehicles.filter(
        status=VehicleStatus.AVAILABLE
    ).aggregate(total=Sum('selling_price'))['total'] or 0
    
    # Pagination
    paginator = Paginator(vehicles, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'total_vehicles': total_vehicles,
        'available_count': available_count,
        'sold_count': sold_count,
        'reserved_count': reserved_count,
        'total_inventory_value': total_inventory_value,
    }
    return render(request, 'vehicles/vehicle_list.html', context)


@login_required
@module_permission_required('vehicles', AccessLevel.READ_ONLY)
def vehicle_detail_view(request, pk):
    """View vehicle details"""
    vehicle = get_object_or_404(
        Vehicle.objects.select_related('added_by').prefetch_related('photos', 'history')
        , pk=pk
    )
    
    # Get history
    history = vehicle.history.select_related('changed_by').all()[:10]
    
    # Log view action
    AuditLog.log_read(
        user=request.user,
        obj=vehicle,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    context = {
        'vehicle': vehicle,
        'history': history,
    }
    return render(request, 'vehicles/vehicle_detail.html', context)


@login_required
@module_permission_required('vehicles', AccessLevel.READ_WRITE)
def vehicle_create_view(request):
    """Create new vehicle"""
    if request.method == 'POST':
        print("\n" + "="*50)
        print("POST REQUEST RECEIVED")
        print("="*50)
        print("POST Data:", request.POST)
        print("FILES:", request.FILES)
        print("-"*50)
        
        form = VehicleForm(request.POST, request.FILES)
        print("Form created, checking validity...")
        
        if form.is_valid():
            print("✓ Form is VALID!")
            vehicle = form.save(commit=False)
            vehicle.added_by = request.user
            vehicle.save()
            
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
        form = VehicleForm()
    
    context = {
        'form': form,
        'title': 'Add New Vehicle',
    }
    return render(request, 'vehicles/vehicle_form.html', context)


@login_required
@module_permission_required('vehicles', AccessLevel.READ_WRITE)
def vehicle_update_view(request, pk):
    """Update vehicle information"""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    # Store old values for audit
    old_values = {
        'make': vehicle.make,
        'model': vehicle.model,
        'status': vehicle.status,
        'selling_price': str(vehicle.selling_price),
    }
    
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=vehicle)
        if form.is_valid():
            vehicle = form.save()
            
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
        form = VehicleForm(instance=vehicle)
    
    context = {
        'form': form,
        'vehicle': vehicle,
        'title': f'Edit Vehicle: {vehicle.full_name}',
    }
    return render(request, 'vehicles/vehicle_form.html', context)


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
            photo = form.save(commit=False)
            photo.vehicle = vehicle
            photo.uploaded_by = request.user
            photo.save()
            
            messages.success(request, 'Photo uploaded successfully!')
            return redirect('vehicles:detail', pk=vehicle.pk)
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
        ),
        'avg_price': float(
            Vehicle.objects.filter(status=VehicleStatus.AVAILABLE).aggregate(
                avg=Avg('selling_price')
            )['avg'] or 0
        ),
        'by_make': list(
            Vehicle.objects.values('make').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
        ),
    }
    
    return JsonResponse(stats)