from django.shortcuts import render

from django.views.generic import ListView, DetailView
from .models import AuditLog, LoginAttempt, UserSession, SystemEvent, DataExport, ComplianceReport

class AuditLogListView(ListView):
	model = AuditLog
	template_name = 'audit/auditlog_list.html'
	context_object_name = 'audit_logs'

class AuditLogDetailView(DetailView):
	model = AuditLog
	template_name = 'audit/auditlog_detail.html'
	context_object_name = 'audit_log'

class LoginAttemptListView(ListView):
	model = LoginAttempt
	template_name = 'audit/loginattempt_list.html'
	context_object_name = 'login_attempts'

class LoginAttemptDetailView(DetailView):
	model = LoginAttempt
	template_name = 'audit/loginattempt_detail.html'
	context_object_name = 'login_attempt'

class UserSessionListView(ListView):
	model = UserSession
	template_name = 'audit/usersession_list.html'
	context_object_name = 'user_sessions'

class UserSessionDetailView(DetailView):
	model = UserSession
	template_name = 'audit/usersession_detail.html'
	context_object_name = 'user_session'

class SystemEventListView(ListView):
	model = SystemEvent
	template_name = 'audit/systemevent_list.html'
	context_object_name = 'system_events'

class SystemEventDetailView(DetailView):
	model = SystemEvent
	template_name = 'audit/systemevent_detail.html'
	context_object_name = 'system_event'

class DataExportListView(ListView):
	model = DataExport
	template_name = 'audit/dataexport_list.html'
	context_object_name = 'data_exports'

class DataExportDetailView(DetailView):
	model = DataExport
	template_name = 'audit/dataexport_detail.html'
	context_object_name = 'data_export'

class ComplianceReportListView(ListView):
	model = ComplianceReport
	template_name = 'audit/compliancereport_list.html'
	context_object_name = 'compliance_reports'

class ComplianceReportDetailView(DetailView):
	model = ComplianceReport
	template_name = 'audit/compliancereport_detail.html'
	context_object_name = 'compliance_report'

# Create your views here.
