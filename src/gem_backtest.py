"""
Global Equities Momentum (GEM) / Dual Momentum backtest.

Strategy, as specified by Antonacci
-----------------------------------
Once a month, using only information available at that month-end:

    if  12m return(US equity)  >  12m return(T-bills):        # absolute momentum
            hold whichever of US / ex-US equity has the
            higher 12m return                                 # relative momentum
    else:
            hold aggregate bonds

The position taken at the close of month t earns the return of month t+1. No
information from month t+1 enters the decision, so the backtest is free of
look-ahead by construction.

Run:  python src/gem_backtest.py
Out:  output/figures/*.png, output/tables/*.csv
"""

from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")

# The Windows console defaults to cp1252 and mangles the accented output below.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_CSV = os.path.join(ROOT, "data", "gem_dataset.csv")
FIG_DIR = os.path.join(ROOT, "output", "figures")
TAB_DIR = os.path.join(ROOT, "output", "tables")

LOOKBACK = 12          # months of trailing return used by both momentum tests
MONTHS = 12            # periods per year
COST_BPS = 0.0         # round-trip cost applied on every allocation change

# Muted, print-friendly palette; distinguishable in greyscale.
COLORS = {
    "GEM": "#1a1a1a",
    "S&P 500": "#c0392b",
    "Ex-US equity": "#2874a6",
    "US bonds": "#7d8c8c",
    "T-bills": "#b8b8b8",
    "60/40": "#8e6c1f",
    "Absolute only": "#5b2c6f",
    "Relative only": "#1e8449",
}

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 200,
    "font.size": 9,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "figure.autolayout": True,
})


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------

def newey_west_se(x, lags=None):
    """Newey-West standard error of the mean of ``x``.

    Monthly strategy returns are mildly autocorrelated -- a momentum rule holds
    the same asset for months at a time -- so a plain t-test overstates
    significance. Bartlett kernel, Newey-West's own 4*(T/100)^(2/9) bandwidth.
    """
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    T = len(x)
    if T < 3:
        return np.nan
    if lags is None:
        lags = int(np.floor(4 * (T / 100.0) ** (2.0 / 9.0)))
    e = x - x.mean()
    s = float(e @ e) / T                                   # gamma_0
    for j in range(1, lags + 1):
        gamma = float(e[j:] @ e[:-j]) / T
        s += 2.0 * (1.0 - j / (lags + 1.0)) * gamma
    return np.sqrt(max(s, 0.0) / T)


