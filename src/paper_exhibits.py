"""
Exhibits produced specifically for the paper.

The backtest script writes the exhibits that fall out of the analysis itself.
This one writes the four that exist to explain rather than to measure: the
decision rule as a diagram, the provenance of the data as a timeline, annual
returns side by side, and the summary statistics of the four input series.

Run:  python src/paper_exhibits.py
Out:  output/figures/{00_decision_rule,09_provenance,06_annual_returns}.{png,pdf}
      output/tables/00_summary_statistics.csv
"""

from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gem_backtest import (  # noqa: E402
    COLORS, FIG_DIR, MONTHS, TAB_DIR, drawdown_series, gem_rule,
    newey_west_se, run_rule, save_figure,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_CSV = os.path.join(ROOT, "data", "gem_dataset.csv")

ASSET_COLORS = {"US": "#c0392b", "EXUS": "#2874a6", "BOND": "#7d8c8c"}


# --------------------------------------------------------------------------
# Figure 1 — the decision rule
# --------------------------------------------------------------------------

def fig_decision_rule(held, path):
    """Draw the rule as a decision tree.

    A reader should be able to take in the whole strategy from this one exhibit,
    including the fact that the two momentum tests do different jobs: the first
    decides whether to hold equities at all, the second decides which.
    """
    share = held.value_counts(normalize=True) * 100
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    def box(x, y, w, h, text, fc, ec, fontsize=9, weight="normal",
            tc="#1a1a1a", ty=None):
        ax.add_patch(mpatches.FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=1.2", linewidth=1.2,
            facecolor=fc, edgecolor=ec, zorder=2))
        ax.text(x, y if ty is None else ty, text, ha="center", va="center",
                fontsize=fontsize, fontweight=weight, color=tc, zorder=3,
                linespacing=1.5)

    def arrow(x1, y1, x2, y2, label=None, side="left"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", linewidth=1.1,
                                    color="#555", shrinkA=3, shrinkB=3))
        if label:
            dx = -3.5 if side == "left" else 3.5
            ax.text((x1 + x2) / 2 + dx, (y1 + y2) / 2, label,
                    ha="center", va="center", fontsize=8.5,
                    fontweight="bold", color="#555")

    box(50, 93, 32, 7, "Each month-end", "#f2f2f2", "#999", 9.5)

    # The gloss sits inside each decision box: outside it, the branch arrows
    # cross the text.
    box(50, 76, 60, 15,
        "Absolute momentum\n"
        "12-month return on US equity  >  12-month return on T-bills ?",
        "#fdf6e3", "#b8912f", 9.5, "bold", ty=78.5)
    ax.text(50, 71.2, "is the market worth holding at all?", ha="center",
            va="center", fontsize=8, style="italic", color="#8a7024", zorder=3)

    box(30, 46, 42, 15,
        "Relative momentum\n"
        "12-month US  ≥  12-month ex-US ?",
        "#eef5fb", "#2874a6", 9.5, "bold", ty=48.5)
    ax.text(30, 41.2, "which of the two?", ha="center", va="center",
            fontsize=8, style="italic", color="#1f5f86", zorder=3)

    box(83, 46, 26, 12,
        "Hold\nUS aggregate bonds", "#eceff0", "#7d8c8c", 9.5, "bold")
    box(14, 15, 24, 11, "Hold\nUS equity", "#fbeeec", "#c0392b", 9.5, "bold")
    box(46, 15, 24, 11, "Hold\nex-US equity", "#eef5fb", "#2874a6", 9.5, "bold")

    arrow(50, 89.5, 50, 84)
    arrow(41, 68, 30, 54, "YES", "left")
    arrow(61, 68, 83, 52.5, "NO", "right")
    arrow(23, 38, 14, 21, "YES", "left")
    arrow(37, 38, 46, 21, "NO", "right")

    for x, key in ((14, "US"), (46, "EXUS"), (83, "BOND")):
        ax.text(x, 4.0, "%.0f%% of months" % share.get(key, 0.0),
                ha="center", va="center", fontsize=8.5, color="#666")

    ax.set_title("The Global Equities Momentum decision rule",
                 loc="left", fontsize=11.5, fontweight="bold", y=1.0)
    ax.text(0, -4.5, "The position taken at the close of month $t$ earns the "
                   "return of month $t\\!+\\!1$.",
            fontsize=8, color="#666", ha="left", va="center")
    save_figure(fig, path)


# --------------------------------------------------------------------------
# Figure 2 — provenance of the data
# --------------------------------------------------------------------------

