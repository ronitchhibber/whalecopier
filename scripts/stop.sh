#!/bin/bash
# Stop script for Polymarket Copy Trading System

echo "🛑 Stopping Polymarket Copy Trading System..."
echo ""

cd "$(dirname "$0")/.."

# Stop all services
docker-compose down

echo ""
echo "✅ All services stopped"
echo ""
echo "💾 Data is preserved in Docker volumes"
echo "🗑️  To remove all data: docker-compose down -v"
echo ""
