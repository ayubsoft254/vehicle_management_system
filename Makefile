.PHONY: help build up down restart logs shell migrate makemigrations createsuperuser collectstatic \
        test clean rebuild-web rebuild-celery rebuild-beat restart-web restart-celery restart-beat \
        backup-db restore-db ps stop-web stop-celery stop-beat deploy update

# Variables
DOCKER_COMPOSE = docker-compose
SERVICE_WEB = web
SERVICE_DB = db
SERVICE_REDIS = redis
SERVICE_CELERY = celery_worker
SERVICE_BEAT = celery_beat

# Colors for output
BLUE = \033[0;34m
GREEN = \033[0;32m
RED = \033[0;31m
NC = \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Vehicle Management System - Docker Commands$(NC)"
	@echo "$(GREEN)================================================$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# Initial deployment
deploy: ## Initial deployment - Build and start all services
	@echo "$(BLUE)Starting initial deployment...$(NC)"
	@if not exist .env (echo "$(RED)Error: .env file not found. Copy .env.example to .env and configure it.$(NC)" && exit 1)
	$(DOCKER_COMPOSE) up -d --build
	@echo "$(GREEN)Waiting for services to be ready...$(NC)"
	@timeout /t 10 /nobreak > nul
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) python manage.py migrate
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) python manage.py collectstatic --noinput
	@echo "$(GREEN)Deployment complete!$(NC)"
	@echo "$(BLUE)Application is running on http://localhost:3333$(NC)"
	@echo "$(BLUE)Run 'make createsuperuser' to create an admin user$(NC)"

# Build commands
build: ## Build all Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	$(DOCKER_COMPOSE) build

build-web: ## Build only web service
	@echo "$(BLUE)Building web service...$(NC)"
	$(DOCKER_COMPOSE) build $(SERVICE_WEB)

# Start/Stop commands
up: ## Start all services
	@echo "$(BLUE)Starting all services...$(NC)"
	$(DOCKER_COMPOSE) up -d

down: ## Stop and remove all containers
	@echo "$(BLUE)Stopping all services...$(NC)"
	$(DOCKER_COMPOSE) down

stop: ## Stop all services without removing containers
	@echo "$(BLUE)Stopping all services...$(NC)"
	$(DOCKER_COMPOSE) stop

start: ## Start stopped services
	@echo "$(BLUE)Starting services...$(NC)"
	$(DOCKER_COMPOSE) start

# Restart commands
restart: ## Restart all services
	@echo "$(BLUE)Restarting all services...$(NC)"
	$(DOCKER_COMPOSE) restart

restart-web: ## Restart only web service
	@echo "$(BLUE)Restarting web service...$(NC)"
	$(DOCKER_COMPOSE) restart $(SERVICE_WEB)

restart-celery: ## Restart only Celery worker
	@echo "$(BLUE)Restarting Celery worker...$(NC)"
	$(DOCKER_COMPOSE) restart $(SERVICE_CELERY)

restart-beat: ## Restart only Celery beat
	@echo "$(BLUE)Restarting Celery beat...$(NC)"
	$(DOCKER_COMPOSE) restart $(SERVICE_BEAT)

restart-redis: ## Restart only Redis
	@echo "$(BLUE)Restarting Redis...$(NC)"
	$(DOCKER_COMPOSE) restart $(SERVICE_REDIS)

# Stop specific services
stop-web: ## Stop web service
	@echo "$(BLUE)Stopping web service...$(NC)"
	$(DOCKER_COMPOSE) stop $(SERVICE_WEB)

stop-celery: ## Stop Celery worker
	@echo "$(BLUE)Stopping Celery worker...$(NC)"
	$(DOCKER_COMPOSE) stop $(SERVICE_CELERY)

stop-beat: ## Stop Celery beat
	@echo "$(BLUE)Stopping Celery beat...$(NC)"
	$(DOCKER_COMPOSE) stop $(SERVICE_BEAT)

# Rebuild commands (without affecting database)
rebuild-web: ## Rebuild and restart web service only
	@echo "$(BLUE)Rebuilding web service...$(NC)"
	$(DOCKER_COMPOSE) stop $(SERVICE_WEB)
	$(DOCKER_COMPOSE) build $(SERVICE_WEB)
	$(DOCKER_COMPOSE) up -d $(SERVICE_WEB)
	@echo "$(GREEN)Web service rebuilt successfully!$(NC)"

rebuild-celery: ## Rebuild and restart Celery worker only
	@echo "$(BLUE)Rebuilding Celery worker...$(NC)"
	$(DOCKER_COMPOSE) stop $(SERVICE_CELERY)
	$(DOCKER_COMPOSE) build $(SERVICE_CELERY)
	$(DOCKER_COMPOSE) up -d $(SERVICE_CELERY)
	@echo "$(GREEN)Celery worker rebuilt successfully!$(NC)"

rebuild-beat: ## Rebuild and restart Celery beat only
	@echo "$(BLUE)Rebuilding Celery beat...$(NC)"
	$(DOCKER_COMPOSE) stop $(SERVICE_BEAT)
	$(DOCKER_COMPOSE) build $(SERVICE_BEAT)
	$(DOCKER_COMPOSE) up -d $(SERVICE_BEAT)
	@echo "$(GREEN)Celery beat rebuilt successfully!$(NC)"

# Logs
logs: ## Show logs for all services
	$(DOCKER_COMPOSE) logs -f

logs-web: ## Show logs for web service
	$(DOCKER_COMPOSE) logs -f $(SERVICE_WEB)

logs-celery: ## Show logs for Celery worker
	$(DOCKER_COMPOSE) logs -f $(SERVICE_CELERY)

logs-beat: ## Show logs for Celery beat
	$(DOCKER_COMPOSE) logs -f $(SERVICE_BEAT)

logs-db: ## Show logs for database
	$(DOCKER_COMPOSE) logs -f $(SERVICE_DB)

# Shell access
shell: ## Open Django shell
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) python manage.py shell

