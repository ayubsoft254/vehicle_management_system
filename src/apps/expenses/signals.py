"""
Signal handlers for the expenses app.
Handles automatic processing, notifications, and audit logging.
"""

from django.db.models.signals import post_save, pre_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.core.files.storage import default_storage

from .models import (
    Expense, ExpenseCategory, ExpenseReceipt, ExpenseReport,
    RecurringExpense, ExpenseApprovalWorkflow
)
from .utils import (
    notify_expense_submitted, notify_expense_approved,
    notify_expense_rejected, notify_budget_threshold,
    calculate_budget_status
)


# ============================================================================
# Expense Signals
# ============================================================================

@receiver(pre_save, sender=Expense)
def expense_pre_save(sender, instance, **kwargs):
    """
    Process expense before saving.
    - Calculate total amount
    - Track status changes
    """
    # Calculate total amount
    instance.total_amount = instance.amount + instance.tax_amount
    
    # Track status changes for notifications
    if instance.pk:
        try:
            old_instance = Expense.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Expense.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Expense)
def expense_post_save(sender, instance, created, **kwargs):
    """
    Process expense after saving.
    - Send notifications on status changes
    - Update timestamps
    - Check budget thresholds
    """
    if created:
        # Log expense creation
        print(f"Expense created: {instance.title} by {instance.submitted_by}")
        
        # Create audit log if audit app available
        try:
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=instance.submitted_by,
                action='expense_created',
                model_name='Expense',
                object_id=instance.pk,
                details={
                    'title': instance.title,
                    'amount': str(instance.total_amount),
                    'category': instance.category.name if instance.category else None,
                }
            )
        except ImportError:
            pass
        except Exception as e:
            print(f"Error creating audit log: {e}")
    
    else:
        # Check for status changes
        old_status = getattr(instance, '_old_status', None)
        
        if old_status and old_status != instance.status:
            handle_expense_status_change(instance, old_status, instance.status)
    
    # Check budget threshold after saving approved expenses
    if instance.status == 'APPROVED' and instance.category:
        budget_status = calculate_budget_status(instance.category)
        if budget_status and budget_status['percentage'] >= 80:
            try:
                notify_budget_threshold(instance.category)
            except Exception as e:
                print(f"Error sending budget notification: {e}")


@receiver(post_delete, sender=Expense)
def expense_post_delete(sender, instance, **kwargs):
    """
    Cleanup after expense deletion.
    - Log deletion
    """
    # Create audit log
    try:
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=instance.submitted_by if hasattr(instance, 'submitted_by') else None,
            action='expense_deleted',
            model_name='Expense',
            object_id=instance.pk,
            details={
                'title': instance.title,
                'amount': str(instance.total_amount),
                'status': instance.status,
            }
        )
    except ImportError:
        pass
    except Exception as e:
        print(f"Error creating deletion audit log: {e}")
    
    print(f"Expense deleted: {instance.title}")


def handle_expense_status_change(expense, old_status, new_status):
    """
    Handle status change notifications and logging.
    """
    # Send notifications based on status change
    try:
        if new_status == 'SUBMITTED':
            notify_expense_submitted(expense)
            print(f"Expense submitted for approval: {expense.title}")
        
        elif new_status == 'APPROVED':
            notify_expense_approved(expense)
            print(f"Expense approved: {expense.title}")
        
        elif new_status == 'REJECTED':
            notify_expense_rejected(expense)
            print(f"Expense rejected: {expense.title}")
        
        elif new_status == 'PAID':
            print(f"Expense marked as paid: {expense.title}")
    
    except Exception as e:
        print(f"Error sending notification: {e}")
    
    # Create audit log for status change
    try:
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=expense.approved_by if expense.approved_by else expense.submitted_by,
            action='expense_status_changed',
            model_name='Expense',
            object_id=expense.pk,
            details={
                'title': expense.title,
                'old_status': old_status,
                'new_status': new_status,
                'amount': str(expense.total_amount),
            }
        )
    except ImportError:
        pass
    except Exception as e:
        print(f"Error creating status change audit log: {e}")


# ============================================================================
# Expense Receipt Signals
# ============================================================================

@receiver(pre_save, sender=ExpenseReceipt)
def receipt_pre_save(sender, instance, **kwargs):
    """
    Process receipt before saving.
    - Extract file metadata
    """
    if instance.file:
        if not instance.file_name:
            instance.file_name = instance.file.name
        
        if not instance.file_size:
            instance.file_size = instance.file.size
        
        if not instance.file_type:
            instance.file_type = instance.file.content_type


