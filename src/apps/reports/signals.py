"""
Reports App - Signal Handlers
"""

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import Report, ReportExecution, ReportTemplate, SavedReport
from apps.audit.models import AuditLog


# ============================================================================
# REPORT SIGNALS
# ============================================================================

@receiver(post_save, sender=Report)
def report_post_save(sender, instance, created, **kwargs):
    """Handle actions after report is saved"""
    
    if created:
        handle_new_report(instance)
    else:
        handle_report_update(instance)


def handle_new_report(report):
    """Handle new report creation"""
    
    # Calculate initial next_run if scheduled
    if report.is_scheduled and not report.next_run:
        report.next_run = report.calculate_next_run()
        report.save(update_fields=['next_run'])
    
    # Create audit log
    if report.created_by:
        AuditLog.objects.create(
            user=report.created_by,
            action='CREATE',
            model_name='Report',
            object_id=report.id,
            object_repr=str(report),
            changes={
                'name': report.name,
                'report_type': report.report_type,
                'is_scheduled': report.is_scheduled,
                'output_format': report.output_format,
            }
        )


def handle_report_update(report):
    """Handle report updates"""
    
    # Update next_run if scheduling changed
    if report.is_scheduled and hasattr(report, '_schedule_changed'):
        report.next_run = report.calculate_next_run()
        report.save(update_fields=['next_run'])
    
    # Create audit log
    if hasattr(report, '_changed_by'):
        AuditLog.objects.create(
            user=report._changed_by,
            action='UPDATE',
            model_name='Report',
            object_id=report.id,
            object_repr=str(report),
            changes={
                'updated_at': str(timezone.now())
            }
        )


@receiver(pre_save, sender=Report)
def report_pre_save(sender, instance, **kwargs):
    """Handle actions before report is saved"""
    
    if instance.pk:
        try:
            old_instance = Report.objects.get(pk=instance.pk)
            
            # Track if scheduling changed
            if (old_instance.is_scheduled != instance.is_scheduled or
                old_instance.frequency != instance.frequency or
                old_instance.schedule_time != instance.schedule_time):
                instance._schedule_changed = True
        
        except Report.DoesNotExist:
            pass


@receiver(post_delete, sender=Report)
def report_post_delete(sender, instance, **kwargs):
    """Handle actions after report is deleted"""
    
    # Create audit log
    if hasattr(instance, '_deleted_by'):
        AuditLog.objects.create(
            user=instance._deleted_by,
            action='DELETE',
            model_name='Report',
            object_id=instance.id,
            object_repr=str(instance),
            changes={
                'name': instance.name,
                'deleted_at': str(timezone.now())
            }
        )


# ============================================================================
# REPORT EXECUTION SIGNALS
# ============================================================================

@receiver(post_save, sender=ReportExecution)
def execution_post_save(sender, instance, created, **kwargs):
    """Handle actions after execution is saved"""
    
    if created:
        handle_new_execution(instance)
    else:
        handle_execution_update(instance)


def handle_new_execution(execution):
    """Handle new execution creation"""
    
    # Send notification to triggered user
    if execution.triggered_by:
        from apps.notifications.utils import create_notification
        
        create_notification(
            user=execution.triggered_by,
            title='Report Execution Started',
            message=f'Report "{execution.report.name}" is being generated.',
            notification_type='info',
            priority='low',
            related_object_type='report_execution',
            related_object_id=execution.id
        )


def handle_execution_update(execution):
    """Handle execution status updates"""
    
    # Check if status changed to completed
    if hasattr(execution, '_previous_status'):
        if execution.status == 'completed' and execution._previous_status != 'completed':
            handle_execution_completed(execution)
        elif execution.status == 'failed' and execution._previous_status != 'failed':
            handle_execution_failed(execution)


def handle_execution_completed(execution):
    """Handle completed execution"""
    
    # Send notification
    if execution.triggered_by:
        from apps.notifications.utils import create_notification
        
        create_notification(
            user=execution.triggered_by,
            title='Report Ready',
            message=f'Your report "{execution.report.name}" has been generated successfully.',
            notification_type='success',
            priority='medium',
            action_text='Download Report',
            action_url=f'/reports/execution/{execution.id}/download/',
            related_object_type='report_execution',
            related_object_id=execution.id
        )
    
    # Notify report creator if different from triggered user
    if execution.report.created_by and execution.report.created_by != execution.triggered_by:
        from apps.notifications.utils import create_notification
        
        create_notification(
            user=execution.report.created_by,
            title='Report Executed',
            message=f'Report "{execution.report.name}" was executed by {execution.triggered_by.get_full_name() if execution.triggered_by else "System"}.',
            notification_type='info',
            priority='low',
            related_object_type='report_execution',
            related_object_id=execution.id
        )


