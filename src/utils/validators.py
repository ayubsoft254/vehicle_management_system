"""
Utils - Custom Validators
Shared validation functions for the Vehicle Management System
"""

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal
import magic  # python-magic for file type detection


# ============================================================================
# PHONE NUMBER VALIDATORS
# ============================================================================

def validate_phone_number(value):
    """
    Validate phone number format
    Accepts: +254712345678, 0712345678, 254712345678
    """
    # Remove spaces, dashes, and parentheses
    cleaned = re.sub(r'[\s\-\(\)]', '', str(value))
    
    # Kenyan phone number patterns
    patterns = [
        r'^(\+254|254)[17]\d{8}$',  # +254712345678 or 254712345678
        r'^0[17]\d{8}$',             # 0712345678
    ]
    
    if not any(re.match(pattern, cleaned) for pattern in patterns):
        raise ValidationError(
            _('Enter a valid phone number. Format: +254712345678 or 0712345678'),
            code='invalid_phone'
        )
    
    return cleaned


def validate_international_phone(value):
    """
    Validate international phone number format
    More lenient for international numbers
    """
    cleaned = re.sub(r'[\s\-\(\)]', '', str(value))
    
    # International format: +XXX followed by 7-15 digits
    pattern = r'^\+\d{7,15}$'
    
    if not re.match(pattern, cleaned):
        raise ValidationError(
            _('Enter a valid international phone number. Format: +1234567890'),
            code='invalid_international_phone'
        )
    
    return cleaned


# ============================================================================
# VEHICLE VALIDATORS
# ============================================================================

def validate_vin(value):
    """
    Validate Vehicle Identification Number (VIN)
    17 characters, alphanumeric, no I, O, Q
    """
    if not value:
        return value
    
    # VIN should be 17 characters
    if len(value) != 17:
        raise ValidationError(
            _('VIN must be exactly 17 characters long.'),
            code='invalid_vin_length'
        )
    
    # VIN should not contain I, O, or Q
    if re.search(r'[IOQ]', value.upper()):
        raise ValidationError(
            _('VIN cannot contain letters I, O, or Q.'),
            code='invalid_vin_characters'
        )
    
    # VIN should be alphanumeric
    if not value.isalnum():
        raise ValidationError(
            _('VIN must contain only letters and numbers.'),
            code='invalid_vin_format'
        )
    
    return value.upper()


def validate_license_plate(value):
    """
    Validate Kenyan license plate format
    Examples: KAA 123A, KBZ 456B, KCA 789C
    """
    if not value:
        return value
    
    # Kenyan plate format: KXX 123X
    pattern = r'^K[A-Z]{2}\s?\d{3}[A-Z]$'
    
    cleaned = value.upper().strip()
    
    if not re.match(pattern, cleaned):
        raise ValidationError(
            _('Enter a valid Kenyan license plate. Format: KAA 123A'),
            code='invalid_license_plate'
        )
    
    return cleaned


def validate_engine_number(value):
    """
    Validate engine number format
    """
    if not value:
        return value
    
    # Engine number should be 6-20 alphanumeric characters
    if not 6 <= len(value) <= 20:
        raise ValidationError(
            _('Engine number must be between 6 and 20 characters.'),
            code='invalid_engine_number_length'
        )
    
    if not value.isalnum():
        raise ValidationError(
            _('Engine number must contain only letters and numbers.'),
            code='invalid_engine_number_format'
        )
    
    return value.upper()


def validate_chassis_number(value):
    """
    Validate chassis number format
    """
    if not value:
        return value
    
    # Chassis number should be 6-20 alphanumeric characters
    if not 6 <= len(value) <= 20:
        raise ValidationError(
            _('Chassis number must be between 6 and 20 characters.'),
            code='invalid_chassis_number_length'
        )
    
    if not value.isalnum():
        raise ValidationError(
            _('Chassis number must contain only letters and numbers.'),
            code='invalid_chassis_number_format'
        )
    
    return value.upper()


def validate_year(value):
    """
    Validate vehicle year
    Should be between 1900 and next year
    """
    current_year = timezone.now().year
    min_year = 1900
    max_year = current_year + 1
    
    if not min_year <= value <= max_year:
        raise ValidationError(
            _(f'Year must be between {min_year} and {max_year}.'),
            code='invalid_year'
        )
    
    return value


def validate_mileage(value):
    """
    Validate vehicle mileage
    """
    if value < 0:
        raise ValidationError(
            _('Mileage cannot be negative.'),
            code='negative_mileage'
        )
    
    if value > 10000000:  # 10 million km is unrealistic
        raise ValidationError(
            _('Mileage seems unrealistic. Please check the value.'),
            code='unrealistic_mileage'
        )
    
    return value


# ============================================================================
# FINANCIAL VALIDATORS
# ============================================================================

def validate_positive_amount(value):
    """
    Validate that amount is positive
    """
    if value <= 0:
        raise ValidationError(
            _('Amount must be greater than zero.'),
            code='non_positive_amount'
        )
    
    return value


