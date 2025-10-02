"""
Reports App - Background Tasks (Celery)
"""

from celery import shared_task
from django.utils import timezone
from django.core.mail import EmailMessage
from django.conf import settings
from datetime import timedelta
import logging
import os
import traceback

from .models import Report, ReportExecution, ReportSchedule
from .utils import (
    generate_financial_report_data,
    generate_vehicle_report_data,
    generate_client_report_data,
    generate_auction_report_data,
    generate_payment_report_data,
    generate_sales_report_data,
)

logger = logging.getLogger(__name__)


# ============================================================================
# REPORT EXECUTION TASKS
# ============================================================================

@shared_task(bind=True, max_retries=3)
def execute_report_task(self, execution_id):
    """
    Execute a report and generate output file
    
    Args:
        execution_id: ReportExecution UUID
    """
    
    try:
        execution = ReportExecution.objects.get(id=execution_id)
        report = execution.report
        
        logger.info(f"Starting execution of report: {report.name}")
        
        # Mark as started
        execution.mark_as_started()
        
        # Get date range
        date_from, date_to = execution.date_from, execution.date_to
        if not date_from or not date_to:
            date_from, date_to = report.get_date_range()
        
        # Generate report data based on type
        data = generate_report_data(report.report_type, date_from, date_to, report.query_config)
        
        # Generate output file
        from .generators import generate_report_file
        file_path, file_size = generate_report_file(
            report=report,
            data=data,
            output_format=execution.output_format,
            date_from=date_from,
            date_to=date_to
        )
        
        # Store result data summary
        execution.result_data = {
            'summary': data.get('summary', {}),
            'row_count': len(data.get('items', [])) if 'items' in data else 0,
        }
        execution.row_count = execution.result_data.get('row_count', 0)
        
        # Mark as completed
        execution.mark_as_completed(
            file_path=file_path,
            file_size=file_size,
            row_count=execution.row_count
        )
        
        logger.info(f"Completed execution of report: {report.name}")
        
        # Send email if configured
        if report.send_email and report.get_email_recipients_list():
            send_report_email.delay(str(execution.id))
        
        return {
            'status': 'completed',
            'execution_id': str(execution_id),
            'file_path': file_path
        }
    
    except ReportExecution.DoesNotExist:
        logger.error(f"ReportExecution {execution_id} not found")
        return {'status': 'error', 'message': 'Execution not found'}
    
    except Exception as e:
        logger.error(f"Error executing report: {e}")
        logger.error(traceback.format_exc())
        
        try:
            execution = ReportExecution.objects.get(id=execution_id)
            execution.mark_as_failed(
                error_message=str(e),
                stack_trace=traceback.format_exc()
            )
        except:
            pass
        
        # Retry
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {'status': 'failed', 'error': str(e)}


def generate_report_data(report_type, date_from, date_to, query_config=None):
    """
    Generate report data based on type
    
    Args:
        report_type: Type of report
        date_from: Start date
        date_to: End date
        query_config: Additional query configuration
    
    Returns:
        dict: Report data
    """
    
    generators = {
        'financial': generate_financial_report_data,
        'vehicle': generate_vehicle_report_data,
        'client': generate_client_report_data,
        'auction': generate_auction_report_data,
        'payment': generate_payment_report_data,
        'sales': generate_sales_report_data,
    }
    
    generator = generators.get(report_type)
    
    if generator:
        return generator(date_from, date_to)
    else:
        # Generic report generation
        return {
            'summary': {},
            'items': [],
        }


# ============================================================================
# REPORT EMAIL TASKS
# ============================================================================

@shared_task(bind=True, max_retries=3)
def send_report_email(self, execution_id):
    """
    Send report via email
    
    Args:
        execution_id: ReportExecution UUID
    """
    
    try:
        execution = ReportExecution.objects.get(id=execution_id)
        report = execution.report
        
        if execution.status != 'completed' or not execution.file_path:
            logger.warning(f"Cannot send email for incomplete execution: {execution_id}")
            return {'status': 'skipped', 'reason': 'Execution not completed'}
        
        # Get recipients
        recipients = report.get_email_recipients_list()
        if not recipients:
            logger.warning(f"No recipients for report: {report.name}")
            return {'status': 'skipped', 'reason': 'No recipients'}
        
        # Prepare email
        subject = f"Report: {report.name}"
        
        body = f"""
Hello,

Your scheduled report "{report.name}" has been generated.

Report Period: {execution.date_from} to {execution.date_to}
Generated: {execution.completed_at.strftime('%Y-%m-%d %H:%M:%S')}
Execution Time: {execution.execution_time:.2f} seconds

Please find the report attached.

Best regards,
Vehicle Management System
        """
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients
        )
        
        # Attach report file
        if os.path.exists(execution.file_path):
            filename = f"{report.name}_{execution.created_at.strftime('%Y%m%d')}.{execution.output_format}"
            email.attach_file(execution.file_path, mimetype=get_mimetype(execution.output_format))
        
        email.send()
        
        logger.info(f"Sent report email to {len(recipients)} recipient(s)")
        
        return {
            'status': 'sent',
            'execution_id': str(execution_id),
            'recipients': len(recipients)
        }
    
    except ReportExecution.DoesNotExist:
        logger.error(f"ReportExecution {execution_id} not found")
        return {'status': 'error', 'message': 'Execution not found'}
    
    except Exception as e:
        logger.error(f"Error sending report email: {e}")
        
        # Retry
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {'status': 'failed', 'error': str(e)}


