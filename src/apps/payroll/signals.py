"""
Signal handlers for the payroll app.
Handles automatic processing, notifications, and audit logging.
"""

from django.db.models.signals import post_save, pre_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    Employee, SalaryStructure, Commission, Deduction,
    PayrollRun, Payslip, Attendance, Leave, Loan
)
from .utils import (
    notify_payslip_ready, notify_leave_decision,
    calculate_leave_balance
)


# ============================================================================
# Employee Signals
# ============================================================================

@receiver(post_save, sender=Employee)
def employee_post_save(sender, instance, created, **kwargs):
    """
    Process employee after saving.
    - Send welcome email on creation
    - Log employee changes
    """
    if created:
        print(f"New employee created: {instance.get_full_name()} ({instance.employee_id})")
        
        # Send welcome email
        if instance.email:
            try:
                subject = f"Welcome to the Team - {instance.get_full_name()}"
                message = f"""
Dear {instance.get_full_name()},

Welcome to {instance.department}!

Your employee details:
Employee ID: {instance.employee_id}
Job Title: {instance.job_title}
Department: {instance.department}
Start Date: {instance.hire_date}

Please contact HR if you have any questions.

Best regards,
HR Department
                """
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [instance.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Error sending welcome email: {e}")
        
        # Create audit log
        try:
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=instance.user,
                action='employee_created',
                model_name='Employee',
                object_id=instance.pk,
                details={
                    'employee_id': instance.employee_id,
                    'name': instance.get_full_name(),
                    'job_title': instance.job_title,
                    'department': instance.department,
                }
            )
        except ImportError:
            pass
        except Exception as e:
            print(f"Error creating audit log: {e}")


@receiver(pre_save, sender=Employee)
def employee_pre_save(sender, instance, **kwargs):
    """
    Process employee before saving.
    - Track status changes
    """
    if instance.pk:
        try:
            old_instance = Employee.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Employee.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Employee)
def track_employee_status_change(sender, instance, created, **kwargs):
    """
    Track employee status changes.
    """
    if not created:
        old_status = getattr(instance, '_old_status', None)
        
        if old_status and old_status != instance.status:
            print(f"Employee {instance.employee_id} status changed: {old_status} → {instance.status}")
            
            # Send notification for termination
            if instance.status == 'TERMINATED' and instance.email:
                try:
                    subject = "Employment Status Update"
                    message = f"""
Dear {instance.get_full_name()},

Your employment status has been updated to {instance.get_status_display()}.

Please contact HR for further information.

Best regards,
HR Department
                    """
                    
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [instance.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"Error sending status change email: {e}")


# ============================================================================
# Salary Structure Signals
# ============================================================================

@receiver(post_save, sender=SalaryStructure)
def salary_structure_post_save(sender, instance, created, **kwargs):
    """
    Process salary structure after saving.
    - Log salary changes
    - Notify employee of salary update
    """
    action = 'created' if created else 'updated'
    print(f"Salary structure {action} for {instance.employee.get_full_name()}")
    
    # Send notification to employee
    if not created and instance.employee.email:
        try:
            subject = "Salary Structure Updated"
            message = f"""
Dear {instance.employee.get_full_name()},

Your salary structure has been updated effective from {instance.effective_from}.

Basic Salary: {instance.currency} {instance.basic_salary:,.2f}
Gross Salary: {instance.currency} {instance.calculate_gross_salary():,.2f}

Please contact HR if you have any questions.

Best regards,
HR Department
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [instance.employee.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending salary update email: {e}")
    
    # Create audit log
    try:
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=instance.employee.user,
            action=f'salary_{action}',
            model_name='SalaryStructure',
            object_id=instance.pk,
            details={
                'employee': instance.employee.get_full_name(),
                'basic_salary': str(instance.basic_salary),
                'gross_salary': str(instance.calculate_gross_salary()),
                'effective_from': str(instance.effective_from),
            }
        )
    except ImportError:
        pass
    except Exception as e:
        print(f"Error creating audit log: {e}")


# ============================================================================
# Commission Signals
# ============================================================================

@receiver(post_save, sender=Commission)
def commission_post_save(sender, instance, created, **kwargs):
    """
    Process commission after saving.
    - Notify employee when approved
    """
    if created:
        print(f"Commission created: {instance.amount} for {instance.employee.get_full_name()}")
    
    # Check for status change to approved
    if not created and instance.status == 'APPROVED':
        if instance.employee.email:
            try:
                subject = "Commission Approved"
                message = f"""
Dear {instance.employee.get_full_name()},

Your commission has been approved!

Description: {instance.description}
Amount: KES {instance.amount:,.2f}
Commission Date: {instance.commission_date}
Payroll Month: {instance.payroll_month.strftime('%B %Y')}

This will be included in your {instance.payroll_month.strftime('%B %Y')} payslip.

Best regards,
HR Department
                """
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [instance.employee.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Error sending commission approval email: {e}")


# ============================================================================
# Deduction Signals
# ============================================================================

@receiver(post_save, sender=Deduction)
def deduction_post_save(sender, instance, created, **kwargs):
    """
    Process deduction after saving.
    - Notify employee about new deductions
    """
    if created and instance.employee.email:
        try:
            subject = "New Deduction Added"
            message = f"""
