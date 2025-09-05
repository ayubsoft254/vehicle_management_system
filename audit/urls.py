
from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
	path('auditlogs/', views.AuditLogListView.as_view(), name='auditlog-list'),
	path('auditlogs/<int:pk>/', views.AuditLogDetailView.as_view(), name='auditlog-detail'),

	path('loginattempts/', views.LoginAttemptListView.as_view(), name='loginattempt-list'),
	path('loginattempts/<int:pk>/', views.LoginAttemptDetailView.as_view(), name='loginattempt-detail'),

	path('usersessions/', views.UserSessionListView.as_view(), name='usersession-list'),
	path('usersessions/<int:pk>/', views.UserSessionDetailView.as_view(), name='usersession-detail'),

	path('systemevents/', views.SystemEventListView.as_view(), name='systemevent-list'),
	path('systemevents/<int:pk>/', views.SystemEventDetailView.as_view(), name='systemevent-detail'),

	path('dataexports/', views.DataExportListView.as_view(), name='dataexport-list'),
	path('dataexports/<int:pk>/', views.DataExportDetailView.as_view(), name='dataexport-detail'),

	path('compliancereports/', views.ComplianceReportListView.as_view(), name='compliancereport-list'),
	path('compliancereports/<int:pk>/', views.ComplianceReportDetailView.as_view(), name='compliancereport-detail'),
]
