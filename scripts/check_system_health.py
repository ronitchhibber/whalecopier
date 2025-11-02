#!/usr/bin/env python3
"""
System Health Check Script
==========================
Identifies and reports bugs/issues in the Polymarket copy-trading system.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import requests
import json

# Database connection
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'

def check_database_health():
    """Check database connectivity and data integrity."""
    issues = []
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Check whale data
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total_whales,
                    COUNT(CASE WHEN quality_score > 0 THEN 1 END) as scored_whales,
                    COUNT(CASE WHEN quality_score >= 70 THEN 1 END) as high_quality_whales,
                    COUNT(CASE WHEN is_copying_enabled = true THEN 1 END) as enabled_for_copying
                FROM whales
            """))
            whale_stats = result.fetchone()

            print(f"📊 WHALE STATISTICS:")
            print(f"   Total whales: {whale_stats[0]}")
            print(f"   Scored whales: {whale_stats[1]}")
            print(f"   High quality (>70): {whale_stats[2]}")
            print(f"   Enabled for copying: {whale_stats[3]}")

            if whale_stats[0] == 0:
                issues.append("❌ No whales in database")
            elif whale_stats[3] == 0:
                issues.append("⚠️ No whales enabled for copying")

            # Check trades
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as trades_24h,
                    COUNT(CASE WHEN followed = true THEN 1 END) as followed_trades,
                    COUNT(CASE WHEN is_whale_trade = true THEN 1 END) as whale_trades,
                    COUNT(CASE WHEN market_id IS NULL OR market_id = '' THEN 1 END) as missing_market_id
                FROM trades
            """))
            trade_stats = result.fetchone()

            print(f"\n📈 TRADE STATISTICS:")
            print(f"   Total trades: {trade_stats[0]}")
            print(f"   Last 24h: {trade_stats[1]}")
            print(f"   Followed trades: {trade_stats[2]}")
            print(f"   Whale trades: {trade_stats[3]}")
            print(f"   Missing market ID: {trade_stats[4]}")

            if trade_stats[0] > 0 and trade_stats[4] / trade_stats[0] > 0.5:
                issues.append(f"❌ {trade_stats[4]}/{trade_stats[0]} trades missing market_id")

            # Check markets
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total_markets,
                    COUNT(CASE WHEN outcome IS NOT NULL THEN 1 END) as resolved_markets,
                    COUNT(CASE WHEN question IS NULL OR question = '' THEN 1 END) as missing_question
                FROM markets
            """))
            market_stats = result.fetchone()

            print(f"\n🎲 MARKET STATISTICS:")
            print(f"   Total markets: {market_stats[0]}")
            print(f"   Resolved: {market_stats[1]}")
            print(f"   Missing question: {market_stats[2]}")

            if market_stats[0] > 0 and market_stats[2] / market_stats[0] > 0.3:
                issues.append(f"⚠️ {market_stats[2]}/{market_stats[0]} markets missing question text")

            # Check for stale data
            result = conn.execute(text("""
                SELECT MAX(created_at) as latest_trade
                FROM trades
            """))
            latest_trade = result.fetchone()[0]

            if latest_trade:
                hours_since_trade = (datetime.utcnow() - latest_trade).total_seconds() / 3600
                print(f"\n⏰ FRESHNESS:")
                print(f"   Latest trade: {latest_trade} ({hours_since_trade:.1f} hours ago)")

                if hours_since_trade > 24:
                    issues.append(f"⚠️ No new trades in {hours_since_trade:.0f} hours")

    except Exception as e:
        issues.append(f"❌ Database connection error: {str(e)}")

    return issues

