# Vehicle Management System

A comprehensive vehicle sales management system built with Django 5.1, featuring role-based access control, payment tracking, inventory management, background task processing with Celery, and production-ready Docker deployment.

## Features

- **Role-Based Access Control**: Admin, Sales, Accountant, Auctioneer, Manager, Staff
- **Vehicle Inventory Management**: Track vehicles with detailed specifications
- **Client Management**: Comprehensive client profiles and history
- **Payment Processing**: Installment plans, tracking, and automated reminders
- **Payroll Management**: Employee salaries, bonuses, and deductions
- **Expense Tracking**: Monitor operational costs
- **Repossession & Auction Management**: Handle repossessed vehicles and auctions
- **Insurance Management**: Track policies and expiry notifications
- **Notifications Center**: In-app notifications with unread counts, read/unread actions, filters, and user delivery preferences
- **Document Management**: Upload and manage contracts, agreements, and documents
- **Comprehensive Reporting**: PDF/CSV exports for all modules
- **Audit Logging**: Complete system activity tracking
- **Background Tasks**: Celery for asynchronous processing
- **Scheduled Tasks**: Automated reminders, notifications, and reports
- **Docker Ready**: Production deployment with Gunicorn and Nginx

## Notifications

- Top navigation bell now links to the live Notifications module.
- Sidebar Notifications link opens the same module for quick access.
- Navbar badge shows unread notification count for the logged-in user.
- Users can mark notifications as read/unread, dismiss, or clear items from the Notifications pages.
- Notification preferences support in-app, email, SMS, and push delivery settings.

## Quick Start with Docker (Recommended)

### Prerequisites
- **Windows**: Docker Desktop installed and running
- **Linux/Ubuntu**: Docker and Docker Compose (see [UBUNTU_DEPLOYMENT.md](UBUNTU_DEPLOYMENT.md))
- Git (optional)

### 3-Step Deployment

**Windows:**
```bash
# 1. Configure environment
copy .env.example .env
notepad .env  # Edit with your settings

# 2. Deploy everything
make deploy

# 3. Create admin user
make createsuperuser
```

**Ubuntu/Linux:**
```bash
# 1. Run automated setup script
chmod +x setup-ubuntu.sh
./setup-ubuntu.sh

# Or manually:
cp .env.example .env
nano .env  # Edit with your settings
make deploy
make createsuperuser
```

**Access at:** http://localhost:3333

**For Ubuntu Server deployment:** See [UBUNTU_DEPLOYMENT.md](UBUNTU_DEPLOYMENT.md) for complete production setup with Nginx and SSL.

### Docker Commands Quick Reference

```bash
make help              # Show all available commands
make up                # Start all services
make down              # Stop all services
make restart-web       # Restart web service only (DB safe)
make rebuild-web       # Rebuild web service (DB safe)
make logs-web          # View web logs
make backup-db         # Backup database
make ps                # Show container status
```

** Full Docker documentation:** [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md) | [DEPLOYMENT.md](DEPLOYMENT.md)

## Manual Installation (Without Docker)

### Prerequisites
- Python 3.12+ (or 3.11+)
- PostgreSQL 13+ (or SQLite for dev)
- Redis (for Celery)

### Setup

```bash
# 1. Virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
copy .env.example .env
notepad .env

# 4. Database
cd src
python manage.py migrate

# 5. Create admin
python manage.py createsuperuser

# 6. Run
python manage.py runserver
```

## Architecture

### Docker Services

- **web**: Django + Gunicorn (port 3333)
- **db**: PostgreSQL with persistent storage
- **redis**: Cache and Celery message broker
- **celery_worker**: Background task processing
- **celery_beat**: Scheduled task execution

### Project Structure

```
vehicle_management_system/
├── src/
│   ├── config/              # Django settings & Celery config
│   ├── apps/                # Application modules
│   │   ├── authentication/  # User auth & RBAC
│   │   ├── vehicles/        # Vehicle inventory
│   │   ├── clients/         # Client management
│   │   ├── payments/        # Payment processing
│   │   ├── payroll/         # Payroll management
│   │   ├── expenses/        # Expense tracking
│   │   ├── repossessions/   # Repo management
│   │   ├── auctions/        # Auction management
│   │   ├── insurance/       # Insurance tracking
│   │   ├── notifications/   # SMS/Email alerts
│   │   ├── documents/       # Document management
│   │   ├── reports/         # Report generation
│   │   ├── audit/           # Audit logging
│   │   ├── permissions/     # Permissions
│   │   └── dashboard/       # Dashboard & analytics
│   ├── templates/           # HTML templates
│   ├── static/              # Static files
│   └── media/               # User uploads
├── Dockerfile               # Docker image
├── docker-compose.yml       # Multi-container setup
├── Makefile                 # Deployment commands
├── nginx.conf.example       # Nginx configuration
└── requirements.txt         # Dependencies
```

## User Roles

| Role | Access Level |
|------|--------------|
| **Admin** | Full system access |
| **Manager** | Full access except system settings |
| **Sales** | Vehicles, clients, payments |
| **Accountant** | Payments, payroll, expenses, reports |
| **Auctioneer** | Repossessions, auctions |
| **Staff** | View-only basic access |

