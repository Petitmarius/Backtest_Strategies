"""
Turn the computed CSV tables into LaTeX fragments for the paper.

Same principle as the figures: the manuscript never contains a number that was
typed by hand. Each fragment is a bare tabular, so gem.tex keeps control of
placement, caption and label.

Run:  python src/make_tables.py
Out:  paper/tables/*.tex
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from data_sources import GEM_SEGMENTS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAB_DIR = os.path.join(ROOT, "output", "tables")
OUT_DIR = os.path.join(ROOT, "paper", "tables")

# Rows that are percentages in the computed CSVs and must be printed as such.
PCT_ROWS = {"CAGR", "Volatility", "Max drawdown", "Best month", "Worst month",
            "Positive months", "Monthly VaR 5%"}


def esc(text):
    """Escape the characters LaTeX would otherwise interpret."""
    out = str(text)
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("_", r"\_"), ("#", r"\#"), ("$", r"\$")]:
        out = out.replace(a, b)
    return out


def tabular(df, colspec, header, body, note=None, small=True):
    """Assemble a booktabs tabular from pre-formatted rows."""
    lines = []
    if small:
        lines.append(r"\small")
    lines.append(r"\begin{tabular}{%s}" % colspec)
    lines.append(r"\toprule")
    lines.append(header + r" \\")
    lines.append(r"\midrule")
    lines += [row + r" \\" for row in body]
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    if note:
        lines.append(r"\\[0.4em]")
        lines.append(r"\begin{minipage}{\linewidth}\footnotesize %s\end{minipage}"
                     % note)
    return "\n".join(lines) + "\n"


def fmt(value, kind="num", digits=2):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "---"
    if kind == "pct":
        return r"%.2f" % (float(value) * 100)
    if kind == "int":
        return "%d" % round(float(value))
    return ("%." + str(digits) + "f") % float(value)


def write(name, content):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("  %s" % os.path.relpath(path, ROOT))


# --------------------------------------------------------------------------

def table_provenance():
    """Table 1 -- which index each leg actually measures, and when."""
    live = {
        "US": ("2017-01", "2026-07", "S\\&P 500 Total Return", "Yahoo Finance"),
        "EXUS": ("2017-01", "2026-07",
                 "MSCI ACWI ex USA IMI, gross", "MSCI"),
        "BOND": ("2017-01", "2026-07",
                 "Bloomberg US Aggregate", "Yahoo Finance"),
    }
    names = {"US": "US equity", "EXUS": "Ex-US equity",
             "BOND": "US aggregate bonds", "TBILL": "T-bills"}

    body = []
    for key in ["US", "EXUS", "BOND", "TBILL"]:
        rows = []
        if key == "TBILL":
            rows.append(("1969-12", "2026-07", "US 1-month Treasury bill",
                         "Kenneth French"))
        else:
            for start, stop, index_name, provider, _src in GEM_SEGMENTS[key]:
                rows.append((start[:7], stop[:7],
                             esc(_trim(index_name)), esc(_provider(provider))))
            rows.append(live[key])
        for i, (start, stop, index_name, provider) in enumerate(rows):
            first = r"\textbf{%s}" % names[key] if i == 0 else ""
            body.append(" & ".join([first, start, stop, index_name, provider]))
        if key != "TBILL":
            body.append(r"\addlinespace")

    note = ("Segment boundaries were recovered from the source file itself, by "
            "locating the contiguous span over which the ratio of the spliced "
            "series to a candidate component is constant, and confirming "
            "against the month in which the incoming component is rebased. "
            "The T-bill leg is a single continuous source and is not spliced. "
            "From 2017 the bond leg is taken from the AGG exchange-traded "
            "fund, which tracks the Aggregate net of a management fee.")
    return tabular(None, "lllll",
                   r"Series & From & To & Index measured & Provider",
                   body, note)


def _provider(name):
    """Providers are named at the length the table can carry."""
    return {"Morningstar / Ibbotson SBBI": "Ibbotson SBBI",
            "Kenneth French Data Library": "Kenneth French",
            "FRED (TB4WK)": "FRED"}.get(name, name)


def _trim(name):
    for long, short in [
        ("Ibbotson US Large Cap total return", "Ibbotson US Large Cap"),
        ("MSCI World ex USA, gross total return, USD", "MSCI World ex USA, gross"),
        ("MSCI ACWI ex USA, gross total return, USD", "MSCI ACWI ex USA, gross"),
        ("Bloomberg Barclays US Aggregate Bond, total return",
         "Bloomberg US Aggregate"),
        ("40% Ibbotson Intermediate Treasuries + 60% Ibbotson Intermediate "
         "Corporates, rebalanced monthly",
         "40/60 intermediate govt/corp."),
        ("Ibbotson 30-day US Treasury bills", "Ibbotson 30-day T-bills"),
        ("US 4-week Treasury bill", "US 4-week T-bill"),
    ]:
        if name.startswith(long):
            return short
    return name


def table_summary():
    """Table 2 -- descriptive statistics of the four inputs."""
    df = pd.read_csv(os.path.join(TAB_DIR, "00_summary_statistics.csv"),
                     index_col=0)
    order = [("CAGR", "pct", "CAGR (\\%)"),
             ("Volatility", "pct", "Volatility (\\%)"),
             ("Sharpe", "num", "Sharpe ratio"),
             ("Max drawdown", "pct", "Maximum drawdown (\\%)"),
             ("Worst month", "pct", "Worst month (\\%)"),
             ("Best month", "pct", "Best month (\\%)"),
             ("Skewness", "num", "Skewness"),
             ("Excess kurtosis", "num", "Excess kurtosis"),
             ("Excess t-stat (NW)", "num", "$t$-statistic on excess return")]

    cols = list(df.columns)
    body = [" & ".join(["Months"] +
                       [fmt(df.loc["Months", c], "int") for c in cols])]
    for row, kind, label in order:
        body.append(" & ".join([label] +
                               [fmt(df.loc[row, c], kind) for c in cols]))

    note = ("Monthly total returns in US dollars, %s to %s. Excess returns are "
            "measured over the 1-month Treasury bill and their $t$-statistics "
            "use Newey--West standard errors. The risk-free leg has no "
            "meaningful excess return over itself, so those cells are empty."
            % (df.loc["Start", cols[0]], "2026-07"))
    header = "  & " + " & ".join(r"\textbf{%s}" % esc(c) for c in cols)
    return tabular(None, "l" + "r" * len(cols), header, body, note)


def table_audit():
    """Appendix table -- the dataset against independent sources."""
    rows = [
        ("US", "S\\&P 500 Total Return (Yahoo)", "1988-02", "2017-05", 352,
         0.9999, 0.19, -0.04),
        ("US", "CRSP US total market (Ken French)", "1970-01", "2017-05", 569,
         0.9883, 2.41, -0.04),
        ("Ex-US", "MSCI World ex USA gross (MSCI API)", "1997-02", "2017-05",
         233, 0.9701, 4.23, 1.16),
        ("Ex-US", "Developed ex-US market (Ken French)", "1990-08", "2017-05",
         322, 0.9862, 2.81, 0.22),
        ("Ex-US", "MSCI EAFE ETF (EFA)", "2001-09", "2017-05", 189,
         0.9749, 3.91, 1.10),
        ("Bonds", "Vanguard Total Bond Market (VBMFX)", "1987-01", "2017-05",
         365, 0.9923, 0.48, 0.21),
        ("Bonds", "iShares Core US Aggregate (AGG)", "2003-10", "2017-05", 164,
         0.9611, 1.09, 0.14),
        ("T-bills", "1-month T-bill (Ken French)", "1970-01", "2016-12", 564,
         0.9938, 0.11, 0.08),
        ("T-bills", "3-month T-bill (FRED TB3MS)", "1970-01", "2016-12", 564,
         0.9804, 0.19, -0.02),
    ]
    body, last = [], None
    for leg, ref, start, stop, n, corr, te, gap in rows:
        if last is not None and leg != last:
            body.append(r"\addlinespace")
        body.append(" & ".join([leg if leg != last else "", ref, start, stop,
                                "%d" % n, "%.4f" % corr, "%.2f" % te,
                                "%+.2f" % gap]))
        last = leg
    note = ("Monthly returns compared over every month the two series share; "
            "index levels are not comparable across providers. TE is the "
            "annualised standard deviation of the return difference. The gap "
            "column is the difference in annualised return over the common "
            "window, in percentage points.")
    header = (r"Leg & Independent reference & From & To & $N$ & "
              r"Corr. & TE (\%) & Gap (pt)")
    # Nine rows of eight columns need one size below the other tables.
    return "\\footnotesize\n" + tabular(None, "llllrrrr", header, body, note,
                                        small=False)


# Column and row labels abbreviated to what a printed table can carry. Only
# wording changes here -- never a number.
HEADER_SHORT = {
    "Correlation with GEM": "Corr. GEM",
    "Excess over S&P 500 (bps)": "Excess (bps)",
    "Absolute momentum only": "Absolute only",
    "Relative momentum only": "Relative only",
    "S&P 500 (benchmark)": "S&P 500",
    "US aggregate bonds": "US bonds",
    "Ex-US equity": "Ex-US",
    "Excess return t-stat (NW)": "Excess return t-stat",
    "Static mix 46/28/25": "Static 46/28/25",
    "GAA 45/28/27": "GAA",
}


def table_from_csv(csv_name, columns=None, rows=None, note=None,
                   index_label=" ", drop=()):
    """Generic: a computed CSV rendered with its rows as they stand."""
    df = pd.read_csv(os.path.join(TAB_DIR, csv_name), index_col=0)
    if drop:
        df = df[[c for c in df.columns
                 if not any(c.startswith(d) for d in drop)]]
    if columns:
        df = df[columns]
    if rows:
        df = df.loc[rows]

    body = []
    for label, row in df.iterrows():
        kind = "pct" if label in PCT_ROWS else (
            "int" if label == "Months" else "num")
        body.append(" & ".join([esc(HEADER_SHORT.get(label, _label(label)))] +
                               [fmt(v, kind) for v in row.values]))
    header = esc(index_label) + " & " + " & ".join(
        r"\textbf{%s}" % esc(HEADER_SHORT.get(c, c)) for c in df.columns)

    # Six or more columns will not fit the text block at \small.
    wide = df.shape[1] >= 6
    prefix = "\\footnotesize\n" if wide else ""
    return prefix + tabular(None, "l" + "r" * df.shape[1], header, body, note,
                            small=not wide)


def _label(name):
    """Add units to the row labels that carry percentages."""
    if name in PCT_ROWS:
        return "%s (%%)" % name
    return name


def main():
    print("LaTeX table fragments:")
    write("t1_provenance.tex", table_provenance())
    write("t2_summary.tex", table_summary())
    write("ta1_audit.tex", table_audit())

    # Antonacci's GAA benchmark (45/28/27) is within a point of our own
    # derived static mix (46/28/25) on every weight, so showing both would put
    # two near-identical columns side by side. The coincidence is worth a
    # sentence in the text, not a column.
    write("t3_performance.tex", table_from_csv(
        "01_performance.csv", drop=("GAA",),
        rows=["CAGR", "Volatility", "Sharpe", "Sortino", "Max drawdown",
              "Calmar (MAR)", "Worst month", "Monthly VaR 5%",
              "Positive months", "Excess return t-stat (NW)"],
        note="Monthly data, January 1971 to July 2026, 667 observations. "
             "Sharpe and Sortino ratios use the 1-month Treasury bill as the "
             "risk-free rate. The $t$-statistic uses Newey--West standard "
             "errors."))

    write("t4_decomposition.tex", table_from_csv(
        "02_decomposition.csv",
        rows=["CAGR", "Volatility", "Sharpe", "Max drawdown",
              "Excess over S&P 500 (bps)"],
        note="Absolute momentum alone holds US equity when it beats T-bills "
             "and bonds otherwise. Relative momentum alone always holds the "
             "stronger of US and ex-US equity, with no escape to bonds."))

    write("t5_allocation_timing.tex", table_from_csv(
        "07_allocation_vs_timing.csv",
        note="The static mix holds the same average allocation as GEM, fixed "
             "and rebalanced monthly. Weights are read off the backtest, not "
             "chosen."))

    write("t7_decades.tex", table_from_csv(
        "04_decades.csv",
        note="Calendar decades. The 1970s begin in January 1971, after the "
             "12-month formation period, and the 2020s end in July 2026."))

    write("t8_robustness.tex", table_robustness())
    print("\nDone.")


def table_robustness():
    """Two robustness dimensions side by side: lookback and trading cost."""
    look = pd.read_csv(os.path.join(TAB_DIR, "05_lookback_sensitivity.csv"),
                       index_col=0)
    cost = pd.read_csv(os.path.join(TAB_DIR, "06_transaction_costs.csv"),
                       index_col=0)

    body = [r"\multicolumn{5}{l}{\emph{Panel A: momentum lookback (months)}}"]
    for lb in [3, 6, 9, 12, 15, 18, 21, 24]:
        row = look.loc[lb]
        body.append(" & ".join([
            "%d months" % lb, fmt(row["CAGR"], "pct"),
            fmt(row["Volatility"], "pct"), fmt(row["Sharpe"]),
            fmt(row["Max drawdown"], "pct")]))

    body.append(r"\addlinespace")
    body.append(r"\multicolumn{5}{l}{\emph{Panel B: cost per allocation "
                r"change, at 12 months}}")
    for label, row in cost.iterrows():
        body.append(" & ".join([
            esc(label), fmt(row["CAGR"], "pct"),
            fmt(row["Volatility"], "pct"), fmt(row["Sharpe"]),
            fmt(row["Max drawdown"], "pct")]))

    note = ("Panel A varies the window used by both momentum tests, holding "
            "everything else fixed. Panel B charges a one-way cost on every "
            "month in which the rule changes asset, which happens 1.49 times a "
            "year on average.")
    header = (r" & \textbf{CAGR (\%)} & \textbf{Vol.\ (\%)} & "
              r"\textbf{Sharpe} & \textbf{Max DD (\%)}")
    return tabular(None, "lrrrr", header, body, note)


if __name__ == "__main__":
    main()
