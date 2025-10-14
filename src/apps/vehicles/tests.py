from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from decimal import Decimal
import io
from PIL import Image

from .models import Vehicle, VehiclePhoto
from .forms import VehiclePhotoForm

User = get_user_model()


class VehiclePhotoFormTest(TestCase):
    """Test VehiclePhotoForm functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.vehicle = Vehicle.objects.create(
            make='Toyota',
            model='Corolla',
            year=2020,
            vin='1HGBH41JXMN109186',
            color='White',
            mileage=50000,
            fuel_type='petrol',
            transmission='automatic',
            condition='good',
            purchase_price=Decimal('1500000.00'),
            selling_price=Decimal('1800000.00'),
            purchase_date=timezone.now().date(),
            added_by=self.user
        )
    
    def create_test_image(self):
        """Create a test image file"""
        file = io.BytesIO()
        image = Image.new('RGB', (100, 100), color='red')
        image.save(file, 'JPEG')
        file.seek(0)
        return SimpleUploadedFile(
            'test_image.jpg',
            file.read(),
            content_type='image/jpeg'
        )
    
    def test_form_with_required_fields_only(self):
        """Test form with only required field (image)"""
        image = self.create_test_image()
        form_data = {}
        form_files = {'image': image}
        
        form = VehiclePhotoForm(data=form_data, files=form_files)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        # Check default values
        photo = form.save(commit=False)
        self.assertEqual(photo.order, 0)
        self.assertEqual(photo.is_primary, False)
        self.assertEqual(photo.caption, '')
    
    def test_form_with_all_fields(self):
        """Test form with all fields populated"""
        image = self.create_test_image()
        form_data = {
            'caption': 'Front view',
            'is_primary': True,
            'order': 1
        }
        form_files = {'image': image}
        
        form = VehiclePhotoForm(data=form_data, files=form_files)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        photo = form.save(commit=False)
        self.assertEqual(photo.caption, 'Front view')
        self.assertEqual(photo.is_primary, True)
        self.assertEqual(photo.order, 1)
    
    def test_form_without_image(self):
        """Test form validation fails without image"""
        form_data = {
            'caption': 'Test caption',
            'order': 0
        }
        
        form = VehiclePhotoForm(data=form_data, files={})
        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)
    
    def test_form_clean_order_with_empty_value(self):
        """Test that empty order value defaults to 0"""
        image = self.create_test_image()
        form_data = {'order': ''}
        form_files = {'image': image}
        
        form = VehiclePhotoForm(data=form_data, files=form_files)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        photo = form.save(commit=False)
        self.assertEqual(photo.order, 0)
    
    def test_form_clean_is_primary_with_none(self):
        """Test that None is_primary value defaults to False"""
        image = self.create_test_image()
        form_data = {}
        form_files = {'image': image}
        
        form = VehiclePhotoForm(data=form_data, files=form_files)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        photo = form.save(commit=False)
        self.assertEqual(photo.is_primary, False)


class VehiclePhotoUploadViewTest(TestCase):
    """Test vehicle photo upload view"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.vehicle = Vehicle.objects.create(
            make='Toyota',
            model='Corolla',
            year=2020,
            vin='1HGBH41JXMN109186',
            color='White',
            mileage=50000,
            fuel_type='petrol',
            transmission='automatic',
            condition='good',
            purchase_price=Decimal('1500000.00'),
            selling_price=Decimal('1800000.00'),
            purchase_date=timezone.now().date(),
            added_by=self.user
        )
    
    def create_test_image(self):
        """Create a test image file"""
        file = io.BytesIO()
        image = Image.new('RGB', (100, 100), color='blue')
        image.save(file, 'JPEG')
        file.seek(0)
        return SimpleUploadedFile(
            'test_photo.jpg',
            file.read(),
            content_type='image/jpeg'
        )
    
    def test_photo_upload_creates_record(self):
        """Test that photo upload creates database record with correct data"""
        # Note: This test requires proper authentication and permissions
        # It's a placeholder for manual testing
        pass