## Configuration

### Environment Variables (.env)

```env
# Django
SECRET_KEY=your-secret-key-here-change-this
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Database (PostgreSQL for production)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=vms_db
DB_USER=vms_user
DB_PASSWORD=strong-password-here
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# SMS (Twilio)
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token
TWILIO_PHONE_NUMBER=+1234567890

# M-Pesa Daraja (Paybill tracking)
MPESA_ENV=sandbox
MPESA_CONSUMER_KEY=your-daraja-consumer-key
MPESA_CONSUMER_SECRET=your-daraja-consumer-secret
MPESA_SHORTCODE=your-paybill-number
MPESA_PASSKEY=your-daraja-passkey
MPESA_INITIATOR_NAME=your-api-initiator-name
MPESA_SECURITY_CREDENTIAL=your-encrypted-security-credential
MPESA_RESULT_URL_BASE=https://your-public-domain
MPESA_C2B_CONFIRMATION_URL=https://taifaassist.xyz/confirmation
MPESA_C2B_VALIDATION_URL=https://taifaassist.xyz/validation
MPESA_STK_CALLBACK_URL=https://taifaassist.xyz/mpesa-callback
```

M-Pesa account reference rule:
- Use the vehicle registration number as the account reference / bill reference.
- This lets the system reconcile partial payments and payments from different phone numbers to the same vehicle account.

## Common Tasks

### Docker Operations

```bash
# After code changes
make rebuild-web          # Rebuild & restart web (DB untouched)
make migrate              # Run new migrations
make collectstatic        # Update static files

# Database operations
make backup-db            # Create timestamped backup
make restore-db FILE=...  # Restore from backup
make shell                # Django shell
make shell-db             # PostgreSQL shell

# Monitoring
make logs                 # All logs
make logs-web             # Web service logs
make logs-celery          # Celery logs
make ps                   # Container status
make health               # Health check
```

### Service Management (Database Safe)

```bash
make restart-web          # Restart web only
make restart-celery       # Restart Celery only
make restart-beat         # Restart scheduler only
make rebuild-web          # Rebuild web (DB safe)
make rebuild-celery       # Rebuild Celery (DB safe)
```

## Production Deployment

### 1. Configure Nginx

```bash
# Copy template
sudo cp nginx.conf.example /etc/nginx/sites-available/vms

# Edit configuration
sudo nano /etc/nginx/sites-available/vms
# Update: server_name, static/media paths

# Enable site
sudo ln -s /etc/nginx/sites-available/vms /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 2. Setup SSL/HTTPS

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### 3. Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Generate strong `SECRET_KEY`
- [ ] Use strong database passwords
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Set up PostgreSQL (not SQLite)
- [ ] Configure email/SMS properly
- [ ] Enable SSL/HTTPS
- [ ] Configure firewall
- [ ] Set up automated backups
- [ ] Test backup/restore
- [ ] Configure log rotation
- [ ] Monitor resources

## Backup & Restore

### Manual Backup

```bash
make backup-db
# Creates: backups/db_backup_YYYYMMDD_HHMMSS.sql
```

### Restore

```bash
make restore-db FILE=backups/db_backup_20250112_120000.sql
```

### Automated Backups (Windows)

**Windows Task Scheduler:**
1. Open Task Scheduler
2. Create Basic Task → Daily at 2:00 AM
3. Action: Start a program
   - Program: `powershell.exe`
   - Arguments: `-Command "cd C:\path\to\project; make backup-db"`

**Linux/Mac Cron:**
```bash
crontab -e
# Add: 0 2 * * * cd /path/to/project && make backup-db
```

## Testing

```bash
# With Docker
make test

# Without Docker
python manage.py test
```

## Performance Tuning

### Gunicorn Workers

Edit `.env` or `docker-compose.yml`:

```env
GUNICORN_WORKERS=8        # (2 × CPU cores) + 1
GUNICORN_THREADS=4
```

### Monitor Resources

```bash
docker stats              # Real-time container stats
make ps                   # Container status
```

## Troubleshooting

### Container won't start
```bash
make logs-web
make ps
```

### Database issues
```bash
make logs-db
make shell-db
```

### Port 3333 in use
```bash
# Windows
netstat -ano | findstr :3333
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:3333 | xargs kill -9
```

### Reset everything
```bash
make down
make clean-containers
make up
```

## Updating Application

```bash
# Pull latest code
git pull origin main

# Update services (DB untouched)
make rebuild-web
make rebuild-celery
make rebuild-beat
make migrate
```

Or use single command:
```bash
make update
```

## Documentation

- **[DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md)** - Quick Docker reference
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide
- **[SETUP_COMPLETE.md](SETUP_COMPLETE.md)** - Setup overview
- **[nginx.conf.example](nginx.conf.example)** - Nginx configuration

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## License

This project is licensed under the MIT License.

## Issues & Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check existing documentation
- Review logs: `make logs-web`

## Roadmap

- [ ] REST API implementation
- [ ] Mobile application
- [ ] Advanced analytics dashboard
- [ ] Accounting software integration
- [ ] WhatsApp notifications
- [ ] GPS vehicle tracking
- [ ] Payment gateway integration
- [ ] Multi-language support
---