#!/usr/bin/env python3
"""
Test if pagination gives us older trades.
"""
import requests
from datetime import datetime
import json

test_address = '0x9066aa36f98c0acf0a089bb5ce58a8a48de432c3'

print('=' * 80)
print('TESTING API PAGINATION FOR HISTORICAL DATA')
print('=' * 80)
print()

# Make first request
url = f'https://data-api.polymarket.com/trades?trader={test_address}&limit=50'
print(f'Request 1: {url}')

response = requests.get(url, timeout=15)
data = response.json()

print(f'Response type: {type(data)}')

# Check if it's a dict with pagination info
if isinstance(data, dict):
    trades = data.get('data', data.get('trades', []))
    next_cursor = data.get('next_cursor') or data.get('nextCursor')
    print(f'Got {len(trades)} trades')
    print(f'Next cursor: {next_cursor}')
else:
    trades = data
    print(f'Got {len(trades)} trades (no pagination structure)')

if trades:
    timestamps = [int(t.get('timestamp')) for t in trades if t.get('timestamp')]
    if timestamps:
        min_dt = datetime.fromtimestamp(min(timestamps))
        max_dt = datetime.fromtimestamp(max(timestamps))
        print(f'Time range: {min_dt} to {max_dt}')

print()
print('Sample response structure:')
print(json.dumps(data if isinstance(data, dict) else {'trades': data[:2]}, indent=2)[:500])
