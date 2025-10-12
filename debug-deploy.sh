#!/bin/bash
# Debug deployment script

echo "🔍 Vehicle Management System - Deployment Debugger"
echo "=================================================="
echo ""

# Check .env file
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    exit 1
fi
echo "✅ .env file exists"

# Start services
echo ""
echo "🚀 Starting containers..."
docker-compose up -d

# Wait and check
echo ""
echo "⏳ Waiting 20 seconds for initial startup..."
sleep 20

# Show status
echo ""
echo "📊 Container Status:"
docker-compose ps

echo ""
echo "🔍 Web Container Logs:"
docker-compose logs --tail=100 web

echo ""
echo "❓ Is web container healthy? Checking..."
if docker ps | grep -q "vms_web"; then
    echo "✅ Web container is running"
    
    echo ""
    echo "⏳ Waiting 30 more seconds..."
    sleep 30
    
    echo ""
    echo "🔄 Trying to run migrations..."
    docker-compose exec web python manage.py migrate
    
    echo ""
    echo "📦 Collecting static files..."
    docker-compose exec web python manage.py collectstatic --noinput
    
    echo ""
    echo "✅ Done! Access at http://localhost:3333"
else
    echo "❌ Web container is NOT running or restarting"
    echo ""
    echo "🔍 Full logs:"
    docker-compose logs web
    
    echo ""
    echo "💡 Common issues:"
    echo "   1. Check .env file has correct SECRET_KEY"
    echo "   2. Check database credentials in .env"
    echo "   3. Check src/config/settings.py for errors"
    echo ""
    echo "🛠️ To fix:"
    echo "   1. Fix the issue above"
    echo "   2. Run: docker-compose down"
    echo "   3. Run: docker-compose up -d --build"
fi
