# WhaleTracker Frontend Guide

## Overview
The WhaleTracker system now features a fully integrated unified dashboard that consolidates all frontend pages with seamless navigation and compact display formats.

## Key Features

### 1. Unified Dashboard
- **Location**: `http://localhost:8890/`
- **Features**:
  - 6 integrated tabs: Overview, Whales, Live Trades, Settings, Analytics, Backtest
  - Real-time data updates via WebSocket
  - Embedded display format selector with live preview
  - Responsive design with navigation bar

### 2. Display Format System
Successfully resolved the "numbers off the screen" issue with 7 compact display formats:

| Format | Lines | Description | Best For |
|--------|-------|-------------|----------|
| `single` | 1 | Ultra minimal scrolling | Terminal status bars |
| `status` | 2 | Minimal status bar | Quick monitoring |
| `metrics` | 4 | Key numbers only | Dashboard widgets |
| `ticker` | 5 | Essential info ticker | Sidebar displays |
| `grid` | 8 | Organized metric grid | Structured overview |
| `mini` | 10 | Balanced view | **Default - optimal balance** |
| `compact` | 15 | Full dashboard | Detailed monitoring |

### 3. Navigation Structure
All pages now feature consistent navigation:
- **Home** → Unified Dashboard (default)
- **Dashboard** → Live trading dashboard (port 8000)
- **Settings** → Configuration interface
- **Whales** → Whale analytics
- **API** → Direct API access

## Access Points

### Frontend Server (Port 8890)
```bash
# Main dashboard (auto-redirect from root)
http://localhost:8890/

# Direct pages
http://localhost:8890/unified_dashboard.html  # Main dashboard
http://localhost:8890/settings.html           # Settings page
http://localhost:8890/index.html              # Auto-redirects to dashboard
```

### API Server (Port 8000)
```bash
http://localhost:8000/api/whales       # Whale data
http://localhost:8000/api/trades       # Trade history
http://localhost:8000/api/stats/summary # System statistics
http://localhost:8000/dashboard        # Legacy dashboard
```

## Configuration

### Settings Storage
- **Location**: `config/settings.json`
- **Structure**:
```json
{
  "display": {
    "format": "mini",  // Selected display format
    "refresh_rate": 5,
    "show_alerts": true,
    "format_options": {...}
  },
  "trading": {...},
  "risk": {...},
  "whales": {...}
}
```

### Updating Display Format

#### Via Web Interface
1. Navigate to `http://localhost:8890/`
2. Click the Settings tab
3. Select desired format from dropdown
4. Changes save automatically

#### Via Command Line
```bash
# Interactive selector
python3 scripts/update_display_format.py --interactive

# Direct update
python3 scripts/update_display_format.py mini

# Preview formats
python3 scripts/update_display_format.py --preview mini
```

#### Via API
```bash
curl -X POST http://localhost:8890/api/settings \
  -H "Content-Type: application/json" \
  -d '{"display": {"format": "mini"}}'
```

## Starting the System

### Quick Start
```bash
# Start frontend server (if not running)
cd frontend
python3 server.py 8890

# Access unified dashboard
open http://localhost:8890/
```

### Full System Launch
```bash
# 1. Start API server
python3 api/main.py &

# 2. Start frontend server
cd frontend && python3 server.py &

# 3. Open dashboard
open http://localhost:8890/
```

## File Structure
```
frontend/
├── unified_dashboard.html  # Main dashboard (NEW)
├── settings.html           # Settings interface
├── index.html             # Auto-redirect to dashboard
├── server.py              # Frontend server (updated)
└── settings.css           # Styling

config/
└── settings.json          # Persistent settings

scripts/
├── display_with_settings.py     # Display format renderer
└── update_display_format.py     # Format selector tool
```

## Recent Updates
1. ✅ Fixed "numbers off the screen" issue with compact formats
2. ✅ Created unified dashboard combining all pages
3. ✅ Added seamless navigation between all frontend pages
4. ✅ Made unified dashboard the default landing page
5. ✅ Implemented auto-redirect from index.html
6. ✅ Updated server to serve unified dashboard as root
7. ✅ Committed all changes to git

## Troubleshooting

### Display Too Large
- Switch to `single`, `status`, or `metrics` format
- Use web interface Settings tab for easy selection

### Navigation Not Working
- Ensure frontend server is running on port 8890
- Check API server is running on port 8000
- Clear browser cache if needed

### Settings Not Saving
- Check `config/settings.json` exists and is writable
- Verify frontend server has proper permissions

## Next Steps
The frontend integration is complete with:
- ✅ Compact display formats solving screen overflow
- ✅ Unified dashboard with all features
- ✅ Seamless navigation between pages
- ✅ Persistent settings configuration
- ✅ Git repository updated

The system is now fully operational with an integrated, user-friendly interface.