def validate_non_negative_amount(value):
    """
    Validate that amount is not negative
    """
    if value < 0:
        raise ValidationError(
            _('Amount cannot be negative.'),
            code='negative_amount'
        )
    
    return value


def validate_percentage(value):
    """
    Validate percentage (0-100)
    """
    if not 0 <= value <= 100:
        raise ValidationError(
            _('Percentage must be between 0 and 100.'),
            code='invalid_percentage'
        )
    
    return value


def validate_interest_rate(value):
    """
    Validate interest rate (0-50%)
    """
    if not 0 <= value <= 50:
        raise ValidationError(
            _('Interest rate must be between 0 and 50%.'),
            code='invalid_interest_rate'
        )
    
    return value


def validate_discount_percentage(value):
    """
    Validate discount percentage (0-100)
    """
    if not 0 <= value <= 100:
        raise ValidationError(
            _('Discount percentage must be between 0 and 100.'),
            code='invalid_discount'
        )
    
    return value


# ============================================================================
# DATE VALIDATORS
# ============================================================================

def validate_future_date(value):
    """
    Validate that date is in the future
    """
    if isinstance(value, datetime):
        value = value.date()
    
    if value <= timezone.now().date():
        raise ValidationError(
            _('Date must be in the future.'),
            code='past_date'
        )
    
    return value


def validate_past_date(value):
    """
    Validate that date is in the past
    """
    if isinstance(value, datetime):
        value = value.date()
    
    if value >= timezone.now().date():
        raise ValidationError(
            _('Date must be in the past.'),
            code='future_date'
        )
    
    return value


def validate_date_not_too_old(value, max_years=100):
    """
    Validate that date is not too far in the past
    """
    if isinstance(value, datetime):
        value = value.date()
    
    years_ago = timezone.now().date().replace(year=timezone.now().year - max_years)
    
    if value < years_ago:
        raise ValidationError(
            _(f'Date cannot be more than {max_years} years ago.'),
            code='date_too_old'
        )
    
    return value


def validate_date_range(start_date, end_date):
    """
    Validate that end_date is after start_date
    """
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    if end_date < start_date:
        raise ValidationError(
            _('End date must be after start date.'),
            code='invalid_date_range'
        )
    
    return True


# ============================================================================
# IDENTIFICATION VALIDATORS
# ============================================================================

def validate_national_id(value):
    """
    Validate Kenyan National ID
    Should be 7-8 digits
    """
    if not value:
        return value
    
    cleaned = re.sub(r'\D', '', str(value))
    
    if not 7 <= len(cleaned) <= 8:
        raise ValidationError(
            _('National ID must be 7 or 8 digits.'),
            code='invalid_national_id'
        )
    
    return cleaned


def validate_passport_number(value):
    """
    Validate passport number format
    Alphanumeric, 6-12 characters
    """
    if not value:
        return value
    
    cleaned = value.strip().upper()
    
    if not 6 <= len(cleaned) <= 12:
        raise ValidationError(
            _('Passport number must be between 6 and 12 characters.'),
            code='invalid_passport_length'
        )
    
    if not cleaned.isalnum():
        raise ValidationError(
            _('Passport number must contain only letters and numbers.'),
            code='invalid_passport_format'
        )
    
    return cleaned


def validate_kra_pin(value):
    """
    Validate KRA PIN format
    Format: A123456789X (letter + 9 digits + letter)
    """
    if not value:
        return value
    
    cleaned = value.strip().upper()
    pattern = r'^[A-Z]\d{9}[A-Z]$'
    
    if not re.match(pattern, cleaned):
        raise ValidationError(
            _('Enter a valid KRA PIN. Format: A123456789X'),
            code='invalid_kra_pin'
        )
    
    return cleaned


# ============================================================================
# FILE VALIDATORS
# ============================================================================

def validate_file_size(value, max_size_mb=10):
    """
    Validate uploaded file size
    
    Args:
        value: UploadedFile object
        max_size_mb: Maximum file size in MB
    """
    max_size = max_size_mb * 1024 * 1024  # Convert to bytes
    
    if value.size > max_size:
        raise ValidationError(
            _(f'File size cannot exceed {max_size_mb}MB. Current size: {value.size / (1024*1024):.2f}MB'),
            code='file_too_large'
        )
    
    return value


def validate_image_file(value):
    """
    Validate that uploaded file is an image
    """
    valid_mime_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    
    try:
        file_mime_type = magic.from_buffer(value.read(1024), mime=True)
        value.seek(0)  # Reset file pointer
        
        if file_mime_type not in valid_mime_types:
            raise ValidationError(
                _('Only JPEG, PNG, GIF, and WebP images are allowed.'),
                code='invalid_image_type'
            )
    except Exception:
        # Fallback to extension check if magic fails
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        ext = value.name.lower().split('.')[-1] if '.' in value.name else ''
        
        if f'.{ext}' not in valid_extensions:
            raise ValidationError(
                _('Only JPEG, PNG, GIF, and WebP images are allowed.'),
                code='invalid_image_extension'
            )
    
    return value


