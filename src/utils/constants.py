"""
System-wide Constants and Enumerations
"""

# User Roles
class UserRole:
    ADMIN = 'admin'
    SALES = 'sales'
    ACCOUNTANT = 'accountant'
    AUCTIONEER = 'auctioneer'
    MANAGER = 'manager'
    CLERK = 'clerk'
    
    CHOICES = [
        (ADMIN, 'Administrator'),
        (SALES, 'Sales Person'),
        (ACCOUNTANT, 'Accountant'),
        (AUCTIONEER, 'Auctioneer'),
        (MANAGER, 'Manager'),
        (CLERK, 'Clerk'),
    ]

# Vehicle Status
class VehicleStatus:
    AVAILABLE = 'available'
    RESERVED = 'reserved'
    SOLD = 'sold'
    REPOSSESSED = 'repossessed'
    AUCTIONED = 'auctioned'
    MAINTENANCE = 'maintenance'
    
    CHOICES = [
        (AVAILABLE, 'Available'),
        (RESERVED, 'Reserved'),
        (SOLD, 'Sold'),
        (REPOSSESSED, 'Repossessed'),
        (AUCTIONED, 'Auctioned'),
        (MAINTENANCE, 'Under Maintenance'),
    ]

# Payment Status
class PaymentStatus:
    PENDING = 'pending'
    COMPLETED = 'completed'
    OVERDUE = 'overdue'
    PARTIAL = 'partial'
    DEFAULTED = 'defaulted'
    
    CHOICES = [
        (PENDING, 'Pending'),
        (COMPLETED, 'Completed'),
        (OVERDUE, 'Overdue'),
        (PARTIAL, 'Partial'),
        (DEFAULTED, 'Defaulted'),
    ]

# Payment Methods
class PaymentMethod:
    CASH = 'cash'
    MPESA = 'mpesa'
    BANK_TRANSFER = 'bank_transfer'
    CHEQUE = 'cheque'
    CARD = 'card'
    
    CHOICES = [
        (CASH, 'Cash'),
        (MPESA, 'M-Pesa'),
        (BANK_TRANSFER, 'Bank Transfer'),
        (CHEQUE, 'Cheque'),
        (CARD, 'Credit/Debit Card'),
    ]

# Document Types
class DocumentType:
    CONTRACT = 'contract'
    LOGBOOK = 'logbook'
    INSURANCE = 'insurance'
    ID_CARD = 'id_card'
    AGREEMENT = 'agreement'
    INVOICE = 'invoice'
    RECEIPT = 'receipt'
    OTHER = 'other'
    
    CHOICES = [
        (CONTRACT, 'Contract'),
        (LOGBOOK, 'Logbook'),
        (INSURANCE, 'Insurance Document'),
        (ID_CARD, 'ID Card/Passport'),
        (AGREEMENT, 'Agreement'),
        (INVOICE, 'Invoice'),
        (RECEIPT, 'Receipt'),
        (OTHER, 'Other'),
    ]

# Expense Categories
class ExpenseCategory:
    FUEL = 'fuel'
    MAINTENANCE = 'maintenance'
    INSURANCE = 'insurance'
    TAX = 'tax'
    SALARY = 'salary'
    RENT = 'rent'
    UTILITIES = 'utilities'
    MARKETING = 'marketing'
    OFFICE_SUPPLIES = 'office_supplies'
    LEGAL = 'legal'
    OTHER = 'other'
    
    CHOICES = [
        (FUEL, 'Fuel'),
        (MAINTENANCE, 'Maintenance & Repairs'),
        (INSURANCE, 'Insurance'),
        (TAX, 'Taxes'),
        (SALARY, 'Salaries'),
        (RENT, 'Rent'),
        (UTILITIES, 'Utilities'),
        (MARKETING, 'Marketing & Advertising'),
        (OFFICE_SUPPLIES, 'Office Supplies'),
        (LEGAL, 'Legal Fees'),
        (OTHER, 'Other'),
    ]

# Auction Expense Types
class AuctionExpenseType:
    VALUATION = 'valuation'
    ADVERTISEMENT = 'advertisement'
    PARKING = 'parking'
    TRANSPORT = 'transport'
    LEGAL = 'legal'
    OTHER = 'other'
    
    CHOICES = [
        (VALUATION, 'Valuation Fees'),
        (ADVERTISEMENT, 'Advertisement Fees'),
        (PARKING, 'Parking Fees'),
        (TRANSPORT, 'Transport'),
        (LEGAL, 'Legal Fees'),
        (OTHER, 'Other Expenses'),
    ]