def ols_nw(y, x, lags=None):
    """Regress y on [1, x] with Newey-West standard errors.

    Returns annualised alpha, beta, R^2 and the two Newey-West t-statistics.
    """
    y = np.asarray(y, dtype=float)
    X = np.column_stack([np.ones(len(y)), np.asarray(x, dtype=float)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    T, k = X.shape
    if lags is None:
        lags = int(np.floor(4 * (T / 100.0) ** (2.0 / 9.0)))

    XtX_inv = np.linalg.inv(X.T @ X)
    S = (X * resid[:, None]).T @ (X * resid[:, None])
    for j in range(1, lags + 1):
        A = (X[j:] * resid[j:, None]).T @ (X[:-j] * resid[:-j, None])
        S += (1.0 - j / (lags + 1.0)) * (A + A.T)
    cov = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.diag(cov))

    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return {
        "alpha_ann": (1 + beta[0]) ** MONTHS - 1,
        "alpha_t": beta[0] / se[0],
        "beta": beta[1],
        "beta_t": beta[1] / se[1],
        "r2": 1 - ss_res / ss_tot,
        "n": T,
    }


def performance(returns, rf=None, name=""):
    """Full statistics block for one monthly return series."""
    r = pd.Series(returns).dropna()
    n = len(r)
    equity = (1 + r).cumprod()
    drawdown = equity / equity.cummax() - 1

    cagr = equity.iloc[-1] ** (MONTHS / n) - 1
    vol = r.std(ddof=1) * np.sqrt(MONTHS)
    downside = r[r < 0].std(ddof=1) * np.sqrt(MONTHS)
    mdd = drawdown.min()

    excess = r if rf is None else (r - pd.Series(rf).reindex(r.index)).dropna()
    se = newey_west_se(excess)

    stats = {
        "CAGR": cagr,
        "Volatility": vol,
        "Sharpe": (excess.mean() * MONTHS) / vol if vol else np.nan,
        "Sortino": (excess.mean() * MONTHS) / downside if downside else np.nan,
        "Max drawdown": mdd,
        "Calmar (MAR)": cagr / abs(mdd) if mdd else np.nan,
        "Best month": r.max(),
        "Worst month": r.min(),
        "Positive months": (r > 0).mean(),
        "Skewness": r.skew(),
        "Excess kurtosis": r.kurtosis(),
        "Monthly VaR 5%": r.quantile(0.05),
        "Excess return t-stat (NW)": excess.mean() / se if se else np.nan,
        "Months": n,
    }
    return pd.Series(stats, name=name)


def drawdown_series(returns):
    equity = (1 + pd.Series(returns).dropna()).cumprod()
    return equity / equity.cummax() - 1


# --------------------------------------------------------------------------
# strategies
# --------------------------------------------------------------------------

def signals(prices, lookback=LOOKBACK):
    """Trailing total return over ``lookback`` months, per asset."""
    return prices / prices.shift(lookback) - 1


def run_rule(prices, decide, lookback=LOOKBACK, cost_bps=COST_BPS):
    """Backtest an allocation rule.

    ``decide`` maps a row of trailing momentum values to one column name. It is
    evaluated on month t-1 and the resulting position earns the month-t return,
    which is what makes the backtest implementable.
    """
    mom = signals(prices, lookback)
    rets = prices.pct_change()

    dates, held, out = [], [], []
    previous = None
    for i in range(1, len(prices)):
        row = mom.iloc[i - 1]
        if row.isna().any():
            continue
        pick = decide(row)
        r = rets.iloc[i][pick]
        if cost_bps and previous is not None and pick != previous:
            r -= cost_bps / 10000.0
        dates.append(prices.index[i])
        held.append(pick)
        out.append(r)
        previous = pick

    return pd.Series(out, index=dates), pd.Series(held, index=dates)


def static_mix(prices, weights, index=None):
    """Fixed-weight portfolio, rebalanced every month.

    The point of this benchmark is to hold GEM's *average* asset mix while doing
    none of its timing. Whatever it earns is the part of GEM's return that came
    from simply being diversified across those three assets; the remainder is
    what the monthly switching actually added.
    """
    rets = prices.pct_change()
    if index is not None:
        rets = rets.reindex(index)
    total = float(sum(weights.values()))
    mix = sum(rets[asset] * (w / total) for asset, w in weights.items())
    return mix.dropna()


def gem_rule(row):
    """Dual momentum: absolute filter, then relative selection."""
    if row["US"] > row["TBILL"]:
        return "US" if row["US"] >= row["EXUS"] else "EXUS"
    return "BOND"


def absolute_only(row):
    """US equity when it beats T-bills, bonds otherwise. No ex-US leg."""
    return "US" if row["US"] > row["TBILL"] else "BOND"


def relative_only(row):
    """Best of US / ex-US at all times. No escape to bonds."""
    return "US" if row["US"] >= row["EXUS"] else "EXUS"


# --------------------------------------------------------------------------
# figures
# --------------------------------------------------------------------------

def fig_equity(curves, path):
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for name, r in curves.items():
        equity = 100 * (1 + r).cumprod()
        emphasis = name == "GEM" or name.startswith("Mix statique")
        ax.plot(equity.index, equity.values, label=name,
                color=COLORS.get(name), linewidth=1.9 if name == "GEM"
                else (1.5 if emphasis else 1.0),
                zorder=3 if emphasis else 2)
    ax.set_yscale("log")
    ax.set_ylabel("Croissance de 100 USD (échelle log)")
    ax.set_xlabel("")
    ax.set_title("Global Equities Momentum vs buy-and-hold", loc="left",
                 fontsize=11, fontweight="bold")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda v, _: "{:,.0f}".format(v)))
    ax.legend(loc="upper left", ncol=2)
    first, last = next(iter(curves.values())).index[[0, -1]]
    ax.annotate("%s – %s" % (first.strftime("%b %Y"), last.strftime("%b %Y")),
                xy=(0.995, 0.02), xycoords="axes fraction", ha="right",
                fontsize=8, color="#666")
    fig.savefig(path)
    plt.close(fig)


