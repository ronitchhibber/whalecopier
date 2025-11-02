#!/usr/bin/env python3
"""
Historical Data Fetcher using Polymarket Subgraphs (Goldsky)
=============================================================

Fetches 60+ days of historical whale trades and market resolutions
from Polymarket's Goldsky-hosted subgraphs.

NO API KEY REQUIRED - Public Goldsky endpoints
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from libs.common.models import Market, Trade, Whale
from decimal import Decimal
import time

# Goldsky subgraph endpoints (public, no API key needed)
ORDERBOOK_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"
PNL_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/pnl-subgraph/0.0.1/gn"

# Database setup
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

# Configuration
DAYS_TO_FETCH = 60
WHALE_THRESHOLD_USDC = 1000 * 1_000_000  # $1000 in 6-decimal USDC
BATCH_SIZE = 1000

print('=' * 80)
print('POLYMARKET HISTORICAL DATA FETCHER (GOLDSKY)')
print('=' * 80)
print()
print(f'Target: {DAYS_TO_FETCH} days of whale trades with real market resolutions')
print(f'Source: Goldsky subgraphs (public, no API key needed)')
print(f'Whale threshold: ${WHALE_THRESHOLD_USDC / 1_000_000:,.0f} USD')
print()

class GraphDataFetcher:
    def __init__(self):
        self.session = Session()

        # Setup orderbook client
        orderbook_transport = RequestsHTTPTransport(url=ORDERBOOK_URL)
        self.orderbook_client = Client(transport=orderbook_transport, fetch_schema_from_transport=False)

        # Setup PNL client
        pnl_transport = RequestsHTTPTransport(url=PNL_URL)
        self.pnl_client = Client(transport=pnl_transport, fetch_schema_from_transport=False)

        # Calculate timestamp range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=DAYS_TO_FETCH)
        self.start_timestamp = int(start_time.timestamp())
        self.end_timestamp = int(end_time.timestamp())

        print(f'✅ Connected to Goldsky subgraphs')
        print(f'   Date range: {start_time.strftime("%Y-%m-%d")} to {end_time.strftime("%Y-%m-%d")}')
        print(f'   Timestamp range: {self.start_timestamp} to {self.end_timestamp}')
        print()

    def fetch_whale_trades(self):
        """
        Fetch whale trades using cursor-based pagination.
        CRITICAL: Must use timestamp-based cursors to avoid 5,000 skip limit!
        """
        print('PHASE 1: FETCHING WHALE TRADES')
        print('=' * 80)

        all_trades = []
        cursor_timestamp = self.start_timestamp
        page = 0

        query = gql("""
        query GetWhaleTrades($minTimestamp: BigInt!, $minAmount: BigInt!) {
          orderFilledEvents(
            first: 1000
            where: {
              timestamp_gte: $minTimestamp
              takerAmountFilled_gte: $minAmount
            }
            orderBy: timestamp
            orderDirection: asc
          ) {
            id
            timestamp
            transactionHash
            taker
            makerAssetId
            takerAssetId
            makerAmountFilled
            takerAmountFilled
          }
        }
        """)

        while cursor_timestamp < self.end_timestamp:
            page += 1

            try:
                result = self.orderbook_client.execute(query, variable_values={
                    "minTimestamp": str(cursor_timestamp),
                    "minAmount": str(WHALE_THRESHOLD_USDC)
                })

                trades = result['orderFilledEvents']

                if not trades:
                    print(f'   Page {page}: No more trades found')
                    break

                all_trades.extend(trades)

                # Update cursor to last trade's timestamp
                last_timestamp = int(trades[-1]['timestamp'])
                cursor_timestamp = last_timestamp + 1  # Move to next second

                # Progress update
                last_date = datetime.fromtimestamp(last_timestamp)
                print(f'   Page {page}: Fetched {len(trades)} trades (total: {len(all_trades):,}, date: {last_date.strftime("%Y-%m-%d")})')

                # Rate limiting - be respectful to free API
                time.sleep(0.2)

            except Exception as e:
                print(f'   ❌ Error on page {page}: {e}')
                # Try to continue from where we left off
                cursor_timestamp += 3600  # Skip 1 hour forward
                continue

        print()
        print(f'✅ Fetched {len(all_trades):,} whale trades')

        if all_trades:
            first_date = datetime.fromtimestamp(int(all_trades[0]['timestamp']))
            last_date = datetime.fromtimestamp(int(all_trades[-1]['timestamp']))
            print(f'   Date range: {first_date.strftime("%Y-%m-%d")} to {last_date.strftime("%Y-%m-%d")}')
            print(f'   Duration: {last_date - first_date}')

        print()
        return all_trades

    def extract_condition_ids(self, trades):
        """Extract unique condition IDs from token IDs"""
        condition_ids = set()

        for trade in trades:
            # Token IDs encode: condition_id (32 bytes) + index (1 byte)
            # We need to extract the condition_id part
            try:
                token_id = int(trade['takerAssetId'])
                # Extract condition ID (first 32 bytes)
                condition_id = hex(token_id >> 8)  # Shift right 8 bits to remove index
                condition_ids.add(condition_id)
            except:
                pass

        return list(condition_ids)

    def fetch_market_resolutions(self, condition_ids):
        """
        Fetch market resolutions from PNL subgraph.
        Must batch into groups to avoid query size limits.
        """
        print('PHASE 2: FETCHING MARKET RESOLUTIONS')
        print('=' * 80)
        print(f'Fetching resolutions for {len(condition_ids)} unique markets...')
        print()

        resolutions = {}
        batch_size = 500  # GraphQL query size limit

        query = gql("""
        query GetResolutions($ids: [ID!]!) {
          conditions(where: { id_in: $ids }) {
            id
            payoutNumerators
            outcomeSlotCount
            resolved
          }
        }
        """)

        for i in range(0, len(condition_ids), batch_size):
            batch = condition_ids[i:i+batch_size]
            batch_num = (i // batch_size) + 1

            try:
                result = self.pnl_client.execute(query, variable_values={"ids": batch})

                for condition in result['conditions']:
                    if condition['payoutNumerators'] and condition['resolved']:
                        # Determine winner from payout numerators
                        # Winner is the index with max payout (usually 1)
                        payouts = [int(x) for x in condition['payoutNumerators']]
                        winner_index = payouts.index(max(payouts))
                        # Index 0 = YES, Index 1 = NO (typically)
                        outcome = "YES" if winner_index == 0 else "NO"
                        resolutions[condition['id']] = outcome

                print(f'   Batch {batch_num}/{(len(condition_ids)-1)//batch_size + 1}: {len(result["conditions"])} found, {len(resolutions)} resolved')

                time.sleep(0.1)

            except Exception as e:
                print(f'   ❌ Error fetching batch {batch_num}: {e}')
                continue

        print()
        print(f'✅ Found {len(resolutions):,} resolved markets')
        resolved_pct = (len(resolutions) / len(condition_ids) * 100) if condition_ids else 0
        print(f'   Resolution rate: {resolved_pct:.1f}%')
        print()

        return resolutions

    def store_to_database(self, trades, resolutions):
        """Store trades and markets in database with deduplication"""
        print('PHASE 3: STORING TO DATABASE')
        print('=' * 80)

        markets_created = 0
        trades_stored = 0
        trades_skipped = 0

        # Group trades by condition ID
        trades_by_market = {}
        for trade in trades:
            try:
                token_id = int(trade['takerAssetId'])
                condition_id = hex(token_id >> 8)

                if condition_id not in trades_by_market:
                    trades_by_market[condition_id] = []
                trades_by_market[condition_id].append(trade)
            except:
                continue

        print(f'Processing {len(trades_by_market)} unique markets...')
        print()

        # Store markets first
        for condition_id, market_trades in trades_by_market.items():
            try:
                # Check if market exists
                existing = self.session.query(Market).filter_by(condition_id=condition_id).first()

                if not existing:
                    # Calculate total volume for this market
                    total_volume = sum(
                        Decimal(str(int(t['takerAmountFilled']) / 1_000_000))
                        for t in market_trades
                    )

                    # Get outcome if resolved
                    outcome = resolutions.get(condition_id)

                    market = Market(
                        condition_id=condition_id,
                        question=f"Market {condition_id[:16]}...",  # We don't have question from subgraph
                        closed=(outcome is not None),
                        outcome=outcome,
                        volume=total_volume,
                        liquidity=Decimal('0')
                    )
                    self.session.add(market)
                    markets_created += 1

            except Exception as e:
                print(f'   Warning: Error storing market {condition_id[:16]}: {e}')
                continue

        self.session.commit()
        print(f'✅ Stored {markets_created} new markets')
        print()

        # Store trades with deduplication
        print(f'Storing {len(trades):,} trades...')

        for i, trade in enumerate(trades):
            if (i + 1) % 1000 == 0:
                print(f'   Progress: {i+1:,}/{len(trades):,} trades processed...')

            try:
                # Parse trade data
                token_id = int(trade['takerAssetId'])
                condition_id = hex(token_id >> 8)
                outcome_index = token_id & 0xFF  # Last byte is outcome index
                outcome = "YES" if outcome_index == 0 else "NO"

                shares = Decimal(str(int(trade['takerAmountFilled']) / 1_000_000))
                maker_amount = Decimal(str(int(trade['makerAmountFilled']) / 1_000_000))

                # Price is maker_amount / taker_amount
                price = maker_amount / shares if shares > 0 else Decimal('0.5')

                timestamp = datetime.fromtimestamp(int(trade['timestamp']))

                # Check if trade already exists (by transaction hash)
                existing = self.session.query(Trade).filter_by(
                    transaction_hash=trade['transactionHash']
                ).first()

                if existing:
                    trades_skipped += 1
                    continue

                # Create trade record
                trade_record = Trade(
                    market_id=condition_id,
                    trader_address=trade['taker'],
                    transaction_hash=trade['transactionHash'],
                    timestamp=timestamp,
                    outcome=outcome,
                    shares=shares,
                    price=price,
                    is_whale_trade=True
                )
                self.session.add(trade_record)
                trades_stored += 1

                # Commit every 100 trades
                if trades_stored % 100 == 0:
                    self.session.commit()

            except Exception as e:
                print(f'   Warning: Error storing trade {trade["transactionHash"][:16]}: {e}')
                continue

        self.session.commit()

        print()
        print(f'✅ Stored {trades_stored:,} new trades')
        print(f'   Skipped {trades_skipped:,} duplicate trades')
        print()

    def run(self):
        """Main execution flow"""
        try:
            # Step 1: Fetch whale trades
            trades = self.fetch_whale_trades()

            if not trades:
                print('❌ No trades found - check date range or whale threshold')
                return

            # Step 2: Extract condition IDs and fetch resolutions
            condition_ids = self.extract_condition_ids(trades)
            resolutions = self.fetch_market_resolutions(condition_ids)

            # Step 3: Store everything in database
            self.store_to_database(trades, resolutions)

            # Final summary
            print('=' * 80)
            print('DATA COLLECTION COMPLETE')
            print('=' * 80)
            print(f'Total whale trades: {len(trades):,}')
            print(f'Unique markets: {len(condition_ids)}')
            print(f'Resolved markets: {len(resolutions)}')

            if trades:
                first_date = datetime.fromtimestamp(int(trades[0]['timestamp']))
                last_date = datetime.fromtimestamp(int(trades[-1]['timestamp']))
                print(f'Date range: {first_date.strftime("%Y-%m-%d")} to {last_date.strftime("%Y-%m-%d")}')
                print(f'Duration: {last_date - first_date}')

            print()
            print('✅ Real historical data ready for accurate backtesting!')
            print()
            print('Next steps:')
            print('1. Run scripts/check_data_status.py to verify data quality')
            print('2. Update backtester to use real market outcomes')
            print('3. Run backtest with historical data')

        finally:
            self.session.close()

def main():
    fetcher = GraphDataFetcher()
    fetcher.run()

if __name__ == '__main__':
    main()
