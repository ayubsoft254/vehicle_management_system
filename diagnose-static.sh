#!/bin/bash

# Diagnostic Script for Static Files Issue
# Run this inside the container: docker-compose exec web bash diagnose-static.sh

echo "========================================"
echo "STATIC FILES DIAGNOSTIC"
echo "========================================"
echo ""

echo "1. Checking Django Settings..."
echo "----------------------------"
python manage.py diffsettings | grep -E "STATIC|WHITENOISE|DEBUG"
echo ""

echo "2. Checking Middleware..."
echo "----------------------------"
python manage.py diffsettings | grep MIDDLEWARE
echo ""

echo "3. Checking if static_collected directory exists..."
echo "----------------------------"
if [ -d "/app/static_collected" ]; then
    echo "✓ /app/static_collected exists"
    echo "Size: $(du -sh /app/static_collected)"
else
    echo "✗ /app/static_collected does NOT exist"
fi
echo ""

echo "4. Checking admin static files..."
echo "----------------------------"
if [ -d "/app/static_collected/admin" ]; then
    echo "✓ /app/static_collected/admin exists"
    echo "Files count: $(find /app/static_collected/admin -type f | wc -l)"
    echo ""
    echo "Sample admin CSS files:"
    ls -lh /app/static_collected/admin/css/*.css | head -5
else
    echo "✗ /app/static_collected/admin does NOT exist"
fi
echo ""

echo "5. Checking WhiteNoise manifest..."
echo "----------------------------"
if [ -f "/app/static_collected/staticfiles.json" ]; then
    echo "✓ WhiteNoise manifest exists"
    echo "Manifest entries: $(python -c 'import json; print(len(json.load(open("/app/static_collected/staticfiles.json"))))' 2>/dev/null || echo 'Error reading')"
else
    echo "✗ WhiteNoise manifest NOT found"
fi
echo ""

echo "6. Testing URL resolution..."
echo "----------------------------"
echo "Testing static file access from Django..."
python manage.py shell << 'PYTHON'
from django.contrib.staticfiles.storage import staticfiles_storage
from django.conf import settings

print(f"STATIC_URL: {settings.STATIC_URL}")
print(f"STATIC_ROOT: {settings.STATIC_ROOT}")
print(f"DEBUG: {settings.DEBUG}")
print()

try:
    url = staticfiles_storage.url('admin/css/base.css')
    print(f"✓ Admin CSS URL: {url}")
except Exception as e:
    print(f"✗ Error getting URL: {e}")

try:
    path = staticfiles_storage.path('admin/css/base.css')
    print(f"✓ Admin CSS Path: {path}")
    import os
    if os.path.exists(path):
        print(f"  File exists: YES ({os.path.getsize(path)} bytes)")
    else:
        print(f"  File exists: NO")
except Exception as e:
    print(f"✗ Error getting path: {e}")
PYTHON
echo ""

echo "7. Testing HTTP access..."
echo "----------------------------"
echo "Testing if Gunicorn is serving static files..."
curl -I http://localhost:3333/static/admin/css/base.css 2>/dev/null | head -5
echo ""

echo "8. Checking installed packages..."
echo "----------------------------"
pip list | grep -i whitenoise
echo ""

echo "9. Environment variables..."
echo "----------------------------"
echo "DEBUG = $DEBUG"
echo "DJANGO_SETTINGS_MODULE = $DJANGO_SETTINGS_MODULE"
echo ""

echo "========================================"
echo "DIAGNOSTIC COMPLETE"
echo "========================================"
echo ""
echo "RECOMMENDATIONS:"
echo "1. If static_collected doesn't exist: Run 'python manage.py collectstatic --noinput'"
echo "2. If WhiteNoise not installed: Rebuild container"
echo "3. If admin files missing: Check INSTALLED_APPS includes django.contrib.admin"
echo "4. If 404 on static files: Check nginx config proxies to Django"
echo "5. If DEBUG=True: Static files served by Django dev server"
echo ""
