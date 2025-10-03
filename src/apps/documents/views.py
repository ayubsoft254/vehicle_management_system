"""
Views for the documents app.
Simplified to work with existing models only.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone

from .models import Document, DocumentCategory, DocumentShare
from .forms import DocumentForm, DocumentCategoryForm, DocumentShareForm, DocumentSearchForm, BulkDocumentActionForm
from apps.audit.utils import log_audit


@login_required
def document_list(request):
    """Display list of documents with search and filters."""
    form = DocumentSearchForm(request.GET or None)
    
    # Base queryset - all active documents
    documents = Document.objects.filter(is_active=True).select_related(
        'uploaded_by', 'category'
    ).order_by('-uploaded_at')
    
    # Apply search filters
    if form.is_valid():
        query = form.cleaned_data.get('query')
        if query:
            documents = documents.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )
        
        category = form.cleaned_data.get('category')
        if category:
            documents = documents.filter(category=category)
        
        uploaded_by = form.cleaned_data.get('uploaded_by')
        if uploaded_by:
            documents = documents.filter(uploaded_by=uploaded_by)
    
    # Pagination
    paginator = Paginator(documents, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter
    categories = DocumentCategory.objects.filter(is_active=True)
    
    log_audit(request.user, 'read', 'Document', 'Viewed document list')
    
    context = {
        'documents': page_obj,
        'form': form,
        'categories': categories,
        'total_count': documents.count(),
    }
    
    return render(request, 'documents/document_list.html', context)


@login_required
def document_detail(request, pk):
    """Display document details."""
    document = get_object_or_404(Document, pk=pk, is_active=True)
    
    # Check if user has access
    if not (document.uploaded_by == request.user or document.is_public):
        # Check if document is shared with user
        if not DocumentShare.objects.filter(document=document, user=request.user, is_active=True).exists():
            messages.error(request, 'You do not have permission to view this document.')
            return redirect('documents:document_list')
    
    log_audit(request.user, 'read', 'Document', f'Viewed document: {document.title}')
    
    context = {
        'document': document,
    }
    
    return render(request, 'documents/document_detail.html', context)


@login_required
def document_create(request):
    """Create a new document."""
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            document = form.save()
            log_audit(request.user, 'create', 'Document', f'Created document: {document.title}')
            messages.success(request, 'Document uploaded successfully!')
            return redirect('documents:document_detail', pk=document.pk)
    else:
        form = DocumentForm(user=request.user)
    
    context = {
        'form': form,
    }
    
    return render(request, 'documents/document_form.html', context)


@login_required
def document_edit(request, pk):
    """Edit an existing document."""
    document = get_object_or_404(Document, pk=pk, is_active=True)
    
    # Check permissions
    if document.uploaded_by != request.user:
        messages.error(request, 'You do not have permission to edit this document.')
        return redirect('documents:document_detail', pk=document.pk)
    
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, instance=document, user=request.user)
        if form.is_valid():
            document = form.save()
            log_audit(request.user, 'update', 'Document', f'Updated document: {document.title}')
            messages.success(request, 'Document updated successfully!')
            return redirect('documents:document_detail', pk=document.pk)
    else:
        form = DocumentForm(instance=document, user=request.user)
    
    context = {
        'form': form,
        'document': document,
    }
    
    return render(request, 'documents/document_form.html', context)


@login_required
def document_delete(request, pk):
    """Delete a document."""
    document = get_object_or_404(Document, pk=pk, is_active=True)
    
    # Check permissions
    if document.uploaded_by != request.user:
        messages.error(request, 'You do not have permission to delete this document.')
        return redirect('documents:document_detail', pk=document.pk)
    
    if request.method == 'POST':
        document_title = document.title
        document.is_active = False
        document.save()
        log_audit(request.user, 'delete', 'Document', f'Deleted document: {document_title}')
        messages.success(request, 'Document deleted successfully!')
        return redirect('documents:document_list')
    
    context = {
        'document': document,
    }
    
    return render(request, 'documents/document_confirm_delete.html', context)


@login_required
def document_share(request, pk):
    """Share a document with other users."""
    document = get_object_or_404(Document, pk=pk, is_active=True)
    
    # Check permissions
    if document.uploaded_by != request.user:
        messages.error(request, 'You do not have permission to share this document.')
        return redirect('documents:document_detail', pk=document.pk)
    
    if request.method == 'POST':
        form = DocumentShareForm(request.POST, document=document, user=request.user)
        if form.is_valid():
            share = form.save()
            log_audit(request.user, 'create', 'DocumentShare', f'Shared document {document.title} with {share.user.get_full_name()}')
            messages.success(request, f'Document shared with {share.user.get_full_name()} successfully!')
            return redirect('documents:document_detail', pk=document.pk)
    else:
        form = DocumentShareForm(document=document, user=request.user)
    
    # Get existing shares
    shares = DocumentShare.objects.filter(document=document, is_active=True).select_related('user')
    
    context = {
        'form': form,
        'document': document,
        'shares': shares,
    }
    
    return render(request, 'documents/document_share.html', context)


@login_required
def category_list(request):
    """Display list of document categories."""
    categories = DocumentCategory.objects.filter(is_active=True).order_by('name')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'documents/category_list.html', context)


@login_required
def category_create(request):
    """Create a new document category."""
    if request.method == 'POST':
        form = DocumentCategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            log_audit(request.user, 'create', 'DocumentCategory', f'Created category: {category.name}')
            messages.success(request, 'Category created successfully!')
            return redirect('documents:category_list')
    else:
        form = DocumentCategoryForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'documents/category_form.html', context)


@login_required
def download_document(request, pk):
    """Download a document file."""
    document = get_object_or_404(Document, pk=pk, is_active=True)
    
    # Check if user has access
    if not (document.uploaded_by == request.user or document.is_public):
        # Check if document is shared with user
        if not DocumentShare.objects.filter(document=document, user=request.user, is_active=True).exists():
            messages.error(request, 'You do not have permission to download this document.')
            return redirect('documents:document_list')
    
    log_audit(request.user, 'read', 'Document', f'Downloaded document: {document.title}')
    
    try:
        response = HttpResponse(document.file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{document.file.name}"'
        return response
    except Exception as e:
        messages.error(request, 'Error downloading file.')
        return redirect('documents:document_detail', pk=document.pk)


def ajax_search_documents(request):
    """AJAX endpoint for document search."""
    query = request.GET.get('q', '')
    documents = []
    
    if query and len(query) >= 2:
        docs = Document.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query),
            is_active=True
        ).select_related('category')[:10]
        
        documents = [{
            'id': doc.pk,
            'title': doc.title,
            'category': doc.category.name if doc.category else '',
            'url': doc.get_absolute_url() if hasattr(doc, 'get_absolute_url') else '',
        } for doc in docs]
    
    return JsonResponse({'documents': documents})