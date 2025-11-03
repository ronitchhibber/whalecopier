#!/usr/bin/env python3
"""
Add specific high-value whale to tracking list
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Whale
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)

# Whale address from Polymarket screenshot
whale_address = "0x53757615de1c42b83f893b79d4241a009dc2aeea"

with Session(engine) as session:
    # Check if whale exists
    existing = session.query(Whale).filter_by(address=whale_address).first()

    if existing:
        print(f"✅ Whale {whale_address[:10]}... already exists")
        print(f"   Copying enabled: {existing.is_copying_enabled}")
        if not existing.is_copying_enabled:
            existing.is_copying_enabled = True
            session.commit()
            print(f"   ✅ Enabled copying for this whale")
    else:
        # Add new whale with high priority
        whale = Whale(
            address=whale_address,
            total_trades=0,
            total_volume=0.0,
            avg_trade_size=0.0,
            quality_score=90.0,  # High score for manual add
            sharpe_ratio=2.5,
            win_rate=65.0,
            total_pnl=0.0,
            roi=0.0,
            max_drawdown=0.0,
            is_copying_enabled=True,  # Enable copying immediately
            last_updated=datetime.utcnow()
        )
        session.add(whale)
        session.commit()
        print(f"✅ Added whale {whale_address[:10]}... to tracking list")
        print(f"   Quality score: 90.0 (high priority)")
        print(f"   Copying: ENABLED")

print("\n" + "=" * 80)
print("🎯 Whale tracking updated!")
print("=" * 80)
print("The monitor will now track trades from this whale in real-time")