def fig_drawdown(curves, path):
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for name, r in curves.items():
        dd = drawdown_series(r) * 100
        ax.plot(dd.index, dd.values, label=name, color=COLORS.get(name),
                linewidth=1.6 if name == "GEM" else 1.0)
        if name == "GEM":
            ax.fill_between(dd.index, dd.values, 0, color=COLORS[name], alpha=0.12)
    ax.set_ylabel("Drawdown (%)")
    ax.set_title("Pertes depuis le plus haut", loc="left", fontsize=11,
                 fontweight="bold")
    ax.legend(loc="lower left")
    fig.savefig(path)
    plt.close(fig)


def fig_allocation(held, path):
    """Which asset the rule holds, over time."""
    order = ["US", "EXUS", "BOND"]
    labels = {"US": "Actions US", "EXUS": "Actions hors US", "BOND": "Obligations"}
    shades = {"US": "#c0392b", "EXUS": "#2874a6", "BOND": "#7d8c8c"}

    fig, ax = plt.subplots(figsize=(9, 2.2))
    for level, key in enumerate(order):
        mask = (held == key).astype(float).values
        ax.fill_between(held.index, level, level + mask * 0.85,
                        step="pre", color=shades[key], linewidth=0)
    ax.set_yticks([i + 0.42 for i in range(len(order))])
    ax.set_yticklabels([labels[k] for k in order])
    ax.set_ylim(-0.1, len(order))
    ax.grid(axis="y", visible=False)
    ax.set_title("Allocation retenue par la règle", loc="left", fontsize=11,
                 fontweight="bold")
    fig.savefig(path)
    plt.close(fig)


def fig_rolling(gem, bench, path, window=36):
    diff = ((1 + gem).rolling(window).apply(np.prod, raw=True) ** (MONTHS / window)
            - (1 + bench).rolling(window).apply(np.prod, raw=True) ** (MONTHS / window))
    diff = diff.dropna() * 100

    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.fill_between(diff.index, diff.values, 0, where=diff.values >= 0,
                    color="#1e8449", alpha=0.35, interpolate=True)
    ax.fill_between(diff.index, diff.values, 0, where=diff.values < 0,
                    color="#c0392b", alpha=0.35, interpolate=True)
    ax.plot(diff.index, diff.values, color="#1a1a1a", linewidth=0.9)
    ax.set_ylabel("Écart annualisé (points)")
    ax.set_title("Surperformance glissante de GEM sur %d mois vs S&P 500" % window,
                 loc="left", fontsize=11, fontweight="bold")
    share = (diff > 0).mean() * 100
    ax.annotate("GEM devant sur %.0f %% des fenêtres" % share,
                xy=(0.995, 0.05), xycoords="axes fraction", ha="right",
                fontsize=8, color="#666")
    fig.savefig(path)
    plt.close(fig)


