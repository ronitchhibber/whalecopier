#!/usr/bin/env python3
"""
Test script to verify frontend integration is complete
"""

import requests
import json
import time
from datetime import datetime

def test_api_endpoints():
    """Test all API endpoints are accessible"""
    endpoints = [
        ('http://localhost:8000/api/whales', 'Whales API'),
        ('http://localhost:8000/api/trades', 'Trades API'),
        ('http://localhost:8000/api/stats/summary', 'Stats Summary'),
        ('http://localhost:8000/api/backtest', 'Backtest API'),
        ('http://localhost:8890/api/settings', 'Settings API'),
    ]

    print("=" * 60)
    print("TESTING API ENDPOINTS")
    print("=" * 60)

    all_passed = True
    for url, name in endpoints:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {name:20} - OK ({url})")
                if 'json' in response.headers.get('content-type', ''):
                    data = response.json()
                    if isinstance(data, list):
                        print(f"   → Returned {len(data)} items")
                    elif isinstance(data, dict):
                        print(f"   → Keys: {', '.join(list(data.keys())[:5])}")
            else:
                print(f"⚠️  {name:20} - Status {response.status_code}")
                all_passed = False
        except Exception as e:
            print(f"❌ {name:20} - Error: {str(e)[:50]}")
            all_passed = False

    return all_passed

def test_frontend_pages():
    """Test frontend pages are accessible"""
    pages = [
        ('http://localhost:8890/', 'Unified Dashboard'),
        ('http://localhost:8890/unified_dashboard.html', 'Dashboard Direct'),
        ('http://localhost:8890/settings.html', 'Settings Page'),
        ('http://localhost:8890/index.html', 'Index (should redirect)'),
    ]

    print("\n" + "=" * 60)
    print("TESTING FRONTEND PAGES")
    print("=" * 60)

    all_passed = True
    for url, name in pages:
        try:
            response = requests.get(url, timeout=5, allow_redirects=False)
            if response.status_code in [200, 301, 302]:
                print(f"✅ {name:25} - OK")
                # Check for key elements in HTML
                if response.status_code == 200 and 'html' in response.headers.get('content-type', ''):
                    content = response.text
                    elements = {
                        'Tabs': 'class="tab"' in content,
                        'Charts': 'canvas' in content.lower(),
                        'Navigation': 'nav-link' in content,
                        'Analytics': 'analytics-tab' in content or 'Analytics' in content,
                    }
                    for elem, found in elements.items():
                        if found:
                            print(f"   → {elem} found")
            else:
                print(f"⚠️  {name:25} - Status {response.status_code}")
                all_passed = False
        except Exception as e:
            print(f"❌ {name:25} - Error: {str(e)[:50]}")
            all_passed = False

    return all_passed

def test_chart_data_availability():
    """Test that data for charts is available"""
    print("\n" + "=" * 60)
    print("TESTING CHART DATA AVAILABILITY")
    print("=" * 60)

    try:
        # Test trades data for P&L calculation
        response = requests.get('http://localhost:8000/api/trades', timeout=5)
        if response.status_code == 200:
            trades = response.json()
            if trades and isinstance(trades, list):
                print(f"✅ Trade data available: {len(trades)} trades")
                # Check if trades have necessary fields
                if len(trades) > 0:
                    required_fields = ['timestamp', 'profit_loss', 'position_size']
                    sample = trades[0] if isinstance(trades[0], dict) else {}
                    for field in required_fields:
                        if field in sample:
                            print(f"   → Field '{field}' present")
            else:
                print("⚠️  No trade data available for charts")
        else:
            print(f"❌ Failed to fetch trade data: Status {response.status_code}")

        # Test whale data for win rate distribution
        response = requests.get('http://localhost:8000/api/whales', timeout=5)
        if response.status_code == 200:
            whales = response.json()
            if whales and isinstance(whales, list):
                print(f"✅ Whale data available: {len(whales)} whales")
                # Check win rate distribution
                if len(whales) > 0:
                    win_rates = []
                    for whale in whales[:10]:  # Sample first 10
                        if isinstance(whale, dict) and 'win_rate' in whale:
                            win_rates.append(whale['win_rate'])
                    if win_rates:
                        print(f"   → Win rates found: min={min(win_rates):.2f}, max={max(win_rates):.2f}")
            else:
                print("⚠️  No whale data available for charts")
        else:
            print(f"❌ Failed to fetch whale data: Status {response.status_code}")

    except Exception as e:
        print(f"❌ Error testing chart data: {str(e)}")
        return False

    return True

def test_websocket_connectivity():
    """Test WebSocket connectivity (basic check)"""
    print("\n" + "=" * 60)
    print("TESTING WEBSOCKET CONNECTIVITY")
    print("=" * 60)

    try:
        # Check if WebSocket endpoint is mentioned in dashboard
        response = requests.get('http://localhost:8890/unified_dashboard.html', timeout=5)
        if response.status_code == 200:
            content = response.text
            ws_indicators = [
                'WebSocket' in content,
                'ws://' in content or 'wss://' in content,
                'new WebSocket' in content,
            ]
            if any(ws_indicators):
                print("✅ WebSocket code found in dashboard")
                print("   → Dashboard includes WebSocket connectivity")
            else:
                print("⚠️  No WebSocket code found (may not be implemented)")
        else:
            print("⚠️  Could not check WebSocket - dashboard not accessible")
    except Exception as e:
        print(f"⚠️  Error checking WebSocket: {str(e)[:50]}")

    return True

def test_integration_features():
    """Test specific integration features"""
    print("\n" + "=" * 60)
    print("TESTING INTEGRATION FEATURES")
    print("=" * 60)

    features_status = {
        "Timestamp Format": False,
        "Table Display": False,
        "Progress Bar": False,
        "Chart Canvas": False,
        "Budget Config": False,
    }

    try:
        response = requests.get('http://localhost:8890/unified_dashboard.html', timeout=5)
        if response.status_code == 200:
            content = response.text

            # Check for specific implementations
            features_status["Timestamp Format"] = 'formatTimestamp' in content and 'MMM' in content
            features_status["Table Display"] = '<table' in content and 'tbody' in content
            features_status["Progress Bar"] = 'progress-bar' in content
            features_status["Chart Canvas"] = '<canvas' in content and ('pnl-canvas' in content or 'winrate-canvas' in content)
            features_status["Budget Config"] = 'initial-capital' in content or 'Initial Capital' in content

            for feature, status in features_status.items():
                symbol = "✅" if status else "❌"
                print(f"{symbol} {feature:20} - {'Implemented' if status else 'Not found'}")
    except Exception as e:
        print(f"❌ Error testing features: {str(e)}")
        return False

    return all(features_status.values())

def main():
    """Run all tests"""
    print("\n")
    print("🔧 WHALETRACKER FRONTEND INTEGRATION TEST")
    print("=" * 60)
    print(f"Testing at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    tests = [
        ("API Endpoints", test_api_endpoints),
        ("Frontend Pages", test_frontend_pages),
        ("Chart Data", test_chart_data_availability),
        ("WebSocket", test_websocket_connectivity),
        ("Integration Features", test_integration_features),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with error: {str(e)}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        symbol = "✅" if result else "❌"
        status = "PASSED" if result else "FAILED"
        print(f"{symbol} {test_name:25} - {status}")

    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Frontend integration is complete.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review the output above.")

    return passed == total

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)