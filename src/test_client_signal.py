#!/usr/bin/env python
"""
Test script to verify client creation signal
Run from src directory: python test_client_signal.py
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.authentication.models import User
from apps.clients.models import Client
from utils.constants import UserRole
import uuid

def test_client_signal():
    print("\n" + "="*60)
    print("CLIENT CREATION SIGNAL TEST")
    print("="*60)
    
    # Test 1: Check if signal is connected
    print("\n1. Checking if signals are registered...")
    from django.db.models.signals import post_save
    receivers = post_save._live_receivers(User)
    print(f"   Found {len(receivers)} signal receivers for User model")
    
    # Test 2: Create a test user with CLIENT role
    print("\n2. Creating test CLIENT user...")
    test_email = f"test_client_{uuid.uuid4().hex[:8]}@example.com"
    
    try:
        test_user = User.objects.create_user(
            email=test_email,
            password='testpass123',
            first_name='Test',
            last_name='Client',
            phone='+254712345678',
            role=UserRole.CLIENT
        )
        print(f"   ✅ User created: {test_user.email}")
        print(f"      Role: {test_user.get_role_display()}")
        print(f"      ID: {test_user.id}")
        
        # Check if UserProfile was created
        if hasattr(test_user, 'profile'):
            print(f"   ✅ UserProfile created")
        else:
            print(f"   ❌ UserProfile NOT created")
        
        # Check if Client profile was created
        if hasattr(test_user, 'client_profile'):
            client = test_user.client_profile
            print(f"   ✅ Client profile created:")
            print(f"      Name: {client.get_full_name()}")
            print(f"      ID Number: {client.id_number}")
            print(f"      Email: {client.email}")
            print(f"      Phone: {client.phone_primary}")
            print(f"      Status: {client.status}")
        else:
            print(f"   ❌ Client profile NOT created")
            
            # Try to find if client exists but not linked
            try:
                orphan_client = Client.objects.filter(
                    email=test_user.email
                ).first()
                if orphan_client:
                    print(f"   ⚠️  Found orphan client (not linked to user):")
                    print(f"      ID: {orphan_client.id}")
                    print(f"      User: {orphan_client.user}")
                else:
                    print(f"   ❌ No client record found at all")
            except Exception as e:
                print(f"   ❌ Error checking for orphan client: {e}")
        
        # Test 3: Try manually triggering the signal
        print("\n3. Manually testing signal function...")
        from apps.authentication.signals import create_user_profile
        
        try:
            # Create another test user
            test_email2 = f"test_client_{uuid.uuid4().hex[:8]}@example.com"
            test_user2 = User(
                email=test_email2,
                first_name='Manual',
                last_name='Test',
                phone='+254723456789',
                role=UserRole.CLIENT
            )
            test_user2.set_password('testpass123')
            
            # Manually call the signal
            print("   Calling create_user_profile directly...")
            create_user_profile(
                sender=User,
                instance=test_user2,
                created=True
            )
            
            # Now save the user
            test_user2.save()
            
            # Check result
            if hasattr(test_user2, 'client_profile'):
                print(f"   ✅ Manual signal test PASSED")
                print(f"      Client: {test_user2.client_profile.get_full_name()}")
            else:
                print(f"   ❌ Manual signal test FAILED")
                
                # Check if client was created
                manual_client = Client.objects.filter(user=test_user2).first()
                if manual_client:
                    print(f"   ⚠️  Client exists but not accessible via reverse relation")
                    print(f"      This suggests a database or migration issue")
                else:
                    print(f"   ❌ No client created at all - signal not working")
            
        except Exception as e:
            print(f"   ❌ Error in manual test: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Test 4: Check for any errors in the signal
        print("\n4. Testing signal with error catching...")
        test_email3 = f"test_client_{uuid.uuid4().hex[:8]}@example.com"
        
        try:
            import logging
            logging.basicConfig(level=logging.INFO)
            
            test_user3 = User.objects.create_user(
                email=test_email3,
                password='testpass123',
                first_name='Debug',
                last_name='Test',
                phone='+254734567890',
                role=UserRole.CLIENT
            )
            print(f"   User created: {test_user3.email}")
            
            # Force check
            import time
            time.sleep(0.5)  # Give signal time to process
            
            # Refresh from database
            test_user3.refresh_from_db()
            
            if hasattr(test_user3, 'client_profile'):
                print(f"   ✅ Client profile verified after refresh")
            else:
                print(f"   ❌ Still no client profile after refresh")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"   ❌ Error creating user: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Test 5: Check existing CLIENT users
    print("\n5. Checking existing CLIENT role users...")
    client_users = User.objects.filter(role=UserRole.CLIENT)
    print(f"   Total CLIENT users: {client_users.count()}")
    
    for user in client_users[:5]:  # Show first 5
        has_profile = hasattr(user, 'client_profile')
        print(f"   - {user.email}: {'✅ Has client profile' if has_profile else '❌ No client profile'}")
    
    # Test 6: Check Client records
    print("\n6. Checking Client records...")
    clients = Client.objects.all()
    print(f"   Total Client records: {clients.count()}")
    
    clients_with_user = clients.filter(user__isnull=False).count()
    clients_without_user = clients.filter(user__isnull=True).count()
    
    print(f"   - Linked to user: {clients_with_user}")
    print(f"   - Not linked: {clients_without_user}")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    
    print("\n📝 DIAGNOSIS:")
    if hasattr(test_user, 'client_profile'):
        print("   ✅ Signal is working correctly!")
        print("   New users with CLIENT role will automatically get a Client profile")
    else:
        print("   ❌ Signal is NOT working!")
        print("\n   Possible causes:")
        print("   1. Signal not properly connected in apps.py")
        print("   2. Database migration issue with OneToOneField reverse relation")
        print("   3. Exception being silently caught in signal")
        print("   4. Circular import preventing signal registration")
        print("\n   Solutions to try:")
        print("   1. Restart Django server")
        print("   2. Run: python manage.py makemigrations")
        print("   3. Run: python manage.py migrate")
        print("   4. Check logs for any errors")
        print("   5. Verify apps.authentication.signals is imported in apps.py")
    
    print("\n   Cleaning up test users...")
    try:
        User.objects.filter(email__startswith='test_client_').delete()
        print("   ✅ Test users deleted")
    except:
        print("   ⚠️  Could not delete test users")
    
    print()

if __name__ == '__main__':
    test_client_signal()