def check_api_health():
    """Check API server health and endpoints."""
    issues = []
    try:
        # Check main API
        response = requests.get('http://localhost:8000/api/stats/summary', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\n🌐 API STATUS:")
            print(f"   Status: ✅ Online")
            print(f"   Whales tracked: {data.get('total_whales', 0)}")
            print(f"   24h volume: ${data.get('volume_24h', 0):,.2f}")
        else:
            issues.append(f"❌ API returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        issues.append(f"❌ API not responding: {str(e)}")

    # Check critical endpoints
    endpoints = [
        '/api/whales',
        '/api/trades',
        '/api/trading/mode'
    ]

    for endpoint in endpoints:
        try:
            response = requests.get(f'http://localhost:8000{endpoint}', timeout=5)
            if response.status_code != 200:
                issues.append(f"⚠️ Endpoint {endpoint} returned {response.status_code}")
        except:
            issues.append(f"❌ Endpoint {endpoint} not responding")

    return issues

def check_services():
    """Check if critical services are running."""
    issues = []

    # Check for copy trading service
    try:
        with open('/tmp/copy_trading.log', 'r') as f:
            lines = f.readlines()[-20:]
            recent_logs = ''.join(lines)

            if 'error' in recent_logs.lower() or 'exception' in recent_logs.lower():
                issues.append("⚠️ Errors found in copy trading logs")

            # Check if service is active
            if lines:
                last_line_time = lines[-1].split()[0] if lines[-1].strip() else None
                # Simple check - if no timestamp, assume stale
                if not last_line_time or 'ERROR' in lines[-1]:
                    issues.append("⚠️ Copy trading service may be stalled")
    except FileNotFoundError:
        issues.append("❌ Copy trading service not running (no log file)")
    except Exception as e:
        issues.append(f"⚠️ Could not check copy trading service: {str(e)}")

    return issues

def check_data_quality():
    """Check for data quality issues."""
    issues = []
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Check for duplicate trades
            result = conn.execute(text("""
                SELECT transaction_hash, COUNT(*) as count
                FROM trades
                WHERE transaction_hash IS NOT NULL
                GROUP BY transaction_hash
                HAVING COUNT(*) > 1
                LIMIT 5
            """))
            duplicates = result.fetchall()

            if duplicates:
                issues.append(f"❌ Found {len(duplicates)} duplicate transaction hashes")

            # Check for invalid whale scores
            result = conn.execute(text("""
                SELECT COUNT(*)
                FROM whales
                WHERE quality_score < 0 OR quality_score > 100
            """))
            invalid_scores = result.fetchone()[0]

            if invalid_scores > 0:
                issues.append(f"❌ {invalid_scores} whales have invalid quality scores")

            # Check for orphaned trades
            result = conn.execute(text("""
                SELECT COUNT(*)
                FROM trades t
                LEFT JOIN whales w ON t.trader_address = w.address
                WHERE w.address IS NULL AND t.is_whale_trade = true
            """))
            orphaned = result.fetchone()[0]

            if orphaned > 0:
                issues.append(f"⚠️ {orphaned} whale trades without matching whale records")

    except Exception as e:
        issues.append(f"❌ Data quality check failed: {str(e)}")

    return issues

def main():
    print("=" * 80)
    print("SYSTEM HEALTH CHECK")
    print("=" * 80)
    print()

    all_issues = []

    # Run all health checks
    print("1️⃣ CHECKING DATABASE...")
    db_issues = check_database_health()
    all_issues.extend(db_issues)

    print("\n2️⃣ CHECKING API...")
    api_issues = check_api_health()
    all_issues.extend(api_issues)

    print("\n3️⃣ CHECKING SERVICES...")
    service_issues = check_services()
    all_issues.extend(service_issues)

    print("\n4️⃣ CHECKING DATA QUALITY...")
    quality_issues = check_data_quality()
    all_issues.extend(quality_issues)

    # Summary
    print("\n" + "=" * 80)
    print("ISSUES FOUND")
    print("=" * 80)

    if all_issues:
        print(f"\n⚠️ Found {len(all_issues)} issues:\n")
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")

        # Provide fixes
        print("\n" + "=" * 80)
        print("RECOMMENDED FIXES")
        print("=" * 80)

        if any("No whales" in issue for issue in all_issues):
            print("\n🔧 FIX: Run whale discovery scripts:")
            print("   python3 scripts/discover_best_whales.py")

        if any("not running" in issue for issue in all_issues):
            print("\n🔧 FIX: Start copy trading service:")
            print("   python3 scripts/start_copy_trading.py > /tmp/copy_trading.log 2>&1 &")

        if any("missing market_id" in issue for issue in all_issues):
            print("\n🔧 FIX: Enrich trade data:")
            print("   python3 scripts/enrich_trade_data.py")

        if any("duplicate" in issue for issue in all_issues):
            print("\n🔧 FIX: Clean duplicate trades:")
            print("   python3 scripts/clean_duplicate_trades.py")

    else:
        print("\n✅ No critical issues found! System is healthy.")

    return len(all_issues)

if __name__ == '__main__':
    exit(main())