"""
Layer 0 finale — print Polymarket and CME-implied probabilities side by side.

Polymarket contract : "Will no Fed rate cuts happen in 2026?"
  → P(any cut in 2026) = 1 - P(YES on that contract)

CME FedWatch proxy  : P(25 bp cut at next FOMC meeting)
  → derived from 30-day Fed Funds Futures via the FedWatch formula

These measure different horizons (full year vs. one meeting), so the CME
number will always be smaller; the gap shows how each crowd weighs the risk.
"""

from datetime import date, datetime, timezone

import pandas as pd

from layer0_data import extract_probability, fetch_fed_markets
from layer0_fedwatch import (
    cut_probability,
    get_current_rate,
    get_futures_implied_rate,
    next_fomc_after,
    zq_ticker,
)

W = 62  # table width


def rule(char="-"):
    return char * W


def row(label, detail, value, flag=""):
    return f"  {label:<18}  {detail:<28}  {value:>8}  {flag}"


def fetch_polymarket() -> tuple[str, float]:
    """Return (question, P(any cut in 2026)) from the highest-volume no-cut contract."""
    markets = fetch_fed_markets()
    no_cut = [m for m in markets if "no fed rate cut" in m.get("question", "").lower()]
    if not no_cut:
        raise RuntimeError("Could not find 'no Fed rate cuts' contract on Polymarket.")
    # Pick the 2026 contract (fullest year, highest volume)
    target = max(no_cut, key=lambda m: float(m.get("volume", 0)))
    p_no_cut = extract_probability(target)
    p_any_cut = 1.0 - p_no_cut
    return target["question"], p_any_cut


def fetch_cme(today: date) -> tuple[str, float, float, float]:
    """Return (ticker, r_current, r_implied, P(cut)) for the next FOMC meeting."""
    meeting = next_fomc_after(today)
    r_current = get_current_rate()
    r_implied = get_futures_implied_rate(meeting.year, meeting.month)
    prob = cut_probability(meeting, r_current)
    ticker = zq_ticker(meeting.year, meeting.month)
    return meeting, ticker, r_current, r_implied, prob


HISTORY_FILE = "layer0_history.csv"
HISTORY_COLS = ["timestamp", "polymarket_probability", "cme_probability"]


def log_history(ts: datetime, poly_prob: float, cme_prob: float) -> None:
    """Append one row to layer0_history.csv, creating the file with headers if absent."""
    import os
    new_row = pd.DataFrame(
        [{"timestamp": ts.isoformat(), "polymarket_probability": poly_prob, "cme_probability": cme_prob}]
    )
    write_header = not os.path.exists(HISTORY_FILE)
    new_row.to_csv(HISTORY_FILE, mode="a", index=False, header=write_header)


def main():
    today = date.today()

    print(f"\nFetching Polymarket data...")
    poly_question, poly_prob = fetch_polymarket()

    print(f"Fetching CME futures data...")
    meeting, ticker, r_current, r_implied, cme_prob = fetch_cme(today)

    gap = poly_prob - cme_prob
    lean = "Polymarket more dovish" if gap > 0 else "CME more dovish"

    # ── Print table ───────────────────────────────────────────────────────────
    print()
    print(rule("="))
    print(f"  LAYER 0 — CROSS-MARKET PROBABILITY COMPARISON")
    print(f"  {today}  |  Event: Fed rate cuts in 2026")
    print(rule("="))
    print(f"  {'Source':<18}  {'Contract / Instrument':<28}  {'P(cut)':>8}")
    print(rule())
    print(row("Polymarket", "No cuts in 2026 (inverted)", f"{poly_prob:.1%}"))
    print(row("CME FedWatch", f"Meeting {meeting}  ({ticker})", f"{cme_prob:.1%}"))
    print(rule())
    print()
    print(f"  Rate context   :  proxy rate {r_current:.3f}%  →  futures imply {r_implied:.3f}%")
    print(f"  Gap (Poly−CME) :  {gap:+.1%}  ({lean})")
    print()
    print(f"  Note: horizons differ. Polymarket = any cut across all 8 meetings in 2026.")
    print(f"        CME number = probability of a cut at this single meeting only.")
    print(rule("="))

    # ── Save snapshot ─────────────────────────────────────────────────────────
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": today.isoformat(),
        "polymarket_question": poly_question,
        "polymarket_p_any_cut": poly_prob,
        "cme_meeting": meeting.isoformat(),
        "cme_ticker": ticker,
        "cme_rate_proxy_pct": r_current,
        "cme_futures_implied_pct": r_implied,
        "cme_p_cut_next_meeting": cme_prob,
        "gap_poly_minus_cme": gap,
    }
    pd.DataFrame([record]).to_csv("layer0_snapshot.csv", index=False)
    print(f"  Snapshot saved to layer0_snapshot.csv")

    log_history(datetime.now(timezone.utc), poly_prob, cme_prob)
    print(f"  Row appended to layer0_history.csv\n")


if __name__ == "__main__":
    main()
