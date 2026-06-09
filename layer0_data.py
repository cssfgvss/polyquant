"""
Layer 0 — Hello Data
Goal: fetch the current implied probability for a Fed rate-decision contract
from Polymarket's Gamma API, print it, and save it to a CSV file.
"""

import requests   # the library that lets Python "talk to the internet" via HTTP
import pandas as pd  # the library for working with tabular data (like spreadsheets)
from datetime import datetime  # standard library tool for timestamps


# ── 1. PICK THE CONTRACT ──────────────────────────────────────────────────────
# Polymarket's Gamma API lets us search for markets by keyword.
# We search for "fed" to find rate-decision contracts.
# The base URL is the address of the API server we are calling.
GAMMA_API = "https://gamma-api.polymarket.com"


def fetch_fed_markets():
    """
    Hit the Gamma API and return a list of markets whose title mentions 'fed'.
    Each market is a Python dict (key→value pairs, like a labelled box of data).

    The API returns 100 results per page (one "page" = one batch).
    We scan multiple pages because Fed contracts don't appear in the first batch.
    """

    # ── 2. BUILD THE REQUEST ──────────────────────────────────────────────────
    # An API "endpoint" is a specific URL path that does one job.
    # /markets  →  gives us a list of all markets on Polymarket.
    url = f"{GAMMA_API}/markets"

    keywords = ["fed", "fomc", "federal reserve", "rate cut"]
    found = []

    # ── 3. PAGINATE THROUGH RESULTS ───────────────────────────────────────────
    # The server can't send thousands of markets in one go, so we use "offset"
    # to request successive pages: offset=0 → first 100, offset=100 → next 100…
    # We stop after 4 pages (400 markets) so the script finishes quickly.
    for page in range(4):
        offset = page * 100
        params = {
            "limit": 100,       # 100 results per page
            "offset": offset,   # skip the first `offset` results
            "active": "true",   # only markets open for trading
            "closed": "false",  # exclude markets that have already resolved
        }

        # ── 4. MAKE THE HTTP GET REQUEST ──────────────────────────────────────
        # requests.get(url, params=...) sends an HTTP GET request to the server
        # (like typing a URL into a browser, but from Python).
        print(f"  Fetching page {page + 1} (offset {offset})…")
        response = requests.get(url, params=params, timeout=10)

        # raise_for_status() will crash with a clear error message if the server
        # returned an error code (like 404 Not Found or 500 Server Error).
        response.raise_for_status()

        # ── 5. PARSE THE JSON RESPONSE ────────────────────────────────────────
        # JSON (JavaScript Object Notation) is the standard format APIs use to
        # send data — it looks like Python dicts and lists.
        # .json() converts the raw text the server sent into a real Python object.
        markets = response.json()

        if not markets:          # empty page means we've run out of results
            break

        # Filter this page for Fed-related markets
        for market in markets:
            question = market.get("question", "").lower()
            slug = market.get("slug", "").lower()
            if any(k in question or k in slug for k in keywords):
                found.append(market)

    return found


def find_fed_rate_contract(markets):
    """
    Filter the list of markets down to ones about Fed rate decisions.
    Returns a list of matching market dicts.
    """
    fed_markets = []

    for market in markets:
        # Each market dict has a "question" key with the contract's title.
        # We do a case-insensitive search for "fed" or "rate" or "fomc".
        question = market.get("question", "").lower()
        if any(keyword in question for keyword in ["fed", "rate cut", "fomc", "federal reserve"]):
            fed_markets.append(market)

    return fed_markets


def extract_probability(market):
    """
    Pull the current mid-market probability from a single market dict.

    On Polymarket, each market has an "outcomePrices" field.
    For a binary (YES/NO) contract, the price of the YES outcome IS the
    market-implied probability that the event will happen.
    Prices live between 0 and 1 (or sometimes 0–100 cents — we normalise).

    This is the core number we care about: P(event) as the crowd sees it.
    """
    # outcomePrices is stored as a JSON string like '["0.73", "0.27"]'
    # so we parse it. outcome 0 = YES, outcome 1 = NO.
    import json
    raw = market.get("outcomePrices", "[]")
    try:
        prices = json.loads(raw)
        yes_price = float(prices[0])
        # Polymarket prices are already in [0, 1]; no scaling needed.
        return yes_price
    except (IndexError, ValueError, TypeError):
        return None


def main():
    # ── 5. FETCH AND FILTER ───────────────────────────────────────────────────
    print("Contacting Polymarket Gamma API…")
    # fetch_fed_markets already filters for Fed keywords internally
    fed_markets = fetch_fed_markets()
    print(f"Fed-related markets found: {len(fed_markets)}\n")

    if not fed_markets:
        print("No Fed rate markets found. Try adding more keywords to the list above.")
        return

    # Only show contracts that mention "rate cut" or "rate cuts" — the most
    # directly relevant to the CME FedWatch comparison we'll add in Layer 0b.
    rate_cut_markets = [
        m for m in fed_markets
        if "rate cut" in m.get("question", "").lower()
    ]
    display_markets = rate_cut_markets if rate_cut_markets else fed_markets

    # ── 6. PRINT THE RESULTS ──────────────────────────────────────────────────
    print("=" * 60)
    print("FED RATE DECISION CONTRACTS ON POLYMARKET")
    print("=" * 60)

    rows = []  # we will collect data here to save as a CSV

    for market in display_markets:
        question = market.get("question", "N/A")
        prob = extract_probability(market)
        volume = float(market.get("volume", 0))

        if prob is None:
            continue  # skip markets with no price data

        print(f"\nContract : {question}")
        print(f"  YES probability : {prob:.1%}")   # .1% means "as a percentage, 1 decimal place"
        print(f"  Total volume    : ${volume:,.0f}")

        rows.append({
            "timestamp": datetime.utcnow().isoformat(),
            "question": question,
            "yes_probability": prob,
            "volume_usd": volume,
        })

    # ── 7. SAVE TO CSV ────────────────────────────────────────────────────────
    # CSV (Comma-Separated Values) is a plain-text format every tool can read.
    # pandas DataFrame = a table of data, like a Python spreadsheet.
    if rows:
        df = pd.DataFrame(rows)
        df.to_csv("layer0_polymarket.csv", index=False)
        # index=False means don't write row numbers (0, 1, 2…) into the file
        print(f"\nSaved {len(rows)} rows to layer0_polymarket.csv")
    else:
        print("No data to save.")


# ── 8. ENTRY POINT ────────────────────────────────────────────────────────────
# This is a Python convention. When Python runs this file directly,
# __name__ equals "__main__". The block below only runs in that case —
# it won't run if another file imports this one as a module.
if __name__ == "__main__":
    main()
