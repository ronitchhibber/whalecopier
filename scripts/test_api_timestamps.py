#!/usr/bin/env python3
"""
Test what timestamps the Polymarket API actually returns.
"""
import requests
from datetime import datetime

# Get a sample whale address
test_address = '0x42592084f7a33e17ab296eb0799d447029246966'

print('=' * 80)
print('TESTING POLYMARKET API TIMESTAMPS')
print('=' * 80)
print()

# Fetch trades
url = f'https://data-api.polymarket.com/trades?trader={test_address}&limit=50'
print(f'Fetching: {url}')
print()

response = requests.get(url, timeout=15)

if response.status_code == 200:
    trades = response.json()
    print(f'Got {len(trades)} trades')
    print()

    if trades:
        # Show first 10 with timestamps
        print('First 10 trades with timestamps:')
        print('-' * 80)

        for i, trade in enumerate(trades[:10], 1):
            timestamp_seconds = trade.get('timestamp')
            if timestamp_seconds:
                dt = datetime.fromtimestamp(int(timestamp_seconds))
                print(f'{i:2d}. Timestamp: {timestamp_seconds} -> {dt}')
                print(f'    Market: {trade.get("market", "")[:20]}...')
                print(f'    Side: {trade.get("side")}, Price: {trade.get("price")}, Size: {trade.get("size")}')
                print()

        # Show timestamp range
        timestamps = [int(t.get('timestamp')) for t in trades if t.get('timestamp')]
        if timestamps:
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            min_dt = datetime.fromtimestamp(min_ts)
            max_dt = datetime.fromtimestamp(max_ts)

            print('Timestamp range:')
            print(f'  Earliest: {min_dt} ({min_ts})')
            print(f'  Latest:   {max_dt} ({max_ts})')
            print(f'  Span:     {max_dt - min_dt}')
else:
    print(f'API error: {response.status_code}')
