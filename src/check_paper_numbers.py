"""
Check every number asserted in the manuscript prose against the data.

Tables and figures in the paper are generated, so they cannot drift. The prose
is written by hand, and it drifted once already: rebuilding the dataset moved
the decade figures by a tenth of a point and the paper went on quoting the old
ones. Nothing in the build catches that, because LaTeX is perfectly happy to
typeset a stale number.

This script recomputes each claim from data/gem_dataset.csv and compares it
with what the manuscript says. Every entry below names the section it
appears in, so a failure points straight at the sentence to fix.

Run:  python src/check_paper_numbers.py     (exit code 1 on any mismatch)
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gem_backtest import (  # noqa: E402
    MONTHS, absolute_only, drawdown_series, gem_rule, newey_west_se, ols_nw,
    relative_only, run_rule, static_mix,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_CSV = os.path.join(ROOT, "data", "gem_dataset.csv")


def cagr(r):
    return (1 + r).prod() ** (MONTHS / len(r)) - 1


def vol(r):
    return r.std(ddof=1) * np.sqrt(MONTHS)


def sharpe(r, rf):
    excess = (r - rf.reindex(r.index)).dropna()
    return (excess.mean() * MONTHS) / vol(r)


def main():
    px = pd.read_csv(DATA_CSV, index_col="Date", parse_dates=True)
    gem, held = run_rule(px, gem_rule)
    abs_only, _ = run_rule(px, absolute_only)
    rel_only, _ = run_rule(px, relative_only)

    rets = px.pct_change().reindex(gem.index)
    rf, spx = rets["TBILL"], rets["US"]
    shares = held.value_counts(normalize=True)
    weights = {a: float(shares.get(a, 0.0)) for a in ("US", "EXUS", "BOND")}
    mix = static_mix(px, weights, index=gem.index)
    reg = ols_nw((gem - rf).values, (spx - rf).values)

    early = slice("1971", "2009")
    late = slice("2010", "2026")
    late_held = held.loc[late]
    late_cost = (spx.loc[late] - gem.loc[late])

    annual = pd.DataFrame({
        "gem": (1 + gem).groupby(gem.index.year).prod() - 1,
        "spx": (1 + spx).groupby(spx.index.year).prod() - 1,
    })
    down = annual[annual["spx"] < 0]

    window = 36
    roll = ((1 + gem).rolling(window).apply(np.prod, raw=True)
            - (1 + spx).rolling(window).apply(np.prod, raw=True)).dropna()

    dd = drawdown_series(gem)
    trough = dd.idxmin()
    peak = (1 + gem).cumprod().loc[:trough].idxmax()
    episode = held.loc[peak:trough]

    # (section, claim as printed, computed value, tolerance)
    checks = [
        ("Abstract/4.1", "GEM CAGR 15.18%", cagr(gem) * 100, 15.18, 0.01),
        ("Abstract/4.1", "S&P CAGR 11.27%", cagr(spx) * 100, 11.27, 0.01),
        ("4.1", "GEM volatility 12.91%", vol(gem) * 100, 12.91, 0.01),
        ("4.1", "S&P volatility 15.20%", vol(spx) * 100, 15.20, 0.01),
        ("Abstract/4.1", "GEM max drawdown 21.7%", -dd.min() * 100, 21.7, 0.05),
        ("Abstract/4.1", "S&P max drawdown 50.9%",
         -drawdown_series(spx).min() * 100, 50.9, 0.06),
        ("Abstract/Intro", "GEM Sharpe 0.83", sharpe(gem, rf), 0.83, 0.005),
        ("Abstract/Intro", "S&P Sharpe 0.50", sharpe(spx, rf), 0.50, 0.005),
        ("Abstract/4.1", "GEM terminal $258,057",
         100 * (1 + gem).prod(), 258057, 100),
        ("Abstract/4.1", "S&P terminal $37,908",
         100 * (1 + spx).prod(), 37908, 50),
        ("Abstract/4.1", "1.5 trades a year",
         (held != held.shift()).sum() / (len(held) / MONTHS), 1.49, 0.05),
        ("4.1", "667 observations", len(gem), 667, 0),
        ("4.1", "GEM worst month -14.5%", gem.min() * 100, -14.50, 0.05),
        ("4.1", "S&P worst month -21.5%", spx.min() * 100, -21.54, 0.05),
        ("4.1", "GEM 5th pct month -4.8%", gem.quantile(0.05) * 100, -4.77, 0.05),
        ("4.1", "S&P 5th pct month -6.4%", spx.quantile(0.05) * 100, -6.43, 0.05),
        ("4.1", "GEM positive months 67%", (gem > 0).mean() * 100, 67.0, 0.5),
        ("4.1", "S&P positive months 63%", (spx > 0).mean() * 100, 63.4, 0.5),

        ("4.2", "absolute only CAGR 12.04%", cagr(abs_only) * 100, 12.04, 0.01),
        ("4.2", "relative only CAGR 13.31%", cagr(rel_only) * 100, 13.31, 0.01),
        ("4.2", "absolute only drawdown 29.6%",
         -drawdown_series(abs_only).min() * 100, 29.58, 0.05),
        ("4.2", "relative only drawdown 55%",
         -drawdown_series(rel_only).min() * 100, 54.61, 0.05),
        ("4.2", "absolute only volatility 12.3%", vol(abs_only) * 100, 12.30, 0.01),
        ("4.2", "relative only volatility 15.96%", vol(rel_only) * 100, 15.96, 0.01),
        ("4.2", "absolute only Sharpe 0.64", sharpe(abs_only, rf), 0.64, 0.005),
        ("4.2", "relative only Sharpe 0.60", sharpe(rel_only, rf), 0.60, 0.005),
        ("Abstract/4.2", "absolute adds 77 bps",
         (cagr(abs_only) - cagr(spx)) * 10000, 77, 1),
        ("Abstract/4.2", "relative adds 203 bps",
         (cagr(rel_only) - cagr(spx)) * 10000, 203, 1),
        ("Abstract/4.2", "combined adds 391 bps",
         (cagr(gem) - cagr(spx)) * 10000, 391, 1),

        ("Abstract/4.3", "static mix CAGR 10.03%", cagr(mix) * 100, 10.03, 0.01),
        ("4.3", "static mix drawdown 41.9%",
         -drawdown_series(mix).min() * 100, 41.94, 0.05),
        ("4.3", "allocation effect -124 bps",
         (cagr(mix) - cagr(spx)) * 10000, -124, 1),
        ("4.3", "timing effect 515 bps",
         (cagr(gem) - cagr(mix)) * 10000, 515, 1),
        ("4.3", "weights 46/28/25 US", weights["US"] * 100, 46, 0.5),
        ("4.3", "weights 46/28/25 ex-US", weights["EXUS"] * 100, 28, 0.5),
        ("4.3", "weights 46/28/25 bonds", weights["BOND"] * 100, 25, 0.5),

        ("Intro/4.4", "alpha 6.61%", reg["alpha_ann"] * 100, 6.61, 0.02),
        ("Intro/4.4", "alpha t 4.31", reg["alpha_t"], 4.31, 0.02),
        ("4.4", "beta 0.57", reg["beta"], 0.57, 0.005),
        ("4.4", "R-squared 0.45", reg["r2"], 0.45, 0.005),

        ("4.5", "11 down years for the S&P", len(down), 11, 0),
        ("4.5", "GEM -0.4% in those years", down["gem"].mean() * 100, -0.4, 0.1),
        ("4.5", "S&P -14.4% in those years", down["spx"].mean() * 100, -14.4, 0.1),
        ("4.5", "GEM ahead in 59% of 3y windows", (roll > 0).mean() * 100, 59, 1),

        ("6.1", "1971-2009 GEM 17.71%", cagr(gem.loc[early]) * 100, 17.71, 0.02),
        ("6.1", "1971-2009 S&P 10.03%", cagr(spx.loc[early]) * 100, 10.03, 0.02),
        ("6.1", "2010-2026 GEM 9.45%", cagr(gem.loc[late]) * 100, 9.45, 0.02),
        ("6.1", "2010-2026 S&P 14.26%", cagr(spx.loc[late]) * 100, 14.26, 0.02),
        ("6.1", "shortfall 4.8 points",
         (cagr(spx.loc[late]) - cagr(gem.loc[late])) * 100, 4.8, 0.05),
        ("6.1", "out of US equity 28% of months since 2010",
         (late_held != "US").mean() * 100, 28, 0.5),
        ("6.1", "21 bond months since 2010", (late_held == "BOND").sum(), 21, 0),
        ("6.1", "35 non-US months since 2010", (late_held == "EXUS").sum(), 35, 0),
        ("6.1", "S&P +34.1%/yr during those bond months",
         spx.loc[late][late_held == "BOND"].mean() * 1200, 34.1, 0.2),
        ("6.1", "S&P +5.3%/yr during 1971-2009 bond months",
         spx.loc[early][held.loc[early] == "BOND"].mean() * 1200, 5.3, 0.2),
        ("6.1", "149 defensive months in 1971-2009",
         (held.loc[early] == "BOND").sum(), 149, 0),
        ("6.1", "three quarters of the shortfall from bonds",
         late_cost[late_held == "BOND"].sum() / late_cost.sum() * 100, 77, 2),

        ("6.2", "worst drawdown trough October 2023",
         trough.year * 100 + trough.month, 202310, 0),
        ("6.2", "worst drawdown peak December 2021",
         peak.year * 100 + peak.month, 202112, 0),
        ("6.2", "13 of 23 months in bonds during it",
         (episode == "BOND").sum(), 13, 0),
        ("6.2", "7 of 12 months in bonds in 2022",
         (held.loc["2022"] == "BOND").sum(), 7, 0),
        ("6.2", "GEM -16.9% in 2022",
         ((1 + gem.loc["2022"]).prod() - 1) * 100, -16.9, 0.1),
        ("6.2", "bonds -13.0% in 2022",
         ((1 + rets["BOND"].loc["2022"]).prod() - 1) * 100, -13.0, 0.1),
        ("6.2", "S&P -18.1% in 2022",
         ((1 + spx.loc["2022"]).prod() - 1) * 100, -18.1, 0.1),
    ]

    y25 = held.loc["2025"]
    prior = held.loc[:"2024-12-31"].iloc[-1]
    seq = pd.concat([pd.Series([prior], index=[pd.Timestamp("2024-12-31")]), y25])
    mom = px / px.shift(12) - 1
    switch_months = seq[seq != seq.shift()].index[1:]
    gaps = [abs(mom.iloc[mom.index.get_loc(d) - 1]["US"]
                - mom.iloc[mom.index.get_loc(d) - 1]["EXUS"]) * 100
            for d in switch_months]
    checks += [
        ("6.1", "GEM 16.30% in 2025",
         ((1 + gem.loc["2025"]).prod() - 1) * 100, 16.30, 0.02),
        ("6.1", "US equity 17.88% in 2025",
         ((1 + spx.loc["2025"]).prod() - 1) * 100, 17.88, 0.02),
        ("6.1", "non-US equity 32.67% in 2025",
         ((1 + rets["EXUS"].loc["2025"]).prod() - 1) * 100, 32.67, 0.02),
        ("6.1", "five switches in 2025", len(switch_months), 5, 0),
        ("6.1", "four of five switches inside 1.1 points",
         sum(1 for g in gaps if g <= 1.1), 4, 0),
    ]

    bear = [("1973-01", "1975-06", 83), ("2000-06", "2003-06", 84),
            ("2007-06", "2009-12", 68)]
    for lo, hi, expected in bear:
        window = held.loc[lo:hi]
        checks.append(("4.3", "in bonds %d%% of %s--%s" % (expected, lo, hi),
                       (window == "BOND").mean() * 100, expected, 0.6))
    in_bear = sum((held.loc[lo:hi] == "BOND").sum() for lo, hi, _ in bear)
    checks.append(("4.3", "those windows are 45% of all bond months",
                   in_bear / (held == "BOND").sum() * 100, 45, 1))

    lookback = {}
    for lb in (3, 6, 9, 12, 15, 18, 21, 24):
        r, _ = run_rule(px, gem_rule, lookback=lb)
        lookback[lb] = cagr(r) * 100
    checks += [
        ("5.1", "lookback CAGR minimum 12.21%", min(lookback.values()), 12.21, 0.3),
        ("5.1", "lookback CAGR maximum 15.18%", max(lookback.values()), 15.18, 0.01),
    ]
    for bps, expected in ((25, 14.76), (100, 13.51)):
        r, _ = run_rule(px, gem_rule, cost_bps=bps)
        checks.append(("5.2", "CAGR at %d bps cost" % bps,
                       cagr(r) * 100, expected, 0.02))

    print("Checking %d numbers asserted in the manuscript\n" % len(checks))
    failures = []
    for section, claim, computed, stated, tol in checks:
        ok = abs(float(computed) - float(stated)) <= tol
        if not ok:
            failures.append((section, claim, computed, stated))
        print("  %-4s %-8s %-46s paper %10s   data %10.2f"
              % ("OK" if ok else "FAIL", section, claim, stated, computed))

    print()
    if failures:
        print("%d MISMATCH(ES) -- the manuscript quotes a stale figure:\n"
              % len(failures))
        for section, claim, computed, stated in failures:
            print("  section %s: %s" % (section, claim))
            print("      paper says %s, data says %.4f" % (stated, computed))
        raise SystemExit(1)
    print("All figures in the prose match the data.")


if __name__ == "__main__":
    main()
