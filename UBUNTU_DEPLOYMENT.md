# Ubuntu Server Deployment Guide

Complete guide for deploying the Vehicle Management System on Ubuntu Server with Docker, Gunicorn, and Nginx.

## Prerequisites

- Ubuntu Server 20.04 LTS or newer
- Sudo/root access
- Domain name (optional, for production with SSL)

## Step 1: Install Docker & Docker Compose

```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install required packages
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common git make

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Install Docker Compose (standalone)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add current user to docker group (optional, to run without sudo)
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker-compose --version
```

## Step 2: Clone/Upload Project

### Option A: Clone from Git
```bash
cd /opt
sudo git clone https://github.com/yourusername/vehicle_management_system.git
sudo chown -R $USER:$USER vehicle_management_system
cd vehicle_management_system
```

### Option B: Upload via SCP
```bash
# From your local machine
scp -r vehicle_management_system user@your-server-ip:/opt/

# On server
cd /opt/vehicle_management_system
```

## Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit environment file
nano .env
```

**Important settings to configure:**

```env
# Django - CHANGE THESE!
SECRET_KEY=your-very-long-random-secret-key-here-change-this
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com,your-server-ip

# Database - CHANGE PASSWORD!
DB_ENGINE=django.db.backends.postgresql
DB_NAME=vms_db
DB_USER=vms_user
DB_PASSWORD=CHANGE-THIS-TO-STRONG-PASSWORD
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@gmail.com

# Twilio SMS (optional)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=your-twilio-number

# Company Info
COMPANY_NAME=Your Company Name
COMPANY_EMAIL=info@yourcompany.com
COMPANY_PHONE=+254712345678
```

**Generate a secure SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

## Step 4: Deploy Application

```bash
# Make sure you're in the project directory
cd /opt/vehicle_management_system

# Deploy everything
make deploy

# This will:
# - Build Docker images
# - Start all containers (web, db, redis, celery, beat)
# - Run database migrations
# - Collect static files
```

**Wait for deployment to complete (2-5 minutes)**

## Step 5: Create Admin User

```bash
make createsuperuser
```

Enter:
- Email address
- Password
- Password confirmation

## Step 6: Verify Deployment

```bash
# Check container status
make ps

# View logs
make logs-web

# Health check
make health

# Or manually
curl http://localhost:3333/health/
```

Expected output:
```json
{"status": "healthy", "service": "vehicle_management_system"}
```

## Step 7: Install Nginx (Reverse Proxy)

```bash
# Install Nginx
sudo apt install -y nginx

# Copy example configuration
sudo cp nginx.conf.example /etc/nginx/sites-available/vms

