"""
Views for the documents app.
Handles document upload, management, sharing, and version control.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.urls import reverse
import os
import mimetypes

from .models import (
    Document, DocumentCategory, DocumentShare
)
from .forms import (
    DocumentForm, DocumentCategoryForm, DocumentShareForm,
    DocumentSearchForm, BulkDocumentActionForm
)


# ============================================================================
# Document List and Search Views
# ============================================================================

@login_required
def document_list(request):
    """Display list of documents with search and filters."""
    form = DocumentSearchForm(request.GET or None)
    
    # Base queryset - documents user can access
    documents = Document.objects.filter(
        Q(uploaded_by=request.user) |
        Q(is_public=True) |
        Q(shared_with=request.user)
    ).select_related(
        'uploaded_by', 'category', 'related_vehicle', 'related_client'
    ).prefetch_related(
        'tags'
    ).distinct()
    
    # Apply filters
    if form.is_valid():
        query = form.cleaned_data.get('query')
        if query:
            documents = documents.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(tags__name__icontains=query)
            ).distinct()
        
        category = form.cleaned_data.get('category')
        if category:
            documents = documents.filter(category=category)
        
        tags = form.cleaned_data.get('tags')
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            for tag in tag_list:
                documents = documents.filter(tags__name__icontains=tag)
        
        uploaded_by = form.cleaned_data.get('uploaded_by')
        if uploaded_by:
            documents = documents.filter(uploaded_by=uploaded_by)
        
        date_from = form.cleaned_data.get('date_from')
        if date_from:
            documents = documents.filter(uploaded_at__date__gte=date_from)
        
        date_to = form.cleaned_data.get('date_to')
        if date_to:
            documents = documents.filter(uploaded_at__date__lte=date_to)
        
        is_archived = form.cleaned_data.get('is_archived')
        if is_archived is not None:
            documents = documents.filter(is_archived=is_archived)
    
    # Sort documents
    sort_by = request.GET.get('sort', '-uploaded_at')
    documents = documents.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(documents, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for sidebar
    categories = DocumentCategory.objects.annotate(
        document_count=Count('documents')
    ).order_by('name')
    
    # Get popular tags
    popular_tags = DocumentTag.objects.annotate(
        usage_count=Count('documents')
    ).order_by('-usage_count')[:10]
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'categories': categories,
        'popular_tags': popular_tags,
        'total_count': paginator.count,
    }
    
    return render(request, 'documents/document_list.html', context)


@login_required
def my_documents(request):
    """Display documents uploaded by current user."""
    documents = Document.objects.filter(
        uploaded_by=request.user
    ).select_related(
        'category', 'related_vehicle', 'related_client'
    ).prefetch_related('tags').order_by('-uploaded_at')
    
    # Pagination
    paginator = Paginator(documents, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'title': 'My Documents',
    }
    
    return render(request, 'documents/my_documents.html', context)


@login_required
def shared_with_me(request):
    """Display documents shared with current user."""
    shared_docs = DocumentShare.objects.filter(
        shared_with=request.user
    ).select_related(
        'document', 'document__uploaded_by', 'document__category', 'shared_by'
    ).order_by('-shared_at')
    
    # Pagination
    paginator = Paginator(shared_docs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'title': 'Shared With Me',
    }
    
    return render(request, 'documents/shared_with_me.html', context)


@login_required
def archived_documents(request):
    """Display archived documents."""
    documents = Document.objects.filter(
        Q(uploaded_by=request.user) | Q(is_public=True),
        is_archived=True
    ).select_related(
        'uploaded_by', 'category'
    ).order_by('-archived_at')
    
    # Pagination
    paginator = Paginator(documents, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'title': 'Archived Documents',
    }
    
    return render(request, 'documents/archived_documents.html', context)


# ============================================================================
# Document CRUD Views
# ============================================================================

@login_required
def document_detail(request, pk):
    """Display document details with versions and comments."""
    document = get_object_or_404(Document, pk=pk)
    
    # Check access permission
    if not (document.uploaded_by == request.user or 
            document.is_public or 
            document.shared_with.filter(pk=request.user.pk).exists()):
        messages.error(request, 'You do not have permission to view this document.')
        return redirect('documents:document_list')
    
    # Get versions
    versions = document.versions.select_related('uploaded_by').order_by('-version_number')
    
    # Get comments
    comments = document.comments.select_related('user').order_by('-created_at')
    
    # Get share information
    shares = document.shares.select_related('shared_with', 'shared_by').order_by('-shared_at')
    
    # Check user permissions
    user_share = shares.filter(shared_with=request.user).first()
    can_edit = (document.uploaded_by == request.user or 
                (user_share and user_share.can_edit))
    can_delete = (document.uploaded_by == request.user or 
                  (user_share and user_share.can_delete))
    
    # Comment form
    comment_form = DocumentCommentForm()
    
    context = {
        'document': document,
        'versions': versions,
        'comments': comments,
        'shares': shares,
        'can_edit': can_edit,
        'can_delete': can_delete,
        'comment_form': comment_form,
    }
    
    return render(request, 'documents/document_detail.html', context)


@login_required
def document_create(request):
    """Create a new document."""
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            document = form.save()
            messages.success(request, f'Document "{document.title}" uploaded successfully.')
            
            # Send notifications if specified
            notify_users = form.cleaned_data.get('notify_users')
            if notify_users:
                # TODO: Implement notification sending
                pass
            
            return redirect('documents:document_detail', pk=document.pk)
    else:
        form = DocumentForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Upload Document',
    }
    
    return render(request, 'documents/document_form.html', context)


@login_required
def document_update(request, pk):
    """Update document details."""
    document = get_object_or_404(Document, pk=pk)
    
    # Check permission
    user_share = document.shares.filter(shared_with=request.user).first()
    if not (document.uploaded_by == request.user or 
            (user_share and user_share.can_edit)):
        messages.error(request, 'You do not have permission to edit this document.')
        return redirect('documents:document_detail', pk=document.pk)
    
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, instance=document, user=request.user)
        if form.is_valid():
            document = form.save()
            messages.success(request, f'Document "{document.title}" updated successfully.')
            return redirect('documents:document_detail', pk=document.pk)
    else:
        form = DocumentForm(instance=document, user=request.user)
    
    context = {
        'form': form,
        'document': document,
        'title': 'Edit Document',
    }
    
    return render(request, 'documents/document_form.html', context)


@login_required
def document_delete(request, pk):
    """Delete a document."""
    document = get_object_or_404(Document, pk=pk)
    
    # Check permission
    user_share = document.shares.filter(shared_with=request.user).first()
    if not (document.uploaded_by == request.user or 
            (user_share and user_share.can_delete)):
        messages.error(request, 'You do not have permission to delete this document.')
        return redirect('documents:document_detail', pk=document.pk)
    
    if request.method == 'POST':
        title = document.title
        document.delete()
        messages.success(request, f'Document "{title}" deleted successfully.')
        return redirect('documents:document_list')
    
    context = {
        'document': document,
    }
    
    return render(request, 'documents/document_confirm_delete.html', context)


@login_required
@require_http_methods(["POST"])
def document_archive(request, pk):
    """Archive or unarchive a document."""
    document = get_object_or_404(Document, pk=pk)
    
    # Check permission
    if document.uploaded_by != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    document.is_archived = not document.is_archived
    if document.is_archived:
        document.archived_at = timezone.now()
    else:
        document.archived_at = None
    document.save()
    
    action = 'archived' if document.is_archived else 'unarchived'
    messages.success(request, f'Document "{document.title}" {action} successfully.')
    
    return JsonResponse({
        'success': True,
        'is_archived': document.is_archived,
        'message': f'Document {action} successfully.'
    })


@login_required
def document_download(request, pk):
    """Download a document file."""
    document = get_object_or_404(Document, pk=pk)
    
    # Check access permission
    if not (document.uploaded_by == request.user or 
            document.is_public or 
            document.shared_with.filter(pk=request.user.pk).exists()):
        raise Http404("Document not found")
    
    # Increment download count
    document.download_count += 1
    document.save(update_fields=['download_count'])
    
    # Serve file
    try:
        file_path = document.file.path
        if os.path.exists(file_path):
            # Get mime type
            mime_type, _ = mimetypes.guess_type(file_path)
            
            response = FileResponse(
                open(file_path, 'rb'),
                content_type=mime_type or 'application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{document.file_name}"'
            return response
        else:
            raise Http404("File not found")
    except Exception as e:
        messages.error(request, f'Error downloading file: {str(e)}')
        return redirect('documents:document_detail', pk=document.pk)


@login_required
def document_preview(request, pk):
    """Preview document (for supported file types)."""
    document = get_object_or_404(Document, pk=pk)
    
    # Check access permission
    if not (document.uploaded_by == request.user or 
            document.is_public or 
            document.shared_with.filter(pk=request.user.pk).exists()):
        raise Http404("Document not found")
    
    # Check if file type is previewable
    previewable_types = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.txt']
    ext = os.path.splitext(document.file.name)[1].lower()
    
    if ext not in previewable_types:
        messages.warning(request, 'This file type cannot be previewed.')
        return redirect('documents:document_detail', pk=document.pk)
    
    context = {
        'document': document,
    }
    
    return render(request, 'documents/document_preview.html', context)


# ============================================================================
# Version Control Views
# ============================================================================

@login_required
def version_create(request, document_pk):
    """Upload a new version of a document."""
    document = get_object_or_404(Document, pk=document_pk)
    
    # Check permission
    user_share = document.shares.filter(shared_with=request.user).first()
    if not (document.uploaded_by == request.user or 
            (user_share and user_share.can_edit)):
        messages.error(request, 'You do not have permission to upload new versions.')
        return redirect('documents:document_detail', pk=document.pk)
    
    if request.method == 'POST':
        form = DocumentVersionForm(request.POST, request.FILES, document=document, user=request.user)
        if form.is_valid():
            version = form.save()
            messages.success(request, f'Version {version.version_number} uploaded successfully.')
            return redirect('documents:document_detail', pk=document.pk)
    else:
        form = DocumentVersionForm(document=document, user=request.user)
    
    context = {
        'form': form,
        'document': document,
        'title': 'Upload New Version',
    }
    
    return render(request, 'documents/version_form.html', context)


@login_required
def version_download(request, pk):
    """Download a specific document version."""
    version = get_object_or_404(DocumentVersion, pk=pk)
    document = version.document
    
    # Check access permission
    if not (document.uploaded_by == request.user or 
            document.is_public or 
            document.shared_with.filter(pk=request.user.pk).exists()):
        raise Http404("Version not found")
    
    # Serve file
    try:
        file_path = version.file.path
        if os.path.exists(file_path):
            mime_type, _ = mimetypes.guess_type(file_path)
            
            response = FileResponse(
                open(file_path, 'rb'),
                content_type=mime_type or 'application/octet-stream'
            )
            filename = f"{document.file_name}_v{version.version_number}{os.path.splitext(version.file.name)[1]}"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        else:
            raise Http404("File not found")
    except Exception as e:
        messages.error(request, f'Error downloading version: {str(e)}')
        return redirect('documents:document_detail', pk=document.pk)


# ============================================================================
# Sharing Views
# ============================================================================

@login_required
def document_share(request, pk):
    """Share a document with another user."""
    document = get_object_or_404(Document, pk=pk)
    
    # Only owner can share
    if document.uploaded_by != request.user:
        messages.error(request, 'Only the document owner can share it.')
        return redirect('documents:document_detail', pk=document.pk)
    
    if request.method == 'POST':
        form = DocumentShareForm(request.POST, document=document, user=request.user)
        if form.is_valid():
            share = form.save()
            messages.success(
                request, 
                f'Document shared with {share.shared_with.get_full_name() or share.shared_with.username}.'
            )
            
            # TODO: Send notification to shared user
            
            return redirect('documents:document_detail', pk=document.pk)
    else:
        form = DocumentShareForm(document=document, user=request.user)
    
    # Get existing shares
    shares = document.shares.select_related('shared_with', 'shared_by').order_by('-shared_at')
    
    context = {
        'form': form,
        'document': document,
        'shares': shares,
        'title': 'Share Document',
    }
    
    return render(request, 'documents/document_share.html', context)


@login_required
@require_http_methods(["POST"])
def share_revoke(request, pk):
    """Revoke document share."""
    share = get_object_or_404(DocumentShare, pk=pk)
    document = share.document
    
    # Only owner can revoke
    if document.uploaded_by != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    shared_with_name = share.shared_with.get_full_name() or share.shared_with.username
    share.delete()
    
    messages.success(request, f'Access revoked for {shared_with_name}.')
    
    return JsonResponse({
        'success': True,
        'message': f'Access revoked for {shared_with_name}.'
    })


# ============================================================================
# Comment Views
# ============================================================================

@login_required
@require_http_methods(["POST"])
def comment_create(request, document_pk):
    """Add a comment to a document."""
    document = get_object_or_404(Document, pk=document_pk)
    
    # Check access permission
    if not (document.uploaded_by == request.user or 
            document.is_public or 
            document.shared_with.filter(pk=request.user.pk).exists()):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    form = DocumentCommentForm(request.POST, document=document, user=request.user)
    if form.is_valid():
        comment = form.save()
        
        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'user': comment.user.get_full_name() or comment.user.username,
                'comment': comment.comment,
                'created_at': comment.created_at.strftime('%B %d, %Y at %I:%M %p'),
            }
        })
    
    return JsonResponse({'error': 'Invalid form data'}, status=400)


@login_required
@require_http_methods(["POST"])
def comment_delete(request, pk):
    """Delete a comment."""
    comment = get_object_or_404(DocumentComment, pk=pk)
    
    # Only comment owner or document owner can delete
    if not (comment.user == request.user or comment.document.uploaded_by == request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    comment.delete()
    
    return JsonResponse({
        'success': True,
        'message': 'Comment deleted successfully.'
    })


# ============================================================================
# Category Views
# ============================================================================

@login_required
def category_list(request):
    """Display list of document categories."""
    categories = DocumentCategory.objects.annotate(
        document_count=Count('documents')
    ).order_by('name')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'documents/category_list.html', context)


@login_required
def category_documents(request, pk):
    """Display documents in a specific category."""
    category = get_object_or_404(DocumentCategory, pk=pk)
    
    documents = Document.objects.filter(
        category=category
    ).filter(
        Q(uploaded_by=request.user) | Q(is_public=True) | Q(shared_with=request.user)
    ).select_related(
        'uploaded_by', 'related_vehicle', 'related_client'
    ).distinct().order_by('-uploaded_at')
    
    # Pagination
    paginator = Paginator(documents, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
    }
    
    return render(request, 'documents/category_documents.html', context)


# ============================================================================
# Bulk Actions
# ============================================================================

@login_required
@require_http_methods(["POST"])
def bulk_actions(request):
    """Perform bulk actions on documents."""
    form = BulkDocumentActionForm(request.POST)
    
    if not form.is_valid():
        messages.error(request, 'Invalid action request.')
        return redirect('documents:document_list')
    
    document_ids = form.cleaned_data['document_ids']
    action = form.cleaned_data['action']
    
    # Get documents user has permission to modify
    documents = Document.objects.filter(
        pk__in=document_ids,
        uploaded_by=request.user
    )
    
    count = documents.count()
    
    if action == 'archive':
        documents.update(is_archived=True, archived_at=timezone.now())
        messages.success(request, f'{count} document(s) archived.')
    
    elif action == 'unarchive':
        documents.update(is_archived=False, archived_at=None)
        messages.success(request, f'{count} document(s) unarchived.')
    
    elif action == 'delete':
        documents.delete()
        messages.success(request, f'{count} document(s) deleted.')
    
    elif action == 'change_category':
        new_category = form.cleaned_data.get('new_category')
        documents.update(category=new_category)
        messages.success(request, f'{count} document(s) moved to {new_category.name}.')
    
    elif action == 'add_tags':
        tags_str = form.cleaned_data.get('tags')
        tag_names = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
        
        for document in documents:
            for tag_name in tag_names:
                tag, created = DocumentTag.objects.get_or_create(name=tag_name.lower())
                document.tags.add(tag)
        
        messages.success(request, f'Tags added to {count} document(s).')
    
    return redirect('documents:document_list')


# ============================================================================
# API/AJAX Views
# ============================================================================

@login_required
def quick_search(request):
    """Quick search for documents (AJAX)."""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    documents = Document.objects.filter(
        Q(uploaded_by=request.user) | Q(is_public=True) | Q(shared_with=request.user)
    ).filter(
        Q(title__icontains=query) | Q(description__icontains=query)
    ).select_related('uploaded_by', 'category').distinct()[:10]
    
    results = [{
        'id': doc.id,
        'title': doc.title,
        'category': doc.category.name if doc.category else 'Uncategorized',
        'uploaded_by': doc.uploaded_by.get_full_name() or doc.uploaded_by.username,
        'uploaded_at': doc.uploaded_at.strftime('%Y-%m-%d'),
        'url': reverse('documents:document_detail', args=[doc.pk]),
    } for doc in documents]
    
    return JsonResponse({'results': results})