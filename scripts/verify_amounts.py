#!/usr/bin/env python3
import requests
import json

# Get recent trades
response = requests.get("http://localhost:8000/api/trades?limit=5")
trades = response.json()

print("Verifying Amount Calculations:")
print("=" * 80)

for t in trades[:5]:
    calc_amount = t['size'] * t['price']
    stored_amount = t.get('amount', 0)
    match = '✓' if abs(calc_amount - stored_amount) < 0.01 else '✗'

    print(f"\nMarket: {t['market_title'][:60]}")
    print(f"  Size: {t['size']:.2f} shares")
    print(f"  Price: ${t['price']:.2f}")
    print(f"  Stored Amount: ${stored_amount:.2f}")
    print(f"  Calculated (size×price): ${calc_amount:.2f}")
    print(f"  Match: {match}")

print("\n" + "=" * 80)
print("\nPolymarket Amount Formula: Size × Price")
print("Your frontend now uses: (trade.size * trade.price)")
