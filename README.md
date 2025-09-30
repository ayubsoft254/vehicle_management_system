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
| **Account