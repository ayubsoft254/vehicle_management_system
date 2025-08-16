
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from .models import Vehicle, VehicleImage, VehicleExpense
from .forms import VehicleForm, VehicleImageForm, VehicleExpenseForm

# List all vehicles
@method_decorator(login_required, name='dispatch')
class VehicleListView(ListView):
	model = Vehicle
	template_name = 'vehicles/vehicle_list.html'
	context_object_name = 'vehicles'

# Vehicle detail with images and expenses
@method_decorator(login_required, name='dispatch')
class VehicleDetailView(DetailView):
	model = Vehicle
	template_name = 'vehicles/vehicle_detail.html'
	context_object_name = 'vehicle'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['images'] = self.object.images.all()
		context['expenses'] = self.object.expenses.all()
		return context

# Create a new vehicle
@method_decorator(login_required, name='dispatch')
class VehicleCreateView(CreateView):
	model = Vehicle
	form_class = VehicleForm
	template_name = 'vehicles/vehicle_form.html'
	success_url = reverse_lazy('vehicle-list')

# Update a vehicle
@method_decorator(login_required, name='dispatch')
class VehicleUpdateView(UpdateView):
	model = Vehicle
	form_class = VehicleForm
	template_name = 'vehicles/vehicle_form.html'
	success_url = reverse_lazy('vehicle-list')

# Delete a vehicle
@method_decorator(login_required, name='dispatch')
class VehicleDeleteView(DeleteView):
	model = Vehicle
	template_name = 'vehicles/vehicle_confirm_delete.html'
	success_url = reverse_lazy('vehicle-list')

# Add an image to a vehicle
@login_required
def add_vehicle_image(request, pk):
	vehicle = get_object_or_404(Vehicle, pk=pk)
	if request.method == 'POST':
		form = VehicleImageForm(request.POST, request.FILES)
		if form.is_valid():
			image = form.save(commit=False)
			image.vehicle = vehicle
			image.save()
			return redirect('vehicle-detail', pk=vehicle.pk)
	else:
		form = VehicleImageForm()
	return render(request, 'vehicles/vehicleimage_form.html', {'form': form, 'vehicle': vehicle})

# Delete a vehicle image
@login_required
def delete_vehicle_image(request, image_id):
	image = get_object_or_404(VehicleImage, id=image_id)
	vehicle_pk = image.vehicle.pk
	image.delete()
	return redirect('vehicle-detail', pk=vehicle_pk)

# Add an expense to a vehicle
@login_required
def add_vehicle_expense(request, pk):
	vehicle = get_object_or_404(Vehicle, pk=pk)
	if request.method == 'POST':
		form = VehicleExpenseForm(request.POST)
		if form.is_valid():
			expense = form.save(commit=False)
			expense.vehicle = vehicle
			expense.save()
			return redirect('vehicle-detail', pk=vehicle.pk)
	else:
		form = VehicleExpenseForm()
	return render(request, 'vehicles/vehicleexpense_form.html', {'form': form, 'vehicle': vehicle})

# Delete a vehicle expense
@login_required
def delete_vehicle_expense(request, expense_id):
	expense = get_object_or_404(VehicleExpense, id=expense_id)
	vehicle_pk = expense.vehicle.pk
	expense.delete()
	return redirect('vehicle-detail', pk=vehicle_pk)
