# 🚀 QUICK START GUIDE
**Get the Whale Trading System Running in 5 Minutes**

---

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL 14+
- Node.js 18+ (for frontend)
- 8GB RAM minimum

---

## ⚡ Quick Start (5 Minutes)

### 1. Install Dependencies

\`\`\`bash
# Backend dependencies
pip3 install -r requirements.txt

# Dashboard dependencies  
pip3 install -r requirements_dashboard.txt

# Frontend dependencies (if using React dashboard)
cd frontend
npm install
cd ..
\`\`\`

### 2. Start Services

**Production Dashboard (Recommended):**

\`\`\`bash
./run_dashboard.sh
\`\`\`

Access: http://localhost:8501

### 3. Discover Whales

\`\`\`bash
# Quick discovery (100K trades, ~30 min)
python3 scripts/massive_whale_discovery.py

# Full discovery (1M trades, ~2 hours, runs in background)
nohup python3 scripts/massive_whale_discovery_1M.py > whale_discovery.log 2>&1 &
tail -f whale_discovery.log
\`\`\`

### 4. Run Backtest

\`\`\`bash
python3 scripts/run_whale_backtest.py --start 2024-01-01 --end 2024-12-31
\`\`\`

---

## 🎯 Production Modules

All modules ready to use:
- ✅ 5-Factor WQS Calculator
- ✅ 3-Stage Signal Pipeline
- ✅ Adaptive Kelly Position Sizing
- ✅ Multi-Tier Risk Management
- ✅ Performance Attribution
- ✅ Walk-Forward Backtesting

See `/COMPLETE_SYSTEM_SUMMARY.md` for full documentation.

---

**Last Updated:** November 2, 2025
**Status:** Production Framework Complete ✅
