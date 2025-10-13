#!/usr/bin/env python
"""
Quick test script to verify permission template tags are working
Run this from the src directory: python test_permissions.py
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.permissions.models import RolePermission
from apps.authentication.models import User
from utils.constants import UserRole, ModuleName, AccessLevel

def test_permissions():
    print("\n" + "="*60)
    print("PERMISSION TEMPLATE TAGS TEST")
    print("="*60)
    
    # Check if permissions exist
    print("\n1. Checking if permissions are initialized...")
    perm_count = RolePermission.objects.count()
    print(f"   Total permissions: {perm_count}")
    
    if perm_count == 0:
        print("   ⚠️  WARNING: No permissions found!")
        print("   Run: python manage.py init_permissions")
        return
    
    print("   ✅ Permissions initialized")
    
    # Check vehicles module permissions for each role
    print("\n2. Vehicles Module Permissions by Role:")
    print("-" * 60)
    
    for role_code, role_name in UserRole.CHOICES:
        try:
            perm = RolePermission.objects.get(
                role=role_code,
                module_name=ModuleName.VEHICLES
            )
            print(f"\n   {role_name}:")
            print(f"      Access Level: {perm.get_access_level_display()}")
            print(f"      Can Create:   {'✅' if perm.can_create else '❌'}")
            print(f"      Can Edit:     {'✅' if perm.can_edit else '❌'}")
            print(f"      Can Delete:   {'✅' if perm.can_delete else '❌'}")
            print(f"      Can Export:   {'✅' if perm.can_export else '❌'}")
        except RolePermission.DoesNotExist:
            print(f"\n   {role_name}: ❌ Not configured")
    
    # Test template tag functionality
    print("\n3. Testing Template Tag Functions:")
    print("-" * 60)
    
    # Try to get a test user
    test_user = User.objects.filter(is_superuser=False).first()
    
    if test_user:
        print(f"\n   Testing with user: {test_user.username} (Role: {test_user.get_role_display()})")
        
        try:
            from apps.permissions.templatetags.permission_tags import (
                has_module_permission, can_edit, can_delete, can_create
            )
            
            # Test functions
            has_access = has_module_permission(test_user, ModuleName.VEHICLES, AccessLevel.READ_ONLY)
            can_edit_result = can_edit(test_user, ModuleName.VEHICLES)
            can_delete_result = can_delete(test_user, ModuleName.VEHICLES)
            can_create_result = can_create(test_user, ModuleName.VEHICLES)
            
            print(f"      Has Access:  {'✅' if has_access else '❌'}")
            print(f"      Can Edit:    {'✅' if can_edit_result else '❌'}")
            print(f"      Can Delete:  {'✅' if can_delete_result else '❌'}")
            print(f"      Can Create:  {'✅' if can_create_result else '❌'}")
            
        except ImportError as e:
            print(f"   ❌ Error importing template tags: {e}")
            print("   Make sure the templatetags directory exists and has __init__.py")
    else:
        print("   ⚠️  No non-superuser found for testing")
        print("   Create a test user with a role to test template tags")
    
    # Check superuser
    superuser = User.objects.filter(is_superuser=True).first()
    if superuser:
        print(f"\n   Superuser ({superuser.username}) should have full access to everything")
        print("   ✅ Superusers bypass all permission checks")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    
    print("\n📝 NEXT STEPS:")
    print("   1. Ensure permissions are initialized:")
    print("      python manage.py init_permissions")
    print("\n   2. Test in browser:")
    print("      - Login with different user roles")
    print("      - Navigate to a vehicle detail page")
    print("      - Check which buttons are visible")
    print("\n   3. If buttons still don't show:")
    print("      - Restart the Django server")
    print("      - Clear browser cache")
    print("      - Check user's assigned role")
    print()

if __name__ == '__main__':
    test_permissions()
