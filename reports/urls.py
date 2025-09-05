
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
	path('templates/', views.ReportTemplateListView.as_view(), name='reporttemplate-list'),
	path('templates/create/', views.ReportTemplateCreateView.as_view(), name='reporttemplate-create'),
	path('templates/<int:pk>/', views.ReportTemplateDetailView.as_view(), name='reporttemplate-detail'),

	path('generations/', views.ReportGenerationListView.as_view(), name='reportgeneration-list'),
	path('generations/create/', views.ReportGenerationCreateView.as_view(), name='reportgeneration-create'),
	path('generations/<int:pk>/', views.ReportGenerationDetailView.as_view(), name='reportgeneration-detail'),
]
