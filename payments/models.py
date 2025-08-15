from django.db import models
import uuid
from core.models import User
from vehicles.models import Vehicle
from clients.models import Client


class InstallmentPlan(models.Model):
    """Installment payment plan for vehicle purchases"""
    
    PLAN_STATUS = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='installment_plans')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='installment_plans')
    
    # Plan Details
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    financed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Annual percentage
    number_of_months = models.PositiveIntegerField()
    monthly_payment = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=PLAN_STATUS, default='active')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.client} - {self.vehicle} Plan"
    
    @property
    def total_paid(self):
        return sum(payment.amount for payment in self.payments.filter(status='completed'))
    
    @property
    def balance_remaining(self):
        return self.total_amount - self.total_paid
    
    @property
    def is_completed(self):
        return self.balance_remaining <= 0

class Payment(models.Model):
    """Individual payment records"""
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('mobile_money', 'Mobile Money'),
        ('card', 'Credit/Debit Card'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_TYPES = [
        ('deposit', 'Deposit'),
        ('installment', 'Monthly Installment'),
        ('penalty', 'Late Payment Penalty'),
        ('full_payment', 'Full Payment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    installment_plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name='payments')
    
    # Payment Details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_date = models.DateTimeField()
    due_date = models.DateField()
    
    # Transaction Details
    transaction_id = models.CharField(max_length=100, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=50, blank=True)
    cheque_number = models.CharField(max_length=20, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    notes = models.TextField(blank=True)
    
    # Metadata
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment {self.amount} - {self.installment_plan.client}"
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.due_date < timezone.now().date() and self.status != 'completed'