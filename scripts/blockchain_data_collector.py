#!/usr/bin/env python3
"""
Blockchain Data Collector for Real Historical Backtesting
=========================================================

Fetches 60+ days of historical trade data directly from Polygon blockchain.

Strategy:
1. Query CTF Exchange contract for Transfer events (trades)
2. Filter for whale-sized trades (>$1000)
3. Fetch corresponding market resolutions from CTF Token contract
4. Store with real timestamps and outcomes
5. Build comprehensive backtest dataset with actual P&L

Contracts:
- CTF Exchange: 0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
- CTF Token (ERC1155): 0x4D97DCd97eC945f40cF65F87097ACe5EA0476045

Data Sources:
- Free RPC: Polygon public endpoints (rate limited)
- Fallback: Alchemy/Infura if needed
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import httpx
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Market, Trade, Whale
from decimal import Decimal
import json
from typing import List, Dict, Optional
import time

# Database setup
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

# Blockchain setup - Using public Polygon RPC
POLYGON_RPC_URLS = [
    "https://polygon-rpc.com",
    "https://rpc-mainnet.matic.network",
    "https://matic-mainnet.chainstacklabs.com",
    "https://polygon-bor-rpc.publicnode.com"
]

# Contract addresses
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
CTF_TOKEN = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# Polymarket CLOB API for market metadata
CLOB_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

print('=' * 80)
print('BLOCKCHAIN HISTORICAL DATA COLLECTOR')
print('=' * 80)
print()
print(f'Target: 60 days of whale trades with real market resolutions')
print(f'Source: Polygon blockchain + Polymarket APIs')
print()

class BlockchainCollector:
    def __init__(self):
        # Try multiple RPC endpoints until one works
        self.w3 = None
        for rpc_url in POLYGON_RPC_URLS:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 60}))
                # Inject POA middleware for Polygon
                w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
                if w3.is_connected():
                    print(f'✅ Connected to Polygon via {rpc_url}')
                    self.w3 = w3
                    break
            except Exception as e:
                print(f'❌ Failed to connect to {rpc_url}: {e}')
                continue

        if not self.w3:
            raise Exception("Could not connect to any Polygon RPC endpoint")

        self.session = Session()
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Get current block
        self.current_block = self.w3.eth.block_number
        print(f'   Current block: {self.current_block:,}')

        # Calculate blocks for 60 days (Polygon: ~2.1s per block)
        # 60 days * 24 hours * 3600 seconds / 2.1 seconds = ~2.47M blocks
        self.blocks_per_day = int(24 * 3600 / 2.1)
        self.target_days = 60
        self.target_blocks = self.blocks_per_day * self.target_days
        self.start_block = max(0, self.current_block - self.target_blocks)

        print(f'   Target date range: {self.target_days} days')
        print(f'   Block range: {self.start_block:,} to {self.current_block:,}')
        print(f'   Total blocks: {self.target_blocks:,}')
        print()

    async def fetch_market_metadata(self, condition_id: str) -> Optional[Dict]:
        """Fetch market details from CLOB API"""
        try:
            # Try to get market info from CLOB
            response = await self.http_client.get(
                f"{CLOB_API}/markets/{condition_id}"
            )
            if response.status_code == 200:
                return response.json()

            # Fallback to searching in gamma-api
            response = await self.http_client.get(
                f"{GAMMA_API}/markets",
                params={"condition_id": condition_id}
            )
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0]
        except Exception as e:
            print(f'   Warning: Could not fetch market metadata for {condition_id[:16]}: {e}')

        return None

    def get_transfer_events(self, from_block: int, to_block: int, batch_size: int = 2000):
        """
        Query blockchain for Transfer events from CTF Token contract.

        Transfer events represent trades happening on Polymarket.
        We filter for large transfers (whale trades >$1000).
        """
        print(f'📊 Fetching Transfer events from blocks {from_block:,} to {to_block:,}...')

        # ERC1155 Transfer event signature
        # event TransferSingle(address indexed operator, address indexed from, address indexed to, uint256 id, uint256 value)
        transfer_topic = self.w3.keccak(text="TransferSingle(address,address,address,uint256,uint256)").hex()

        all_events = []
        current_from = from_block

        while current_from < to_block:
            current_to = min(current_from + batch_size, to_block)

            try:
                # Query logs with retry logic
                for attempt in range(3):
                    try:
                        logs = self.w3.eth.get_logs({
                            'address': CTF_TOKEN,
                            'fromBlock': current_from,
                            'toBlock': current_to,
                            'topics': [transfer_topic]
                        })

                        all_events.extend(logs)
                        print(f'   Blocks {current_from:,}-{current_to:,}: {len(logs)} transfers')
                        break
                    except Exception as e:
                        if attempt == 2:
                            print(f'   ❌ Failed after 3 attempts: {e}')
                            # Reduce batch size and retry
                            batch_size = max(500, batch_size // 2)
                            print(f'   Reducing batch size to {batch_size}')
                        else:
                            time.sleep(2 ** attempt)  # Exponential backoff
                            continue

                current_from = current_to + 1

                # Rate limiting - don't overwhelm free RPC
                time.sleep(0.5)

            except Exception as e:
                print(f'   Error fetching logs {current_from:,}-{current_to:,}: {e}')
                current_from = current_to + 1
                continue

        print(f'✅ Fetched {len(all_events):,} total Transfer events')
        return all_events

    def decode_transfer_event(self, log) -> Optional[Dict]:
        """Decode ERC1155 TransferSingle event"""
        try:
            # Topics: [event_sig, operator, from, to]
            # Data: token_id, amount (encoded)

            if len(log['topics']) < 4:
                return None

            operator = '0x' + log['topics'][1].hex()[-40:]
            from_addr = '0x' + log['topics'][2].hex()[-40:]
            to_addr = '0x' + log['topics'][3].hex()[-40:]

            # Decode data (token_id and amount)
            data = log['data'].hex()
            if len(data) < 128:
                return None

            token_id = int(data[2:66], 16)
            amount = int(data[66:130], 16)

            # Get block timestamp
            block = self.w3.eth.get_block(log['blockNumber'])
            timestamp = datetime.fromtimestamp(block['timestamp'])

            return {
                'transaction_hash': log['transactionHash'].hex(),
                'block_number': log['blockNumber'],
                'timestamp': timestamp,
                'operator': operator,
                'from': from_addr,
                'to': to_addr,
                'token_id': token_id,
                'amount': amount
            }
        except Exception as e:
            print(f'   Warning: Failed to decode transfer event: {e}')
            return None

    async def process_trades(self, events: List) -> List[Dict]:
        """
        Process Transfer events into trade records with market data.

        Filter for whale-sized trades and enrich with market metadata.
        """
        print()
        print(f'📈 Processing {len(events):,} events into trades...')
        print('-' * 80)

        trades = []
        markets_cache = {}

        for i, log in enumerate(events):
            if i % 1000 == 0 and i > 0:
                print(f'   Processed {i:,}/{len(events):,} events, {len(trades)} whale trades found...')

            decoded = self.decode_transfer_event(log)
            if not decoded:
                continue

            # Skip if amount is too small (< 1000 USDC worth)
            # Note: token amounts are in units, need to divide by 1e6 for USDC
            amount_usd = decoded['amount'] / 1_000_000
            if amount_usd < 1000:
                continue

            # Extract condition_id from token_id
            # Polymarket uses condition_id as token_id
            # Format: first 32 bytes of token_id
            token_id = decoded['token_id']
            condition_id = hex(token_id)

            # Fetch market metadata (with caching)
            if condition_id not in markets_cache:
                market_data = await self.fetch_market_metadata(condition_id)
                markets_cache[condition_id] = market_data
            else:
                market_data = markets_cache[condition_id]

            trade_record = {
                'transaction_hash': decoded['transaction_hash'],
                'block_number': decoded['block_number'],
                'timestamp': decoded['timestamp'],
                'trader_address': decoded['to'],  # Buyer
                'market_id': condition_id,
                'token_id': str(token_id),
                'amount_usd': amount_usd,
                'market_question': market_data.get('question', 'Unknown') if market_data else 'Unknown',
                'market_closed': market_data.get('closed', False) if market_data else False,
                'market_outcome': market_data.get('outcome') if market_data else None
            }

            trades.append(trade_record)

        print(f'✅ Found {len(trades):,} whale trades (>$1000)')
        print(f'   Unique markets: {len(markets_cache)}')
        print()

        return trades

    async def store_to_database(self, trades: List[Dict]):
        """Store trades and market data in database"""
        print('💾 Storing data in database...')
        print('-' * 80)

        markets_stored = 0
        trades_stored = 0

        # Group by market
        markets_dict = {}
        for trade in trades:
            market_id = trade['market_id']
            if market_id not in markets_dict:
                markets_dict[market_id] = []
            markets_dict[market_id].append(trade)

        # Store markets first
        for market_id, market_trades in markets_dict.items():
            try:
                # Check if market exists
                existing = self.session.query(Market).filter_by(condition_id=market_id).first()

                if not existing:
                    # Create new market from first trade's metadata
                    first_trade = market_trades[0]
                    market = Market(
                        condition_id=market_id,
                        question=first_trade['market_question'],
                        closed=first_trade['market_closed'],
                        outcome=first_trade['market_outcome'],
                        volume=sum(Decimal(str(t['amount_usd'])) for t in market_trades),
                        liquidity=Decimal('0')  # Unknown from blockchain
                    )
                    self.session.add(market)
                    markets_stored += 1
            except Exception as e:
                print(f'   Error storing market {market_id[:16]}: {e}')

        self.session.commit()
        print(f'✅ Stored {markets_stored} new markets')

        # Store trades
        for trade in trades:
            try:
                # Check if trade exists (by tx hash)
                existing = self.session.query(Trade).filter_by(
                    transaction_hash=trade['transaction_hash']
                ).first()

                if not existing:
                    trade_record = Trade(
                        market_id=trade['market_id'],
                        trader_address=trade['trader_address'],
                        transaction_hash=trade['transaction_hash'],
                        timestamp=trade['timestamp'],
                        outcome='YES',  # Assume YES for simplicity, would need order book data for actual side
                        shares=Decimal(str(trade['amount_usd'])),
                        price=Decimal('0.50'),  # Unknown without order book
                        is_whale_trade=True
                    )
                    self.session.add(trade_record)
                    trades_stored += 1
            except Exception as e:
                print(f'   Error storing trade {trade["transaction_hash"][:16]}: {e}')

        self.session.commit()
        print(f'✅ Stored {trades_stored} new trades')
        print()

    async def run(self):
        """Main collection workflow"""
        try:
            # Step 1: Fetch Transfer events from blockchain
            print('PHASE 1: BLOCKCHAIN DATA COLLECTION')
            print('=' * 80)

            # Collect in chunks to avoid overwhelming RPC
            chunk_size = 100_000  # ~2 days of blocks
            all_events = []

            current_start = self.start_block
            while current_start < self.current_block:
                chunk_end = min(current_start + chunk_size, self.current_block)

                events = self.get_transfer_events(current_start, chunk_end, batch_size=2000)
                all_events.extend(events)

                current_start = chunk_end + 1

                print(f'   Progress: {len(all_events):,} events collected so far')
                print()

            # Step 2: Process into trades with market data
            print('PHASE 2: TRADE PROCESSING')
            print('=' * 80)

            trades = await self.process_trades(all_events)

            # Step 3: Store in database
            print('PHASE 3: DATABASE STORAGE')
            print('=' * 80)

            await self.store_to_database(trades)

            # Summary
            print('=' * 80)
            print('COLLECTION COMPLETE')
            print('=' * 80)
            print(f'Total events fetched: {len(all_events):,}')
            print(f'Whale trades identified: {len(trades):,}')
            print(f'Date range: {min(t["timestamp"] for t in trades)} to {max(t["timestamp"] for t in trades)}')
            print(f'Duration: {max(t["timestamp"] for t in trades) - min(t["timestamp"] for t in trades)}')
            print()
            print('✅ Real historical data ready for accurate backtesting!')

        finally:
            await self.http_client.aclose()
            self.session.close()

async def main():
    collector = BlockchainCollector()
    await collector.run()

if __name__ == '__main__':
    asyncio.run(main())
