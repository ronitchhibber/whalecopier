#!/usr/bin/env python3
"""
Debug script to see what fields the trades API actually returns
"""
import asyncio
import httpx
import json

async def debug_trades():
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Get one active market
        gamma_url = "https://gamma-api.polymarket.com/markets"
        params = {"closed": "false", "limit": 1, "order": "volume24hr", "ascending": "false"}

        response = await client.get(gamma_url, params=params)
        markets = response.json()

        if len(markets) > 0:
            market_id = markets[0].get('id') or markets[0].get('condition_id')
            print(f"Testing market: {markets[0].get('question')}")
            print(f"Market ID: {market_id}")
            print()

            # Fetch trades
            trades_url = "https://data-api.polymarket.com/trades"
            trades_params = {"market": market_id, "limit": 3}

            trades_response = await client.get(trades_url, params=trades_params)

            if trades_response.status_code == 200:
                trades = trades_response.json()
                print(f"Got {len(trades)} trades")
                print()

                if len(trades) > 0:
                    print("First trade structure:")
                    print(json.dumps(trades[0], indent=2))
            else:
                print(f"Error: HTTP {trades_response.status_code}")
                print(trades_response.text)

if __name__ == "__main__":
    asyncio.run(debug_trades())