# ============================================================================
# SCHEDULED REPORT TASKS
# ============================================================================

@shared_task
def process_scheduled_reports():
    """
    Process scheduled reports that are due
    Scheduled to run every 5 minutes
    """
    
    now = timezone.now()
    
    # Get reports due for execution
    due_reports = Report.objects.filter(
        is_active=True,
        is_scheduled=True,
        next_run__lte=now
    )
    
    count = 0
    
    for report in due_reports:
        try:
            # Create execution record
            execution = ReportExecution.objects.create(
                report=report,
                is_scheduled=True,
                output_format=report.output_format,
                date_from=report.get_date_range()[0],
                date_to=report.get_date_range()[1]
            )
            
            # Queue execution
            execute_report_task.delay(str(execution.id))
            
            # Update next run time
            report.next_run = report.calculate_next_run()
            report.save(update_fields=['next_run'])
            
            count += 1
            
            logger.info(f"Queued scheduled report: {report.name}")
        
        except Exception as e:
            logger.error(f"Error processing scheduled report {report.name}: {e}")
    
    logger.info(f"Processed {count} scheduled reports")
    
    return {'status': 'completed', 'processed': count}


# ============================================================================
# CLEANUP TASKS
# ============================================================================

@shared_task
def cleanup_old_report_files():
    """
    Clean up old report files
    Scheduled to run daily
    """
    
    # Delete files older than 90 days
    cutoff = timezone.now() - timedelta(days=90)
    
    old_executions = ReportExecution.objects.filter(
        completed_at__lt=cutoff,
        status='completed'
    )
    
    count = 0
    deleted_size = 0
    
    for execution in old_executions:
        if execution.file_path and os.path.exists(execution.file_path):
            try:
                file_size = os.path.getsize(execution.file_path)
                os.remove(execution.file_path)
                deleted_size += file_size
                count += 1
                
                # Clear file path in database
                execution.file_path = ''
                execution.save(update_fields=['file_path'])
            
            except Exception as e:
                logger.error(f"Error deleting file {execution.file_path}: {e}")
    
    logger.info(f"Cleaned up {count} old report files ({deleted_size / 1024 / 1024:.2f} MB)")
    
    return {
        'status': 'completed',
        'files_deleted': count,
        'size_deleted_mb': deleted_size / 1024 / 1024
    }


@shared_task
def cleanup_old_executions():
    """
    Clean up old execution records
    Scheduled to run weekly
    """
    
    # Delete execution records older than 1 year
    cutoff = timezone.now() - timedelta(days=365)
    
    count = ReportExecution.objects.filter(
        created_at__lt=cutoff
    ).delete()[0]
    
    logger.info(f"Cleaned up {count} old execution records")
    
    return {'status': 'completed', 'deleted': count}


# ============================================================================
# STATISTICS TASKS
# ============================================================================

@shared_task
def update_report_statistics():
    """
    Update cached report statistics
    Scheduled to run hourly
    """
    
    from django.core.cache import cache
    
    reports = Report.objects.filter(is_active=True)
    
    for report in reports:
        try:
            from .utils import calculate_report_statistics
            stats = calculate_report_statistics(report)
            
            # Cache for 1 hour
            cache.set(f'report_stats_{report.id}', stats, timeout=3600)
        
        except Exception as e:
            logger.error(f"Error updating stats for report {report.name}: {e}")
    
    logger.info(f"Updated statistics for {reports.count()} reports")
    
    return {'status': 'completed', 'updated': reports.count()}


