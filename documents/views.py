
from django.views.generic import ListView, DetailView, CreateView
from .models import Document, DocumentCategory
from django.urls import reverse_lazy

class DocumentListView(ListView):
	model = Document
	template_name = 'documents/document_list.html'
	context_object_name = 'documents'

class DocumentDetailView(DetailView):
	model = Document
	template_name = 'documents/document_detail.html'
	context_object_name = 'document'

class DocumentCreateView(CreateView):
	model = Document
	fields = '__all__'
	template_name = 'documents/document_form.html'
	success_url = reverse_lazy('documents:document-list')

class DocumentCategoryListView(ListView):
	model = DocumentCategory
	template_name = 'documents/documentcategory_list.html'
	context_object_name = 'categories'

class DocumentCategoryDetailView(DetailView):
	model = DocumentCategory
	template_name = 'documents/documentcategory_detail.html'
	context_object_name = 'category'

class DocumentCategoryCreateView(CreateView):
	model = DocumentCategory
	fields = '__all__'
	template_name = 'documents/documentcategory_form.html'
	success_url = reverse_lazy('documents:documentcategory-list')
