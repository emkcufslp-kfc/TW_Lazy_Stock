# -*- coding: utf-8 -*-
"""Quick test: verify the fixed Goodinfo scraping works for 2330."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])

from data_sources import fetch_dividend_from_goodinfo

# Test with TSMC (2330)
print("Testing 2330 (台積電)...")
df = fetch_dividend_from_goodinfo("2330")
if df.empty:
    print("FAILED: No data returned")
else:
    print(f"SUCCESS: {len(df)} years of dividend data")
    print(df.to_string(index=False))
    
print()

# Test with 2412 (中華電)
print("Testing 2412 (中華電)...")
import time
time.sleep(2)
df2 = fetch_dividend_from_goodinfo("2412")
if df2.empty:
    print("FAILED: No data returned")
else:
    print(f"SUCCESS: {len(df2)} years of dividend data")
    print(df2.to_string(index=False))
