# 🚗 Vehicle Sales Management System

A comprehensive multi-tenant vehicle sales management system built with Django 5.2.6, featuring role-based access control, payment tracking, inventory management, and more.

## 📋 Features

- **Multi-Tenancy**: Each company gets their own database schema
- **Role-Based Access Control**: Admin, Sales, Accountant, Auctioneer, Manager, Staff
- **Vehicle Inventory Management**: Track vehicles with detailed specs
- **Client Management**: Comprehensive client profiles and history
- **Payment Processing**: Installment plans, tracking, and reporting
- **Payroll Management**: Employee salaries, bonuses, deductions
- **Expense Tracking**: Monitor operational costs
- **Repossession & Auction Management**: Handle repo vehicles and auctions
- **Insurance Management**: Track policies and expiry dates
- **Document Management**: Upload and manage contracts, agreements
- **Comprehensive Reporting**: PDF/CSV exports for all modules
- **Audit Logging**: Track all system activities

## 🚀 Installation

### Prerequisites

- Python 3.10+
- PostgreSQL 13+
- Redis (for Celery tasks)

### Setup Steps

1. **Clone the repository**
```bash
git clone <repository-url>
cd vehicle_sales_system
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
cd src
pip install -r requirements.txt
```

4. **Environment Configuration**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Database Setup**
```bash
# Create PostgreSQL database
createdb vehicle_sales_db

# Run migrations
python manage.py migrate_schemas --shared

# Create public tenant
python manage.py shell
from apps.core.models import Client, Domain
tenant = Client(schema_name='public', name='Public')
tenant.save()
domain = Domain()
domain.domain = 'localhost'  # your domain
domain.tenant = tenant
domain.is_primary = True
domain.save()
exit()
```

6. **Create Superuser**
```bash
python manage.py createsuperuser
```

7. **Setup Default Roles**
```bash
python manage.py setup_roles
```

8. **Run Development Server**
```bash
python manage.py runserver
```

Visit `http://localhost:8000` to access the application.

## 🏗️ Project Structure

```
vehicle_sales_system/
├── src/
│   ├── manage.py
│   ├── config/              # Django settings
│   ├── apps/
│   │   ├── core/            # Authentication, RBAC, Dashboard
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
│   │   └── audit/           # Audit logging
│   ├── static/              # Static files
│   ├── media/               # User uploads
│   └── templates/           # HTML templates
├── requirements.txt
├── .env
└── README.md
```

## 👥 User Roles & Permissions

| Role | Access Level |
|------|--------------|
| **Admin** | Full system access |
| **Manager** | Full access except settings |
| **Sales** | Vehicles, clients, payments |
| **Accountant** | Payments, payroll, expenses, reports |
| **Auctioneer** | Repossessions, auctions |
| **Staff** | View-only access to basic modules |

## 🔧 Configuration

### Environment Variables

Key environment variables in `.env`:

```env
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=vehicle_sales_db
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-app-password

# SMS (Twilio)
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token
TWILIO_PHONE_NUMBER=+1234567890
```

## 📱 Multi-Tenancy Setup

### Creating a New Tenant

```python
from apps.core.models import Client, Domain

# Create tenant
tenant = Client(
    schema_name='company_schema',
    name='Company Name',
    company_name='Company Full Name',
    company_email='info@company.com',
    company_phone='+1234567890'
)
tenant.save()

# Create domain
domain = Domain()
domain.domain = 'company.yourdomain.com'
domain.tenant = tenant
domain.is_primary = True
domain.save()

# Run tenant migrations
python manage.py migrate_schemas --tenant=company_schema
```

## 📊 Running the Application

### Development

```bash
# Run development server
python manage.py runserver

# Run Celery worker (for background tasks)
celery -A config worker -l info

# Run Celery beat (for scheduled tasks)
celery -A config beat -l info
```

### Production

```bash
# Collect static files
python manage.py collectstatic --noinput

# Run with Gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

## 🧪 Testing

```bash
# Run tests
python manage.py test

# Run tests with coverage
coverage run --source='.' manage.py test
coverage report
```

## 📝 Management Commands

```bash
# Setup default role permissions
python manage.py setup_roles

# Create tenant
python manage.py create_tenant

# Migrate all tenants
python manage.py migrate_schemas

# Migrate specific tenant
python manage.py migrate_schemas --tenant=schema_name
```

## 🎨 Customization

### Theme Colors

Each tenant can customize their theme colors in the admin panel or via the Client model:

- `primary_color`: Main brand color (default: #3B82F6)
- `secondary_color`: Secondary brand color (default: #10B981)

### Company Branding

Update tenant information:
- Company Name
- Logo
- Contact Details
- Address

## 📚 API Documentation

*(To be added when API endpoints are implemented)*

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🐛 Known Issues

- None currently

## 📞 Support

For support, email support@yourcompany.com or create an issue in the repository.

## ✨ Roadmap

- [ ] REST API implementation
- [ ] Mobile application
- [ ] Advanced analytics dashboard
- [ ] Integration with accounting software
- [ ] WhatsApp notifications
- [ ] Vehicle tracking with GPS
- [ ] Online payment gateway integration
- [ ] Multi-language support

## 🙏 Acknowledgments

- Django Framework
- Tailwind CSS
- Font Awesome Icons
- All open-source contributors

---

**Built with ❤️ using Django 5.2.6**