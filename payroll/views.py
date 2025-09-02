
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Payroll, EmployeeLoan
from .forms import PayrollForm, EmployeeLoanForm

# Payroll Views
@method_decorator(login_required, name='dispatch')
class PayrollListView(ListView):
	model = Payroll
	template_name = 'payroll/payroll_list.html'
	context_object_name = 'payrolls'

@method_decorator(login_required, name='dispatch')
class PayrollDetailView(DetailView):
	model = Payroll
	template_name = 'payroll/payroll_detail.html'
	context_object_name = 'payroll'

@method_decorator(login_required, name='dispatch')
class PayrollCreateView(CreateView):
	model = Payroll
	form_class = PayrollForm
	template_name = 'payroll/payroll_form.html'
	success_url = reverse_lazy('payroll-list')

@method_decorator(login_required, name='dispatch')
class PayrollUpdateView(UpdateView):
	model = Payroll
	form_class = PayrollForm
	template_name = 'payroll/payroll_form.html'
	success_url = reverse_lazy('payroll-list')

@method_decorator(login_required, name='dispatch')
class PayrollDeleteView(DeleteView):
	model = Payroll
	template_name = 'payroll/payroll_confirm_delete.html'
	success_url = reverse_lazy('payroll-list')

# Employee Loan Views
@method_decorator(login_required, name='dispatch')
class EmployeeLoanListView(ListView):
	model = EmployeeLoan
	template_name = 'payroll/loan_list.html'
	context_object_name = 'loans'

@method_decorator(login_required, name='dispatch')
class EmployeeLoanDetailView(DetailView):
	model = EmployeeLoan
	template_name = 'payroll/loan_detail.html'
	context_object_name = 'loan'

@method_decorator(login_required, name='dispatch')
class EmployeeLoanCreateView(CreateView):
	model = EmployeeLoan
	form_class = EmployeeLoanForm
	template_name = 'payroll/loan_form.html'
	success_url = reverse_lazy('loan-list')

@method_decorator(login_required, name='dispatch')
class EmployeeLoanUpdateView(UpdateView):
	model = EmployeeLoan
	form_class = EmployeeLoanForm
	template_name = 'payroll/loan_form.html'
	success_url = reverse_lazy('loan-list')

@method_decorator(login_required, name='dispatch')
class EmployeeLoanDeleteView(DeleteView):
	model = EmployeeLoan
	template_name = 'payroll/loan_confirm_delete.html'
	success_url = reverse_lazy('loan-list')
