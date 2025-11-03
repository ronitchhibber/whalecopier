#!/bin/bash
# Live Trading Monitor Runner
# Runs the realtime trade monitor with Python 3.11 (required for py-clob-client)

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Real-Time Whale Trade Monitor${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if Python 3.11 is available
if ! command -v /opt/homebrew/bin/python3.11 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3.11 not found at /opt/homebrew/bin/python3.11${NC}"
    echo "Please install Python 3.11 via Homebrew:"
    echo "  brew install python@3.11"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 3.11 found"

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${RED}ERROR: .env file not found${NC}"
    echo "Please create a .env file with your Polymarket credentials"
    exit 1
fi

echo -e "${GREEN}✓${NC} .env file found"

# Check if py-clob-client is installed
if ! /opt/homebrew/bin/python3.11 -c "import py_clob_client" 2>/dev/null; then
    echo -e "${YELLOW}WARNING: py-clob-client not installed${NC}"
    echo "Installing py-clob-client..."
    /opt/homebrew/bin/python3.11 -m pip install py-clob-client
fi

echo -e "${GREEN}✓${NC} py-clob-client installed"
echo ""

# Display mode warning
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  IMPORTANT: Trading Mode${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo "The monitor is currently in PAPER mode (simulated trading)."
echo "To enable LIVE trading with real money:"
echo "  1. Edit scripts/realtime_trade_monitor.py"
echo "  2. Change mode='PAPER' to mode='LIVE' on line 48"
echo "  3. IMPORTANT: Start with small amounts!"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the monitor${NC}"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Run the monitor with Python 3.11
echo -e "${GREEN}Starting monitor...${NC}"
echo ""
exec /opt/homebrew/bin/python3.11 -u scripts/realtime_trade_monitor.py
