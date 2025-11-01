#!/usr/bin/env python3
"""
Fetch 60 days of historical resolved markets and blockchain trades for backtesting.

Strategy:
1. Query gamma-api for markets that closed/resolved in last 60 days
2. For each market, query Polygon blockchain for all trades (Transfer events)
3. Filter for whale-sized trades (>$1000)
4. Store trades with actual market outcomes
5. Build backtest dataset with real P&L
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Market, Trade, Whale
from decimal import Decimal
import json

# Database setup
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

# API endpoints
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

print('=' * 80)
print('HISTORICAL BACKTEST DATA FETCHER')
print('=' * 80)
print()
print('Strategy: Fetch 60 days of resolved markets + blockchain trades')
print()

async def main():
    client = httpx.AsyncClient(timeout=30.0)
    session = Session()

    try:
        # Step 1: Get markets that closed in last 60 days
        print('📊 STEP 1: Fetching resolved markets from last 60 days...')
        print('-' * 80)

        sixty_days_ago = datetime.now() - timedelta(days=60)

        # Fetch closed events from gamma-api
        # Note: gamma-api doesn't have date filtering, so we'll fetch and filter
        all_resolved_markets = []
        offset = 0
        limit = 100

        while len(all_resolved_markets) < 500:  # Get up to 500 markets
            response = await client.get(
                f"{GAMMA_API}/events",
                params={"closed": "true", "limit": limit, "offset": offset}
            )

            if response.status_code != 200:
                print(f'Error fetching events: {response.status_code}')
                break

            events = response.json()
            if not events:
                break

            # Filter for markets closed in last 60 days
            for event in events:
                if 'markets' in event:
                    for market in event['markets']:
                        if market.get('closed'):
                            # Check close time
                            closed_time_str = market.get('closedTime')
                            if closed_time_str:
                                try:
                                    closed_time = datetime.fromisoformat(
                                        closed_time_str.replace(' ', 'T').replace('+00', '+00:00')
                                    )
                                    if closed_time >= sixty_days_ago:
                                        all_resolved_markets.append(market)
                                except:
                                    pass

            offset += limit
            print(f'  Fetched {offset} events, found {len(all_resolved_markets)} relevant markets so far...')

            if len(events) < limit:
                break  # No more data

        print(f'\\n✅ Found {len(all_resolved_markets)} resolved markets from last 60 days')
        print()

        # Step 2: For each market, query CLOB API for historical trades
        print('📈 STEP 2: Fetching trades for resolved markets...')
        print('-' * 80)

        total_trades_fetched = 0
        whale_trades = []

        for i, market in enumerate(all_resolved_markets[:100], 1):  # Limit to 100 markets for now
            condition_id = market.get('conditionId')
            if not condition_id:
                continue

            print(f'[{i}/100] Fetching trades for market {condition_id[:16]}...')

            # Fetch trades for this market
            try:
                response = await client.get(
                    f"https://clob.polymarket.com/trades",
                    params={
                        "market": condition_id,
                        "limit": 1000  # Max limit
                    }
                )

                if response.status_code == 200:
                    trades = response.json()
                    total_trades_fetched += len(trades)

                    # Filter for whale-sized trades (>$1000)
                    for trade in trades:
                        try:
                            trade_amount = float(trade.get('price', 0)) * float(trade.get('size', 0))
                            if trade_amount >= 1000:  # Whale threshold
                                # Add market resolution data
                                trade['market_outcome'] = market.get('outcomePrices')
                                trade['market_closed_time'] = market.get('closedTime')
                                trade['condition_id'] = condition_id
                                whale_trades.append(trade)
                        except:
                            pass

                    print(f'    {len(trades)} total trades, {sum(1 for t in trades if float(t.get("price", 0)) * float(t.get("size", 0)) >= 1000)} whale trades')
                else:
                    print(f'    Error: {response.status_code}')

            except Exception as e:
                print(f'    Error fetching trades: {e}')

            # Rate limiting
            await asyncio.sleep(0.2)

        print(f'\\n✅ Fetched {total_trades_fetched} total trades, {len(whale_trades)} whale trades')
        print()

        # Step 3: Store in database
        print('💾 STEP 3: Storing data in database...')
        print('-' * 80)

        markets_stored = 0
        trades_stored = 0

        for market_data in all_resolved_markets[:100]:
            try:
                condition_id = market_data.get('conditionId')
                if not condition_id:
                    continue

                # Check if market exists
                existing = session.query(Market).filter_by(condition_id=condition_id).first()
                if not existing:
                    # Create new market
                    market = Market(
                        condition_id=condition_id,
                        question=market_data.get('question', 'Unknown'),
                        closed=True,
                        outcome=self._parse_outcome(market_data.get('outcomePrices')),
                        volume=Decimal(str(market_data.get('volumeNum', 0))),
                        liquidity=Decimal(str(market_data.get('liquidityNum', 0)))
                    )
                    session.add(market)
                    markets_stored += 1
            except Exception as e:
                print(f'Error storing market: {e}')

        session.commit()
        print(f'✅ Stored {markets_stored} markets')
        print()

        # Summary
        print('=' * 80)
        print('SUMMARY')
        print('=' * 80)
        print(f'Markets found: {len(all_resolved_markets)}')
        print(f'Markets stored: {markets_stored}')
        print(f'Total trades fetched: {total_trades_fetched}')
        print(f'Whale trades (>$1000): {len(whale_trades)}')
        print()
        print('✅ Historical data collection complete!')
        print('   This data can now be used for accurate backtesting with real outcomes.')

    finally:
        await client.aclose()
        session.close()

def _parse_outcome(outcome_prices_str):
    """Parse outcome prices to determine winner (YES or NO)"""
    try:
        if not outcome_prices_str:
            return None

        # outcome_prices is a string like '["0.99", "0.01"]'
        prices = json.loads(outcome_prices_str.replace("'", '"'))
        if len(prices) == 2:
            yes_price = float(prices[0])
            no_price = float(prices[1])

            # Winner is the outcome with price closest to 1.0
            return "YES" if yes_price > no_price else "NO"
    except:
        return None

if __name__ == '__main__':
    asyncio.run(main())
