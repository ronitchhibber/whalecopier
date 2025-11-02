#!/bin/bash

# Whale Trading Dashboard Launcher
# Starts the Streamlit production dashboard

echo "=========================================="
echo "🐋 Whale Trading Dashboard"
echo "=========================================="
echo ""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit not installed"
    echo "Installing dashboard dependencies..."
    pip3 install -r requirements_dashboard.txt
    echo ""
fi

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "⚠️  WARNING: PostgreSQL doesn't appear to be running"
    echo "   The dashboard may not display data correctly."
    echo ""
fi

echo "✅ Starting dashboard on http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo "=========================================="
echo ""

# Run streamlit
streamlit run dashboard/production_dashboard.py \
    --server.port 8501 \
    --server.headless true \
    --browser.gatherUsageStats false