def validate_pdf_file(value):
    """
    Validate that uploaded file is a PDF
    """
    valid_mime_types = ['application/pdf']
    
    try:
        file_mime_type = magic.from_buffer(value.read(1024), mime=True)
        value.seek(0)
        
        if file_mime_type not in valid_mime_types:
            raise ValidationError(
                _('Only PDF files are allowed.'),
                code='invalid_pdf_type'
            )
    except Exception:
        # Fallback to extension check
        if not value.name.lower().endswith('.pdf'):
            raise ValidationError(
                _('Only PDF files are allowed.'),
                code='invalid_pdf_extension'
            )
    
    return value


def validate_document_file(value):
    """
    Validate document file types (PDF, DOC, DOCX, XLS, XLSX)
    """
    valid_mime_types = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ]
    
    valid_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx']
    
    try:
        file_mime_type = magic.from_buffer(value.read(1024), mime=True)
        value.seek(0)
        
        if file_mime_type not in valid_mime_types:
            raise ValidationError(
                _('Only PDF, Word, and Excel documents are allowed.'),
                code='invalid_document_type'
            )
    except Exception:
        # Fallback to extension check
        ext = f".{value.name.lower().split('.')[-1]}" if '.' in value.name else ''
        
        if ext not in valid_extensions:
            raise ValidationError(
                _('Only PDF, Word, and Excel documents are allowed.'),
                code='invalid_document_extension'
            )
    
    return value


# ============================================================================
# TEXT VALIDATORS
# ============================================================================

def validate_no_special_characters(value):
    """
    Validate that text contains no special characters
    Only letters, numbers, spaces, hyphens, and underscores allowed
    """
    pattern = r'^[a-zA-Z0-9\s\-_]+$'
    
    if not re.match(pattern, value):
        raise ValidationError(
            _('Only letters, numbers, spaces, hyphens, and underscores are allowed.'),
            code='invalid_characters'
        )
    
    return value


def validate_alpha_only(value):
    """
    Validate that text contains only letters
    """
    if not value.replace(' ', '').isalpha():
        raise ValidationError(
            _('Only letters are allowed.'),
            code='non_alpha'
        )
    
    return value


def validate_alphanumeric(value):
    """
    Validate that text contains only letters and numbers
    """
    if not value.replace(' ', '').isalnum():
        raise ValidationError(
            _('Only letters and numbers are allowed.'),
            code='non_alphanumeric'
        )
    
    return value


def validate_min_words(value, min_words=10):
    """
    Validate minimum number of words in text
    """
    word_count = len(value.split())
    
    if word_count < min_words:
        raise ValidationError(
            _(f'Text must contain at least {min_words} words. Current: {word_count} words.'),
            code='insufficient_words'
        )
    
    return value


# ============================================================================
# EMAIL VALIDATORS
# ============================================================================

def validate_business_email(value):
    """
    Validate business email (no free email providers)
    """
    free_domains = [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'aol.com', 'icloud.com', 'mail.com', 'protonmail.com'
    ]
    
    domain = value.split('@')[-1].lower()
    
    if domain in free_domains:
        raise ValidationError(
            _('Please use a business email address.'),
            code='free_email_not_allowed'
        )
    
    return value


# ============================================================================
# URL VALIDATORS
# ============================================================================

def validate_secure_url(value):
    """
    Validate that URL uses HTTPS
    """
    if not value.startswith('https://'):
        raise ValidationError(
            _('URL must use HTTPS protocol.'),
            code='insecure_url'
        )
    
    return value


# ============================================================================
# COMPOSITE VALIDATORS
# ============================================================================

def validate_payment_amount(amount, min_amount=None, max_amount=None):
    """
    Validate payment amount with optional min/max constraints
    """
    if amount <= 0:
        raise ValidationError(
            _('Payment amount must be greater than zero.'),
            code='invalid_payment_amount'
        )
    
    if min_amount and amount < min_amount:
        raise ValidationError(
            _(f'Payment amount must be at least {min_amount}.'),
            code='payment_too_low'
        )
    
    if max_amount and amount > max_amount:
        raise ValidationError(
            _(f'Payment amount cannot exceed {max_amount}.'),
            code='payment_too_high'
        )
    
    return amount


def validate_installment_schedule(total_amount, down_payment, installment_amount, num_installments):
    """
    Validate installment payment schedule
    """
    if down_payment < 0:
        raise ValidationError(
            _('Down payment cannot be negative.'),
            code='negative_down_payment'
        )
    
    if down_payment >= total_amount:
        raise ValidationError(
            _('Down payment must be less than total amount.'),
            code='down_payment_too_high'
        )
    
    remaining = total_amount - down_payment
    expected_total = installment_amount * num_installments
    
    if abs(remaining - expected_total) > 1:  # Allow for rounding
        raise ValidationError(
            _(f'Installment calculation error. Remaining: {remaining}, Expected: {expected_total}'),
            code='invalid_installment_schedule'
        )
    
    return True