@receiver(post_save, sender=ExpenseReceipt)
def receipt_post_save(sender, instance, created, **kwargs):
    """
    Process receipt after saving.
    - Update expense timestamp
    - Log receipt upload
    """
    if created:
        # Update parent expense's updated_at
        instance.expense.updated_at = timezone.now()
        instance.expense.save(update_fields=['updated_at'])
        
        print(f"Receipt uploaded for expense: {instance.expense.title}")
        
        # Create audit log
        try:
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=instance.uploaded_by,
                action='receipt_uploaded',
                model_name='ExpenseReceipt',
                object_id=instance.pk,
                details={
                    'expense_title': instance.expense.title,
                    'file_name': instance.file_name,
                    'file_size': instance.file_size,
                }
            )
        except ImportError:
            pass
        except Exception as e:
            print(f"Error creating receipt audit log: {e}")


@receiver(post_delete, sender=ExpenseReceipt)
def receipt_post_delete(sender, instance, **kwargs):
    """
    Cleanup after receipt deletion.
    - Delete file from storage
    """
    if instance.file:
        try:
            if default_storage.exists(instance.file.name):
                default_storage.delete(instance.file.name)
                print(f"Deleted receipt file: {instance.file.name}")
        except Exception as e:
            print(f"Error deleting receipt file: {e}")


# ============================================================================
# Expense Category Signals
# ============================================================================

@receiver(post_save, sender=ExpenseCategory)
def category_post_save(sender, instance, created, **kwargs):
    """
    Process category after saving.
    - Check budget status if limit changed
    """
    if not created and instance.budget_limit:
        # Check if we're near or over budget
        budget_status = calculate_budget_status(instance)
        if budget_status and budget_status['percentage'] >= 80:
            print(f"Category {instance.name} is at {budget_status['percentage']}% of budget")


# ============================================================================
# Expense Report Signals
# ============================================================================

@receiver(post_save, sender=ExpenseReport)
def report_post_save(sender, instance, created, **kwargs):
    """
    Process report after saving.
    - Log report creation
    """
    if created:
        print(f"Expense report created: {instance.report_number} by {instance.submitted_by}")
        
        # Create audit log
        try:
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=instance.submitted_by,
                action='report_created',
                model_name='ExpenseReport',
                object_id=instance.pk,
                details={
                    'report_number': instance.report_number,
                    'title': instance.title,
                    'date_range': f"{instance.start_date} to {instance.end_date}",
                }
            )
        except ImportError:
            pass
        except Exception as e:
            print(f"Error creating report audit log: {e}")


# ============================================================================
# Recurring Expense Signals
# ============================================================================

@receiver(post_save, sender=RecurringExpense)
def recurring_expense_post_save(sender, instance, created, **kwargs):
    """
    Process recurring expense after saving.
    - Log creation
    """
    if created:
        print(f"Recurring expense created: {instance.title} ({instance.get_frequency_display()})")
        
        # Create audit log
        try:
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=instance.submitted_by,
                action='recurring_expense_created',
                model_name='RecurringExpense',
                object_id=instance.pk,
                details={
                    'title': instance.title,
                    'frequency': instance.frequency,
                    'amount': str(instance.amount),
                }
            )
        except ImportError:
            pass
        except Exception as e:
            print(f"Error creating recurring expense audit log: {e}")


# ============================================================================
# Expense Tag Signals
# ============================================================================

@receiver(m2m_changed, sender=Expense.tags.through)
def expense_tags_changed(sender, instance, action, **kwargs):
    """
    Process tag changes on expenses.
    - Update expense timestamp
    """
    if action in ['post_add', 'post_remove', 'post_clear']:
        # Update expense's updated_at
        instance.updated_at = timezone.now()
        instance.save(update_fields=['updated_at'])
        
        if action == 'post_add':
            print(f"Tags added to expense: {instance.title}")
        elif action == 'post_remove':
            print(f"Tags removed from expense: {instance.title}")
        elif action == 'post_clear':
            print(f"All tags cleared from expense: {instance.title}")


# ============================================================================
# Approval Workflow Signals
# ============================================================================

@receiver(post_save, sender=ExpenseApprovalWorkflow)
def approval_workflow_post_save(sender, instance, created, **kwargs):
    """
    Process approval workflow after saving.
    - Log approval actions
    - Update expense status if needed
    """
    if created:
        print(f"Approval workflow created: Level {instance.level} for {instance.expense.title}")
    
    elif instance.status in ['APPROVED', 'REJECTED']:
        print(f"Approval action: {instance.status} by {instance.approver} for {instance.expense.title}")
        
        # Create audit log
        try:
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=instance.approver,
                action=f'expense_{instance.status.lower()}',
                model_name='Expense',
                object_id=instance.expense.pk,
                details={
                    'expense_title': instance.expense.title,
                    'level': instance.level,
                    'comments': instance.comments,
                }
            )
        except ImportError:
            pass
        except Exception as e:
            print(f"Error creating approval audit log: {e}")


# ============================================================================
# Automatic Expense Processing
# ============================================================================