@shared_task
def generate_system_report():
    """
    Generate daily system usage report
    Scheduled to run daily at midnight
    """
    
    yesterday = timezone.now().date() - timedelta(days=1)
    
    # Get statistics
    executions = ReportExecution.objects.filter(
        created_at__date=yesterday
    )
    
    stats = {
        'date': yesterday.isoformat(),
        'total_executions': executions.count(),
        'successful': executions.filter(status='completed').count(),
        'failed': executions.filter(status='failed').count(),
        'total_execution_time': sum(
            float(e.execution_time or 0) for e in executions if e.execution_time
        ),
        'reports_run': executions.values('report').distinct().count(),
    }
    
    logger.info(f"System report for {yesterday}: {stats}")
    
    # TODO: Send to admins or store in database
    
    return stats


# ============================================================================
# RETRY TASKS
# ============================================================================

@shared_task
def retry_failed_executions():
    """
    Retry failed report executions
    Scheduled to run every 6 hours
    """
    
    # Get failed executions from last 24 hours
    yesterday = timezone.now() - timedelta(days=1)
    
    failed = ReportExecution.objects.filter(
        status='failed',
        created_at__gte=yesterday
    )
    
    count = 0
    
    for execution in failed:
        try:
            # Create new execution
            new_execution = ReportExecution.objects.create(
                report=execution.report,
                triggered_by=execution.triggered_by,
                is_scheduled=execution.is_scheduled,
                output_format=execution.output_format,
                date_from=execution.date_from,
                date_to=execution.date_to
            )
            
            # Queue execution
            execute_report_task.delay(str(new_execution.id))
            
            count += 1
        
        except Exception as e:
            logger.error(f"Error retrying execution {execution.id}: {e}")
    
    logger.info(f"Retried {count} failed executions")
    
    return {'status': 'completed', 'retried': count}


# ============================================================================
# NOTIFICATION TASKS
# ============================================================================

@shared_task
def notify_report_completion(execution_id):
    """
    Send notification when report completes
    
    Args:
        execution_id: ReportExecution UUID
    """
    
    try:
        execution = ReportExecution.objects.get(id=execution_id)
        
        if execution.triggered_by:
            from apps.notifications.utils import create_notification
            
            create_notification(
                user=execution.triggered_by,
                title='Report Completed',
                message=f'Your report "{execution.report.name}" has been generated successfully.',
                notification_type='report',
                priority='medium',
                action_text='Download Report',
                action_url=f'/reports/execution/{execution.id}/',
                related_object_type='report_execution',
                related_object_id=execution.id
            )
        
        return {'status': 'sent'}
    
    except ReportExecution.DoesNotExist:
        logger.error(f"ReportExecution {execution_id} not found")
        return {'status': 'error'}
    
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def notify_report_failure(execution_id):
    """
    Send notification when report fails
    
    Args:
        execution_id: ReportExecution UUID
    """
    
    try:
        execution = ReportExecution.objects.get(id=execution_id)
        
        if execution.triggered_by:
            from apps.notifications.utils import create_notification
            
            create_notification(
                user=execution.triggered_by,
                title='Report Failed',
                message=f'Report "{execution.report.name}" failed to generate. Error: {execution.error_message}',
                notification_type='error',
                priority='high',
                action_text='View Details',
                action_url=f'/reports/execution/{execution.id}/',
                related_object_type='report_execution',
                related_object_id=execution.id
            )
        
        return {'status': 'sent'}
    
    except ReportExecution.DoesNotExist:
        logger.error(f"ReportExecution {execution_id} not found")
        return {'status': 'error'}
    
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return {'status': 'error', 'message': str(e)}


# ============================================================================
# EXPORT TASKS
# ============================================================================

@shared_task
def export_report_data(execution_id, export_format='csv'):
    """
    Export report data to different format
    
    Args:
        execution_id: ReportExecution UUID
        export_format: Export format (csv, json, excel)
    """
    
    try:
        execution = ReportExecution.objects.get(id=execution_id)
        
        # Generate export file
        from .generators import export_report_data as generate_export
        file_path = generate_export(execution, export_format)
        
        return {
            'status': 'completed',
            'file_path': file_path
        }
    
    except ReportExecution.DoesNotExist:
        logger.error(f"ReportExecution {execution_id} not found")
        return {'status': 'error'}
    
    except Exception as e:
        logger.error(f"Error exporting report data: {e}")
        return {'status': 'error', 'message': str(e)}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_mimetype(output_format):
    """Get MIME type for output format"""
    
    mimetypes = {
        'pdf': 'application/pdf',
        'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'csv': 'text/csv',
        'json': 'application/json',
        'html': 'text/html',
    }
    
    return mimetypes.get(output_format, 'application/octet-stream')