def fig_provenance(path):
    """Timeline of which vendor series feeds each leg, and when it changes.

    The point of showing this is that the series are not homogeneous: the ex-US
    leg gains emerging markets in 1988, and the Aggregate bond index does not
    exist before 1976. A reader should see those breaks rather than read about
    them.
    """
    detailed = pd.read_csv(
        os.path.join(ROOT, "data", "gem_dataset_detailed.csv"),
        parse_dates=["date"])

    rows = ["US", "EXUS", "BOND", "TBILL"]
    labels = {"US": "US equity", "EXUS": "Ex-US equity",
              "BOND": "US aggregate bonds", "TBILL": "T-bills"}
    # One hue family per row, shaded by segment order, so colour carries the
    # series identity rather than the order in which segments were encountered.
    palette = {
        "US": ["#b5342a", "#d9796f"],
        "EXUS": ["#1f5f86", "#4b90bd", "#8fbcd9"],
        "BOND": ["#4f6062", "#8ba0a2", "#bcc9ca"],
        "TBILL": ["#8e6c1f", "#bda05e"],
    }

    # autolayout fights the manual margins this figure needs for its legend.
    with plt.rc_context({"figure.autolayout": False}):
        return _draw_provenance(detailed, rows, labels, palette, path)


def _draw_provenance(detailed, rows, labels, palette, path):
    fig, ax = plt.subplots(figsize=(10.0, 4.2))
    fig.subplots_adjust(left=0.16, right=0.985, top=0.84, bottom=0.24)

    colour_of, outside = {}, {}
    for i, key in enumerate(rows):
        sub = detailed[detailed["series"] == key]

        # Merge consecutive segments that measure the SAME index. The US leg
        # changes data provider in 2013 and again in 2017 but keeps measuring
        # the S&P 500 throughout; drawing three blocks there would suggest a
        # break in the series that does not exist.
        spans = []
        for seg, block in sub.groupby("segment", sort=False):
            label = _short(block["index_name"].iloc[0])
            start, end = block["date"].min(), block["date"].max()
            if spans and spans[-1][0] == label:
                spans[-1][2] = end
            else:
                spans.append([label, start, end])

        shades = palette[key]
        for j, (label, start, end) in enumerate(spans):
            colour_of[label] = shades[j % len(shades)]
            ax.barh(i, (end - start).days, left=start, height=0.5,
                    color=colour_of[label], edgecolor="white", linewidth=1.0)

            # Only write inside the bar when the text actually fits: roughly
            # 0.55 years per character at this font size and figure width.
            years = (end - start).days / 365.25
            if years > 0.55 * len(label):
                ax.text(start + (end - start) / 2, i, label,
                        ha="center", va="center", fontsize=7.4,
                        color="white", fontweight="bold")
            else:
                outside[label] = colour_of[label]

    for year in (1976, 1988, 2013, 2017):
        when = pd.Timestamp("%d-01-01" % year)
        ax.axvline(when, color="#333", linestyle=":", linewidth=0.9, zorder=0)
        ax.text(when, -0.72, str(year), ha="center", va="bottom",
                fontsize=7.5, color="#333")

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([labels[k] for k in rows])
    ax.invert_yaxis()
    ax.set_ylim(3.6, -0.85)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", alpha=0.2)
    ax.set_title("Provenance of each series over time", loc="left",
                 fontsize=11.5, fontweight="bold", pad=16)

    if outside:
        # Segments too narrow to carry their label inside the bar.
        ax.legend(handles=[mpatches.Patch(color=c, label=l)
                           for l, c in outside.items()],
                  loc="upper left", bbox_to_anchor=(0.0, -0.13),
                  ncol=3, fontsize=7.6, handlelength=1.2, columnspacing=1.6)

    fig.text(0.16, 0.015,
             "Dotted lines mark where a leg changes source. The ex-US leg gains "
             "emerging markets in 1988; the Aggregate bond index does not exist "
             "before 1976.",
             fontsize=7.8, color="#666", ha="left", va="bottom")
    save_figure(fig, path)


def _short(name):
    """Compact an index name enough to sit inside a bar."""
    for long, short in [
        ("Ibbotson US Large Cap total return", "Ibbotson US Large Cap"),
        ("S&P 500 Total Return", "S&P 500 TR"),
        ("MSCI World ex USA, gross total return, USD", "MSCI World ex USA"),
        ("MSCI ACWI ex USA IMI, gross total return, USD", "ACWI ex USA IMI"),
        ("MSCI ACWI ex USA, gross total return, USD", "MSCI ACWI ex USA"),
        ("Bloomberg Barclays US Aggregate Bond, total return", "Bloomberg US Agg"),
        ("Bloomberg US Aggregate Bond (via ETF", "Bloomberg US Agg"),
        ("US 1-month Treasury bill", "1-month T-bill (Ken French)"),
    ]:
        if name.startswith(long):
            return short
    if name.startswith("40% Ibbotson"):
        return "Ibbotson 40/60 gov-corp"
    return name[:28]


# --------------------------------------------------------------------------
# Figure 5 — annual returns
# --------------------------------------------------------------------------