shell-web: ## Open bash shell in web container
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) /bin/bash

shell-db: ## Open PostgreSQL shell
	$(DOCKER_COMPOSE) exec $(SERVICE_DB) psql -U vms_user -d vms_db

# Django commands
migrate: ## Run database migrations
	@echo "$(BLUE)Running migrations...$(NC)"
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) python manage.py migrate

makemigrations: ## Create new migrations
	@echo "$(BLUE)Creating migrations...$(NC)"
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) python manage.py makemigrations

createsuperuser: ## Create Django superuser
	@echo "$(BLUE)Creating superuser...$(NC)"
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) python manage.py createsuperuser

collectstatic: ## Collect static files
	@echo "$(BLUE)Collecting static files...$(NC)"
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) python manage.py collectstatic --noinput

# Database backup and restore
backup-db: ## Backup database to file
	@echo "$(BLUE)Backing up database...$(NC)"
	@if not exist backups mkdir backups
	$(DOCKER_COMPOSE) exec -T $(SERVICE_DB) pg_dump -U vms_user vms_db > backups/db_backup_$(shell powershell -Command "Get-Date -Format 'yyyyMMdd_HHmmss'").sql
	@echo "$(GREEN)Database backup created in backups/ directory$(NC)"

restore-db: ## Restore database from backup (Usage: make restore-db FILE=backups/backup.sql)
	@if "$(FILE)"=="" (echo "$(RED)Error: Please specify backup file. Usage: make restore-db FILE=backups/backup.sql$(NC)" && exit 1)
	@echo "$(BLUE)Restoring database from $(FILE)...$(NC)"
	$(DOCKER_COMPOSE) exec -T $(SERVICE_DB) psql -U vms_user -d vms_db < $(FILE)
	@echo "$(GREEN)Database restored successfully!$(NC)"

# Status and monitoring
ps: ## Show running containers
	$(DOCKER_COMPOSE) ps

status: ## Show detailed status of services
	@echo "$(BLUE)Service Status:$(NC)"
	$(DOCKER_COMPOSE) ps

# Testing
test: ## Run tests
	@echo "$(BLUE)Running tests...$(NC)"
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) python manage.py test

# Cleanup
clean: ## Remove all containers, volumes, and images
	@echo "$(RED)Warning: This will remove all containers, volumes, and images!$(NC)"
	@echo "$(RED)Database data will be lost!$(NC)"
	@choice /C YN /M "Are you sure you want to continue"
	$(DOCKER_COMPOSE) down -v --rmi all
	@echo "$(GREEN)Cleanup complete!$(NC)"

clean-containers: ## Remove all containers (keeps volumes)
	@echo "$(BLUE)Removing all containers...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)Containers removed!$(NC)"

# Update application (pull latest code and restart)
update: ## Update application code and restart services
	@echo "$(BLUE)Updating application...$(NC)"
	git pull
	$(DOCKER_COMPOSE) build $(SERVICE_WEB) $(SERVICE_CELERY) $(SERVICE_BEAT)
	$(DOCKER_COMPOSE) up -d
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) python manage.py migrate
	$(DOCKER_COMPOSE) exec $(SERVICE_WEB) python manage.py collectstatic --noinput
	@echo "$(GREEN)Application updated successfully!$(NC)"

# Development helpers
dev-setup: ## Setup development environment
	@echo "$(BLUE)Setting up development environment...$(NC)"
	@if not exist .env (copy .env.example .env)
	@echo "$(GREEN)Development environment setup complete!$(NC)"
	@echo "$(BLUE)Please edit .env file with your configuration$(NC)"

# Health check
health: ## Check health of all services
	@echo "$(BLUE)Checking service health...$(NC)"
	@echo "Web service:"
	@curl -f http://localhost:3333/ > nul 2>&1 && echo "$(GREEN)OK$(NC)" || echo "$(RED)FAIL$(NC)"
	@echo "Database:"
	@$(DOCKER_COMPOSE) exec $(SERVICE_DB) pg_isready -U vms_user && echo "$(GREEN)OK$(NC)" || echo "$(RED)FAIL$(NC)"
	@echo "Redis:"
	@$(DOCKER_COMPOSE) exec $(SERVICE_REDIS) redis-cli ping > nul 2>&1 && echo "$(GREEN)OK$(NC)" || echo "$(RED)FAIL$(NC)"
