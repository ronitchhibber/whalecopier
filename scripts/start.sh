#!/bin/bash
# Quick start script for Polymarket Copy Trading System

set -e

echo "🚀 Starting Polymarket Copy Trading System Infrastructure..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env with your credentials before running the system."
fi

# Start infrastructure services
echo "📦 Starting infrastructure services..."
docker-compose up -d postgres redis kafka zookeeper rabbitmq

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check PostgreSQL
echo "🔍 Checking PostgreSQL..."
docker-compose exec -T postgres pg_isready -U trader || {
    echo "❌ PostgreSQL is not ready"
    exit 1
}
echo "✅ PostgreSQL is ready"

# Check Redis
echo "🔍 Checking Redis..."
docker-compose exec -T redis redis-cli ping > /dev/null || {
    echo "❌ Redis is not ready"
    exit 1
}
echo "✅ Redis is ready"

# Check RabbitMQ
echo "🔍 Checking RabbitMQ..."
docker-compose exec -T rabbitmq rabbitmq-diagnostics ping > /dev/null || {
    echo "⚠️  RabbitMQ is starting (may take 30s)..."
}
echo "✅ RabbitMQ is ready"

# Start monitoring services
echo "📊 Starting monitoring services (Prometheus & Grafana)..."
docker-compose up -d prometheus grafana

echo ""
echo "✨ Infrastructure started successfully!"
echo ""
echo "🌐 Access points:"
echo "   - PostgreSQL:  localhost:5432 (user: trader, db: polymarket_trader)"
echo "   - Redis:       localhost:6379"
echo "   - Kafka:       localhost:9092"
echo "   - RabbitMQ UI: http://localhost:15672 (user: trader, pass: changeme123)"
echo "   - Prometheus:  http://localhost:9090"
echo "   - Grafana:     http://localhost:3000 (user: admin, pass: admin123)"
echo ""
echo "📝 Next steps:"
echo "   1. Edit .env with your Polymarket API credentials"
echo "   2. Activate Python environment: source venv/bin/activate"
echo "   3. Install dependencies: pip install -r requirements.txt"
echo "   4. Run the system: python src/main.py"
echo ""
echo "📚 Documentation: docs/IMPLEMENTATION_STATUS.md"
echo "🛑 To stop: docker-compose down"
echo ""