def handle_execution_failed(execution):
    """Handle failed execution"""
    
    # Send notification
    if execution.triggered_by:
        from apps.notifications.utils import create_notification
        
        create_notification(
            user=execution.triggered_by,
            title='Report Generation Failed',
            message=f'Failed to generate report "{execution.report.name}". Error: {execution.error_message}',
            notification_type='error',
            priority='high',
            action_text='View Details',
            action_url=f'/reports/execution/{execution.id}/',
            related_object_type='report_execution',
            related_object_id=execution.id
        )
    
    # Notify admins for scheduled report failures
    if execution.is_scheduled:
        from django.contrib.auth import get_user_model
        from apps.notifications.utils import create_notification
        
        User = get_user_model()
        admins = User.objects.filter(is_staff=True, is_active=True)
        
        for admin in admins:
            create_notification(
                user=admin,
                title='Scheduled Report Failed',
                message=f'Scheduled report "{execution.report.name}" failed to execute.',
                notification_type='error',
                priority='high',
                action_text='View Details',
                action_url=f'/reports/execution/{execution.id}/',
                related_object_type='report_execution',
                related_object_id=execution.id
            )


@receiver(pre_save, sender=ReportExecution)
def execution_pre_save(sender, instance, **kwargs):
    """Handle actions before execution is saved"""
    
    if instance.pk:
        try:
            old_instance = ReportExecution.objects.get(pk=instance.pk)
            instance._previous_status = old_instance.status
        except ReportExecution.DoesNotExist:
            pass


# ============================================================================
# REPORT TEMPLATE SIGNALS
# ============================================================================

@receiver(post_save, sender=ReportTemplate)
def template_post_save(sender, instance, created, **kwargs):
    """Handle actions after template is saved"""
    
    if created:
        # Create audit log
        if instance.created_by:
            AuditLog.objects.create(
                user=instance.created_by,
                action='CREATE',
                model_name='ReportTemplate',
                object_id=instance.id,
                object_repr=str(instance),
                changes={
                    'name': instance.name,
                    'report_type': instance.report_type,
                }
            )


@receiver(post_delete, sender=ReportTemplate)
def template_post_delete(sender, instance, **kwargs):
    """Handle actions after template is deleted"""
    
    # Create audit log
    if hasattr(instance, '_deleted_by'):
        AuditLog.objects.create(
            user=instance._deleted_by,
            action='DELETE',
            model_name='ReportTemplate',
            object_id=instance.id,
            object_repr=str(instance),
            changes={
                'name': instance.name,
                'deleted_at': str(timezone.now())
            }
        )


# ============================================================================
# SAVED REPORT SIGNALS
# ============================================================================

@receiver(post_save, sender=SavedReport)
def saved_report_post_save(sender, instance, created, **kwargs):
    """Handle actions after saved report is created"""
    
    if created:
        # Send notification
        from apps.notifications.utils import create_notification
        
        create_notification(
            user=instance.user,
            title='Report Saved',
            message=f'Report "{instance.report.name}" has been added to your favorites.',
            notification_type='info',
            priority='low',
            action_text='View Report',
            action_url=f'/reports/{instance.report.id}/',
            related_object_type='report',
            related_object_id=instance.report.id
        )


@receiver(post_delete, sender=SavedReport)
def saved_report_post_delete(sender, instance, **kwargs):
    """Handle actions after saved report is deleted"""
    
    # No action needed
    pass


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def notify_report_recipients(report, execution):
    """
    Notify all report recipients when execution completes
    
    Args:
        report: Report instance
        execution: ReportExecution instance
    """
    
    from apps.notifications.utils import create_notification
    
    recipients = report.recipients.all()
    
    for recipient in recipients:
        if recipient != execution.triggered_by:
            create_notification(
                user=recipient,
                title=f'Report Available: {report.name}',
                message=f'The report "{report.name}" has been generated and is available for download.',
                notification_type='info',
                priority='medium',
                action_text='Download Report',
                action_url=f'/reports/execution/{execution.id}/download/',
                related_object_type='report_execution',
                related_object_id=execution.id
            )