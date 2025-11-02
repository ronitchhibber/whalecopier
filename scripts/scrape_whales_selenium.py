"""
Scrape Polymarket leaderboard using Selenium for JS-rendered content.
Find top traders and add them to the database.
"""

import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)


def setup_driver():
    """Setup headless Chrome driver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"❌ Chrome driver error: {e}")
        print("Trying Firefox...")
        try:
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("--headless")
            driver = webdriver.Firefox(options=firefox_options)
            return driver
        except Exception as e2:
            print(f"❌ Firefox driver error: {e2}")
            return None


def scrape_leaderboard():
    """Scrape the Polymarket leaderboard page."""
    print("\n" + "="*80)
    print("🔍 SCRAPING POLYMARKET LEADERBOARD")
    print("="*80)

    driver = setup_driver()
    if not driver:
        print("\n❌ No browser driver available. Install ChromeDriver or GeckoDriver:")
        print("   brew install chromedriver")
        print("   OR")
        print("   brew install geckodriver")
        return []

    try:
        print("\n📥 Loading leaderboard page...")
        driver.get("https://polymarket.com/leaderboard")

        # Wait for leaderboard to load
        print("⏳ Waiting for JavaScript to render...")
        wait = WebDriverWait(driver, 20)

        # Try to find leaderboard rows (adjust selector based on actual page structure)
        time.sleep(5)  # Give extra time for JS

        # Look for common leaderboard patterns
        selectors_to_try = [
            "tr[data-testid*='leaderboard']",
            "div[class*='leaderboard-row']",
            "div[class*='LeaderboardRow']",
            "a[href*='/profile/']",
            "div[class*='trader']",
        ]

        traders = []
        for selector in selectors_to_try:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"✅ Found {len(elements)} elements with selector: {selector}")

                    for element in elements[:50]:  # Top 50
                        try:
                            # Try to extract address from href
                            if 'href' in element.get_attribute('outerHTML'):
                                href = element.get_attribute('href')
                                if '/profile/' in href:
                                    address = href.split('/profile/')[-1].split('/')[0].split('?')[0]
                                    if address.startswith('0x') and len(address) == 42:
                                        traders.append(address)
                                        print(f"  Found whale: {address}")
                        except:
                            continue

                    if traders:
                        break
            except:
                continue

        driver.quit()

        print(f"\n✅ Extracted {len(traders)} unique whale addresses")
        return list(set(traders))

    except Exception as e:
        print(f"\n❌ Error scraping leaderboard: {e}")
        if driver:
            driver.quit()
        return []


def scrape_popular_markets():
    """Alternative: Scrape popular markets to find active traders."""
    print("\n" + "="*80)
    print("🔍 SCRAPING POPULAR MARKETS FOR ACTIVE TRADERS")
    print("="*80)

    import requests

    try:
        # Get popular markets from Gamma API
        response = requests.get("https://gamma-api.polymarket.com/events?limit=20&active=true", timeout=10)

        if response.status_code != 200:
            print(f"❌ Gamma API returned {response.status_code}")
            return []

        events = response.json()
        print(f"\n✅ Found {len(events)} active events")

        all_traders = set()

        # For each event, try to get market data
        for event in events[:10]:  # Top 10 events
            try:
                markets = event.get('markets', [])
                for market in markets[:2]:  # First 2 markets per event
                    market_id = market.get('id')
                    if not market_id:
                        continue

                    print(f"\n📊 Checking market: {market.get('question', market_id)[:60]}...")

                    # Try to get orderbook (may reveal traders)
                    try:
                        book_response = requests.get(
                            f"https://clob.polymarket.com/book?token_id={market_id}",
                            timeout=5
                        )
                        if book_response.status_code == 200:
                            book = book_response.json()
                            print(f"   ✅ Got orderbook data")
                    except:
                        pass

                    time.sleep(0.5)  # Rate limit
            except Exception as e:
                continue

        return list(all_traders)

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def add_whales_to_db(addresses):
    """Add discovered whale addresses to database."""
    if not addresses:
        print("\n❌ No addresses to add")
        return

    print("\n" + "="*80)
    print(f"💾 ADDING {len(addresses)} WHALES TO DATABASE")
    print("="*80)

    with Session(engine) as session:
        added = 0
        skipped = 0

        for address in addresses:
            try:
                # Check if already exists
                existing = session.query(Whale).filter(Whale.address == address).first()

                if existing:
                    print(f"⏭️  Skipped (exists): {address}")
                    skipped += 1
                    continue

                # Add new whale
                whale = Whale(
                    address=address,
                    pseudonym=f"Trader_{address[:8]}",
                    tier="MEDIUM",  # Default, will be updated by scoring
                    quality_score=50.0,  # Default
                    total_volume=0.0,
                    total_trades=0,
                    win_rate=0.0,
                    sharpe_ratio=0.0,
                    total_pnl=0.0,
                    is_copying_enabled=True,
                    last_active=datetime.utcnow()
                )

                session.add(whale)
                session.commit()

                print(f"✅ Added: {address}")
                added += 1

            except Exception as e:
                print(f"❌ Error adding {address}: {e}")
                session.rollback()
                continue

        print(f"\n" + "="*80)
        print(f"✅ Added: {added} whales")
        print(f"⏭️  Skipped: {skipped} whales (already in DB)")
        print("="*80)


def main():
    print("\n" + "="*80)
    print("🐋 WHALE DISCOVERY - WEB SCRAPING METHOD")
    print("="*80)

    # Method 1: Scrape leaderboard with Selenium
    print("\n[Method 1] Scraping leaderboard page...")
    traders = scrape_leaderboard()

    # Method 2: Alternative - scan popular markets
    if len(traders) < 10:
        print("\n[Method 2] Scanning popular markets...")
        market_traders = scrape_popular_markets()
        traders.extend(market_traders)
        traders = list(set(traders))

    if traders:
        add_whales_to_db(traders)
        print(f"\n🎉 Discovery complete! Found {len(traders)} whale addresses")
        print("\nNext steps:")
        print("1. View them in dashboard: http://localhost:8000/dashboard")
        print("2. Run scoring: python3 scripts/score_whales.py")
        print("3. Start monitoring: python3 services/ingestion/main.py")
    else:
        print("\n❌ No whales discovered. Try manual method:")
        print("1. Visit: https://polymarket.com/leaderboard")
        print("2. Copy addresses manually")
        print("3. Run: python3 scripts/add_whale_address.py <ADDRESS>")


if __name__ == "__main__":
    main()
