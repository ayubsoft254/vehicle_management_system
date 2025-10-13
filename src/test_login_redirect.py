"""
Test script to verify login redirect logic
Run from src directory: python test_login_redirect.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.authentication.models import User
from apps.authentication.adapters import CustomAccountAdapter
from django.test import RequestFactory
from utils.constants import UserRole

def test_login_redirects():
    """Test login redirect for different user roles"""
    
    adapter = CustomAccountAdapter()
    factory = RequestFactory()
    
    # Test cases
    test_users = [
        ('CLIENT', '/clients/portal/'),
        ('ADMIN', '/dashboard/'),
        ('MANAGER', '/dashboard/'),
        ('SALES', '/dashboard/'),
        ('ACCOUNTANT', '/dashboard/'),
        ('CLERK', '/dashboard/'),
        ('AUCTIONEER', '/auctions/'),
    ]
    
    print("\n" + "="*60)
    print("LOGIN REDIRECT TEST")
    print("="*60 + "\n")
    
    for role, expected_url in test_users:
        # Create a mock request
        request = factory.get('/accounts/login/')
        
        # Create a mock user with the role
        class MockUser:
            def __init__(self, role):
                self.role = role
                self.is_authenticated = True
        
        request.user = MockUser(role)
        
        # Get redirect URL
        redirect_url = adapter.get_login_redirect_url(request)
        
        # Check result
        status = "✅ PASS" if redirect_url == expected_url else "❌ FAIL"
        print(f"{status} | Role: {role:12} | Expected: {expected_url:20} | Got: {redirect_url}")
    
    print("\n" + "="*60)
    print("Test completed!")
    print("="*60 + "\n")

if __name__ == '__main__':
    test_login_redirects()
