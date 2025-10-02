"""
URL configuration for the payroll app.
"""

from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
    # ========================================================================
    # Dashboard
    # ========================================================================
    path('', views.payroll_dashboard, name='payroll_dashboard'),
    
    # ========================================================================
    # Employee Management URLs
    # ========================================================================
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/create/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/edit/', views.employee_update, name='employee_update'),
    
    # ========================================================================
    # Salary Structure URLs
    # ========================================================================
    path('employees/<int:employee_pk>/salary/', views.salary_structure_create, name='salary_structure_create'),
    
    # ========================================================================
    # Commission URLs
    # ========================================================================
    path('commissions/', views.commission_list, name='commission_list'),
    path('commissions/create/', views.commission_create, name='commission_create'),
    path('commissions/<int:pk>/approve/', views.commission_approve, name='commission_approve'),
    
    # ========================================================================
    # Deduction URLs
    # ========================================================================
    path('deductions/', views.deduction_list, name='deduction_list'),
    path('deductions/create/', views.deduction_create, name='deduction_create'),
    
    # ========================================================================
    # Payroll Run URLs
    # ========================================================================
    path('runs/', views.payroll_run_list, name='payroll_run_list'),
    path('runs/create/', views.payroll_run_create, name='payroll_run_create'),
    path('runs/<int:pk>/', views.payroll_run_detail, name='payroll_run_detail'),
    path('runs/<int:pk>/process/', views.payroll_run_process, name='payroll_run_process'),
    path('runs/<int:pk>/approve/', views.payroll_run_approve, name='payroll_run_approve'),
    
    # ========================================================================
    # Payslip URLs
    # ========================================================================
    path('payslips/<int:pk>/', views.payslip_detail, name='payslip_detail'),
    path('payslips/<int:pk>/download/', views.payslip_download, name='payslip_download'),
    
    # ========================================================================
    # Attendance URLs
    # ========================================================================
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/mark/', views.attendance_mark, name='attendance_mark'),
    path('attendance/bulk-mark/', views.attendance_bulk_mark, name='attendance_bulk_mark'),
    
    # ========================================================================
    # Leave Management URLs
    # ========================================================================
    path('leaves/', views.leave_list, name='leave_list'),
    path('leaves/create/', views.leave_create, name='leave_create'),
    path('leaves/<int:pk>/approve/', views.leave_approve, name='leave_approve'),
    
    # ========================================================================
    # Loan Management URLs
    # ========================================================================
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/create/', views.loan_create, name='loan_create'),
    path('loans/<int:pk>/approve/', views.loan_approve, name='loan_approve'),
    
    # ========================================================================
    # Reports URLs
    # ========================================================================
    path('reports/', views.payroll_reports, name='payroll_reports'),
]