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
from .services.docuseal import DocuSealError, create_signature_request
from apps.audit.utils import log_audit


@login_required
def document_list(request):
    """Display all documents in the system: standalone uploads + client documents."""
    from apps.clients.models import ClientDocument
    import os

    query = request.GET.get('query', '').strip()
    source_filter = request.GET.get('source', '')
    category_id = request.GET.get('category')
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')

    # --- Standalone Document records ---
    docs_qs = Document.objects.filter(is_active=True).select_related('uploaded_by', 'category')
    if query:
        docs_qs = docs_qs.filter(
            Q(title__icontains=query) | Q(description__icontains=query) |
            Q(document_number__icontains=query) | Q(tags__icontains=query)
        )
    if category_id:
        docs_qs = docs_qs.filter(category_id=category_id)
    if date_from_str:
        try:
            from datetime import datetime as _dt
            docs_qs = docs_qs.filter(uploaded_at__date__gte=_dt.strptime(date_from_str, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to_str:
        try:
            from datetime import datetime as _dt
            docs_qs = docs_qs.filter(uploaded_at__date__lte=_dt.strptime(date_to_str, '%Y-%m-%d').date())
        except ValueError:
            pass

    # --- ClientDocument records ---
    client_docs_qs = ClientDocument.objects.select_related('client', 'uploaded_by')
    if query:
        client_docs_qs = client_docs_qs.filter(
            Q(title__icontains=query) | Q(description__icontains=query) |
            Q(client__first_name__icontains=query) | Q(client__last_name__icontains=query)
        )
    if date_from_str:
        try:
            from datetime import datetime as _dt
            client_docs_qs = client_docs_qs.filter(uploaded_at__date__gte=_dt.strptime(date_from_str, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to_str:
        try:
            from datetime import datetime as _dt
            client_docs_qs = client_docs_qs.filter(uploaded_at__date__lte=_dt.strptime(date_to_str, '%Y-%m-%d').date())
        except ValueError:
            pass

    # Source filter
    if source_filter == 'standalone':
        client_docs_qs = client_docs_qs.none()
    elif source_filter == 'client':
        docs_qs = docs_qs.none()
        category_id = None

    # --- Build unified list ---
    def _ext(filename):
        return os.path.splitext(filename)[1].lower() if filename else ''

    combined = []

    for d in docs_qs:
        ext = d.get_file_extension()
        combined.append({
            'pk': d.pk,
            'doc_type': 'standalone',
            'title': d.title,
            'description': d.description or '',
            'uploaded_at': d.uploaded_at,
            'uploaded_by': d.uploaded_by,
            'category_name': d.category.name if d.category else 'Uncategorised',
            'category_color': d.category.color if d.category else '#6b7280',
            'subtitle': f"Doc No: {d.document_number}" if d.document_number else '',
            'file_size_formatted': d.file_size_formatted,
            'is_pdf': ext == '.pdf',
            'is_image': ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'),
            'is_spreadsheet': ext in ('.xls', '.xlsx', '.csv', '.ods'),
            'is_word': ext in ('.doc', '.docx', '.txt', '.rtf', '.odt'),
            'expiry_date': d.expiry_date,
            'is_expired': d.is_expired,
            'is_expiring_soon': d.is_expiring_soon,
            'days_until_expiry': d.days_until_expiry,
            'detail_url': f"/documents/{d.pk}/",
            'download_url': f"/documents/{d.pk}/download/",
            'delete_url': f"/documents/{d.pk}/delete/",
            'is_own': d.uploaded_by == request.user,
            'version': d.version,
        })

    for d in client_docs_qs:
        ext = _ext(d.file.name) if d.file else ''
        combined.append({
            'pk': d.pk,
            'doc_type': 'client',
            'title': d.title,
            'description': d.description or '',
            'uploaded_at': d.uploaded_at,
            'uploaded_by': d.uploaded_by,
            'category_name': d.get_document_type_display(),
            'category_color': '#3b82f6',
            'subtitle': f"Client: {d.client.first_name} {d.client.last_name}",
            'file_size_formatted': d.file_size,
            'is_pdf': ext == '.pdf',
            'is_image': ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp'),
            'is_spreadsheet': ext in ('.xls', '.xlsx', '.csv'),
            'is_word': ext in ('.doc', '.docx', '.txt', '.rtf'),
            'expiry_date': None,
            'is_expired': False,
            'is_expiring_soon': False,
            'days_until_expiry': None,
            'detail_url': f"/clients/{d.client.pk}/",
            'download_url': f"/clients/documents/{d.pk}/download/",
            'delete_url': None,
            'is_own': False,
            'version': 1,
        })

    combined.sort(key=lambda x: x['uploaded_at'], reverse=True)

    total_count = len(combined)

    paginator = Paginator(combined, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = DocumentCategory.objects.filter(is_active=True)

    log_audit(request.user, 'read', 'Document', 'Viewed document list')

    context = {
        'documents': page_obj,
        'categories': categories,
        'total_count': total_count,
        'standalone_count': Document.objects.filter(is_active=True).count(),
        'client_doc_count': ClientDocument.objects.count(),
        'query': query,
        'category_id': category_id,
        'source_filter': source_filter,
        'date_from': date_from_str,
        'date_to': date_to_str,
    }

    return render(request, 'documents/document_list.html', context)


@login_required
def document_detail(request, pk):
    """Display document details."""
    document = get_object_or_404(Document, pk=pk, is_active=True)
    
    # Private documents: only the uploader or admins can view
    if document.is_private and document.uploaded_by != request.user and not request.user.is_staff:
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
            log_audit(request.user, 'create', 'DocumentShare', f'Created share link for {document.title}')
            messages.success(request, 'Share link created successfully!')
            return redirect('documents:document_detail', pk=document.pk)
    else:
        form = DocumentShareForm(document=document, user=request.user)

    shares = DocumentShare.objects.filter(document=document, is_active=True).select_related('created_by')

    context = {
        'form': form,
        'document': document,
        'shares': shares,
    }

    return render(request, 'documents/document_share.html', context)


@login_required
def request_signature(request, pk):
    """Create an e-signature request for a document via DocuSeal."""
    document = get_object_or_404(Document, pk=pk, is_active=True)

    if document.uploaded_by != request.user:
        messages.error(request, 'You do not have permission to request signatures for this document.')
        return redirect('documents:document_detail', pk=document.pk)

    if request.method != 'POST':
        return redirect('documents:document_detail', pk=document.pk)

    signer_name = (request.POST.get('signer_name') or '').strip()
    signer_email = (request.POST.get('signer_email') or '').strip()

    if not signer_name or not signer_email:
        messages.error(request, 'Signer name and signer email are required.')
        return redirect('documents:document_detail', pk=document.pk)

    try:
        result = create_signature_request(document, signer_name=signer_name, signer_email=signer_email)
    except DocuSealError as exc:
        document.esign_provider = 'docuseal'
        document.esign_status = 'failed'
        document.save(update_fields=['esign_provider', 'esign_status'])
        messages.error(request, str(exc))
        return redirect('documents:document_detail', pk=document.pk)

    document.esign_provider = 'docuseal'
    document.esign_submission_id = result['submission_id']
    document.esign_signer_name = signer_name
    document.esign_signer_email = signer_email
    document.esign_signing_link = result['signing_link']
    document.esign_status = 'pending'
    document.esign_requested_at = timezone.now()
    document.save(
        update_fields=[
            'esign_provider',
            'esign_submission_id',
            'esign_signer_name',
            'esign_signer_email',
            'esign_signing_link',
            'esign_status',
            'esign_requested_at',
        ]
    )

    messages.success(request, 'E-signature request created successfully.')
    return redirect('documents:document_detail', pk=document.pk)


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
    
    # Private documents: only the uploader or admins can download
    if document.is_private and document.uploaded_by != request.user and not request.user.is_staff:
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