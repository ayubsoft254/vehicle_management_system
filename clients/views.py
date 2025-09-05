
from django.views.generic import ListView, DetailView, CreateView
from .models import Client
from django.urls import reverse_lazy

class ClientListView(ListView):
	model = Client
	template_name = 'clients/client_list.html'
	context_object_name = 'clients'

class ClientDetailView(DetailView):
	model = Client
	template_name = 'clients/client_detail.html'
	context_object_name = 'client'

class ClientCreateView(CreateView):
	model = Client
	fields = '__all__'
	template_name = 'clients/client_form.html'
	success_url = reverse_lazy('clients:client-list')