@receiver(post_save, sender=Expense)
def auto_create_approval_workflow(sender, instance, created, **kwargs):
    """
    Automatically create approval workflow when expense is submitted.
    """
    if instance.status == 'SUBMITTED' and instance.category.requires_approval:
        # Check if approval workflow already exists
        if not instance.approval_workflow.exists():
            # Get users with approval permission
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            approvers = User.objects.filter(
                is_active=True,
                user_permissions__codename='approve_expense'
            ) | User.objects.filter(
                is_active=True,
                groups__permissions__codename='approve_expense'
            )
            
            approvers = approvers.distinct()
            
            # Create approval workflow entries
            level = 1
            for approver in approvers[:3]:  # Limit to first 3 approvers
                ExpenseApprovalWorkflow.objects.create(
                    expense=instance,
                    approver=approver,
                    level=level,
                    status='PENDING'
                )
                level += 1
            
            print(f"Approval workflow created for expense: {instance.title}")


# ============================================================================
# Budget Monitoring
# ============================================================================

@receiver(post_save, sender=Expense)
def monitor_category_budget(sender, instance, created, **kwargs):
    """
    Monitor category budget when expenses are approved.
    """
    if instance.status == 'APPROVED' and instance.category and instance.category.budget_limit:
        budget_status = calculate_budget_status(instance.category)
        
        if budget_status:
            if budget_status['is_over_budget']:
                print(f"⚠️  BUDGET EXCEEDED: {instance.category.name} is over budget!")
                # Send urgent notification
                try:
                    notify_budget_threshold(instance.category, percentage=100)
                except Exception as e:
                    print(f"Error sending budget exceeded notification: {e}")
            
            elif budget_status['is_near_limit']:
                print(f"⚠️  BUDGET WARNING: {instance.category.name} is at {budget_status['percentage']}% of budget")


# ============================================================================
# Reimbursement Tracking
# ============================================================================

@receiver(post_save, sender=Expense)
def track_reimbursement_status(sender, instance, created, **kwargs):
    """
    Track when expenses are marked as reimbursed.
    """
    if not created and instance.reimbursed and instance.is_reimbursable:
        old_instance = Expense.objects.filter(pk=instance.pk).first()
        if old_instance and not old_instance.reimbursed:
            print(f"Expense reimbursed: {instance.title} - {instance.currency} {instance.total_amount}")
            
            # Send notification to user
            if instance.submitted_by.email:
                from django.core.mail import send_mail
                from django.conf import settings
                
                try:
                    send_mail(
                        f"Reimbursement Processed: {instance.title}",
                        f"""
Your expense has been reimbursed.

Expense: {instance.title}
Amount: {instance.currency} {instance.total_amount}
Reimbursement Date: {instance.reimbursement_date}
Reference: {instance.reimbursement_reference or 'N/A'}

Thank you.
                        """,
                        settings.DEFAULT_FROM_EMAIL,
                        [instance.submitted_by.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"Error sending reimbursement notification: {e}")


# ============================================================================
# Data Integrity Signals
# ============================================================================

@receiver(pre_save, sender=Expense)
def validate_expense_data(sender, instance, **kwargs):
    """
    Validate expense data before saving.
    """
    # Ensure approved expenses have an approver
    if instance.status == 'APPROVED' and not instance.approved_by:
        print(f"Warning: Approved expense {instance.title} has no approver set")
    
    # Ensure rejected expenses have a reason
    if instance.status == 'REJECTED' and not instance.rejection_reason:
        print(f"Warning: Rejected expense {instance.title} has no rejection reason")
    
    # Ensure reimbursed expenses are marked as paid
    if instance.reimbursed and instance.status != 'PAID':
        print(f"Warning: Reimbursed expense {instance.title} is not marked as paid")


# ============================================================================
# Integration Signals
# ============================================================================

@receiver(post_save, sender=Expense)
def sync_expense_with_external_systems(sender, instance, created, **kwargs):
    """
    Sync expense data with external systems.
    Placeholder for integrations with accounting software, etc.
    """
    # TODO: Implement external system integrations
    # Examples:
    # - Sync with QuickBooks/Xero
    # - Update accounting ledger
    # - Sync with payroll system for reimbursements
    # - Push to data warehouse for analytics
    pass


@receiver(post_save, sender=ExpenseReport)
def sync_report_with_external_systems(sender, instance, created, **kwargs):
    """
    Sync expense reports with external systems.
    """
    # TODO: Implement report integrations
    # Examples:
    # - Generate PDF reports
    # - Send to accounting system
    # - Archive in document management system
    pass


# ============================================================================
# Signal Connection
# ============================================================================

# All signals are automatically connected via @receiver decorator
# To disconnect a signal for testing:
# post_save.disconnect(expense_post_save, sender=Expense)

# To manually connect a signal:
# post_save.connect(expense_post_save, sender=Expense)