def fig_lookback(table, path):
    fig, ax1 = plt.subplots(figsize=(7.5, 3.6))
    ax2 = ax1.twinx()
    ax1.bar(table.index, table["CAGR"] * 100, color="#2874a6", alpha=0.75,
            width=0.6, label="CAGR")
    ax2.plot(table.index, table["Max drawdown"] * 100, color="#c0392b",
             marker="o", markersize=4, linewidth=1.4, label="Max drawdown")
    ax1.axvline(LOOKBACK, color="#1a1a1a", linestyle="--", linewidth=1.0)
    ax1.set_xlabel("Fenêtre de momentum (mois)")
    ax1.set_ylabel("CAGR (%)", color="#2874a6")
    ax2.set_ylabel("Max drawdown (%)", color="#c0392b")
    ax2.grid(False)
    ax1.set_title("Sensibilité à la fenêtre de momentum", loc="left",
                  fontsize=11, fontweight="bold")
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    if not os.path.exists(DATA_CSV):
        sys.exit("missing %s -- run python src/build_dataset.py first" % DATA_CSV)
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(TAB_DIR, exist_ok=True)

    prices = pd.read_csv(DATA_CSV, index_col="Date", parse_dates=True)
    print("Dataset : %s -> %s (%d months)\n"
          % (prices.index[0].date(), prices.index[-1].date(), len(prices)))

    # ---- strategies -----------------------------------------------------
    gem, held = run_rule(prices, gem_rule)
    abs_only, _ = run_rule(prices, absolute_only)
    rel_only, _ = run_rule(prices, relative_only)

    rets = prices.pct_change().reindex(gem.index)
    rf = rets["TBILL"]
    bench = rets["US"]
    sixty_forty = (0.6 * rets["US"] + 0.4 * rets["BOND"])

    # Static benchmark carrying GEM's own average allocation. Weights are read
    # off the backtest rather than hard-coded, so they stay correct if the rule,
    # the lookback or the sample ever changes.
    shares = held.value_counts(normalize=True)
    weights = {a: float(shares.get(a, 0.0)) for a in ("US", "EXUS", "BOND")}
    matched = static_mix(prices, weights, index=gem.index)
    matched_label = "Mix statique %d/%d/%d" % tuple(
        round(weights[a] * 100) for a in ("US", "EXUS", "BOND"))

    # Antonacci's own Global Asset Allocation benchmark, for comparability with
    # the published article.
    gaa = static_mix(prices, {"US": 0.45, "EXUS": 0.28, "BOND": 0.27},
                     index=gem.index)

    curves = {
        "GEM": gem,
        matched_label: matched,
        "S&P 500": bench,
        "Ex-US equity": rets["EXUS"],
        "US bonds": rets["BOND"],
        "60/40": sixty_forty,
    }
    COLORS[matched_label] = "#6c3483"

    # ---- table 1: headline stats ---------------------------------------
    stats = pd.concat([
        performance(gem, rf, "GEM"),
        performance(matched, rf, matched_label),
        performance(gaa, rf, "GAA 45/28/27"),
        performance(bench, rf, "S&P 500"),
        performance(rets["EXUS"], rf, "Actions hors US"),
        performance(rets["BOND"], rf, "Obligations US"),
        performance(sixty_forty, rf, "60/40"),
    ], axis=1)
    stats.to_csv(os.path.join(TAB_DIR, "01_performance.csv"))

    print("=" * 88)
    print("TABLE 1 — Performance, %s to %s"
          % (gem.index[0].strftime("%Y-%m"), gem.index[-1].strftime("%Y-%m")))
    print("=" * 88)
    print(_fmt(stats).to_string())

    # ---- table 2: Antonacci decomposition ------------------------------
    decomp = pd.concat([
        performance(bench, rf, "S&P 500 (référence)"),
        performance(abs_only, rf, "Momentum absolu seul"),
        performance(rel_only, rf, "Momentum relatif seul"),
        performance(gem, rf, "GEM (combiné)"),
    ], axis=1)
    spread = (decomp.loc["CAGR"] - decomp.loc["CAGR", "S&P 500 (référence)"]) * 10000
    decomp.loc["Écart vs S&P 500 (bps)"] = spread
    decomp.to_csv(os.path.join(TAB_DIR, "02_decomposition.csv"))

    print("\n" + "=" * 88)
    print("TABLE 2 — Décomposition d'Antonacci : d'où vient la surperformance ?")
    print("=" * 88)
    print(_fmt(decomp).to_string())
    print("\nLes deux briques prises isolément n'expliquent pas le total : "
          "%.0f + %.0f = %.0f bps contre %.0f bps combinés."
          % (spread["Momentum absolu seul"], spread["Momentum relatif seul"],
             spread["Momentum absolu seul"] + spread["Momentum relatif seul"],
             spread["GEM (combiné)"]))

    # ---- table 2b: allocation effect vs timing effect ------------------
    def cagr_of(r):
        return (1 + r).prod() ** (MONTHS / len(r)) - 1

    c_bench, c_mix, c_gem = cagr_of(bench), cagr_of(matched), cagr_of(gem)
    timing = pd.DataFrame({
        "CAGR": [c_bench, c_mix, c_gem],
        "Volatilité": [bench.std() * np.sqrt(MONTHS),
                       matched.std() * np.sqrt(MONTHS),
                       gem.std() * np.sqrt(MONTHS)],
        "Max drawdown": [drawdown_series(bench).min(),
                         drawdown_series(matched).min(),
                         drawdown_series(gem).min()],
        "Corrélation avec GEM": [bench.corr(gem), matched.corr(gem), 1.0],
    }, index=["S&P 500", matched_label, "GEM"])
    timing["Écart vs S&P 500 (bps)"] = (timing["CAGR"] - c_bench) * 10000
    timing.to_csv(os.path.join(TAB_DIR, "07_allocation_vs_timing.csv"))

    print("\n" + "=" * 88)
    print("TABLE 2b — Effet allocation contre effet timing")
    print("=" * 88)
    show = timing.copy()
    for c in ["CAGR", "Volatilité", "Max drawdown"]:
        show[c] = (show[c] * 100).round(2)
    print(show.round(2).to_string())
    print("\n  Le mix statique détient la MÊME allocation moyenne que GEM "
          "(%.0f%% US / %.0f%% hors US / %.0f%% obligations), figée, rebalancée "
          "chaque mois." % tuple(weights[a] * 100 for a in ("US", "EXUS", "BOND")))
    alloc_effect = (c_mix - c_bench) * 10000
    timing_effect = (c_gem - c_mix) * 10000
    print("  Effet allocation (détenir ce panier, sans timing) : %+.0f bps/an"
          % alloc_effect)
    print("  Effet timing (ce qu'ajoute la commutation)        : %+.0f bps/an"
          % timing_effect)
    if alloc_effect < 0:
        print("  -> Le panier d'actifs a COÛTÉ %.0f bps/an sur la période : hors US "
              "et obligations ont sous-performé les actions US." % -alloc_effect)
        print("     La totalité de la surperformance de GEM vient donc du timing, "
              "qui doit d'abord effacer ce handicap.")
    else:
        print("  -> %.0f%% de la surperformance vient du timing, %.0f%% du panier."
              % (timing_effect / (timing_effect + alloc_effect) * 100,
                 alloc_effect / (timing_effect + alloc_effect) * 100))
    dd_b, dd_m, dd_g = (drawdown_series(x).min()
                        for x in (bench, matched, gem))
    print("  Drawdown : %.1f pt de moins grâce à l'allocation, "
          "%.1f pt de plus grâce au timing (%.1f%% -> %.1f%% -> %.1f%%)."
          % ((dd_m - dd_b) * 100, (dd_g - dd_m) * 100,
             dd_b * 100, dd_m * 100, dd_g * 100))

    # ---- table 3: regression vs benchmark ------------------------------
    reg = ols_nw((gem - rf).values, (bench - rf).values)
    reg_tbl = pd.Series({
        "Alpha annualisé": reg["alpha_ann"],
        "Alpha t-stat (Newey-West)": reg["alpha_t"],
        "Bêta vs S&P 500": reg["beta"],
        "Bêta t-stat (Newey-West)": reg["beta_t"],
        "R²": reg["r2"],
        "Observations": reg["n"],
    }, name="GEM vs S&P 500 (excès de rendement)")
    reg_tbl.to_frame().to_csv(os.path.join(TAB_DIR, "03_regression.csv"))

    print("\n" + "=" * 88)
    print("TABLE 3 — Régression des excès de rendement GEM sur ceux du S&P 500")
    print("=" * 88)
    for k, v in reg_tbl.items():
        print("  %-32s %s" % (k, ("%.4f" % v) if abs(v) < 1000 else "%.0f" % v))

    # ---- table 4: by decade --------------------------------------------
    decade = []
    for label, sl in _decades(gem.index):
        g, b = gem[sl], bench[sl]
        if len(g) < 12:
            continue
        decade.append({
            "Décennie": label,
            "GEM CAGR": (1 + g).prod() ** (MONTHS / len(g)) - 1,
            "S&P 500 CAGR": (1 + b).prod() ** (MONTHS / len(b)) - 1,
            "Écart": ((1 + g).prod() ** (MONTHS / len(g))
                      - (1 + b).prod() ** (MONTHS / len(b))),
            "GEM MaxDD": drawdown_series(g).min(),
            "S&P 500 MaxDD": drawdown_series(b).min(),
        })
    dec = pd.DataFrame(decade).set_index("Décennie")
    dec.to_csv(os.path.join(TAB_DIR, "04_decades.csv"))

    print("\n" + "=" * 88)
    print("TABLE 4 — Par décennie")
    print("=" * 88)
    print((dec * 100).round(2).to_string())

    # ---- table 5: robustness to the lookback ---------------------------
    rows = {}
    for lb in range(3, 25):
        r, h = run_rule(prices, gem_rule, lookback=lb)
        s = performance(r, rf.reindex(r.index))
        s["Trades/an"] = (h != h.shift()).sum() / (len(h) / MONTHS)
        rows[lb] = s
    look = pd.DataFrame(rows).T
    look.index.name = "Lookback (mois)"
    look.to_csv(os.path.join(TAB_DIR, "05_lookback_sensitivity.csv"))

    print("\n" + "=" * 88)
    print("TABLE 5 — Sensibilité à la fenêtre de momentum")
    print("=" * 88)
    show = look[["CAGR", "Volatility", "Sharpe", "Max drawdown", "Trades/an"]].copy()
    for c in ["CAGR", "Volatility", "Max drawdown"]:
        show[c] = (show[c] * 100).round(2)
    print(show.round(2).to_string())
    print("\n  CAGR de %.2f%% à %.2f%% selon la fenêtre — "
          "amplitude %.2f pt. La fenêtre de 12 mois retenue par Antonacci "
          "donne %.2f%%."
          % (look["CAGR"].min() * 100, look["CAGR"].max() * 100,
             (look["CAGR"].max() - look["CAGR"].min()) * 100,
             look.loc[LOOKBACK, "CAGR"] * 100))

    # ---- table 6: transaction costs ------------------------------------
    cost_rows = {}
    for bps in [0, 5, 10, 25, 50, 100]:
        r, h = run_rule(prices, gem_rule, cost_bps=bps)
        cost_rows["%d bps" % bps] = performance(r, rf.reindex(r.index))
    costs = pd.DataFrame(cost_rows).T
    costs.index.name = "Coût par changement d'allocation"
    costs.to_csv(os.path.join(TAB_DIR, "06_transaction_costs.csv"))

    turnover = (held != held.shift()).sum() / (len(held) / MONTHS)
    print("\n" + "=" * 88)
    print("TABLE 6 — Sensibilité aux coûts de transaction (%.2f changements/an)"
          % turnover)
    print("=" * 88)
    print((costs[["CAGR", "Sharpe", "Max drawdown"]]
           .assign(CAGR=lambda d: (d["CAGR"] * 100).round(2),
                   **{"Max drawdown": lambda d: (d["Max drawdown"] * 100).round(2)})
           ).round(3).to_string())

    # ---- allocation summary --------------------------------------------
    alloc = (held.value_counts(normalize=True) * 100).round(1)
    print("\n" + "=" * 88)
    print("Allocation dans le temps : %s"
          % ", ".join("%s %.1f%%" % (k, v) for k, v in alloc.items()))
    print("Position actuelle : %s (signal du %s)"
          % (held.iloc[-1], held.index[-1].date()))

    # ---- figures --------------------------------------------------------
    fig_equity(curves, os.path.join(FIG_DIR, "01_equity_curves.png"))
    fig_drawdown({"GEM": gem, "S&P 500": bench},
                 os.path.join(FIG_DIR, "02_drawdowns.png"))
    fig_allocation(held, os.path.join(FIG_DIR, "03_allocation.png"))
    fig_rolling(gem, bench, os.path.join(FIG_DIR, "04_rolling_excess.png"))
    fig_lookback(look, os.path.join(FIG_DIR, "05_lookback_sensitivity.png"))

    print("\nFigures -> %s" % FIG_DIR)
    print("Tables  -> %s" % TAB_DIR)


def _fmt(df):
    """Percent-format the ratio rows of a stats table for terminal display."""
    pct = ["CAGR", "Volatility", "Max drawdown", "Best month", "Worst month",
           "Positive months", "Monthly VaR 5%"]
    out = df.copy().astype(float)
    for row in out.index:
        out.loc[row] = (out.loc[row] * 100).round(2) if row in pct \
            else out.loc[row].round(2)
    return out


def _decades(index):
    start = (index[0].year // 10) * 10
    for y in range(start, index[-1].year + 1, 10):
        label = "%ds" % y
        yield label, slice("%d-01-01" % y, "%d-12-31" % (y + 9))


if __name__ == "__main__":
    main()
