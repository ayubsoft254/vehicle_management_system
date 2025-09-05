
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView
from .models import User, RolePermission, Company


# Dashboard view with all features
from auctions.models import Auction, AuctionVehicle
from vehicles.models import Vehicle
from clients.models import Client
from payments.models import Payment
from payroll.models import Payroll
from insurance.models import Insurance
from expenses.models import Expense
from documents.models import Document
from notifications.models import Notification
from reports.models import ReportGeneration
from audit.models import AuditLog

@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
	template_name = 'dashboard/dashboard.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		# Vehicles
		context['vehicle_count'] = Vehicle.objects.count()
		context['available_count'] = Vehicle.objects.filter(status='available').count() if hasattr(Vehicle, 'status') else None
		context['sold_count'] = Vehicle.objects.filter(status='sold').count() if hasattr(Vehicle, 'status') else None
		context['recent_vehicles'] = Vehicle.objects.order_by('-created_at')[:5] if hasattr(Vehicle, 'created_at') else Vehicle.objects.all()[:5]
		# Auctions
		context['auction_count'] = Auction.objects.count()
		context['active_auction_count'] = Auction.objects.filter(status='active').count()
		context['recent_auctions'] = Auction.objects.order_by('-start_date')[:5]
		# Clients
		context['client_count'] = Client.objects.count()
		context['recent_clients'] = Client.objects.order_by('-id')[:5]
		# Payments
		context['payment_count'] = Payment.objects.count()
		context['recent_payments'] = Payment.objects.order_by('-created_at')[:5] if hasattr(Payment, 'created_at') else Payment.objects.all()[:5]
		# Payroll
		context['payroll_count'] = Payroll.objects.count()
		# Insurance
		context['insurance_count'] = Insurance.objects.count()
		# Expenses
		context['expense_count'] = Expense.objects.count()
		# Documents
		context['document_count'] = Document.objects.count()
		# Notifications
		context['notification_count'] = Notification.objects.count()
		# Reports
		context['report_count'] = ReportGeneration.objects.count()
		# Audit Logs
		context['auditlog_count'] = AuditLog.objects.count()
		return context

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

def contact(request):
	return render(request, 'dashboard/contact.html')