#!/bin/bash
# Vehicle Management System - Ubuntu Quick Setup Script
# Run this script on Ubuntu Server to set up the application

set -e

echo "================================================"
echo "Vehicle Management System - Ubuntu Setup"
echo "================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}Please do not run this script as root${NC}"
    echo "Run as regular user with sudo privileges"
    exit 1
fi

echo -e "${BLUE}Step 1: Checking prerequisites...${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Creating .env from template..."
    cp .env.example .env
    echo -e "${GREEN}.env file created${NC}"
    echo ""
    echo -e "${RED}IMPORTANT: Edit .env file before continuing!${NC}"
    echo "Set the following:"
    echo "  - SECRET_KEY (generate with: python3 -c \"import secrets; print(secrets.token_urlsafe(50))\")"
    echo "  - DB_PASSWORD"
    echo "  - Email settings"
    echo ""
    read -p "Have you edited the .env file? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Please edit .env and run this script again"
        exit 0
    fi
fi

# Check Docker
echo -e "${BLUE}Checking Docker installation...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker not found. Installing...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${GREEN}Docker installed${NC}"
    echo -e "${RED}Please log out and log back in, then run this script again${NC}"
    exit 0
else
    echo -e "${GREEN}Docker found: $(docker --version)${NC}"
fi

# Check Docker Compose
echo -e "${BLUE}Checking Docker Compose installation...${NC}"
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Docker Compose not found. Installing...${NC}"
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}Docker Compose installed${NC}"
else
    echo -e "${GREEN}Docker Compose found: $(docker-compose --version)${NC}"
fi

# Check if make is installed
if ! command -v make &> /dev/null; then
    echo -e "${YELLOW}make not found. Installing...${NC}"
    sudo apt update
    sudo apt install -y make
fi

echo ""
echo -e "${BLUE}Step 2: Deploying application...${NC}"
echo "This will:"
echo "  - Build Docker images"
echo "  - Start all containers"
echo "  - Run database migrations"
echo "  - Collect static files"
echo ""
read -p "Continue with deployment? (yes/no): " deploy
if [ "$deploy" != "yes" ]; then
    echo "Deployment cancelled"
    exit 0
fi

# Deploy
make deploy

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo -e "${BLUE}Step 3: Creating admin user...${NC}"
echo "You will be prompted to create an admin user"
echo ""
make createsuperuser

echo ""
echo "================================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo "================================================"
echo ""
echo "Your application is running!"
echo ""
echo "Local access:"
echo "  - Application: http://localhost:3333"
echo "  - Admin: http://localhost:3333/admin/"
echo ""
echo "Next steps:"
echo "  1. Install Nginx: sudo apt install nginx"
echo "  2. Configure Nginx: sudo cp nginx.conf.example /etc/nginx/sites-available/vms"
echo "  3. Enable site: sudo ln -s /etc/nginx/sites-available/vms /etc/nginx/sites-enabled/"
echo "  4. Update Nginx config with your domain/IP"
echo "  5. Test: sudo nginx -t"
echo "  6. Restart: sudo systemctl restart nginx"
echo "  7. Setup SSL: sudo apt install certbot python3-certbot-nginx"
echo "  8. Get certificate: sudo certbot --nginx -d yourdomain.com"
echo ""
echo "Useful commands:"
echo "  make help       - Show all commands"
echo "  make ps         - Show container status"
echo "  make logs-web   - View web logs"
echo "  make backup-db  - Backup database"
echo ""
echo "Full documentation: UBUNTU_DEPLOYMENT.md"
echo ""
