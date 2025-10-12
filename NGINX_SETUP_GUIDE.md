# Nginx Setup Guide for vms.ayubsoft-inc.systems

This guide will help you set up Nginx as a reverse proxy for your Vehicle Management System on your Ubuntu server.

## Prerequisites

- Ubuntu server with root/sudo access
- Docker containers running (web service on port 3333)
- Domain `vms.ayubsoft-inc.systems` pointing to your server's IP address

## Step 1: Install Nginx

```bash
sudo apt update
sudo apt install nginx -y
```

## Step 2: Install Certbot for SSL Certificates

```bash
sudo apt install certbot python3-certbot-nginx -y
```

## Step 3: Create Static and Media Directories

```bash
# Create directories for static and media files
sudo mkdir -p /var/www/vms/static
sudo mkdir -p /var/www/vms/media

# Set permissions
sudo chown -R www-data:www-data /var/www/vms
sudo chmod -R 755 /var/www/vms
```

## Step 4: Copy Static and Media Files from Docker

```bash
# Copy static files from Docker container
docker cp vms_web:/app/static_collected/. /var/www/vms/static/

# Copy media files from Docker container
docker cp vms_web:/app/media/. /var/www/vms/media/

# Fix permissions
sudo chown -R www-data:www-data /var/www/vms
```

## Step 5: Deploy Nginx Configuration

```bash
# Copy the Nginx config file to sites-available
sudo cp nginx-vms.ayubsoft-inc.systems.conf /etc/nginx/sites-available/vms.ayubsoft-inc.systems

# Create symbolic link to sites-enabled
sudo ln -s /etc/nginx/sites-available/vms.ayubsoft-inc.systems /etc/nginx/sites-enabled/

# Remove default Nginx site (optional)
sudo rm /etc/nginx/sites-enabled/default
```

## Step 6: Obtain SSL Certificate

Before obtaining the SSL certificate, temporarily comment out the HTTPS server block in the Nginx config:

```bash
# Edit the config file
sudo nano /etc/nginx/sites-available/vms.ayubsoft-inc.systems

# Comment out lines 21-145 (the entire HTTPS server block)
# Or use this automated command:
sudo sed -i '21,145s/^/# /' /etc/nginx/sites-available/vms.ayubsoft-inc.systems
```

Test and reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Now obtain the SSL certificate:

```bash
sudo certbot --nginx -d vms.ayubsoft-inc.systems
```

After obtaining the certificate, uncomment the HTTPS server block:

```bash
# Uncomment lines 21-145
sudo sed -i '21,145s/^# //' /etc/nginx/sites-available/vms.ayubsoft-inc.systems

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

## Alternative: Use Certbot to Automatically Configure SSL

If you prefer Certbot to handle everything:

```bash
# Just run certbot and let it configure Nginx
sudo certbot --nginx -d vms.ayubsoft-inc.systems

# Certbot will automatically:
# 1. Obtain the certificate
# 2. Configure SSL in your Nginx config
# 3. Set up automatic renewal
```

## Step 7: Verify Configuration

Test Nginx configuration:

```bash
sudo nginx -t
```

If successful, reload Nginx:

```bash
sudo systemctl reload nginx
```

## Step 8: Enable Nginx on Boot

```bash
sudo systemctl enable nginx
```

## Step 9: Configure Firewall

```bash
# Allow HTTP and HTTPS traffic
sudo ufw allow 'Nginx Full'

# Check status
sudo ufw status
```

## Step 10: Set Up Automatic Certificate Renewal

Certbot automatically installs a cron job or systemd timer for renewal. Test it:

```bash
sudo certbot renew --dry-run
```

## Step 11: Update Django Settings

Make sure your Django `settings.py` has the correct configuration:

```python
# In src/config/settings.py
ALLOWED_HOSTS = ['vms.ayubsoft-inc.systems', 'localhost', '127.0.0.1']

# Security settings for HTTPS
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

Rebuild your Docker containers:

```bash
cd /path/to/vehicle_management_system
docker-compose down
docker-compose up -d --build
```

## Step 12: Sync Static Files (Ongoing Maintenance)

Whenever you update static files, sync them to Nginx:

```bash
# Collect static files in Docker
docker-compose exec web python manage.py collectstatic --noinput

# Copy to Nginx directory
sudo rm -rf /var/www/vms/static/*
docker cp vms_web:/app/static_collected/. /var/www/vms/static/
sudo chown -R www-data:www-data /var/www/vms/static
```

You can also create a script for this:

```bash
# Create sync script
sudo nano /usr/local/bin/sync-vms-static.sh
```

Add this content:

```bash
#!/bin/bash
docker-compose -f /path/to/vehicle_management_system/docker-compose.yml exec web python manage.py collectstatic --noinput
sudo rm -rf /var/www/vms/static/*
docker cp vms_web:/app/static_collected/. /var/www/vms/static/
sudo chown -R www-data:www-data /var/www/vms/static
echo "Static files synced successfully!"
```

