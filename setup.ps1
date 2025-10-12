# Vehicle Management System - Windows Setup Script
# This script helps set up the Docker environment on Windows

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Vehicle Management System Setup" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
Write-Host "Checking Docker installation..." -ForegroundColor Yellow
$dockerVersion = docker --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}
Write-Host "Docker found: $dockerVersion" -ForegroundColor Green

# Check if Docker is running
Write-Host "Checking if Docker is running..." -ForegroundColor Yellow
docker ps > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker is not running" -ForegroundColor Red
    Write-Host "Please start Docker Desktop" -ForegroundColor Yellow
    exit 1
}
Write-Host "Docker is running" -ForegroundColor Green
Write-Host ""

# Check if .env file exists
if (-Not (Test-Path ".env")) {
    Write-Host ".env file not found. Creating from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host ".env file created!" -ForegroundColor Green
    Write-Host ""
    Write-Host "IMPORTANT: Please edit .env file with your configuration:" -ForegroundColor Red
    Write-Host "  - SECRET_KEY (generate a random string)" -ForegroundColor Yellow
    Write-Host "  - DB_PASSWORD (set a strong password)" -ForegroundColor Yellow
    Write-Host "  - Email settings (if using email notifications)" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Have you edited the .env file? (yes/no)"
    if ($continue -ne "yes") {
        Write-Host "Please edit .env file and run this script again" -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host ".env file found" -ForegroundColor Green
}
Write-Host ""

# Check if make is available
Write-Host "Checking for make command..." -ForegroundColor Yellow
$makeVersion = make --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: 'make' command not found" -ForegroundColor Yellow
    Write-Host "You can install make using chocolatey: choco install make" -ForegroundColor Yellow
    Write-Host "Or use docker-compose commands directly" -ForegroundColor Yellow
    $useMake = $false
} else {
    Write-Host "make found: $($makeVersion[0])" -ForegroundColor Green
    $useMake = $true
}
Write-Host ""

# Ask user what to do
Write-Host "What would you like to do?" -ForegroundColor Cyan
Write-Host "1. Initial deployment (first time setup)" -ForegroundColor White
Write-Host "2. Start existing containers" -ForegroundColor White
Write-Host "3. Stop containers" -ForegroundColor White
Write-Host "4. View logs" -ForegroundColor White
Write-Host "5. Backup database" -ForegroundColor White
Write-Host "6. Exit" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Enter your choice (1-6)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "Starting initial deployment..." -ForegroundColor Cyan
        if ($useMake) {
            make deploy
        } else {
            Write-Host "Building and starting containers..." -ForegroundColor Yellow
            docker-compose up -d --build
            Write-Host "Waiting for services to start..." -ForegroundColor Yellow
            Start-Sleep -Seconds 10
            Write-Host "Running migrations..." -ForegroundColor Yellow
            docker-compose exec web python manage.py migrate
            Write-Host "Collecting static files..." -ForegroundColor Yellow
            docker-compose exec web python manage.py collectstatic --noinput
        }
        Write-Host ""
        Write-Host "Deployment complete!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Application is running at: http://localhost:3333" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "1. Create a superuser:" -ForegroundColor White
        if ($useMake) {
            Write-Host "   make createsuperuser" -ForegroundColor Gray
        } else {
            Write-Host "   docker-compose exec web python manage.py createsuperuser" -ForegroundColor Gray
        }
        Write-Host "2. Visit http://localhost:3333/admin to login" -ForegroundColor White
    }
    "2" {
        Write-Host ""
        Write-Host "Starting containers..." -ForegroundColor Cyan
        if ($useMake) {
            make up
        } else {
            docker-compose up -d
        }
        Write-Host "Containers started!" -ForegroundColor Green
        Write-Host "Application available at: http://localhost:3333" -ForegroundColor Cyan
    }
    "3" {
        Write-Host ""
        Write-Host "Stopping containers..." -ForegroundColor Cyan
        if ($useMake) {
            make down
        } else {
            docker-compose down
        }
        Write-Host "Containers stopped!" -ForegroundColor Green
    }
    "4" {
        Write-Host ""
        Write-Host "Showing logs (Ctrl+C to exit)..." -ForegroundColor Cyan
        if ($useMake) {
            make logs
        } else {
            docker-compose logs -f
        }
    }
    "5" {
        Write-Host ""
        if (-Not (Test-Path "backups")) {
            New-Item -ItemType Directory -Path "backups" | Out-Null
        }
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupFile = "backups/db_backup_$timestamp.sql"
        Write-Host "Creating database backup..." -ForegroundColor Cyan
        docker-compose exec -T db pg_dump -U vms_user vms_db > $backupFile
        Write-Host "Backup created: $backupFile" -ForegroundColor Green
    }
    "6" {
        Write-Host "Goodbye!" -ForegroundColor Cyan
        exit 0
    }
    default {
        Write-Host "Invalid choice" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "For more commands, see:" -ForegroundColor Yellow
Write-Host "  - DOCKER_QUICKSTART.md" -ForegroundColor Gray
Write-Host "  - DEPLOYMENT.md" -ForegroundColor Gray
if ($useMake) {
    Write-Host "  - Run 'make help' for all available commands" -ForegroundColor Gray
}
Write-Host ""
