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
import logging

from .models1 import Payment, InstallmentPlan, PaymentSchedule, PaymentReminder, PaybillTransaction
from apps.clients.models import ClientVehicle, Client

logger = logging.getLogger(__name__)

# ==================== SAFE HELPER FUNCTIONS ====================

def _safe_recalculate_vehicle(client_vehicle):
    """
    Safely recalculate vehicle state without raising exceptions
    that could break the main transaction.
    """
    try:
        if not client_vehicle:
            return
        
        today = timezone.now().date()
        
        total_paid = Payment.objects.filter(
            client_vehicle=client_vehicle,
            payment_date__lte=today,
            is_reversed=False,
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        client_vehicle.total_paid = total_paid
        client_vehicle.balance = client_vehicle.purchase_price - client_vehicle.total_paid

        if client_vehicle.balance <= 0:
            client_vehicle.is_paid_off = True
            client_vehicle.balance = Decimal('0.00')
            if not client_vehicle.date_paid_off:
                client_vehicle.date_paid_off = today

            client = client_vehicle.client
            if client and client.status != 'completed':
                client.status = 'completed'
                client.save(update_fields=['status'])

            try:
                plan = client_vehicle.installment_plan
                if plan and (not plan.is_completed or plan.is_active):
                    plan.is_completed = True
                    plan.is_active = False
                    plan.save(update_fields=['is_completed', 'is_active'])
            except InstallmentPlan.DoesNotExist:
                pass
        else:
            client_vehicle.is_paid_off = False
            client_vehicle.date_paid_off = None

            client = client_vehicle.client
            if client and client.status == 'completed':
                client.status = 'active'
                client.save(update_fields=['status'])

            try:
                plan = client_vehicle.installment_plan
                if plan:
                    if plan.is_completed:
                        plan.is_completed = False
                    if not plan.is_active:
                        plan.is_active = True
                    plan.save(update_fields=['is_completed', 'is_active'])
            except InstallmentPlan.DoesNotExist:
                pass

        client_vehicle.save(update_fields=['total_paid', 'balance', 'is_paid_off', 'date_paid_off'])
        return True
        
    except Exception as e:
        logger.error(f"Error recalculating vehicle {client_vehicle.id if client_vehicle else 'unknown'}: {e}")
        return False


def _safe_link_paybill_to_payment(payment):
    """Safely link a paybill transaction to a payment."""
    if not payment or not payment.transaction_reference:
        return False
    
    try:
        paybill_tx = PaybillTransaction.objects.filter(
            trans_id=payment.transaction_reference,
            is_linked_to_payment=False
        ).first()
        
        if paybill_tx:
            paybill_tx.is_linked_to_payment = True
            paybill_tx.save(update_fields=['is_linked_to_payment'])
            return True
    except Exception as e:
        logger.warning(f"Could not link paybill transaction: {e}")
    
    return False


def _invalidate_dashboard_metric_cache():
    """Safely clear cached metrics."""
    try:
        from apps.dashboard.models import MetricCache
        MetricCache.objects.filter(metric_key__startswith='widget_data_').delete()
    except Exception:
        # Dashboard cache should never block payment processing
        pass


def _safe_update_payment_schedules(payment):
    """Safely update payment schedules without breaking main flow."""
    if not payment or not payment.client_vehicle:
        return
    
    try:
        if payment.payment_date and payment.payment_date > timezone.now().date():
            return

        client_vehicle = payment.client_vehicle
        
        try:
            plan = client_vehicle.installment_plan
            if not plan:
                return
            
            pending_schedules = plan.payment_schedules.filter(
                is_paid=False
            ).order_by('installment_number')
            
            remaining_amount = payment.amount
            
            for schedule in pending_schedules:
                if remaining_amount <= 0:
                    break
                
                amount_to_apply = min(remaining_amount, schedule.remaining_amount)
                
                schedule.amount_paid += amount_to_apply
                schedule.payment = payment
                schedule.payment_date = payment.payment_date
                
                if schedule.amount_paid >= schedule.amount_due:
                    schedule.is_paid = True
                
                schedule.save()
                remaining_amount -= amount_to_apply
                
        except InstallmentPlan.DoesNotExist:
            pass
    except Exception as e:
        logger.error(f"Error updating payment schedules for payment {payment.id}: {e}")


# ==================== PAYMENT SIGNALS ====================

@receiver(post_save, sender=Payment)
def update_client_vehicle_after_payment(sender, instance, created, **kwargs):
    """
    ✅ SAFE: Update ClientVehicle balance and status after payment is recorded
    Wrapped in try/except to prevent breaking the main transaction
    """
    try:
        # Always run in a separate transaction to avoid blocking
        with transaction.atomic():
            _safe_recalculate_vehicle(instance.client_vehicle)
            _invalidate_dashboard_metric_cache()
            
            # Link to paybill transaction if this is an M-Pesa payment
            if instance.payment_method == 'mpesa' and instance.transaction_reference:
                _safe_link_paybill_to_payment(instance)
                
    except Exception as e:
        logger.error(f"Error in update_client_vehicle_after_payment: {e}")


@receiver(post_save, sender=Payment)
def update_payment_schedules_after_payment(sender, instance, created, **kwargs):
    """
    ✅ SAFE: Update payment schedules when a payment is recorded
    Wrapped in try/except to prevent breaking the main transaction
    """
    try:
        if created:
            with transaction.atomic():
                _safe_update_payment_schedules(instance)
    except Exception as e:
        logger.error(f"Error in update_payment_schedules_after_payment: {e}")


@receiver(post_save, sender=Payment)
def update_paybill_transaction_status(sender, instance, created, **kwargs):
    """
    ✅ SAFE: Update paybill transaction status when payment is created
    """
    try:
        if instance.transaction_reference:
            with transaction.atomic():
                paybill_tx = PaybillTransaction.objects.filter(
                    trans_id=instance.transaction_reference
                ).first()
                
                if paybill_tx and not paybill_tx.is_linked_to_payment:
                    paybill_tx.is_linked_to_payment = True
                    paybill_tx.save(update_fields=['is_linked_to_payment'])
    except Exception as e:
        logger.warning(f"Could not update paybill transaction status: {e}")


@receiver(post_delete, sender=Payment)
def revert_payment_on_delete(sender, instance, **kwargs):
    """
    ✅ SAFE: Revert balance changes when a payment is deleted
    """
    try:
        if instance.client_vehicle:
            with transaction.atomic():
                _safe_recalculate_vehicle(instance.client_vehicle)
                
                # Clear payment schedules linked to this payment
                PaymentSchedule.objects.filter(payment=instance).update(
                    payment=None,
                    amount_paid=Decimal('0.00'),
                    is_paid=False,
                    payment_date=None
                )
                _invalidate_dashboard_metric_cache()
    except Exception as e:
        logger.error(f"Error in revert_payment_on_delete: {e}")


# ==================== PAYBILL TRANSACTION SIGNALS ====================

def _normalize_reg(value):
    """Normalize a vehicle registration number for fuzzy matching."""
    import re
    return re.sub(r'[^A-Z0-9]', '', str(value or '').upper())


def _find_vehicle_by_bill_ref(bill_ref_number):
    """Find an active ClientVehicle from a bill reference / account reference."""
    if not bill_ref_number:
        return None

    normalized = _normalize_reg(bill_ref_number)
    if not normalized:
        return None

    # Exact case-insensitive match first
    cv = ClientVehicle.objects.select_related('vehicle', 'client').filter(
        is_active=True,
        vehicle__registration_number__iexact=bill_ref_number.strip(),
    ).first()
    if cv:
        return cv

    # Normalized match (ignore spaces/dashes)
    for cv in ClientVehicle.objects.select_related('vehicle', 'client').filter(
        is_active=True,
        vehicle__registration_number__isnull=False,
    ).iterator():
        if _normalize_reg(cv.vehicle.registration_number) == normalized:
            return cv
    return None


@receiver(post_save, sender=PaybillTransaction)
def process_paybill_transaction(sender, instance, created, **kwargs):
    """
    Create a Payment record from an incoming C2B PaybillTransaction.
    Only fires on creation. Skipped if a matching Payment already exists.
    """
    try:
        if not created:
            return

        if not instance.trans_id or not instance.trans_amount or instance.trans_amount <= 0:
            return

        # If a Payment with this M-Pesa code already exists (created by the view),
        # just ensure the link flag is set and exit.
        existing_payment = Payment.objects.filter(
            transaction_reference=instance.trans_id,
            payment_method='mpesa'
        ).first()

        if existing_payment:
            if not instance.is_linked_to_payment:
                instance.is_linked_to_payment = True
                instance.save(update_fields=['is_linked_to_payment'])
            return

        # Transaction was saved but no Payment exists yet — create one if we
        # can resolve the bill reference to an active vehicle.
        if not instance.bill_ref_number:
            logger.warning(
                f"PaybillTransaction {instance.trans_id}: no bill_ref_number, cannot auto-create payment."
            )
            return

        client_vehicle = _find_vehicle_by_bill_ref(instance.bill_ref_number)

        if not client_vehicle:
            logger.warning(
                f"PaybillTransaction {instance.trans_id}: vehicle not found for ref "
                f"'{instance.bill_ref_number}'. Transaction stored as unlinked."
            )
            return

        payment_date = (
            instance.trans_time.date() if instance.trans_time else timezone.now().date()
        )

        with transaction.atomic():
            payment = Payment.objects.create(
                client_vehicle=client_vehicle,
                amount=instance.trans_amount,
                payment_date=payment_date,
                payment_method='mpesa',
                transaction_reference=instance.trans_id,
                recorded_by=None,
                notes=(
                    f'Paybill payment received. Account ref: {instance.bill_ref_number}. '
                    f'Phone: {instance.msisdn or "N/A"}.'
                ),
            )

            instance.is_linked_to_payment = True
            instance.save(update_fields=['is_linked_to_payment'])

            logger.info(
                f"✅ Payment {payment.receipt_number} created from PaybillTransaction {instance.trans_id}"
            )
    except Exception as e:
        logger.error(f"Error processing paybill transaction {getattr(instance, 'id', '?')}: {e}")


# ==================== INSTALLMENT PLAN SIGNALS ====================

@receiver(post_save, sender=InstallmentPlan)
def generate_schedules_on_plan_creation(sender, instance, created, **kwargs):
    """
    ✅ SAFE: Generate schedules when plan is created
    """
    try:
        if created:
            instance.generate_payment_schedule()
    except Exception as e:
        logger.error(f"Error generating schedules for plan {instance.id}: {e}")


@receiver(post_save, sender=InstallmentPlan)
def check_plan_completion(sender, instance, created, **kwargs):
    """
    ✅ SAFE: Check if plan should be marked as completed
    """
    try:
        if not created:
            total_schedules = instance.payment_schedules.count()
            paid_schedules = instance.payment_schedules.filter(is_paid=True).count()
            
            if total_schedules > 0 and total_schedules == paid_schedules:
                if not instance.is_completed:
                    instance.is_completed = True
                    instance.is_active = False
                    
                    # Avoid infinite loop
                    post_save.disconnect(check_plan_completion, sender=InstallmentPlan)
                    instance.save()
                    post_save.connect(check_plan_completion, sender=InstallmentPlan)
    except Exception as e:
        logger.error(f"Error checking plan completion for {instance.id}: {e}")


@receiver(pre_save, sender=InstallmentPlan)
def calculate_end_date(sender, instance, **kwargs):
    """
    ✅ SAFE: Calculate end date if not provided
    """
    try:
        if instance.start_date and not instance.end_date:
            from dateutil.relativedelta import relativedelta
            instance.end_date = instance.start_date + relativedelta(
                months=instance.number_of_installments
            )
    except Exception as e:
        logger.error(f"Error calculating end date: {e}")


# ==================== PAYMENT SCHEDULE SIGNALS ====================

@receiver(post_save, sender=PaymentSchedule)
def update_client_status_on_schedule_change(sender, instance, created, **kwargs):
    """
    ✅ SAFE: Update client status based on payment history
    """
    try:
        if not instance.installment_plan or not instance.installment_plan.client_vehicle:
            return
        
        client = instance.installment_plan.client_vehicle.client
        if not client:
            return
        
        # Only check overdue if schedule is not paid
        if not instance.is_paid and instance.is_overdue:
            overdue_count = PaymentSchedule.objects.filter(
                installment_plan__client_vehicle__client=client,
                is_paid=False,
                due_date__lt=timezone.now().date()
            ).count()
            
            if overdue_count > 0 and client.status == 'active':
                client.status = 'defaulted'
                client.save()
    except Exception as e:
        logger.error(f"Error updating client status: {e}")


@receiver(post_save, sender=PaymentSchedule)
def create_reminder_on_due_date(sender, instance, created, **kwargs):
    """
    ✅ SAFE: Create reminder when schedule is approaching due date
    """
    try:
        if not instance.is_paid:
            today = timezone.now().date()
            days_until_due = (instance.due_date - today).days
            
            if days_until_due == 3:
                existing_reminder = PaymentReminder.objects.filter(
                    payment_schedule=instance,
                    reminder_date__date=today
                ).exists()
                
                if not existing_reminder:
                    client = instance.installment_plan.client_vehicle.client
                    vehicle = instance.installment_plan.client_vehicle.vehicle
                    
                    message = (
                        f"Dear {client.get_full_name()}, "
                        f"payment of KES {instance.amount_due:,.2f} "
                        f"for {vehicle} is due on {instance.due_date.strftime('%d/%m/%Y')}."
                    )
                    
                    PaymentReminder.objects.create(
                        payment_schedule=instance,
                        reminder_type='sms',
                        message=message,
                        status='pending'
                    )
    except Exception as e:
        logger.error(f"Error creating reminder: {e}")


@receiver(post_save, sender=PaymentSchedule)
def auto_update_client_status_on_payment(sender, instance, **kwargs):
    """
    ✅ SAFE: Auto-update client status based on payment history
    """
    try:
        if not instance.installment_plan or not instance.installment_plan.client_vehicle:
            return
        
        client = instance.installment_plan.client_vehicle.client
        if not client:
            return
        
        overdue_count = PaymentSchedule.objects.filter(
            installment_plan__client_vehicle__client=client,
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).count()
        
        active_purchases = ClientVehicle.objects.filter(
            client=client,
            is_paid_off=False
        ).count()
        
        if overdue_count > 2:
            if client.status != 'defaulted':
                client.status = 'defaulted'
                client.save()
        elif active_purchases > 0:
            if client.status != 'active':
                client.status = 'active'
                client.save()
        elif active_purchases == 0:
            all_paid = ClientVehicle.objects.filter(
                client=client
            ).count() == ClientVehicle.objects.filter(
                client=client,
                is_paid_off=True
            ).count()
            
            if all_paid and client.status != 'completed':
                client.status = 'completed'
                client.save()
    except Exception as e:
        logger.error(f"Error auto-updating client status: {e}")


# ==================== PAYMENT REMINDER SIGNALS ====================

@receiver(post_save, sender=PaymentReminder)
def process_reminder_sending(sender, instance, created, **kwargs):
    """
    ✅ SAFE: Process reminder sending
    """
    try:
        if created and instance.status == 'pending':
            # Mark as sent (actual SMS/Email integration would go here)
            instance.status = 'sent'
            
            post_save.disconnect(process_reminder_sending, sender=PaymentReminder)
            instance.save()
            post_save.connect(process_reminder_sending, sender=PaymentReminder)
    except Exception as e:
        logger.error(f"Error sending reminder {instance.id}: {e}")


# ==================== VALIDATION SIGNALS ====================

@receiver(pre_save, sender=Payment)
def validate_payment_before_save(sender, instance, **kwargs):
    """
    ✅ SAFE: Validate payment before saving
    """
    try:
        if instance.amount and instance.amount <= 0:
            raise ValueError("Payment amount must be greater than zero")
    except Exception as e:
        logger.error(f"Payment validation error: {e}")
        raise


@receiver(pre_save, sender=PaymentSchedule)
def validate_schedule_before_save(sender, instance, **kwargs):
    """
    ✅ SAFE: Validate payment schedule before saving
    """
    try:
        if instance.amount_due and instance.amount_due <= 0:
            raise ValueError("Schedule amount must be greater than zero")
        if instance.amount_paid and instance.amount_paid < 0:
            raise ValueError("Amount paid cannot be negative")
    except Exception as e:
        logger.error(f"Schedule validation error: {e}")
        raise


# ==================== LOGGING SIGNALS ====================

@receiver(post_save, sender=Payment)
def log_payment_activity(sender, instance, created, **kwargs):
    """
    ✅ SAFE: Log payment activity for audit trail
    """
    try:
        if created:
            from apps.audit.utils import log_audit
            
            log_audit(
                user=instance.recorded_by,
                action='create',
                model_name='Payment',
                description=f'Payment recorded: {instance.receipt_number} - KES {instance.amount:,.2f}'
            )
    except Exception as e:
        logger.warning(f"Could not create audit log: {e}")


@receiver(post_save, sender=Payment)
def update_statistics_cache(sender, instance, created, **kwargs):
    """
    ✅ SAFE: Update cached statistics
    """
    try:
        if created:
            _invalidate_dashboard_metric_cache()
    except Exception as e:
        logger.debug(f"Could not update statistics cache: {e}")