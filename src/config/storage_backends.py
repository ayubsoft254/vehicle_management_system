"""
Custom storage backends for media and static files

This module provides storage backend configurations for different environments:
- Development: Local file system
- Production (current): Django's file system with proper security
- Production (future): Cloud storage (S3, Azure Blob, etc.)

To switch to cloud storage:
1. Install django-storages: pip install django-storages boto3 (for S3)
2. Update settings.py STORAGES configuration
3. Set cloud provider credentials in environment variables
"""

from django.core.files.storage import FileSystemStorage
from django.conf import settings


class SecureMediaStorage(FileSystemStorage):
    """
    Custom storage for media files with enhanced security.
    
    This storage backend ensures:
    - Media files are stored in the correct location
    - Proper file permissions are set
    - URL generation works correctly
    """
    
    def __init__(self, *args, **kwargs):
        kwargs['location'] = settings.MEDIA_ROOT
        kwargs['base_url'] = settings.MEDIA_URL
        super().__init__(*args, **kwargs)
    
    def get_available_name(self, name, max_length=None):
        """
        Generate a unique filename to prevent overwriting existing files.
        """
        # Remove any directory traversal attempts
        name = name.replace('../', '').replace('..\\', '')
        return super().get_available_name(name, max_length)


# Example AWS S3 Configuration (for future use)
# Uncomment and configure when ready to use S3
"""
from storages.backends.s3boto3 import S3Boto3Storage

class MediaStorage(S3Boto3Storage):
    '''S3 storage for media files'''
    location = 'media'
    default_acl = 'private'
    file_overwrite = False
    custom_domain = False

class StaticStorage(S3Boto3Storage):
    '''S3 storage for static files'''
    location = 'static'
    default_acl = 'public-read'
    file_overwrite = True
"""

# Example Azure Blob Storage Configuration (for future use)
"""
from storages.backends.azure_storage import AzureStorage

class AzureMediaStorage(AzureStorage):
    '''Azure Blob storage for media files'''
    account_name = settings.AZURE_ACCOUNT_NAME
    account_key = settings.AZURE_ACCOUNT_KEY
    azure_container = 'media'
    expiration_secs = None

class AzureStaticStorage(AzureStorage):
    '''Azure Blob storage for static files'''
    account_name = settings.AZURE_ACCOUNT_NAME
    account_key = settings.AZURE_ACCOUNT_KEY
    azure_container = 'static'
    expiration_secs = None
"""
