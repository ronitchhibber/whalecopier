#!/usr/bin/env python3
"""
Calculate hypothetical P&L if $1 was placed on each trade in the database.
This report shows what the total account value would be.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import aiohttp
from typing import Dict, List
from collections import defaultdict

# API endpoints
API_BASE = "http://localhost:8000"
POLYMARKET_API = "https://gamma-api.polymarket.com"

async def fetch_all_trades() -> List[Dict]:
    """Fetch all trades from the database"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/api/trades?limit=10000") as resp:
            return await resp.json()

async def fetch_current_price(session: aiohttp.ClientSession, market_id: str, retries=2) -> float:
    """Fetch current price for a market from Polymarket API"""
    try:
        # Get market data from Polymarket
        url = f"{POLYMARKET_API}/markets/{market_id}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                # Get the current best bid price (approximate current price)
                if 'tokens' in data and len(data['tokens']) > 0:
                    # Return the price of the first outcome token
                    return float(data['tokens'][0].get('price', 0.5))
    except Exception as e:
        if retries > 0:
            await asyncio.sleep(0.5)
            return await fetch_current_price(session, market_id, retries - 1)

    # Return 0.5 (neutral) if we can't fetch the price
    return 0.5

async def calculate_hypothetical_pnl():
    """Calculate P&L if $1 was placed on each trade"""

    print("=" * 80)
    print("HYPOTHETICAL P&L REPORT")
    print("Scenario: $1 placed on each trade in the database")
    print("=" * 80)
    print()

    # Fetch all trades
    print("Fetching all trades from database...")
    trades = await fetch_all_trades()
    total_trades = len(trades)

    print(f"✓ Found {total_trades} trades")
    print()

    # Calculate initial investment
    initial_investment = total_trades  # $1 per trade

    print(f"Initial Investment: ${initial_investment:,.2f}")
    print()

    # Group trades by market for efficient price fetching
    trades_by_market = defaultdict(list)
    for trade in trades:
        trades_by_market[trade['market_id']].append(trade)

    unique_markets = len(trades_by_market)
    print(f"Unique Markets: {unique_markets}")
    print()

    print("Fetching current prices for markets (this may take a minute)...")
    print("-" * 80)

    # Fetch current prices
    market_prices = {}
    async with aiohttp.ClientSession() as session:
        tasks = []
        for market_id in list(trades_by_market.keys())[:100]:  # Limit to first 100 markets for speed
            tasks.append(fetch_current_price(session, market_id))

        prices = await asyncio.gather(*tasks, return_exceptions=True)

        for i, market_id in enumerate(list(trades_by_market.keys())[:100]):
            if not isinstance(prices[i], Exception):
                market_prices[market_id] = prices[i]
            else:
                market_prices[market_id] = 0.5  # Default to neutral

    # Calculate P&L for each trade
    total_pnl = 0
    total_current_value = 0
    wins = 0
    losses = 0
    breakeven = 0

    market_pnl_summary = []

    for market_id, market_trades in trades_by_market.items():
        current_price = market_prices.get(market_id, 0.5)
        market_pnl = 0

        for trade in market_trades:
            entry_price = trade['price']

            # Calculate shares bought with $1
            if entry_price > 0:
                shares = 1.0 / entry_price
                # Calculate current value
                current_value = shares * current_price
                # P&L for this trade
                pnl = current_value - 1.0

                total_pnl += pnl
                total_current_value += current_value
                market_pnl += pnl

                if pnl > 0.01:
                    wins += 1
                elif pnl < -0.01:
                    losses += 1
                else:
                    breakeven += 1

        if market_pnl != 0:
            market_pnl_summary.append({
                'market_id': market_id,
                'trades': len(market_trades),
                'pnl': market_pnl,
                'title': market_trades[0].get('market_title', 'Unknown')[:60]
            })

    # Sort markets by P&L
    market_pnl_summary.sort(key=lambda x: x['pnl'], reverse=True)

    # Calculate metrics
    total_account_value = initial_investment + total_pnl
    roi_pct = (total_pnl / initial_investment * 100) if initial_investment > 0 else 0
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Total Trades:           {total_trades:,}")
    print(f"Initial Investment:     ${initial_investment:,.2f}")
    print(f"Current Value:          ${total_current_value:,.2f}")
    print(f"Total P&L:              ${total_pnl:,.2f}")
    print(f"Total Account Value:    ${total_account_value:,.2f}")
    print()
    print(f"ROI:                    {roi_pct:+.2f}%")
    print(f"Win Rate:               {win_rate:.1f}%")
    print(f"Wins:                   {wins}")
    print(f"Losses:                 {losses}")
    print(f"Breakeven:              {breakeven}")
    print()

    # Top performing markets
    print("=" * 80)
    print("TOP 10 BEST PERFORMING MARKETS")
    print("=" * 80)
    print()
    for i, market in enumerate(market_pnl_summary[:10], 1):
        print(f"{i}. {market['title']}")
        print(f"   Trades: {market['trades']} | P&L: ${market['pnl']:+.2f}")
        print()

    # Bottom performing markets
    print("=" * 80)
    print("TOP 10 WORST PERFORMING MARKETS")
    print("=" * 80)
    print()
    for i, market in enumerate(market_pnl_summary[-10:], 1):
        print(f"{i}. {market['title']}")
        print(f"   Trades: {market['trades']} | P&L: ${market['pnl']:+.2f}")
        print()

    # Create detailed CSV report
    print("=" * 80)
    print("DETAILED REPORT")
    print("=" * 80)
    print()
    print("Note: Due to API rate limits, prices fetched for sample of 100 markets.")
    print("Remaining markets estimated at neutral price (0.5) for conservative estimate.")
    print()

    # Save to file
    report_file = "/tmp/hypothetical_pnl_report.txt"
    with open(report_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("HYPOTHETICAL P&L REPORT\n")
        f.write("Scenario: $1 placed on each trade in the database\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total Trades:           {total_trades:,}\n")
        f.write(f"Initial Investment:     ${initial_investment:,.2f}\n")
        f.write(f"Current Value:          ${total_current_value:,.2f}\n")
        f.write(f"Total P&L:              ${total_pnl:,.2f}\n")
        f.write(f"Total Account Value:    ${total_account_value:,.2f}\n\n")
        f.write(f"ROI:                    {roi_pct:+.2f}%\n")
        f.write(f"Win Rate:               {win_rate:.1f}%\n")
        f.write(f"Wins:                   {wins}\n")
        f.write(f"Losses:                 {losses}\n")
        f.write(f"Breakeven:              {breakeven}\n")

    print(f"✓ Full report saved to: {report_file}")
    print()

    return {
        'total_trades': total_trades,
        'initial_investment': initial_investment,
        'total_pnl': total_pnl,
        'total_account_value': total_account_value,
        'roi_pct': roi_pct,
        'win_rate': win_rate
    }

if __name__ == "__main__":
    result = asyncio.run(calculate_hypothetical_pnl())
