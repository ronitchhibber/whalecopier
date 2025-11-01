#!/usr/bin/env python3
"""
Test if we can get older historical trades from the API.
Check for pagination and date filtering options.
"""
import requests
from datetime import datetime, timedelta

test_address = '0x42592084f7a33e17ab296eb0799d447029246966'

print('=' * 80)
print('TESTING HISTORICAL TRADE RETRIEVAL')
print('=' * 80)
print()

# Test 1: Try larger limit
print('Test 1: Requesting 100 trades (larger limit)')
print('-' * 80)
url = f'https://data-api.polymarket.com/trades?trader={test_address}&limit=100'
response = requests.get(url, timeout=15)

if response.status_code == 200:
    trades = response.json()
    print(f'Got {len(trades)} trades')

    if trades:
        timestamps = [int(t.get('timestamp')) for t in trades if t.get('timestamp')]
        if timestamps:
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            min_dt = datetime.fromtimestamp(min_ts)
            max_dt = datetime.fromtimestamp(max_ts)

            print(f'Earliest: {min_dt}')
            print(f'Latest:   {max_dt}')
            print(f'Span:     {max_dt - min_dt}')
else:
    print(f'Error: {response.status_code}')

print()

# Test 2: Try offset parameter
print('Test 2: Requesting with offset=50')
print('-' * 80)
url = f'https://data-api.polymarket.com/trades?trader={test_address}&limit=50&offset=50'
response = requests.get(url, timeout=15)

if response.status_code == 200:
    trades = response.json()
    print(f'Got {len(trades)} trades')

    if trades:
        timestamps = [int(t.get('timestamp')) for t in trades if t.get('timestamp')]
        if timestamps:
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            min_dt = datetime.fromtimestamp(min_ts)
            max_dt = datetime.fromtimestamp(max_ts)

            print(f'Earliest: {min_dt}')
            print(f'Latest:   {max_dt}')
            print(f'Span:     {max_dt - min_dt}')
else:
    print(f'Error: {response.status_code}')

print()

# Test 3: Try a well-known high-volume whale for more data
print('Test 3: Trying different whale address for more historical data')
print('-' * 80)

# Try a few whale addresses from the database
well_known_whale = '0x9066aa36f98c0acf0a089bb5ce58a8a48de432c3'
url = f'https://data-api.polymarket.com/trades?trader={well_known_whale}&limit=100'
response = requests.get(url, timeout=15)

if response.status_code == 200:
    trades = response.json()
    print(f'Got {len(trades)} trades for whale {well_known_whale[:10]}')

    if trades:
        timestamps = [int(t.get('timestamp')) for t in trades if t.get('timestamp')]
        if timestamps:
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            min_dt = datetime.fromtimestamp(min_ts)
            max_dt = datetime.fromtimestamp(max_ts)

            print(f'Earliest: {min_dt}')
            print(f'Latest:   {max_dt}')
            print(f'Span:     {max_dt - min_dt}')

            # Show unique dates
            unique_dates = set(datetime.fromtimestamp(ts).date() for ts in timestamps)
            print(f'Unique dates: {len(unique_dates)}')
            for date in sorted(unique_dates):
                count = sum(1 for ts in timestamps if datetime.fromtimestamp(ts).date() == date)
                print(f'  {date}: {count} trades')
else:
    print(f'Error: {response.status_code}')
