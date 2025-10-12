#!/bin/bash

# WhiteNoise Deployment Script for Ubuntu Server
# This script deploys the nginx configuration on the host server

set -e  # Exit on error

echo "=================================================="
echo "WhiteNoise + nginx Deployment Script"
echo "Vehicle Management System"
echo "=================================================="
echo ""

# Configuration
NGINX_CONFIG_NAME="vms.ayubsoft-inc.systems"
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"
PROJECT_DIR="$(pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root or with sudo${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Backing up current nginx configuration...${NC}"
if [ -f "$NGINX_SITES_AVAILABLE/$NGINX_CONFIG_NAME" ]; then
    cp "$NGINX_SITES_AVAILABLE/$NGINX_CONFIG_NAME" "$NGINX_SITES_AVAILABLE/$NGINX_CONFIG_NAME.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${GREEN}✓ Backup created${NC}"
else
    echo -e "${YELLOW}No existing configuration found${NC}"
fi

echo ""
echo -e "${YELLOW}Step 2: Deploying new nginx configuration...${NC}"
if [ -f "$PROJECT_DIR/nginx.conf" ]; then
    cp "$PROJECT_DIR/nginx.conf" "$NGINX_SITES_AVAILABLE/$NGINX_CONFIG_NAME"
    echo -e "${GREEN}✓ nginx configuration deployed${NC}"
else
    echo -e "${RED}Error: nginx.conf not found in $PROJECT_DIR${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 3: Creating symbolic link...${NC}"
if [ ! -L "$NGINX_SITES_ENABLED/$NGINX_CONFIG_NAME" ]; then
    ln -sf "$NGINX_SITES_AVAILABLE/$NGINX_CONFIG_NAME" "$NGINX_SITES_ENABLED/$NGINX_CONFIG_NAME"
    echo -e "${GREEN}✓ Symbolic link created${NC}"
else
    echo -e "${GREEN}✓ Symbolic link already exists${NC}"
fi

echo ""
echo -e "${YELLOW}Step 4: Testing nginx configuration...${NC}"
if nginx -t; then
    echo -e "${GREEN}✓ nginx configuration is valid${NC}"
else
    echo -e "${RED}✗ nginx configuration test failed${NC}"
    echo -e "${YELLOW}Restoring backup...${NC}"
    if [ -f "$NGINX_SITES_AVAILABLE/$NGINX_CONFIG_NAME.backup.$(date +%Y%m%d_%H%M%S)" ]; then
        cp "$NGINX_SITES_AVAILABLE/$NGINX_CONFIG_NAME.backup.$(date +%Y%m%d_%H%M%S)" "$NGINX_SITES_AVAILABLE/$NGINX_CONFIG_NAME"
    fi
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 5: Reloading nginx...${NC}"
systemctl reload nginx
echo -e "${GREEN}✓ nginx reloaded successfully${NC}"

echo ""
echo -e "${YELLOW}Step 6: Checking nginx status...${NC}"
systemctl status nginx --no-pager | head -n 5

echo ""
echo -e "${GREEN}=================================================="
echo "Deployment Complete!"
echo "==================================================${NC}"
echo ""
echo "Next steps:"
echo "1. Rebuild Docker container: docker-compose build --no-cache"
echo "2. Restart container: docker-compose up -d"
echo "3. Check logs: docker-compose logs -f web"
echo "4. Test admin panel: https://vms.ayubsoft-inc.systems/admin/"
echo ""
echo "Useful commands:"
echo "  - View nginx logs: tail -f /var/log/nginx/$NGINX_CONFIG_NAME.error.log"
echo "  - View access logs: tail -f /var/log/nginx/$NGINX_CONFIG_NAME.access.log"
echo "  - Test Docker connection: curl http://localhost:3333"
echo "  - Restart nginx: sudo systemctl restart nginx"
echo ""