# Edit configuration
sudo nano /etc/nginx/sites-available/vms
```

**Update these in the Nginx config:**

1. **server_name**: Replace with your domain or server IP
```nginx
server_name yourdomain.com www.yourdomain.com;
# OR for IP only
server_name 192.168.1.100;
```

2. **Static files path**: Update to absolute path
```nginx
location /static/ {
    alias /opt/vehicle_management_system/src/static_collected/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

3. **Media files path**: Update to absolute path
```nginx
location /media/ {
    alias /opt/vehicle_management_system/src/media/;
    expires 7d;
    add_header Cache-Control "public";
}
```

**Enable the site:**
```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/vms /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

## Step 8: Configure Firewall

```bash
# Enable UFW firewall
sudo ufw enable

# Allow SSH (IMPORTANT - don't lock yourself out!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

## Step 9: Setup SSL/HTTPS (Production)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Follow the prompts
# Certbot will automatically configure Nginx for HTTPS

# Test auto-renewal
sudo certbot renew --dry-run
```

**Certificate will auto-renew every 90 days**

## Step 10: Setup Automated Backups

```bash
# Create backup script
sudo nano /usr/local/bin/backup-vms.sh
```

Add this content:
```bash
#!/bin/bash
cd /opt/vehicle_management_system
/usr/bin/make backup-db
# Delete backups older than 30 days
find /opt/vehicle_management_system/backups/ -name "*.sql" -type f -mtime +30 -delete
```

Make it executable:
```bash
sudo chmod +x /usr/local/bin/backup-vms.sh
```

**Setup cron job:**
```bash
sudo crontab -e
```

Add this line (daily backup at 2 AM):
```cron
0 2 * * * /usr/local/bin/backup-vms.sh >> /var/log/vms-backup.log 2>&1
```

## Access Your Application

**Without SSL:**
- http://your-domain.com
- http://your-server-ip

**With SSL:**
- https://your-domain.com

**Admin Panel:**
- https://your-domain.com/admin/

## Common Management Commands

```bash
# Navigate to project directory first
cd /opt/vehicle_management_system

# View all commands
make help

# Container management
make up                # Start all services
make down              # Stop all services
make restart           # Restart all services
make ps                # Show container status

# Service-specific (database safe)
make restart-web       # Restart web only
make restart-celery    # Restart Celery only
make rebuild-web       # Rebuild web after code changes

# Logs
make logs              # All logs
make logs-web          # Web service logs
make logs-celery       # Celery logs
make logs-db           # Database logs

# Database
make migrate           # Run migrations
make backup-db         # Create backup
make shell             # Django shell
make shell-db          # PostgreSQL shell

# Maintenance
make collectstatic     # Update static files
make health            # Health check
```

## Updating the Application

```bash
cd /opt/vehicle_management_system

# Pull latest code
git pull origin main

# Update services (database safe)
make rebuild-web
make rebuild-celery
make rebuild-beat

# Run new migrations
make migrate

# Collect static files
make collectstatic

# Or use single command
make update
```

## Monitoring & Logs

```bash
# View live logs
make logs-web

# View last 100 lines
docker-compose logs --tail=100 web

# Follow logs
docker-compose logs -f web

# Check container resource usage
docker stats

# View Nginx logs
sudo tail -f /var/log/nginx/vms_access.log
sudo tail -f /var/log/nginx/vms_error.log
```

## Troubleshooting

### Containers won't start
```bash
make logs-web
docker-compose ps
```

### Database connection issues
```bash
make logs-db
docker-compose restart db
```

### Port 3333 already in use
```bash
sudo lsof -i :3333
# Kill the process
sudo kill -9 <PID>
```

### Permission issues
```bash
sudo chown -R $USER:$USER /opt/vehicle_management_system
```

### Nginx errors
```bash
sudo nginx -t
sudo tail -f /var/log/nginx/error.log
```

### Static files not loading
```bash
make collectstatic
sudo systemctl restart nginx
```

## Performance Optimization

### Adjust Gunicorn Workers

Edit `docker-compose.yml`:
```yaml
environment:
  - GUNICORN_WORKERS=8  # (2 × CPU cores) + 1
  - GUNICORN_THREADS=4
```

Then:
```bash
make rebuild-web
```

### Enable Nginx Caching

Add to Nginx config:
```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m;
```

### Monitor Resources

```bash
# System resources
htop

# Docker resources
docker stats

# Disk usage
df -h
du -sh /opt/vehicle_management_system/
```

## Security Best Practices

✅ **Done:**
- [x] Strong SECRET_KEY
- [x] DEBUG=False
- [x] Strong database password
- [x] Firewall configured
- [x] SSL/HTTPS enabled
- [x] Regular backups

⚠️ **Additional recommendations:**

1. **Change default ports** (optional):
   Edit `docker-compose.yml` to use non-standard ports

2. **Limit SSH access**:
```bash
sudo nano /etc/ssh/sshd_config
# Add: AllowUsers yourusername
sudo systemctl restart sshd
```

3. **Install fail2ban** (brute force protection):
```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
```

4. **Regular updates**:
```bash
sudo apt update && sudo apt upgrade -y
```

## Backup & Restore

### Manual Backup
```bash
make backup-db
# Saved to: backups/db_backup_YYYYMMDD_HHMMSS.sql
```

### Restore from Backup
```bash
make restore-db FILE=backups/db_backup_20250112_120000.sql
```

### Download Backup to Local Machine
```bash
scp user@server-ip:/opt/vehicle_management_system/backups/db_backup_*.sql ./
```

## System Requirements

**Minimum:**
- 2 CPU cores
- 4 GB RAM
- 20 GB disk space

**Recommended:**
- 4+ CPU cores
- 8+ GB RAM
- 50+ GB SSD

## Support

If you encounter issues:

1. Check logs: `make logs-web`
2. Check container status: `make ps`
3. Verify configuration: `make health`
4. Review Nginx logs: `sudo tail -f /var/log/nginx/error.log`

## Quick Reference Card

```bash
# Deployment
make deploy              # Initial deployment
make up                  # Start services
make down                # Stop services

# Updates (DB safe)
make rebuild-web         # After code changes
make restart-web         # Quick restart
make update              # Full update

# Database
make backup-db           # Backup
make migrate             # Run migrations

# Monitoring
make logs-web            # View logs
make ps                  # Status
make health              # Health check
```

---

**🎉 Congratulations! Your Vehicle Management System is now running on Ubuntu Server!**

Access it at: https://your-domain.com or http://your-server-ip:80
