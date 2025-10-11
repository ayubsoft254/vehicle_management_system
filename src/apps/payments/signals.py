"""
Signals for the payments app
Handles automatic updates after payment actions
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from django.db import models
from decimal import Decimal

from .models import Payment, InstallmentPlan, PaymentSchedule, PaymentReminder
from apps.clients.models import ClientVehicle, Client


# ==================== PAYMENT SIGNALS ====================

@receiver(post_save, sender=Payment)
def update_client_vehicle_after_payment(sender, instance, created, **kwargs):
    """
    Update ClientVehicle balance and status after payment is recorded
    """
    if created:
        client_vehicle = instance.client_vehicle
        
        # Update total paid and balance
        client_vehicle.total_paid = Payment.objects.filter(
            client_vehicle=client_vehicle
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        client_vehicle.balance = client_vehicle.purchase_price - client_vehicle.total_paid
        
        # Check if fully paid
        if client_vehicle.balance <= 0:
            client_vehicle.is_paid_off = True
            client_vehicle.balance = Decimal('0.00')  # Ensure no negative balance
            
            # Update client status to completed
            client = client_vehicle.client
            client.status = 'completed'
            client.save()
            
            # Mark installment plan as completed if exists
            try:
                plan = client_vehicle.installment_plan
                plan.is_completed = True
                plan.is_active = False
                plan.save()
            except InstallmentPlan.DoesNotExist:
                pass
        
        client_vehicle.save()


@receiver(post_save, sender=Payment)
def update_payment_schedules_after_payment(sender, instance, created, **kwargs):
    """
    Automatically update payment schedules when a payment is recorded
    """
    if created:
        client_vehicle = instance.client_vehicle
        
        try:
            plan = client_vehicle.installment_plan
            
            # Get unpaid schedules in order
            pending_schedules = plan.payment_schedules.filter(
                is_paid=False
            ).order_by('installment_number')
            
            remaining_amount = instance.amount
            
            for schedule in pending_schedules:
                if remaining_amount <= 0:
                    break
                
                # Calculate how much to apply to this schedule
                amount_to_apply = min(remaining_amount, schedule.remaining_amount)
                
                # Update the schedule
                schedule.amount_paid += amount_to_apply
                schedule.payment = instance
                schedule.payment_date = instance.payment_date
                
                # Mark as paid if fully paid
                if schedule.amount_paid >= schedule.amount_due:
                    schedule.is_paid = True
                
                schedule.save()
                
                remaining_amount -= amount_to_apply
        
        except InstallmentPlan.DoesNotExist:
            # No installment plan exists
            pass


@receiver(post_delete, sender=Payment)
def revert_payment_on_delete(sender, instance, **kwargs):
    """
    Revert balance changes when a payment is deleted
    """
    client_vehicle = instance.client_vehicle
    
    # Recalculate total paid
    client_vehicle.total_paid = Payment.objects.filter(
        client_vehicle=client_vehicle
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    
    client_vehicle.balance = client_vehicle.purchase_price - client_vehicle.total_paid
    
    # Update is_paid_off status
    if client_vehicle.balance > 0:
        client_vehicle.is_paid_off = False
        
        # Revert client status if needed
        client = client_vehicle.client
        if client.status == 'completed':
            client.status = 'active'
            client.save()
    
    client_vehicle.save()
    
    # Clear payment schedules linked to this payment
    PaymentSchedule.objects.filter(payment=instance).update(
        payment=None,
        amount_paid=Decimal('0.00'),
        is_paid=False,
        payment_date=None
    )


# ==================== INSTALLMENT PLAN SIGNALS ====================

@receiver(post_save, sender=InstallmentPlan)
def generate_schedules_on_plan_creation(sender, instance, created, **kwargs):
    """
    Automatically generate payment schedules when installment plan is created
    """
    if created:
        # Generate payment schedules
        instance.generate_payment_schedule()


@receiver(post_save, sender=InstallmentPlan)
def check_plan_completion(sender, instance, created, **kwargs):
    """
    Check if installment plan should be marked as completed
    """
    if not created:
        # Check if all schedules are paid
        total_schedules = instance.payment_schedules.count()
        paid_schedules = instance.payment_schedules.filter(is_paid=True).count()
        
        if total_schedules > 0 and total_schedules == paid_schedules:
            if not instance.is_completed:
                instance.is_completed = True
                instance.is_active = False
                
                # Avoid infinite loop by disconnecting signal temporarily
                post_save.disconnect(check_plan_completion, sender=InstallmentPlan)
                instance.save()
                post_save.connect(check_plan_completion, sender=InstallmentPlan)


@receiver(pre_save, sender=InstallmentPlan)
def calculate_end_date(sender, instance, **kwargs):
    """
    Calculate end date if not provided
    """
    if instance.start_date and not instance.end_date:
        from dateutil.relativedelta import relativedelta
        instance.end_date = instance.start_date + relativedelta(
            months=instance.number_of_installments
        )


# ==================== PAYMENT SCHEDULE SIGNALS ====================

@receiver(post_save, sender=PaymentSchedule)
def check_overdue_schedules(sender, instance, created, **kwargs):
    """
    Check for overdue schedules and update client status
    """
    if not instance.is_paid and instance.is_overdue:
        client = instance.installment_plan.client_vehicle.client
        
        # Count overdue schedules for this client
        overdue_count = PaymentSchedule.objects.filter(
            installment_plan__client_vehicle__client=client,
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).count()
        
        # Mark client as defaulted if they have overdue payments
        if overdue_count > 0 and client.status == 'active':
            client.status = 'defaulted'
            client.save()


@receiver(post_save, sender=PaymentSchedule)
def send_reminder_on_due_date(sender, instance, created, **kwargs):
    """
    Automatically create reminder when schedule is approaching due date
    """
    if not instance.is_paid:
        today = timezone.now().date()
        days_until_due = (instance.due_date - today).days
        
        # Send reminder 3 days before due date
        if days_until_due == 3:
            # Check if reminder already sent
            existing_reminder = PaymentReminder.objects.filter(
                payment_schedule=instance,
                reminder_date__date=today
            ).exists()
            
            if not existing_reminder:
                # Create reminder
                client = instance.installment_plan.client_vehicle.client
                vehicle = instance.installment_plan.client_vehicle.vehicle
                
                message = (
                    f"Dear {client.get_full_name()}, "
                    f"this is a reminder that your payment of KES {instance.amount_due:,.2f} "
                    f"for {vehicle} is due on {instance.due_date.strftime('%d/%m/%Y')}. "
                    f"Please make payment to avoid penalties. "
                    f"Thank you."
                )
                
                PaymentReminder.objects.create(
                    payment_schedule=instance,
                    reminder_type='sms',
                    message=message,
                    status='pending'
                )


# ==================== PAYMENT REMINDER SIGNALS ====================

@receiver(post_save, sender=PaymentReminder)
def process_reminder_sending(sender, instance, created, **kwargs):
    """
    Process reminder sending based on type
    """
    if created and instance.status == 'pending':
        # Here you would integrate with SMS/Email services
        # For now, we'll just mark as sent
        
        # Example integration points:
        # - SMS: Twilio, Africa's Talking, etc.
        # - Email: Django email backend
        # - WhatsApp: Twilio WhatsApp API
        
        try:
            if instance.reminder_type == 'sms':
                # send_sms(instance.payment_schedule.installment_plan.client_vehicle.client.phone_primary, instance.message)
                pass
            elif instance.reminder_type == 'email':
                # send_email(instance.payment_schedule.installment_plan.client_vehicle.client.email, instance.message)
                pass
            
            # Mark as sent
            instance.status = 'sent'
            
            # Avoid infinite loop by disconnecting signal temporarily
            post_save.disconnect(process_reminder_sending, sender=PaymentReminder)
            instance.save()
            post_save.connect(process_reminder_sending, sender=PaymentReminder)
            
        except Exception as e:
            # Mark as failed
            instance.status = 'failed'
            
            # Avoid infinite loop
            post_save.disconnect(process_reminder_sending, sender=PaymentReminder)
            instance.save()
            post_save.connect(process_reminder_sending, sender=PaymentReminder)


# ==================== CLIENT VEHICLE SIGNALS ====================

@receiver(post_save, sender=ClientVehicle)
def update_client_credit_on_vehicle_save(sender, instance, created, **kwargs):
    """
    Update client's available credit when vehicle is assigned
    """
    client = instance.client
    
    # Recalculate current debt (sum of all balances)
    from django.db.models import Sum
    total_debt = ClientVehicle.objects.filter(
        client=client,
        is_paid_off=False
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    # Update client's available credit (this would be a property in the Client model)
    # The actual available_credit is calculated as credit_limit - current_debt


# ==================== UTILITY SIGNALS ====================

@receiver(post_save, sender=Payment)
def log_payment_activity(sender, instance, created, **kwargs):
    """
    Log payment activity for audit trail
    """
    if created:
        from apps.audit.utils import log_audit
        
        # Log the payment
        log_audit(
            user=instance.recorded_by,
            action='create',
            model_name='Payment',
            description=f'Payment recorded: {instance.receipt_number} - KES {instance.amount:,.2f}'
        )


@receiver(post_save, sender=PaymentSchedule)
def notify_on_payment_completion(sender, instance, **kwargs):
    """
    Send notification when payment schedule is completed
    """
    if instance.is_paid:
        # Check if this was just marked as paid
        if instance.tracker.has_changed('is_paid'):
            # Create notification for payment completion
            # This would integrate with your notifications app
            pass


# ==================== AUTOMATIC STATUS UPDATES ====================

@receiver(post_save, sender=PaymentSchedule)
def auto_update_client_status_on_payment(sender, instance, **kwargs):
    """
    Automatically update client status based on payment history
    """
    client = instance.installment_plan.client_vehicle.client
    
    # Check for overdue payments
    overdue_count = PaymentSchedule.objects.filter(
        installment_plan__client_vehicle__client=client,
        is_paid=False,
        due_date__lt=timezone.now().date()
    ).count()
    
    # Count active vehicle purchases
    active_purchases = ClientVehicle.objects.filter(
        client=client,
        is_paid_off=False
    ).count()
    
    # Update status based on payment history
    if overdue_count > 2:  # More than 2 overdue payments
        if client.status != 'defaulted':
            client.status = 'defaulted'
            client.save()
    elif active_purchases > 0:
        if client.status != 'active':
            client.status = 'active'
            client.save()
    elif active_purchases == 0:
        # Check if all purchases are paid off
        all_paid = ClientVehicle.objects.filter(
            client=client
        ).count() == ClientVehicle.objects.filter(
            client=client,
            is_paid_off=True
        ).count()
        
        if all_paid and client.status != 'completed':
            client.status = 'completed'
            client.save()


# ==================== PERFORMANCE OPTIMIZATION ====================

@receiver(post_save, sender=Payment)
def update_statistics_cache(sender, instance, created, **kwargs):
    """
    Update cached statistics after payment is recorded
    """
    if created:
        # Clear or update cached statistics
        # This would integrate with your caching system (Redis, Memcached, etc.)
        pass


# Import models for signals
from django.db import models