# Module Names for Permissions
class ModuleName:
    DASHBOARD = 'dashboard'
    VEHICLES = 'vehicles'
    CLIENTS = 'clients'
    PAYMENTS = 'payments'
    PAYROLL = 'payroll'
    EXPENSES = 'expenses'
    REPOSSESSIONS = 'repossessions'
    AUCTIONS = 'auctions'
    INSURANCE = 'insurance'
    NOTIFICATIONS = 'notifications'
    DOCUMENTS = 'documents'
    REPORTS = 'reports'
    AUDIT = 'audit'
    PERMISSIONS = 'permissions'
    
    CHOICES = [
        (DASHBOARD, 'Dashboard'),
        (VEHICLES, 'Vehicle Management'),
        (CLIENTS, 'Client Management'),
        (PAYMENTS, 'Payment Management'),
        (PAYROLL, 'Payroll Management'),
        (EXPENSES, 'Expense Tracking'),
        (REPOSSESSIONS, 'Repossessions'),
        (AUCTIONS, 'Auction Management'),
        (INSURANCE, 'Insurance Management'),
        (NOTIFICATIONS, 'Notifications'),
        (DOCUMENTS, 'Document Management'),
        (REPORTS, 'Reports'),
        (AUDIT, 'Audit Logs'),
        (PERMISSIONS, 'Permissions Management'),
    ]

# Access Levels
class AccessLevel:
    NO_ACCESS = 'no_access'
    READ_ONLY = 'read_only'
    READ_WRITE = 'read_write'
    FULL_ACCESS = 'full_access'
    
    CHOICES = [
        (NO_ACCESS, 'No Access'),
        (READ_ONLY, 'Read Only'),
        (READ_WRITE, 'Read & Write'),
        (FULL_ACCESS, 'Full Access'),
    ]

# Audit Action Types
class AuditAction:
    CREATE = 'create'
    READ = 'read'
    UPDATE = 'update'
    DELETE = 'delete'
    LOGIN = 'login'
    LOGOUT = 'logout'
    EXPORT = 'export'
    
    CHOICES = [
        (CREATE, 'Create'),
        (READ, 'Read'),
        (UPDATE, 'Update'),
        (DELETE, 'Delete'),
        (LOGIN, 'Login'),
        (LOGOUT, 'Logout'),
        (EXPORT, 'Export'),
    ]

# Notification Types
class NotificationType:
    PAYMENT_REMINDER = 'payment_reminder'
    PAYMENT_OVERDUE = 'payment_overdue'
    INSURANCE_EXPIRY = 'insurance_expiry'
    VEHICLE_AVAILABLE = 'vehicle_available'
    AUCTION_SCHEDULED = 'auction_scheduled'
    GENERAL = 'general'
    
    CHOICES = [
        (PAYMENT_REMINDER, 'Payment Reminder'),
        (PAYMENT_OVERDUE, 'Payment Overdue'),
        (INSURANCE_EXPIRY, 'Insurance Expiry'),
        (VEHICLE_AVAILABLE, 'Vehicle Available'),
        (AUCTION_SCHEDULED, 'Auction Scheduled'),
        (GENERAL, 'General'),
    ]

# Client Status
class ClientStatus:
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    DEFAULTED = 'defaulted'
    COMPLETED = 'completed'
    
    CHOICES = [
        (ACTIVE, 'Active'),
        (INACTIVE, 'Inactive'),
        (DEFAULTED, 'Defaulted'),
        (COMPLETED, 'Completed'),
    ]

# Miscellaneous Expense Types (Dashboard > Others)
class MiscExpenseType:
    DISCOUNT = 'discount'
    AFTER_SALE_REPAIR = 'after_sale_repair'
    PROMOTIONAL = 'promotional'
    WARRANTY = 'warranty'
    REFUND = 'refund'
    OTHER = 'other'
    
    CHOICES = [
        (DISCOUNT, 'Discount'),
        (AFTER_SALE_REPAIR, 'After-Sale Repair'),
        (PROMOTIONAL, 'Promotional Expense'),
        (WARRANTY, 'Warranty'),
        (REFUND, 'Refund'),
        (OTHER, 'Other'),
    ]