#!/bin/bash

# Quick Test Script - Run on Ubuntu Server
# Usage: bash test-static-files.sh

echo "=========================================="
echo "STATIC FILES QUICK TEST"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test 1: Container Running
echo -n "Test 1: Container Running... "
if docker-compose ps | grep -q "web.*Up"; then
    echo -e "${GREEN}✓ PASS${NC}"
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "Container is not running. Run: docker-compose up -d"
    exit 1
fi

# Test 2: Static Files Collected
echo -n "Test 2: Static Files Collected... "
if docker-compose exec -T web test -f /app/static_collected/admin/css/base.css; then
    echo -e "${GREEN}✓ PASS${NC}"
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "Running collectstatic..."
    docker-compose exec -T web python manage.py collectstatic --noinput --clear
fi

# Test 3: WhiteNoise Installed
echo -n "Test 3: WhiteNoise Installed... "
if docker-compose exec -T web pip list | grep -q whitenoise; then
    echo -e "${GREEN}✓ PASS${NC}"
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "WhiteNoise not installed. Rebuild container:"
    echo "  docker-compose build --no-cache web"
    exit 1
fi

# Test 4: Django Serves Static File
echo -n "Test 4: Django Serves Static File... "
HTTP_CODE=$(docker-compose exec -T web curl -s -o /dev/null -w "%{http_code}" http://localhost:3333/static/admin/css/base.css)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASS (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}✗ FAIL (HTTP $HTTP_CODE)${NC}"
    echo "Django is not serving static files correctly"
fi

# Test 5: Host Can Access Django
echo -n "Test 5: Host Can Access Django... "
if command -v curl &> /dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3333/admin/)
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
        echo -e "${GREEN}✓ PASS (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "${RED}✗ FAIL (HTTP $HTTP_CODE)${NC}"
    fi
else
    echo -e "${YELLOW}⊘ SKIP (curl not available)${NC}"
fi

# Test 6: nginx Can Access Django
echo -n "Test 6: nginx Proxies to Django... "
if command -v curl &> /dev/null; then
    if curl -k -s -o /dev/null -w "%{http_code}" https://vms.ayubsoft-inc.systems/admin/ | grep -q "200\|302"; then
        echo -e "${GREEN}✓ PASS${NC}"
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo "nginx may not be configured correctly"
    fi
else
    echo -e "${YELLOW}⊘ SKIP (curl not available)${NC}"
fi

# Test 7: Static Files Through nginx
echo -n "Test 7: Static Files Through nginx... "
if command -v curl &> /dev/null; then
    HTTP_CODE=$(curl -k -s -o /dev/null -w "%{http_code}" https://vms.ayubsoft-inc.systems/static/admin/css/base.css)
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✓ PASS (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "${RED}✗ FAIL (HTTP $HTTP_CODE)${NC}"
        echo "Static files not accessible through nginx"
    fi
else
    echo -e "${YELLOW}⊘ SKIP (curl not available)${NC}"
fi

echo ""
echo "=========================================="
echo "DETAILED INFORMATION"
echo "=========================================="

echo ""
echo "Static Files Count:"
docker-compose exec -T web find /app/static_collected -type f | wc -l

echo ""
echo "Admin Static Files:"
docker-compose exec -T web ls -lh /app/static_collected/admin/css/*.css 2>/dev/null | head -3

echo ""
echo "Django Settings:"
docker-compose exec -T web python manage.py shell << 'PYTHON'
from django.conf import settings
print(f"DEBUG: {settings.DEBUG}")
print(f"STATIC_URL: {settings.STATIC_URL}")
print(f"STATIC_ROOT: {settings.STATIC_ROOT}")

# Check for WhiteNoise middleware
has_whitenoise = any('whitenoise' in m.lower() for m in settings.MIDDLEWARE)
print(f"WhiteNoise Middleware: {'✓ Found' if has_whitenoise else '✗ Missing'}")
PYTHON

echo ""
echo "=========================================="
echo "RECOMMENDATIONS"
echo "=========================================="
echo ""
echo "If tests failed:"
echo "1. Rebuild container: docker-compose build --no-cache web"
echo "2. Restart: docker-compose up -d"
echo "3. Collect static: docker-compose exec web python manage.py collectstatic --noinput"
echo "4. Check logs: docker-compose logs web --tail=50"
echo "5. View detailed troubleshooting: cat TROUBLESHOOTING_STATIC_FILES.md"
echo ""
echo "Test in browser:"
echo "  https://vms.ayubsoft-inc.systems/admin/"
echo ""
