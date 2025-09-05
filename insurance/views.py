
from django.views.generic import ListView, DetailView, CreateView
from .models import Insurance, InsuranceProvider
from django.urls import reverse_lazy

class InsuranceListView(ListView):
	model = Insurance
	template_name = 'insurance/insurance_list.html'
	context_object_name = 'insurances'

class InsuranceDetailView(DetailView):
	model = Insurance
	template_name = 'insurance/insurance_detail.html'
	context_object_name = 'insurance'

class InsuranceCreateView(CreateView):
	model = Insurance
	fields = '__all__'
	template_name = 'insurance/insurance_form.html'
	success_url = reverse_lazy('insurance:insurance-list')

class InsuranceProviderListView(ListView):
	model = InsuranceProvider
	template_name = 'insurance/insuranceprovider_list.html'
	context_object_name = 'providers'

class InsuranceProviderDetailView(DetailView):
	model = InsuranceProvider
	template_name = 'insurance/insuranceprovider_detail.html'
	context_object_name = 'provider'

class InsuranceProviderCreateView(CreateView):
	model = InsuranceProvider
	fields = '__all__'
	template_name = 'insurance/insuranceprovider_form.html'
	success_url = reverse_lazy('insurance:insuranceprovider-list')
