
from django.views.generic import ListView, DetailView, CreateView
from .models import ReportTemplate, ReportGeneration
from django.urls import reverse_lazy

class ReportTemplateListView(ListView):
	model = ReportTemplate
	template_name = 'reports/reporttemplate_list.html'
	context_object_name = 'templates'

class ReportTemplateDetailView(DetailView):
	model = ReportTemplate
	template_name = 'reports/reporttemplate_detail.html'
	context_object_name = 'template'

class ReportTemplateCreateView(CreateView):
	model = ReportTemplate
	fields = '__all__'
	template_name = 'reports/reporttemplate_form.html'
	success_url = reverse_lazy('reports:reporttemplate-list')

class ReportGenerationListView(ListView):
	model = ReportGeneration
	template_name = 'reports/reportgeneration_list.html'
	context_object_name = 'generations'

class ReportGenerationDetailView(DetailView):
	model = ReportGeneration
	template_name = 'reports/reportgeneration_detail.html'
	context_object_name = 'generation'

class ReportGenerationCreateView(CreateView):
	model = ReportGeneration
	fields = '__all__'
	template_name = 'reports/reportgeneration_form.html'
	success_url = reverse_lazy('reports:reportgeneration-list')
