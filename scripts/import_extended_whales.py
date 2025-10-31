"""
Import additional whales from extended leaderboard data.
Filter by strict criteria and avoid duplicates.
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)

# Extended whale data from the comprehensive list
# Format: (rank, username, total_positions, active_positions, total_wins(volume), total_losses, win_rate, current_value, overall_pnl)
EXTENDED_WHALES = [
    # High-volume traders that might not have been in first list
    (40, "rwo", 8321, 42, 1382232, 30975, 95.6, 80562, 1351257),
    (173, "ThereIsNoSpoon", 854, 24, 426223, 2799, 98.2, 6360, 423425),
    (207, "Nowhere-Man", 1032, 16, 579264, 239559, 82.1, 5791, 339705),
    (260, "rbczz", 653, 25, 362070, 86688, 85.8, 12877, 275381),
    (267, "Karajan", 3320, 2168, 272129, 5917, 85.8, 39852, 266213),
    (297, "kutarr", 3848, 14, 346895, 110263, 87.5, 35919, 236632),
    (299, "mr.ozi", 1762, 8, 597965, 364030, 75.2, 64433, 233935),
    (315, "Euan", 1819, 33, 294215, 68378, 73.5, 164055, 225837),
    (320, "cry.eth2", 27483, 3560, 237823, 14465, 68.2, 72543, 223359),
    (329, "Big.Chungus", 1120, 35, 241763, 25854, 71.9, 138454, 215909),
    (349, "wisser", 676, 196, 287190, 83422, 66.6, 300196, 203768),
    (358, "VvVv", 3825, 138, 231615, 34825, 88.8, 86691, 196790),
    (365, "truthteller", 3048, 89, 728170, 533174, 57.9, 37735, 194996),
    (366, "Snoorrason", 4855, 345, 256760, 62025, 62.3, 89165, 194735),
    (379, "MisTKy", 1064, 27, 317379, 130253, 69.5, 94295, 187127),
    (384, "nhpx38txna0500", 537, 48, 331922, 148170, 70.9, 87848, 183752),
    (388, "fatbojangles", 7846, 126, 882784, 699997, 56.1, 152274, 182787),
    (390, "dududududu", 6612, 65, 491030, 309270, 65.1, 37575, 181760),
    (394, "LucasMeow", 90, 12, 179022, 164, 95.1, 475716, 178858),
    (401, "big.bitch", 414, 13, 329511, 155601, 65.1, 542631, 173910),
    (405, "ElonSpam", 2133, 44, 427123, 255669, 58.0, 124057, 171454),
    (406, "Olololo", 153, 8, 315153, 144134, 85.9, 214008, 171019),
    (413, "commeowder", 1346, 116, 236559, 69122, 74.0, 191876, 167437),
    (418, "syncope", 1457, 15, 297422, 133856, 78.4, 3198, 163566),
    (422, "cashy", 403, 13, 189979, 28167, 74.1, 26756, 161812),
    (423, "CrunchWrapoDeLaFuente", 7482, 18, 2047777, 1886101, 56.8, 5674, 161676),
    (424, "peasant", 267, 26, 767441, 605906, 59.6, 40693, 161535),
    (426, "aadvark", 5930, 1747, 1072182, 911056, 58.9, 692516, 161125),
    (431, "JJo", 1202, 66, 269185, 109425, 74.4, 146800, 159760),
    (434, "Martiini", 2403, 358, 210171, 51322, 66.4, 17908, 158849),
    (436, "CoffeeLover", 1229, 133, 242596, 84477, 75.0, 64714, 158119),
    (441, "0x53eCc53E7", 1247, 374, 261780, 106293, 60.3, 186593, 155487),
    (444, "x6916Cc00AA1c3e75ECf4081DF7caE7D2f3592fd4", 3063, 67, 182810, 28617, 58.9, 107495, 154192),
    (446, "tsybka", 476, 6, 174236, 20618, 84.9, 24958, 153618),
    (448, "sportbet", 5062, 132, 1789397, 1637498, 53.2, 88507, 151899),
    (450, "-.o...o.-", 2686, 23, 6374997, 6223910, 64.5, 31930, 151088),
    (452, "tcp2", 4079, 108, 269956, 119836, 61.3, 25784, 150120),
    (455, "Trump2028", 262, 31, 196114, 47352, 90.9, 466801, 148762),
    (462, "Pikachu888", 428, 155, 318456, 171402, 62.9, 102050, 147054),
    (468, "RobXK", 2556, 188, 766700, 621376, 58.0, 138223, 145323),
    (478, "betwick", 494, 88, 579335, 438171, 63.7, 316663, 141164),
    (481, "classified", 873, 108, 169233, 28249, 80.9, 67906, 140984),
    (482, "TealV", 224, 35, 195816, 55154, 80.9, 357352, 140662),
    (483, "hmm ok", 1605, 5, 169928, 29596, 76.6, 1111, 140332),
    (487, "frosen", 1541, 230, 195334, 55849, 59.9, 92992, 139485),
    (490, "MRF", 4714, 841, 369163, 230066, 60.8, 68369, 139097),
    (497, "TradeImbalanceArchitect", 2056, 277, 285348, 147445, 62.1, 147605, 137903),
    (499, "Kevindoto", 229, 34, 373515, 236093, 80.8, 598831, 137422),
    (501, "LambSaauce", 9352, 169, 308296, 171276, 59.2, 14265, 137020),
    (503, "Anon (0x7668...9ec)", 1628, 34, 240696, 104859, 66.0, 13106, 135837),
    (508, "Qualitative", 13520, 94, 410962, 277319, 58.5, 60211, 133643),
    (512, "aespakarina", 20793, 127, 231556, 98994, 62.1, 2663, 132562),
    (519, "Marcus177", 2027, 289, 153688, 23698, 60.7, 8591, 129990),
    (520, "0xf247...5200", 8324, 66, 205331, 75422, 67.1, 1198, 129909),
    (522, "donjo", 669, 84, 196206, 66879, 70.7, 30601, 129328),
    (527, "Eatpraylove", 422, 151, 168439, 40369, 76.2, 448732, 128070),
    (528, "DickTurbin", 6151, 938, 403152, 275470, 58.1, 61561, 127682),
    (533, "niggemon", 1165, 65, 189962, 64284, 78.8, 41001, 125678),
    (534, "JohnnyTenNumbers", 812, 354, 126761, 1284, 68.7, 7012, 125477),
    (538, "0x7298...2160", 1361, 328, 133512, 8492, 80.3, 36681, 125021),
    (539, "Spon", 813, 62, 125756, 1652, 78.4, 111834, 124105),
    (540, "numbersandletters", 208, 30, 347449, 223610, 73.0, 98655, 123839),
    (541, "tourists", 219, 15, 227612, 103901, 72.2, 185311, 123711),
    (544, "sovereign2013", 4313, 140, 821090, 697606, 55.2, 236000, 123484),
    (547, "roldy", 2083, 339, 1506401, 1383607, 52.6, 32054, 122794),
    (549, "daroghi", 44536, 1309, 201836, 79313, 62.4, 12654, 122522),
    (550, "Eridpnc", 3889, 77, 883360, 761781, 57.7, 32471, 121579),
    (551, "asfgh", 481, 79, 769221, 647775, 64.6, 543839, 121447),
    (553, "easypredict", 1835, 588, 599004, 478149, 50.9, 220770, 120855),
    (554, "kdawgpi2", 1475, 52, 369445, 248708, 59.6, 144470, 120738),
    (555, "noovd", 1333, 138, 266483, 146042, 50.0, 80116, 120441),
    (559, "risk-manager", 618, 87, 139439, 19552, 76.9, 79055, 119887),
    (563, "AIisTheNewWalkingDead", 1712, 37, 127466, 8235, 98.7, 10945, 119231),
    (566, "interstellaar", 2462, 77, 134397, 15893, 66.3, 2373, 118504),
    (568, "mostobesegoldfish", 129, 12, 350671, 232822, 61.7, 20929, 117849),
    (572, "kickstandhater", 683, 8, 203897, 87525, 72.6, 12971, 116373),
    (574, "MEPP", 434, 102, 461827, 345730, 58.7, 194301, 116097),
    (580, "DapperChapper", 850, 27, 496185, 380824, 71.7, 89461, 115360),
    (593, "DumplingBMF", 1612, 73, 288362, 176091, 69.1, 94015, 112271),
    (594, "FrancisSP8", 1446, 33, 151046, 38897, 80.2, 9832, 112149),
    (595, "HONDACIVIC", 634, 56, 223270, 111349, 61.4, 10301, 111921),
    (604, "StrideR", 1402, 218, 156592, 45316, 50.3, 78054, 111277),
    (608, "EscalateFund", 927, 34, 672029, 561320, 84.0, 133548, 110708),
    (618, "renzent", 3106, 104, 306755, 196980, 56.1, 13365, 109775),
    (622, "sbimbg", 1398, 111, 633142, 523769, 59.0, 119220, 109373),
    (625, "aureli", 8265, 1398, 118793, 9732, 52.8, 21169, 109061),
    (627, "AiBets", 2451, 95, 185796, 77089, 63.0, 59108, 108707),
    (633, "Anon (0x4e25...7a7)", 7636, 1704, 1185206, 1078226, 62.5, 654342, 106980),
    (634, "Liquidifier", 2195, 137, 165348, 58479, 58.2, 19158, 106869),
    (635, "bosshog", 969, 73, 163123, 56528, 70.7, 217582, 106595),
    (641, "hembag", 15521, 1696, 749999, 644566, 57.2, 1050, 105433),
    (643, "Bombarda", 80, 13, 130120, 24842, 82.6, 44203, 105278),
    (645, "brr69420", 2806, 344, 476970, 372983, 48.9, 63024, 103988),
    (648, "TheRedChip", 1234, 292, 178669, 75037, 45.0, 116206, 103632),
    (650, "getbipped", 889, 341, 314963, 211554, 51.2, 370743, 103409),
    (658, "LifelsBeautiful", 414, 87, 578397, 476296, 58.5, 240175, 102101),
    (667, "aviato", 1452, 31, 140910, 40845, 87.1, 122571, 100065),
]


def calculate_sharpe(volume, pnl):
    """Estimate Sharpe ratio from P&L/volume."""
    if volume <= 0:
        return 1.0
    profit_ratio = pnl / volume
    sharpe = min(max(profit_ratio * 30, 0.5), 4.5)
    return round(sharpe, 2)


def import_extended_whales():
    """Import additional whales from extended list."""
    print("\n" + "="*80)
    print("📊 IMPORTING EXTENDED WHALE LIST")
    print("="*80)
    print(f"\nTotal candidates in list: {len(EXTENDED_WHALES)}")
    print("\nFiltering criteria:")
    print("  ✓ Volume: $100,000+")
    print("  ✓ Win rate: 55%+")
    print("  ✓ Trades: 200+")
    print("  ✓ Sharpe ratio: >2.0\n")

    with Session(engine) as session:
        added = 0
        updated = 0
        skipped = 0
        filtered_out = 0

        for whale_data in EXTENDED_WHALES:
            rank, username, total_pos, active_pos, volume, losses, win_rate, current_val, pnl = whale_data

            # Calculate Sharpe
            sharpe = calculate_sharpe(volume, pnl)

            # Apply strict filters
            if volume < 100000:
                filtered_out += 1
                continue

            if win_rate < 55:
                filtered_out += 1
                continue

            if total_pos < 200:
                filtered_out += 1
                continue

            if sharpe < 2.0:
                filtered_out += 1
                continue

            # Determine tier
            if volume > 10000000:
                tier = 'MEGA'
                quality_score = 92.0
            elif volume > 5000000:
                tier = 'MEGA'
                quality_score = 88.0
            elif volume > 1000000:
                tier = 'HIGH'
                quality_score = 82.0
            elif volume > 500000:
                tier = 'MEDIUM'
                quality_score = 72.0
            else:
                tier = 'MEDIUM'
                quality_score = 65.0

            # Boost for exceptional metrics
            if win_rate > 80:
                quality_score += 6
            elif win_rate > 70:
                quality_score += 4
            if sharpe > 3.5:
                quality_score += 5
            elif sharpe > 3.0:
                quality_score += 3
            if total_pos > 5000:
                quality_score += 3

            quality_score = min(quality_score, 98.0)

            # Generate pseudo-address
            import hashlib
            address_hash = hashlib.sha256(username.encode()).hexdigest()
            pseudo_address = f"0x{address_hash[:40]}"

            try:
                # Check if exists by pseudonym
                existing = session.query(Whale).filter(Whale.pseudonym == username).first()

                if existing:
                    # Update if significantly better data
                    if volume > existing.total_volume * 1.1:
                        existing.total_volume = volume
                        existing.total_pnl = pnl
                        existing.total_trades = total_pos
                        existing.win_rate = win_rate
                        existing.sharpe_ratio = sharpe
                        existing.tier = tier
                        existing.quality_score = quality_score
                        existing.last_active = datetime.utcnow()
                        updated += 1
                    else:
                        skipped += 1
                else:
                    # Add new whale
                    whale = Whale(
                        address=pseudo_address,
                        pseudonym=username,
                        tier=tier,
                        quality_score=quality_score,
                        total_volume=volume,
                        total_pnl=pnl,
                        total_trades=total_pos,
                        win_rate=win_rate,
                        sharpe_ratio=sharpe,
                        is_copying_enabled=True,
                        last_active=datetime.utcnow()
                    )
                    session.add(whale)
                    added += 1

                    if added % 10 == 0:
                        print(f"  ✅ Added: {username} (${volume:,.0f}, {win_rate}% WR, {sharpe} Sharpe)")

                if (added + updated) % 20 == 0:
                    session.commit()

            except Exception as e:
                print(f"  ❌ Error with {username}: {e}")
                session.rollback()

        session.commit()

        print(f"\n" + "="*80)
        print("📊 IMPORT SUMMARY")
        print("="*80)
        print(f"✅ Added: {added} new whales")
        print(f"🔄 Updated: {updated} existing whales")
        print(f"⏭️  Skipped: {skipped} (already have good data)")
        print(f"❌ Filtered out: {filtered_out} (didn't meet criteria)")

        # Show final stats
        total = session.query(Whale).count()
        mega = session.query(Whale).filter(Whale.tier == 'MEGA').count()
        high = session.query(Whale).filter(Whale.tier == 'HIGH').count()
        medium = session.query(Whale).filter(Whale.tier == 'MEDIUM').count()

        high_quality = session.query(Whale).filter(
            Whale.total_volume >= 100000,
            Whale.win_rate >= 55,
            Whale.total_trades >= 200,
            Whale.sharpe_ratio >= 2.0
        ).count()

        print(f"\n" + "="*80)
        print("✅ FINAL DATABASE STATUS")
        print("="*80)
        print(f"Total whales: {total}")
        print(f"  MEGA tier: {mega}")
        print(f"  HIGH tier: {high}")
        print(f"  MEDIUM tier: {medium}")
        print(f"\n🎯 Meeting ALL CRITERIA: {high_quality}")
        print(f"\n🌐 Dashboard: http://localhost:8000/dashboard")

        return added, high_quality


if __name__ == "__main__":
    added, qualified = import_extended_whales()
    print(f"\n✅ Import complete!")
    print(f"   Added {added} additional whales")
    print(f"   {qualified} total whales meet ALL criteria")
