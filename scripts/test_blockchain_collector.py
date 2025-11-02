#!/usr/bin/env python3
"""
Test blockchain data collector on a small sample (1 day of data)
to verify it works before running full 60-day collection.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from datetime import datetime, timedelta

# Blockchain setup
POLYGON_RPC_URLS = [
    "https://polygon-rpc.com",
    "https://rpc-mainnet.matic.network",
    "https://matic-mainnet.chainstacklabs.com",
]

CTF_TOKEN = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

print('=' * 80)
print('BLOCKCHAIN CONNECTION TEST')
print('=' * 80)
print()

# Test connection to Polygon
w3 = None
for rpc_url in POLYGON_RPC_URLS:
    try:
        print(f'Trying {rpc_url}...')
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 60}))
        # Inject POA middleware for Polygon
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if w3.is_connected():
            print(f'✅ Connected!')
            break
    except Exception as e:
        print(f'❌ Failed: {e}')
        continue

if not w3:
    print('❌ Could not connect to any Polygon RPC')
    sys.exit(1)

# Get current block info
current_block = w3.eth.block_number
print(f'\nCurrent block: {current_block:,}')

# Get a recent block to check timestamp
block = w3.eth.get_block(current_block)
block_time = datetime.fromtimestamp(block['timestamp'])
print(f'Current block time: {block_time}')

# Calculate blocks per day (Polygon: ~2.1s per block)
blocks_per_day = int(24 * 3600 / 2.1)
print(f'Blocks per day: {blocks_per_day:,}')

# Test fetching Transfer events for last 100 blocks (~ 3.5 minutes)
# Note: Public RPCs have small batch limits
test_blocks = 100
start_block = current_block - test_blocks

print(f'\n📊 Testing event fetching for last {test_blocks} blocks...')
print(f'Block range: {start_block:,} to {current_block:,}')

try:
    # ERC1155 TransferSingle event signature
    transfer_topic = w3.keccak(text="TransferSingle(address,address,address,uint256,uint256)").hex()

    logs = w3.eth.get_logs({
        'address': CTF_TOKEN,
        'fromBlock': start_block,
        'toBlock': current_block,
        'topics': [transfer_topic]
    })

    print(f'✅ Found {len(logs)} Transfer events in last {test_blocks} blocks')

    if len(logs) > 0:
        # Decode first event as example
        log = logs[0]
        print(f'\nExample event:')
        print(f'  Transaction: {log["transactionHash"].hex()}')
        print(f'  Block: {log["blockNumber"]:,}')

        # Get block timestamp
        block = w3.eth.get_block(log['blockNumber'])
        event_time = datetime.fromtimestamp(block['timestamp'])
        print(f'  Time: {event_time}')

        # Decode topics
        if len(log['topics']) >= 4:
            from_addr = '0x' + log['topics'][2].hex()[-40:]
            to_addr = '0x' + log['topics'][3].hex()[-40:]
            print(f'  From: {from_addr}')
            print(f'  To: {to_addr}')

        # Decode data
        data = log['data'].hex()
        if len(data) >= 130:
            token_id = int(data[2:66], 16)
            amount = int(data[66:130], 16)
            amount_usd = amount / 1_000_000
            print(f'  Token ID: {hex(token_id)}')
            print(f'  Amount: ${amount_usd:,.2f}')

    print()
    print('=' * 80)
    print('✅ CONNECTION TEST SUCCESSFUL')
    print('=' * 80)
    print()
    print(f'Ready to collect 60 days of data (~{blocks_per_day * 60:,} blocks)')

except Exception as e:
    print(f'❌ Error fetching events: {e}')
    import traceback
    traceback.print_exc()
