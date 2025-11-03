# Railway.app Deployment Guide

Complete guide to deploy Whale Trader v0.1 on Railway.app for 24/7 operation.

## Prerequisites

- Railway.app account (sign up at https://railway.app)
- GitHub account (for repository connection)
- Polymarket API credentials
- This codebase pushed to a GitHub repository

## Architecture Overview

Railway.app will run three services:
1. **PostgreSQL Database** - Stores whales, trades, positions, and config
2. **Backend API** - FastAPI server (port 8000)
3. **Realtime Trade Monitor** - Background process that copies trades

## Step 1: Create Railway Project

1. Go to https://railway.app/new
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Authorize Railway to access your GitHub account
5. Select your `Whale.Trader-v0.1` repository

## Step 2: Add PostgreSQL Database

1. In your Railway project, click "New" → "Database" → "Add PostgreSQL"
2. Railway will automatically create a database with connection details
3. Note the connection string format: `postgresql://user:password@host:port/dbname`
4. The `DATABASE_URL` environment variable will be automatically set

## Step 3: Initialize Database Schema

After the database is created, you need to create the tables:

1. Connect to your Railway database locally:
```bash
# Get DATABASE_URL from Railway dashboard
psql "postgresql://user:password@host.railway.app:port/railway"
```

2. Or run the initialization script through Railway CLI:
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Link to your project
railway link

# Run the initialization script
railway run python3 scripts/create_trading_config_table.py
```

## Step 4: Configure Environment Variables

In Railway dashboard, go to your project and add these environment variables:

### Required Variables:
```bash
# Database (automatically set by Railway)
DATABASE_URL=postgresql://user:password@host:port/dbname

# Polymarket API Credentials
POLYMARKET_API_KEY=your_api_key_here
POLYMARKET_API_SECRET=your_api_secret_here
POLYMARKET_API_PASSPHRASE=your_passphrase_here
POLYMARKET_PRIVATE_KEY=your_private_key_here

# The Graph API (for whale discovery)
GRAPH_API_KEY=your_graph_api_key_here

# Python settings
PYTHONUNBUFFERED=1
```

### Optional Variables:
```bash
# Trading Configuration
INITIAL_BALANCE=10000.0
BASE_POSITION_PCT=0.02
MAX_POSITION_PCT=0.05
DAILY_LOSS_LIMIT=100.0
HOURLY_LOSS_LIMIT=100.0
```

## Step 5: Create Services

### Service 1: Backend API

1. In Railway project, click "New" → "Empty Service"
2. Name it "api-backend"
3. Go to Settings:
   - **Start Command**: `python3 api/main.py`
   - **Port**: `8000`
   - **Build Command**: `pip3 install -r requirements.txt` (if you have one)
4. In "Networking" tab, generate a public domain
5. Copy the public URL (e.g., `https://your-project.railway.app`)

### Service 2: Realtime Trade Monitor

1. Click "New" → "Empty Service"
2. Name it "trade-monitor"
3. Go to Settings:
   - **Start Command**: `python3 -u scripts/realtime_trade_monitor.py`
   - **Restart Policy**: Enable "Restart on Exit"
4. This service doesn't need a public port

### Service 3: Frontend (Optional)

If you want to host the frontend on Railway:

1. Click "New" → "Empty Service"
2. Name it "frontend"
3. Go to Settings:
   - **Build Command**: `cd frontend && npm install && npm run build`
   - **Start Command**: `cd frontend && npm run preview -- --host 0.0.0.0 --port $PORT`
   - **Port**: Use Railway's auto-assigned port
4. In "Networking" tab, generate a public domain
5. Update frontend API calls to point to your backend URL

## Step 6: Create requirements.txt

Create a `requirements.txt` file in your project root:

```txt
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
python-dotenv==1.0.0
alembic==1.13.0
pandas==2.1.3
numpy==1.26.2
aiohttp==3.9.1
websockets==12.0
py-clob-client==0.20.0
```

## Step 7: Deploy

Railway will automatically deploy when you push to your GitHub repository.

Manual deployment:
```bash
# Using Railway CLI
railway up
```

## Step 8: Verify Deployment

### Check API is Running:
```bash
curl https://your-project.railway.app/api/stats/summary
```

### Check Trading Config:
```bash
curl https://your-project.railway.app/api/trading-config/status
```

### Test Kill Switch:
```bash
# Disable copy trading
curl -X POST https://your-project.railway.app/api/trading-config/disable

# Enable copy trading
curl -X POST https://your-project.railway.app/api/trading-config/enable
```

## Step 9: Access Frontend Dashboard

1. Open your frontend URL: `https://your-frontend.railway.app`
2. You should see the dashboard with the ON/OFF toggle in the header
3. Click the toggle to control copy trading remotely

## Step 10: Monitor Logs

View logs in Railway dashboard:

1. **API Backend Logs**: Shows incoming requests and trade executions
2. **Trade Monitor Logs**: Shows whale trade discoveries and copy attempts
3. **Database Logs**: Shows connection status and queries

Or use Railway CLI:
```bash
# View API logs
railway logs --service api-backend

# View monitor logs
railway logs --service trade-monitor

# Follow logs in real-time
railway logs --follow
```

## Important Notes

### Cost Estimation
- **Hobby Plan**: $5/month includes 500 hours of compute + $5 credits
- **PostgreSQL**: ~$5/month
- **Estimated Total**: $10-15/month for 24/7 operation

### Monitoring Kill Switch

The kill switch state persists in the database, so:
- ✅ Survives service restarts
- ✅ Survives deployments
- ✅ Accessible from anywhere via dashboard
- ✅ Real-time sync (10-second polling)

### Restart Policy

If the trade monitor crashes:
- Railway will automatically restart it
- Database state is preserved
- Monitoring resumes from last checkpoint

### Security Best Practices

1. **Never commit `.env` files** - Use Railway environment variables
2. **Rotate API keys** regularly
3. **Enable Railway's authentication** for dashboard access
4. **Use Railway's private networking** between services
5. **Monitor your loss limits** regularly

## Troubleshooting

### Database Connection Issues
```bash
# Test database connection
railway run python3 -c "from sqlalchemy import create_engine; import os; engine = create_engine(os.getenv('DATABASE_URL')); print(engine.connect())"
```

### Service Won't Start
1. Check logs: `railway logs --service <service-name>`
2. Verify environment variables are set
3. Ensure `requirements.txt` includes all dependencies
4. Check Railway build logs for errors

### Frontend Can't Connect to Backend
1. Update frontend `.env` or config with backend URL
2. Enable CORS in `api/main.py`:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.railway.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Kill Switch Not Working
1. Verify database table exists: `SELECT * FROM trading_config;`
2. Check API logs for errors
3. Verify trade monitor is checking the switch (should see pause messages)

## Maintenance Commands

```bash
# Restart a service
railway service restart api-backend

# View environment variables
railway variables

# SSH into a service
railway shell

# Run database migrations
railway run python3 scripts/create_trading_config_table.py
```

## Scaling Tips

### For High Volume Trading:
1. Upgrade Railway plan to Pro ($20/month)
2. Increase PostgreSQL storage if needed
3. Consider adding Redis for caching
4. Enable Railway's auto-scaling

### For Multiple Strategies:
1. Deploy multiple trade monitor instances
2. Use different DATABASE_URL for each
3. Or use a single database with strategy filtering

## Emergency Stop

If you need to immediately stop all trading:

**Option 1: Via Dashboard**
- Open your frontend URL
- Click the toggle to OFF

**Option 2: Via API**
```bash
curl -X POST https://your-project.railway.app/api/trading-config/disable
```

**Option 3: Via Railway**
- Pause the `trade-monitor` service in Railway dashboard

**Option 4: Nuclear Option**
- Delete the `trade-monitor` service entirely

## Success Checklist

- [ ] PostgreSQL database created and initialized
- [ ] All environment variables configured
- [ ] API backend deployed and accessible
- [ ] Trade monitor running (check logs for "Monitoring for new trades")
- [ ] Frontend deployed (if hosting on Railway)
- [ ] Kill switch toggle visible in dashboard
- [ ] Kill switch API endpoints working
- [ ] Logs showing monitoring activity
- [ ] Database contains whales and trades
- [ ] Ready for 24/7 operation!

## Next Steps

1. **Run Whale Discovery**: Populate your database with high-quality whales
   ```bash
   railway run python3 scripts/whale_discovery.py
   ```

2. **Monitor Performance**: Check logs regularly for the first week

3. **Adjust Parameters**: Fine-tune position sizes and risk limits based on results

4. **Set Up Alerts**: Configure Railway notifications for service failures

---

**You're now running Whale Trader 24/7 in the cloud! 🚀**

The system will continuously monitor whale trades and copy them automatically when the toggle is ON. You can control it from anywhere via the dashboard.
