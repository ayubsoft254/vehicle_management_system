from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView
from .models import User, RolePermission, Company

# Dashboard related imports
from auctions.models import Auction
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
from django.http import HttpResponseForbidden


# ===== DASHBOARD VIEW =====
@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'dashboard/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        """
        Redirect users based on role:
        - Clients -> ClientDashboardView
        - Staff/Admin -> main dashboard
        """
        if hasattr(request.user, 'role'):
            if request.user.role == 'client':
                return redirect('client-dashboard')
            allowed_roles = ['admin', 'sales', 'accountant', 'auctioneer', 'manager', 'clerk']
            if request.user.role not in allowed_roles:
                return HttpResponseForbidden("You do not have permission to access this dashboard.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Vehicle stats
        context['vehicle_count'] = Vehicle.objects.count()
        context['available_count'] = Vehicle.objects.filter(status='available').count() if hasattr(Vehicle, 'status') else None
        context['sold_count'] = Vehicle.objects.filter(status='sold').count() if hasattr(Vehicle, 'status') else None
        context['recent_vehicles'] = Vehicle.objects.order_by('-created_at')[:5] if hasattr(Vehicle, 'created_at') else Vehicle.objects.all()[:5]
        # Auction stats
        context['auction_count'] = Auction.objects.count()
        context['active_auction_count'] = Auction.objects.filter(status='active').count()
        context['recent_auctions'] = Auction.objects.order_by('-start_date')[:5]
        # Client stats
        context['client_count'] = Client.objects.count()
        context['recent_clients'] = Client.objects.order_by('-id')[:5]
        # Payment stats
        context['payment_count'] = Payment.objects.count()
        context['recent_payments'] = Payment.objects.order_by('-created_at')[:5] if hasattr(Payment, 'created_at') else Payment.objects.all()[:5]
        # Other stats
        context['payroll_count'] = Payroll.objects.count()
        context['insurance_count'] = Insurance.objects.count()
        context['expense_count'] = Expense.objects.count()
        context['document_count'] = Document.objects.count()
        context['notification_count'] = Notification.objects.count()
        context['report_count'] = ReportGeneration.objects.count()
        context['auditlog_count'] = AuditLog.objects.count()
        return context


# ===== CLIENT DASHBOARD VIEW =====
@method_decorator(login_required, name='dispatch')
class ClientDashboardView(TemplateView):
    template_name = 'dashboard/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if hasattr(request.user, 'role') and request.user.role == 'client':
            return super().dispatch(request, *args, **kwargs)
        return HttpResponseForbidden("You do not have permission to access the client dashboard.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client_obj = getattr(self.request.user, 'client', None)
        if client_obj:
            context['my_vehicles'] = client_obj.vehicles.all() if hasattr(client_obj, 'vehicles') else []
            context['my_payments'] = client_obj.payments.all() if hasattr(client_obj, 'payments') else []
            context['my_notifications'] = Notification.objects.filter(client=client_obj)
        else:
            context['my_vehicles'] = []
            context['my_payments'] = []
            context['my_notifications'] = []
        return context


# ===== LANDING PAGE VIEW =====
class LandingPageView(TemplateView):
    template_name = 'dashboard/landing.html'


# ===== USER VIEWS =====
@method_decorator(login_required, name='dispatch')
class UserListView(ListView):
    model = User
    template_name = 'dashboard/user_list.html'
    context_object_name = 'users'


@method_decorator(login_required, name='dispatch')
class UserDetailView(DetailView):
    model = User
    template_name = 'dashboard/user_detail.html'
    context_object_name = 'user_obj'


# ===== COMPANY VIEWS =====
@method_decorator(login_required, name='dispatch')
class CompanyListView(ListView):
    model = Company
    template_name = 'dashboard/company_list.html'
    context_object_name = 'companies'


@method_decorator(login_required, name='dispatch')
class CompanyDetailView(DetailView):
    model = Company
    template_name = 'dashboard/company_detail.html'
    context_object_name = 'company'


# ===== CONTACT VIEW =====
def contact(request):
    return render(request, 'dashboard/contact.html')
