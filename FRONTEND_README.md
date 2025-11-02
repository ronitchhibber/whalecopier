# Whale Trader v0.1 - Frontend

## Overview
Modern React + Vite frontend for the Whale Trader copy-trading system. 
**NO MOCK DATA** - All data comes from real API endpoints.

## Features
- Real-time dashboard with 5-second auto-refresh
- Live whale leaderboard with performance metrics
- Recent trades feed
- Tailwind CSS styling with dark theme
- API proxy configured for seamless backend integration

## Quick Start
```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173  
API: http://localhost:8000 (must be running)

## Tech Stack
- React 18
- Vite
- Tailwind CSS
- Real API integration (no mocks)

## API Endpoints Used
- GET /api/stats/summary - System statistics
- GET /api/whales?limit=20 - Top whales
- GET /api/trades?limit=10 - Recent trades

All data refreshes every 5 seconds automatically.
