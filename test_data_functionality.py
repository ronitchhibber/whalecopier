#!/usr/bin/env python3
"""
Comprehensive Data Functionality Test
Tests database connectivity and data operations
"""

from src.database import get_db_session, Whale, Trade
from decimal import Decimal
from datetime import datetime

print('='*80)
print('COMPREHENSIVE DATA FUNCTIONALITY TEST')
print('='*80)

try:
    # Test 1: Database Connection
    print('\n[1/5] Testing database connection...')
    session = next(get_db_session())
    print('  ✅ Database connection successful')

    # Test 2: Whale Data
    print('\n[2/5] Testing whale data access...')
    whales = session.query(Whale).limit(5).all()
    if whales:
        print(f'  ✅ Found {len(whales)} whales in database')
        for w in whales[:2]:
            print(f'     • {w.address[:10]}... - Win Rate: {w.win_rate:.1f}%, Volume: ${w.total_volume:,.0f}')
    else:
        print('  ⚠️  No whales found in database (empty db - this is OK)')

    # Test 3: Trade Data
    print('\n[3/5] Testing trade data access...')
    trades = session.query(Trade).limit(5).all()
    if trades:
        print(f'  ✅ Found {len(trades)} trades in database')
        for t in trades[:2]:
            print(f'     • Trade {t.id} - Market: {t.market_id} - PnL: ${t.pnl_usd:.2f}')
    else:
        print('  ⚠️  No trades found in database (empty db - this is OK)')

    # Test 4: Data Writes
    print('\n[4/5] Testing data write operations...')
    test_whale = Whale(
        address='0xTEST_WHALE_FOR_TESTING',
        total_volume=Decimal('1000.00'),
        win_rate=Decimal('75.5'),
        sharpe_ratio=Decimal('1.2'),
        is_copying_enabled=False,
        first_seen_date=datetime.utcnow()
    )
    session.add(test_whale)
    session.commit()
    print('  ✅ Data write successful')

    # Clean up test data
    session.delete(test_whale)
    session.commit()
    print('  ✅ Data deletion successful')

    # Test 5: Data Queries
    print('\n[5/5] Testing complex queries...')
    whale_count = session.query(Whale).filter(Whale.is_copying_enabled == True).count()
    print(f'  ✅ Complex query successful - {whale_count} active whales')

    session.close()

    print('\n' + '='*80)
    print('DATA TEST RESULTS: ✅ ALL TESTS PASSED')
    print('='*80)
    print('✅ Database connectivity')
    print('✅ Data read operations')
    print('✅ Data write operations')
    print('✅ Data delete operations')
    print('✅ Complex queries')
    print('\n🎉 DATA FUNCTIONALITY IS WORKING CORRECTLY!')

except Exception as e:
    print(f'\n❌ DATA TEST FAILED: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