def fig_annual_returns(gem, bench, path):
    """Calendar-year returns, side by side.

    This is the exhibit that shows where the edge actually comes from: GEM wins
    by not losing in bad years, not by beating the index in good ones.
    """
    ann = pd.DataFrame({
        "GEM": (1 + gem).groupby(gem.index.year).prod() - 1,
        "S&P 500": (1 + bench).groupby(bench.index.year).prod() - 1,
    }) * 100
    years = ann.index.to_numpy()
    width = 0.42

    fig, ax = plt.subplots(figsize=(11.5, 4.4))
    ax.bar(years - width / 2, ann["GEM"], width, label="GEM",
           color=COLORS["GEM"], zorder=3)
    ax.bar(years + width / 2, ann["S&P 500"], width, label="S&P 500",
           color=COLORS["S&P 500"], zorder=3)
    ax.axhline(0, color="#333", linewidth=0.9, zorder=4)

    ax.set_ylabel("Calendar-year return (%)")
    ax.set_title("Annual returns, GEM versus the S&P 500", loc="left",
                 fontsize=11.5, fontweight="bold")
    ax.legend(loc="lower left", ncol=2)
    ax.set_xlim(years[0] - 1, years[-1] + 1)
    ax.grid(axis="x", visible=False)

    down = ann[ann["S&P 500"] < 0]
    ax.text(0.995, 0.95,
            "In the %d years the S&P 500 fell, GEM averaged %+.1f%% "
            "against %+.1f%%" % (len(down), down["GEM"].mean(),
                                 down["S&P 500"].mean()),
            transform=ax.transAxes, ha="right", va="top",
            fontsize=8.5, color="#444")
    save_figure(fig, path)


# --------------------------------------------------------------------------
# Table 2 — summary statistics of the input series
# --------------------------------------------------------------------------

def table_summary(prices, path):
    """Descriptive statistics of the four building blocks, before any strategy."""
    rows = {}
    labels = {"US": "US equity", "EXUS": "Ex-US equity",
              "BOND": "US aggregate bonds", "TBILL": "T-bills"}
    rf = prices["TBILL"].pct_change()
    for col in ["US", "EXUS", "BOND", "TBILL"]:
        r = prices[col].pct_change().dropna()
        vol = r.std(ddof=1) * np.sqrt(MONTHS)
        excess = (r - rf.reindex(r.index)).dropna()
        se = newey_west_se(excess)
        rows[labels[col]] = {
            "Start": prices[col].dropna().index[0].strftime("%Y-%m"),
            "Months": len(r),
            "CAGR": (1 + r).prod() ** (MONTHS / len(r)) - 1,
            "Volatility": vol,
            "Sharpe": (excess.mean() * MONTHS) / vol if vol else np.nan,
            "Max drawdown": drawdown_series(r).min(),
            "Skewness": r.skew(),
            "Excess kurtosis": r.kurtosis(),
            "Worst month": r.min(),
            "Best month": r.max(),
            "Excess t-stat (NW)": excess.mean() / se if se else np.nan,
        }
    table = pd.DataFrame(rows)
    # Excess return of the risk-free asset over itself is identically zero, so
    # its Sharpe, drawdown and t-statistic are not meaningful quantities.
    for row in ["Sharpe", "Max drawdown", "Excess t-stat (NW)"]:
        table.loc[row, "T-bills"] = np.nan
    table.to_csv(path)
    return table


def main():
    prices = pd.read_csv(DATA_CSV, index_col="Date", parse_dates=True)
    gem, held = run_rule(prices, gem_rule)
    bench = prices["US"].pct_change().reindex(gem.index)

    print("Paper exhibits, %s -> %s\n"
          % (gem.index[0].strftime("%Y-%m"), gem.index[-1].strftime("%Y-%m")))

    fig_decision_rule(held, os.path.join(FIG_DIR, "00_decision_rule.png"))
    print("  Figure 1  decision rule")
    fig_provenance(os.path.join(FIG_DIR, "09_provenance.png"))
    print("  Figure 2  data provenance")
    fig_annual_returns(gem, bench, os.path.join(FIG_DIR, "06_annual_returns.png"))
    print("  Figure 5  annual returns")

    table = table_summary(prices, os.path.join(TAB_DIR, "00_summary_statistics.csv"))
    print("  Table 2   summary statistics\n")
    show = table.copy()
    for row in ["CAGR", "Volatility", "Max drawdown", "Worst month", "Best month"]:
        show.loc[row] = (show.loc[row].astype(float) * 100).round(2)
    for row in ["Sharpe", "Skewness", "Excess kurtosis", "Excess t-stat (NW)"]:
        show.loc[row] = show.loc[row].astype(float).round(2)
    print(show.to_string())


if __name__ == "__main__":
    main()