Make it executable:

```bash
sudo chmod +x /usr/local/bin/sync-vms-static.sh
```

## Testing Your Setup

1. **Check Nginx status:**
   ```bash
   sudo systemctl status nginx
   ```

2. **Check SSL certificate:**
   ```bash
   sudo certbot certificates
   ```

3. **Test HTTP redirect:**
   ```bash
   curl -I http://vms.ayubsoft-inc.systems
   # Should return 301 redirect to HTTPS
   ```

4. **Test HTTPS:**
   ```bash
   curl -I https://vms.ayubsoft-inc.systems
   # Should return 200 OK
   ```

5. **Check in browser:**
   - Visit: https://vms.ayubsoft-inc.systems
   - Verify the SSL padlock icon appears
   - Check static files load correctly

## Troubleshooting

### Nginx won't start
```bash
# Check error logs
sudo tail -f /var/log/nginx/error.log

# Verify configuration
sudo nginx -t
```

### Static files not loading
```bash
# Check file permissions
ls -la /var/www/vms/static/
ls -la /var/www/vms/media/

# Check Nginx access logs
sudo tail -f /var/log/nginx/vms.ayubsoft-inc.systems.access.log
```

### 502 Bad Gateway
```bash
# Check if Docker containers are running
docker-compose ps

# Check if port 3333 is accessible
curl http://localhost:3333/health/

# Check Nginx error log
sudo tail -f /var/log/nginx/vms.ayubsoft-inc.systems.error.log
```

### SSL Certificate Issues
```bash
# Renew certificate manually
sudo certbot renew

# Check certificate expiry
sudo certbot certificates
```

## Log Locations

- **Nginx Access Log:** `/var/log/nginx/vms.ayubsoft-inc.systems.access.log`
- **Nginx Error Log:** `/var/log/nginx/vms.ayubsoft-inc.systems.error.log`
- **Certbot Logs:** `/var/log/letsencrypt/letsencrypt.log`

## Useful Commands

```bash
# Restart Nginx
sudo systemctl restart nginx

# Reload Nginx (graceful, no downtime)
sudo systemctl reload nginx

# Test Nginx configuration
sudo nginx -t

# View Nginx access logs in real-time
sudo tail -f /var/log/nginx/vms.ayubsoft-inc.systems.access.log

# View Nginx error logs in real-time
sudo tail -f /var/log/nginx/vms.ayubsoft-inc.systems.error.log

# Check Nginx status
sudo systemctl status nginx
```

## Security Best Practices

1. ✅ **HTTPS Only** - HTTP automatically redirects to HTTPS
2. ✅ **Strong SSL Configuration** - TLS 1.2+ with secure ciphers
3. ✅ **Security Headers** - HSTS, X-Frame-Options, etc.
4. ✅ **Hidden Files Protected** - `.env`, `.git` directories blocked
5. ✅ **Rate Limiting** (Optional) - Add rate limiting for API endpoints
6. ✅ **Fail2Ban** (Optional) - Install fail2ban to block suspicious IPs

## Performance Optimization

The configuration already includes:
- ✅ Gzip compression
- ✅ Static file caching (30 days)
- ✅ Browser caching headers
- ✅ Connection keep-alive
- ✅ Buffer optimization

## Backup Configuration

Always backup your Nginx configuration:

```bash
sudo cp /etc/nginx/sites-available/vms.ayubsoft-inc.systems /etc/nginx/sites-available/vms.ayubsoft-inc.systems.backup
```

---

## Quick Setup Script

For a quick automated setup, you can use this script:

```bash
#!/bin/bash
# Quick Nginx Setup for VMS

set -e

echo "Installing Nginx and Certbot..."
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx -y

echo "Creating directories..."
sudo mkdir -p /var/www/vms/static
sudo mkdir -p /var/www/vms/media

echo "Copying Nginx configuration..."
sudo cp nginx-vms.ayubsoft-inc.systems.conf /etc/nginx/sites-available/vms.ayubsoft-inc.systems
sudo ln -s /etc/nginx/sites-available/vms.ayubsoft-inc.systems /etc/nginx/sites-enabled/

echo "Testing Nginx configuration..."
sudo nginx -t

echo "Obtaining SSL certificate..."
sudo certbot --nginx -d vms.ayubsoft-inc.systems

echo "Copying static files..."
docker cp vms_web:/app/static_collected/. /var/www/vms/static/
docker cp vms_web:/app/media/. /var/www/vms/media/

echo "Setting permissions..."
sudo chown -R www-data:www-data /var/www/vms
sudo chmod -R 755 /var/www/vms

echo "Reloading Nginx..."
sudo systemctl reload nginx

echo "Setup complete! Visit https://vms.ayubsoft-inc.systems"
```

Save this as `setup-nginx.sh` and run with `bash setup-nginx.sh`
