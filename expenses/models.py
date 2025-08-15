from django.db import models
from core.models import User
import uuid
class ExpenseCategory(models.Model):
    """Categorize different types of business expenses"""
    
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Expense Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Expense(models.Model):
    """General business expenses tracking"""
    
    EXPENSE_TYPES = [
        ('operational', 'Operational'),
        ('administrative', 'Administrative'),
        ('marketing', 'Marketing'),
        ('maintenance', 'Maintenance'),
        ('utilities', 'Utilities'),
        ('transport', 'Transportation'),
        ('office', 'Office Supplies'),
        ('fuel', 'Fuel'),
        ('insurance', 'Insurance'),
        ('taxes', 'Taxes & Licenses'),
        ('other', 'Other'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('card', 'Credit/Debit Card'),
        ('mobile_money', 'Mobile Money'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True)
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPES)
    
    # Financial Details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    
    # Vendor Information
    vendor_name = models.CharField(max_length=100)
    vendor_contact = models.CharField(max_length=100, blank=True)
    
    # Documentation
    receipt_number = models.CharField(max_length=50, blank=True)
    invoice_number = models.CharField(max_length=50, blank=True)
    receipt_image = models.ImageField(upload_to='expenses/receipts/', blank=True, null=True)
    
    # Dates
    expense_date = models.DateField()
    payment_date = models.DateField(blank=True, null=True)
    
    # Approval and Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Metadata
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_expenses')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-expense_date']
    
    def __str__(self):
        return f"{self.title} - {self.amount}"