Dear {instance.employee.get_full_name()},

A new deduction has been added to your salary:

Type: {instance.get_deduction_type_display()}
Description: {instance.description}
Amount: {'{}%'.format(instance.amount) if instance.is_percentage else 'KES {:.2f}'.format(instance.amount)}
Start Date: {instance.start_date}
Frequency: {instance.get_frequency_display()}

Please contact HR if you have any questions.

Best regards,
HR Department
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [instance.employee.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending deduction notification: {e}")


# ============================================================================
# Payroll Run Signals
# ============================================================================

@receiver(post_save, sender=PayrollRun)
def payroll_run_post_save(sender, instance, created, **kwargs):
    """
    Process payroll run after saving.
    - Log payroll processing
    """
    if created:
        print(f"Payroll run created: {instance.payroll_number} for {instance.payroll_month.strftime('%B %Y')}")
    
    # Log status changes
    if instance.status == 'COMPLETED':
        print(f"Payroll completed: {instance.total_employees} employees, Total: KES {instance.total_net:,.2f}")
    
    elif instance.status == 'APPROVED':
        print(f"Payroll approved by {instance.approved_by}")
        
        # Notify all employees that payslips are ready
        for payslip in instance.payslips.all():
            try:
                notify_payslip_ready(payslip)
            except Exception as e:
                print(f"Error notifying employee {payslip.employee.employee_id}: {e}")


# ============================================================================
# Payslip Signals
# ============================================================================

@receiver(post_save, sender=Payslip)
def payslip_post_save(sender, instance, created, **kwargs):
    """
    Process payslip after saving.
    - Update payroll run totals
    """
    if created:
        print(f"Payslip generated for {instance.employee.get_full_name()}: Net KES {instance.net_salary:,.2f}")
    
    # Update loan repayment if applicable
    if instance.loan_repayment > 0:
        active_loans = instance.employee.loans.filter(status='ACTIVE')
        for loan in active_loans:
            if loan.balance > 0:
                # Update loan repayment
                payment = min(instance.loan_repayment, loan.balance)
                loan.amount_repaid += payment
                loan.save()
                
                # Check if loan is fully repaid
                if loan.balance <= 0:
                    loan.status = 'COMPLETED'
                    loan.actual_completion_date = timezone.now().date()
                    loan.save()
                    
                    print(f"Loan completed for {instance.employee.get_full_name()}")


@receiver(post_save, sender=Payslip)
def mark_commissions_as_paid(sender, instance, created, **kwargs):
    """
    Mark commissions as paid when payslip is generated.
    """
    if created and instance.commission_amount > 0:
        # Update commissions status to PAID
        commissions = Commission.objects.filter(
            employee=instance.employee,
            payroll_month=instance.payroll_run.payroll_month,
            status='APPROVED'
        )
        
        updated = commissions.update(status='PAID')
        print(f"Marked {updated} commission(s) as paid for {instance.employee.get_full_name()}")


# ============================================================================
# Attendance Signals
# ============================================================================

@receiver(post_save, sender=Attendance)
def attendance_post_save(sender, instance, created, **kwargs):
    """
    Process attendance after saving.
    - Track attendance patterns
    """
    if created:
        # Check for excessive absences
        from datetime import date, timedelta
        
        # Count absences in last 30 days
        thirty_days_ago = date.today() - timedelta(days=30)
        absences = Attendance.objects.filter(
            employee=instance.employee,
            attendance_date__gte=thirty_days_ago,
            status='ABSENT'
        ).count()
        
        if absences >= 5:
            print(f"⚠️  Warning: {instance.employee.get_full_name()} has {absences} absences in last 30 days")
            
            # TODO: Send notification to manager/HR


# ============================================================================
# Leave Signals
# ============================================================================

@receiver(post_save, sender=Leave)
def leave_post_save(sender, instance, created, **kwargs):
    """
    Process leave after saving.
    - Send notifications on status change
    - Update attendance records
    """
    if created:
        print(f"Leave request created: {instance.employee.get_full_name()} - {instance.get_leave_type_display()}")
        
        # Notify managers/approvers
        # TODO: Get managers and send notification
    
    # Check for status changes
    if not created and instance.status in ['APPROVED', 'REJECTED']:
        try:
            notify_leave_decision(instance)
        except Exception as e:
            print(f"Error sending leave decision notification: {e}")
        
        # If approved, create attendance records
        if instance.status == 'APPROVED':
            from datetime import timedelta
            current_date = instance.start_date
            
            while current_date <= instance.end_date:
                Attendance.objects.update_or_create(
                    employee=instance.employee,
                    attendance_date=current_date,
                    defaults={'status': 'ON_LEAVE'}
                )
                current_date += timedelta(days=1)
            
            print(f"Created attendance records for approved leave: {instance.employee.get_full_name()}")


# ============================================================================
# Loan Signals
# ============================================================================

@receiver(post_save, sender=Loan)
def loan_post_save(sender, instance, created, **kwargs):
    """
    Process loan after saving.
    - Notify employee on approval
    - Create deduction for repayment
    """
    if created:
        print(f"Loan application: {instance.employee.get_full_name()} - KES {instance.loan_amount:,.2f}")
    
    # Check for approval
    if not created and instance.status == 'APPROVED':
        print(f"Loan approved: {instance.employee.get_full_name()} - KES {instance.loan_amount:,.2f}")
        
        # Send notification
        if instance.employee.email:
            try:
                subject = "Loan Application Approved"
                message = f"""
Dear {instance.employee.get_full_name()},

Your loan application has been approved!

Loan Amount: KES {instance.loan_amount:,.2f}
Interest Rate: {instance.interest_rate}%
Monthly Repayment: KES {instance.monthly_repayment:,.2f}
Total Repayable: KES {instance.total_repayable:,.2f}

Disbursement Date: {instance.disbursement_date}
Repayment Start: {instance.repayment_start_date}

The monthly repayment will be deducted from your salary starting {instance.repayment_start_date.strftime('%B %Y')}.

Best regards,
HR Department
                """
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [instance.employee.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Error sending loan approval email: {e}")
        
        # Create automatic deduction
        try:
            Deduction.objects.create(
                employee=instance.employee,
                deduction_type='LOAN',
                description=f"Loan Repayment - {instance.pk}",
                amount=instance.monthly_repayment,
                frequency='MONTHLY',
                start_date=instance.repayment_start_date,
                end_date=instance.expected_completion_date,
                is_active=True,
                reference_number=f"LOAN-{instance.pk}",
                notes=f"Auto-generated deduction for loan #{instance.pk}"
            )
            print(f"Created automatic loan deduction for {instance.employee.get_full_name()}")
        except Exception as e:
            print(f"Error creating loan deduction: {e}")
        
        # Change status to ACTIVE
        instance.status = 'ACTIVE'
        instance.save(update_fields=['status'])


@receiver(post_save, sender=Loan)
def loan_completion_check(sender, instance, **kwargs):
    """
    Check if loan is completed.
    """
    if instance.status == 'ACTIVE' and instance.balance <= 0:
        instance.status = 'COMPLETED'
        instance.actual_completion_date = timezone.now().date()
        instance.save(update_fields=['status', 'actual_completion_date'])
        
        # Deactivate loan deduction
        loan_deductions = Deduction.objects.filter(
            employee=instance.employee,
            deduction_type='LOAN',
            reference_number=f"LOAN-{instance.pk}",
            is_active=True
        )
        loan_deductions.update(is_active=False)
        
        print(f"✓ Loan completed for {instance.employee.get_full_name()}")
        
        # Send completion notification
        if instance.employee.email:
            try:
                subject = "Loan Fully Repaid"
                message = f"""
Dear {instance.employee.get_full_name()},

Congratulations! Your loan has been fully repaid.

Original Amount: KES {instance.loan_amount:,.2f}
Total Repaid: KES {instance.amount_repaid:,.2f}
Completion Date: {instance.actual_completion_date}

Thank you for your timely repayments.

Best regards,
HR Department
                """
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [instance.employee.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Error sending loan completion email: {e}")


# ============================================================================
# Audit and Compliance Signals
# ============================================================================

@receiver(post_save, sender=PayrollRun)
def create_payroll_audit_log(sender, instance, created, **kwargs):
    """
    Create comprehensive audit log for payroll operations.
    """
    try:
        from apps.audit.models import AuditLog
        
        action = 'created' if created else f'status_changed_to_{instance.status.lower()}'
        
        AuditLog.objects.create(
            user=instance.processed_by if instance.processed_by else None,
            action=f'payroll_{action}',
            model_name='PayrollRun',
            object_id=instance.pk,
            details={
                'payroll_number': instance.payroll_number,
                'month': instance.payroll_month.strftime('%Y-%m'),
                'status': instance.status,
                'total_employees': instance.total_employees,
                'total_net': str(instance.total_net),
            }
        )
    except ImportError:
        pass
    except Exception as e:
        print(f"Error creating payroll audit log: {e}")


# ============================================================================
# Data Integrity Signals
# ============================================================================

@receiver(pre_save, sender=Payslip)
def validate_payslip_data(sender, instance, **kwargs):
    """
    Validate payslip data before saving.
    """
    # Ensure net salary is not negative
    if instance.net_salary < 0:
        print(f"⚠️  Warning: Negative net salary for {instance.employee.get_full_name()}: {instance.net_salary}")


@receiver(pre_save, sender=Loan)
def validate_loan_data(sender, instance, **kwargs):
    """
    Validate loan data before saving.
    """
    # Ensure repayment doesn't exceed loan amount
    if instance.amount_repaid > instance.total_repayable:
        print(f"⚠️  Warning: Loan overpayment for {instance.employee.get_full_name()}")


# ============================================================================
# Signal Connection
# ============================================================================

# All signals are automatically connected via @receiver decorator
# To disconnect a signal for testing:
# post_save.disconnect(employee_post_save, sender=Employee)

# To manually connect a signal:
# post_save.connect(employee_post_save, sender=Employee)