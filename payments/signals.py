from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Payment, InstallmentPlan
from django.utils import timezone

@receiver(post_save, sender=Payment)
def update_installment_plan_on_payment(sender, instance, created, **kwargs):
    """
    Signal to update InstallmentPlan status and balance when a Payment is created or updated.
    """
    if created or instance.status == 'completed':
        plan = instance.installment_plan
        # Update balance and status
        if plan.balance_remaining <= 0:
            plan.status = 'completed'
        elif instance.status == 'failed':
            plan.status = 'defaulted'
        plan.save()

@receiver(post_save, sender=Payment)
def log_payment_activity(sender, instance, created, **kwargs):
    """
    Signal to log payment activity (for audit or notification).
    """
    if created:
        # Example: print or log to a file, or create a notification
        print(f"Payment of {instance.amount} recorded for {instance.installment_plan.client} on {timezone.now()}")
        # You can also create a Notification object or AuditLog entry here
