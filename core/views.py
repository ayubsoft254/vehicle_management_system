
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView
from .models import User, RolePermission, Company

# Dashboard view
@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
	template_name = 'dashboard/dashboard.html'

# Landing page view
class LandingPageView(TemplateView):
	template_name = 'dashboard/landing.html'

# User list view
@method_decorator(login_required, name='dispatch')
class UserListView(ListView):
	model = User
	template_name = 'dashboard/user_list.html'
	context_object_name = 'users'

# User detail view
@method_decorator(login_required, name='dispatch')
class UserDetailView(DetailView):
	model = User
	template_name = 'dashboard/user_detail.html'
	context_object_name = 'user_obj'

# Company list view
@method_decorator(login_required, name='dispatch')
class CompanyListView(ListView):
	model = Company
	template_name = 'dashboard/company_list.html'
	context_object_name = 'companies'

# Company detail view
@method_decorator(login_required, name='dispatch')
class CompanyDetailView(DetailView):
	model = Company
	template_name = 'dashboard/company_detail.html'
	context_object_name = 'company'
