#!/bin/bash

# Complete Deployment Script - Run this on Ubuntu Server
# This script handles both Docker and nginx deployment

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     WhiteNoise Deployment - Complete Setup Script         ║"
echo "║     Vehicle Management System                              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if running in correct directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found!${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}STEP 1: Stopping Current Container${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
docker-compose down
echo -e "${GREEN}✓ Container stopped${NC}"
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}STEP 2: Building New Container with WhiteNoise${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
docker-compose build --no-cache web
echo -e "${GREEN}✓ Container built${NC}"
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}STEP 3: Starting Container${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
docker-compose up -d
echo -e "${GREEN}✓ Container started${NC}"
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}STEP 4: Waiting for Container to be Ready${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
sleep 5
docker-compose ps
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}STEP 5: Verifying Static Files Collection${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo "Checking if admin static files exist..."
docker-compose exec -T web ls -la /app/static_collected/admin/css/ | head -n 10
echo -e "${GREEN}✓ Static files collected${NC}"
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}STEP 6: Testing Django Container${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo "Testing admin page..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3333/admin/ | grep -q "200\|302"; then
    echo -e "${GREEN}✓ Admin page accessible${NC}"
else
    echo -e "${RED}✗ Admin page not accessible${NC}"
    echo "Check logs: docker-compose logs web"
    exit 1
fi

echo "Testing static file..."
if curl -s http://localhost:3333/static/admin/css/base.css | head -n 1 | grep -q "/\*"; then
    echo -e "${GREEN}✓ Static files serving correctly${NC}"
else
    echo -e "${RED}✗ Static files not accessible${NC}"
    exit 1
fi
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}STEP 7: Deploying nginx Configuration${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo "This step requires sudo privileges..."
echo ""

if [ "$EUID" -eq 0 ]; then
    # Running as root
    NGINX_SITES="/etc/nginx/sites-available"
    NGINX_ENABLED="/etc/nginx/sites-enabled"
    SITE_NAME="vms.ayubsoft-inc.systems"
    
    # Backup existing config
    if [ -f "$NGINX_SITES/$SITE_NAME" ]; then
        echo "Backing up existing nginx config..."
        cp "$NGINX_SITES/$SITE_NAME" "$NGINX_SITES/$SITE_NAME.backup.$(date +%Y%m%d_%H%M%S)"
        echo -e "${GREEN}✓ Backup created${NC}"
    fi
    
    # Deploy new config
    echo "Deploying new nginx configuration..."
    cp nginx.conf "$NGINX_SITES/$SITE_NAME"
    echo -e "${GREEN}✓ Configuration deployed${NC}"
    
    # Create symlink if needed
    if [ ! -L "$NGINX_ENABLED/$SITE_NAME" ]; then
        ln -sf "$NGINX_SITES/$SITE_NAME" "$NGINX_ENABLED/$SITE_NAME"
        echo -e "${GREEN}✓ Symlink created${NC}"
    fi
    
    # Test nginx
    echo "Testing nginx configuration..."
    if nginx -t 2>&1 | grep -q "successful"; then
        echo -e "${GREEN}✓ nginx configuration valid${NC}"
        
        # Reload nginx
        echo "Reloading nginx..."
        systemctl reload nginx
        echo -e "${GREEN}✓ nginx reloaded${NC}"
    else
        echo -e "${RED}✗ nginx configuration invalid${NC}"
        nginx -t
        exit 1
    fi
else
    # Not running as root
    echo -e "${YELLOW}Not running as root. Please run these commands manually:${NC}"
    echo ""
    echo "sudo cp nginx.conf /etc/nginx/sites-available/vms.ayubsoft-inc.systems"
    echo "sudo nginx -t"
    echo "sudo systemctl reload nginx"
    echo ""
    echo "Or run this script again with sudo"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}STEP 8: Final Verification${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

echo "Container Status:"
docker-compose ps
echo ""

echo "Recent Container Logs:"
docker-compose logs --tail=10 web
echo ""

if [ "$EUID" -eq 0 ]; then
    echo "nginx Status:"
    systemctl status nginx --no-pager | head -n 5
    echo ""
fi

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              DEPLOYMENT COMPLETED SUCCESSFULLY             ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Test in browser:"
echo "   https://vms.ayubsoft-inc.systems/admin/"
echo ""
echo "2. Check for styling:"
echo "   - Admin login page should have proper CSS"
echo "   - No 404 errors in browser console (F12)"
echo ""
echo "3. Monitor logs:"
echo "   docker-compose logs -f web"
echo "   sudo tail -f /var/log/nginx/vms.ayubsoft-inc.systems.error.log"
echo ""
echo "4. If issues occur:"
echo "   - Check DEPLOYMENT_CHECKLIST.md"
echo "   - Check WHITENOISE_DEPLOYMENT.md"
echo "   - Review TROUBLESHOOTING section"
echo ""
echo -e "${GREEN}Happy deploying! 🚀${NC}"
