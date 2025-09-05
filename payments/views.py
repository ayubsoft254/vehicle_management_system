
from django.views.generic import ListView, DetailView, CreateView
from .models import Payment, InstallmentPlan
from django.urls import reverse_lazy

class PaymentListView(ListView):
	model = Payment
	template_name = 'payments/payment_list.html'
	context_object_name = 'payments'

class PaymentDetailView(DetailView):
	model = Payment
	template_name = 'payments/payment_detail.html'
	context_object_name = 'payment'

class PaymentCreateView(CreateView):
	model = Payment
	fields = '__all__'
	template_name = 'payments/payment_form.html'
	success_url = reverse_lazy('payments:payment-list')

class InstallmentPlanListView(ListView):
	model = InstallmentPlan
	template_name = 'payments/installmentplan_list.html'
	context_object_name = 'installment_plans'

class InstallmentPlanDetailView(DetailView):
	model = InstallmentPlan
	template_name = 'payments/installmentplan_detail.html'
	context_object_name = 'installment_plan'

class InstallmentPlanCreateView(CreateView):
	model = InstallmentPlan
	fields = '__all__'
	template_name = 'payments/installmentplan_form.html'
	success_url = reverse_lazy('payments:installmentplan-list')
