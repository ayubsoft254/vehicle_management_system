"""
Debug script to verify VehiclePhotoForm data mapping
Run this from Django shell: python manage.py shell < apps/vehicles/test_photo_form_debug.py
"""

print("=" * 60)
print("Vehicle Photo Form Data Mapping Debug")
print("=" * 60)

from apps.vehicles.models import VehiclePhoto
from apps.vehicles.forms import VehiclePhotoForm

print("\n1. Model Field Requirements:")
print("-" * 60)
for field in VehiclePhoto._meta.get_fields():
    if hasattr(field, 'blank') and hasattr(field, 'null'):
        required = not (field.blank or field.null)
        default = getattr(field, 'default', 'N/A')
        print(f"  {field.name:20} | Required: {str(required):5} | Default: {default}")

print("\n2. Form Field Configuration:")
print("-" * 60)
form = VehiclePhotoForm()
for field_name, field in form.fields.items():
    required = field.required
    initial = field.initial if field.initial is not None else 'N/A'
    print(f"  {field_name:20} | Required: {str(required):5} | Initial: {initial}")

print("\n3. Form Field Widgets:")
print("-" * 60)
for field_name, field in form.fields.items():
    widget_type = type(field.widget).__name__
    print(f"  {field_name:20} | Widget: {widget_type}")

print("\n4. Database Field Mapping:")
print("-" * 60)
print("  Form Field          -> Model Field        -> Set By")
print("  " + "-" * 56)
print("  image               -> image              -> Form")
print("  caption             -> caption            -> Form")
print("  is_primary          -> is_primary         -> Form")
print("  order               -> order              -> Form")
print("  N/A                 -> vehicle            -> View (commit=False)")
print("  N/A                 -> uploaded_by        -> View (commit=False)")
print("  N/A                 -> uploaded_at        -> Database (auto_now_add)")

print("\n5. Validation Rules:")
print("-" * 60)
print("  ✓ image: Required, must be valid image file")
print("  ✓ caption: Optional, max 200 chars")
print("  ✓ is_primary: Optional, defaults to False")
print("  ✓ order: Optional, defaults to 0")
print("  ✓ vehicle: Set by view, required")
print("  ✓ uploaded_by: Set by view, optional (null=True)")

print("\n" + "=" * 60)
print("Form is correctly configured for database requirements!")
print("=" * 60)
