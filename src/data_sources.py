"""
Fetchers for every data source used by the GEM backtest.

All sources are free and publicly accessible. Each function returns a monthly
(month-end indexed) pandas object so that downstream code never has to worry
about the wildly different native formats of these providers.

Two non-obvious traps are handled here, both found by testing rather than by
reading documentation:

  1. yfinance with interval="1mo" SILENTLY truncates history to ~1985.
     ^GSPC returns 1985+ monthly but 1927+ daily. We always download daily and
     resample ourselves. See fetch_yahoo().

  2. The undocumented MSCI endpoint truncates the START of the series when the
     requested window is wide: asking for 1997-2026 in one call returns data
     from 2000 only. We page in 3-year chunks. See fetch_msci().
"""

from __future__ import annotations

import io
import json
import os
import time
import urllib.request
import zipfile

import numpy as np
import pandas as pd

# Browser-like headers. MSCI's endpoint needs these (plus a Referer) to answer.
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept": "*/*",
}

# FRED is the mirror image: it hangs forever on the full Chrome User-Agent, and
# it also hangs when no Accept header is sent at all. It answers in ~0.1s with
# this minimal pair. Both behaviours are silent -- the connection is accepted
# and then simply never answered -- so they look like network flakiness rather
# than a rejection. Found by bisecting the header set.
PLAIN_UA = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

GEM_CSV_URL = "https://raw.githubusercontent.com/alexjansenhome/GEM/master/msci_all_gross.csv"
FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
MSCI_ENDPOINT = ("https://app2.msci.com/products/service/index/indexmaster/"
                 "getLevelDataForGraph")
MSCI_REFERER = "https://app2.msci.com/products/index-data-search/"


def _get(url, referer=None, timeout=60, retries=3, headers=None):
    """GET with retries, using browser-like headers unless told otherwise."""
    headers = dict(UA if headers is None else headers)
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers)
    last = None
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(request, timeout=timeout).read()
        except Exception as exc:  # noqa: BLE001 - retry any transport error
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise last


def _to_month_end(s):
    """Collapse an any-frequency series to the last observation of each month."""
    return s.sort_index().resample("ME").last().dropna()


# --------------------------------------------------------------------------
# 1. Historical core: the Antonacci-style spliced dataset (1969-12 -> 2017-05)
# --------------------------------------------------------------------------

# Component columns of msci_all_gross.csv, i.e. the raw vendor series that the
# spliced columns are built from. The spliced column names are literally
# spreadsheet cell references into this same file: column C is "WORLD ex USA",
# D is "ACWI ex USA", so "Spliced C and D" means C first, then D. Decoding those
# letters is what makes the recipes below verifiable rather than guessed.
GEM_SPREADSHEET_COLUMNS = {
    "B": "USA", "C": "WORLD ex USA", "D": "ACWI ex USA", "E": "Spliced C and D",
    "F": "AGG", "G": "SP500TR", "H": "Large Caps", "I": "Spliced H+G",
    "J": "Mid-Treasuries", "K": "Mid-Corporate Bonds",
    "L": "Spliced F+40%J+60%K", "M": "30 day Treas Bills", "N": "3-Month Bill",
    "O": "Inflation", "P": "CPI", "Q": "3 MONTH", "R": "4-Week Bill",
    "S": "Spliced M+R",
}

# Where each spliced column actually switches vendor. NOT taken on trust: every
# boundary below was recovered from the file itself by finding the contiguous
# run of months over which spliced/component is a constant ratio, then confirmed
# against the month where the incoming component is rebased to 100.
GEM_SEGMENTS = {
    "US": [
        ("1969-12-31", "2012-12-31", "Ibbotson US Large Cap total return",
         "Morningstar / Ibbotson SBBI", "Large Caps (col. H)"),
        ("2013-01-31", "2016-12-31", "S&P 500 Total Return",
         "Yahoo Finance", "SP500TR (col. G)"),
    ],
    "EXUS": [
        ("1969-12-31", "1987-12-31", "MSCI World ex USA, gross total return, USD",
         "MSCI", "WORLD ex USA (col. C)"),
        ("1988-01-31", "2016-12-31", "MSCI ACWI ex USA, gross total return, USD",
         "MSCI", "ACWI ex USA (col. D)"),
    ],
    "BOND": [
        ("1969-12-31", "1975-12-31",
         "40% Ibbotson Intermediate Treasuries + 60% Ibbotson Intermediate "
         "Corporates, rebalanced monthly",
         "Morningstar / Ibbotson SBBI", "Mid-Treasuries + Mid-Corporate (col. J, K)"),
        ("1976-01-31", "2016-12-31",
         "Bloomberg Barclays US Aggregate Bond, total return",
         "Morningstar", "AGG (col. F)"),
    ],
    "TBILL": [
        ("1969-12-31", "2012-12-31", "Ibbotson 30-day US Treasury bills",
         "Morningstar / Ibbotson SBBI", "30 day Treas Bills (col. M)"),
        ("2013-01-31", "2016-12-31", "US 4-week Treasury bill",
         "FRED (TB4WK)", "4-Week Bill (col. R)"),
    ],
}

# Columns of msci_all_gross.csv we rely on, and what they actually contain.
GEM_COLUMNS = {
    "US": (
        "Spliced H+G",
        "Ibbotson US Large Cap TR spliced to S&P 500 Total Return (Yahoo)",
    ),
    "EXUS": (
        "Spliced C and D",
        "MSCI World ex USA gross TR spliced to MSCI ACWI ex USA gross TR",
    ),
    "BOND": (
        "Spliced F+40%J+60%K",
        "40% Ibbotson Intermediate Treasuries + 60% Ibbotson Intermediate "
        "Corporates, spliced to Bloomberg Barclays US Aggregate TR",
    ),
    "TBILL": (
        "Spliced M+R",
        "Ibbotson 30-day T-bills spliced to FRED 4-week T-bill",
    ),
}


def repair_monotone_index(s, name=""):
    """Repair a total-return index that is known to be non-decreasing.

    A cash / T-bill total-return index accrues a positive yield every month, so
    any month-on-month FALL is by construction a data error rather than a market
    move. This is exactly what happens in the redistributed CSV: three November
    observations (1990, 1991, 1992) lost their leading digit, e.g. 0.366 where
    the surrounding levels demand 10.366.

    Each bad point is replaced by the geometric mean of its two neighbours,
    which recovers the dropped digit to four significant figures without
    hard-coding any magic constant. Returns (repaired_series, log_of_repairs).

    Each repair is tagged "material" or "rounding": a fall of less than 0.1% is
    just the published file rounding a level to three decimals, whereas the
    dropped-digit errors are three orders of magnitude larger.
    """
    s = s.dropna().copy()
    values = s.values.astype(float)
    log = []
    for i in range(1, len(values) - 1):
        if values[i] < values[i - 1]:
            before, after = values[i - 1], values[i + 1]
            fixed = float(np.sqrt(before * after))
            drop = (before - values[i]) / before
            log.append({
                "series": name,
                "date": s.index[i],
                "observed": values[i],
                "repaired": fixed,
                "neighbours": (before, after),
                "drop": drop,
                "kind": "material" if drop > 0.001 else "rounding",
            })
            values[i] = fixed
    return pd.Series(values, index=s.index), log


def _read_gem_raw(url=GEM_CSV_URL):
    """Parse the published CSV into a month-end indexed frame of raw columns.

    ``thousands=","`` is essential and not cosmetic: from mid-1986 the USA and
    WORLD ex USA columns cross 1000 and are written "1,079.18". Without it those
    cells parse as strings, pd.to_numeric turns them into NaN, and 293 and 365
    observations respectively vanish without any error being raised.
    """
    raw = _get(url).decode("utf-8-sig")
    df = pd.read_csv(io.StringIO(raw), skiprows=2, thousands=",")
    df.columns = [c.strip() for c in df.columns]

    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%y")
    # 12/31/69 parses as 2069; anything past 2050 belongs to the 1900s.
    df.loc[df["Date"].dt.year > 2050, "Date"] -= pd.DateOffset(years=100)
    return df.set_index("Date").sort_index()


def fetch_gem_components(url=GEM_CSV_URL):
    """The raw vendor component series, as numeric month-end levels.

    These are what the spliced columns are assembled from; the detailed dataset
    uses them to state, for every month, which vendor series was in force.
    """
    df = _read_gem_raw(url)
    out = {}
    for col in df.columns:
        if col == "Date":
            continue
        out[col] = pd.to_numeric(df[col], errors="coerce").replace(0.0, np.nan)
    return pd.DataFrame(out).resample("ME").last()


def fetch_gem_core(url=GEM_CSV_URL, repair=True):
    """Download and parse the bundled historical dataset.

    The file has three quirks that silently corrupt the data if ignored: two
    banner rows above the real header, %m/%d/%y dates that pandas rolls forward
    into the 2060s, and 0.0 used as the missing-value marker.

    With repair=True the TBILL column is passed through repair_monotone_index()
    and the list of repairs is attached as ``df.attrs["repairs"]``. Pass
    repair=False to audit the file exactly as published.
    """
    df = _read_gem_raw(url)

    out = {}
    for key, (col, _desc) in GEM_COLUMNS.items():
        if col not in df.columns:
            raise KeyError("expected column %r missing from %s" % (col, url))
        out[key] = pd.to_numeric(df[col], errors="coerce").replace(0.0, np.nan)

    core = pd.DataFrame(out).resample("ME").last()
    repairs = []
    if repair:
        fixed, repairs = repair_monotone_index(core["TBILL"], name="TBILL")
        core["TBILL"] = fixed.reindex(core.index)
    core.attrs["repairs"] = repairs
    return core


# --------------------------------------------------------------------------
# 2. Live extension / cross-validation sources
# --------------------------------------------------------------------------

def fetch_yahoo(ticker, start="1900-01-01"):
    """Month-end adjusted close from Yahoo, downloaded DAILY on purpose.

    Requesting interval="1mo" truncates history with no warning; daily plus our
    own resample is the only reliable way to get the full record.
    """
    import yfinance as yf

    px = yf.Ticker(ticker).history(
        start=start, interval="1d", auto_adjust=True
    )["Close"].dropna()
    if px.empty:
        raise ValueError("Yahoo returned no data for %r" % ticker)
    px.index = px.index.tz_localize(None)
    return _to_month_end(px)


def fetch_msci(index_code, start_year=1997, end_year=2026, variant="GRTR",
               currency="USD", pause=0.4):
    """Month-end MSCI index levels from MSCI's public (undocumented) endpoint.

    variant: GRTR = gross total return, NETR = net total return, STRD = price.
    Hard floor at 1997-01-01 -- MSCI rejects earlier start dates outright.
    Paged in 3-year windows because wide windows come back truncated.
    """
    rows = []
    for year in range(start_year, end_year + 1, 3):
        url = ("%s?currency_symbol=%s&index_variant=%s"
               "&start_date=%d0101&end_date=%d1231"
               "&data_frequency=END_OF_MONTH&baseValue=false&index_codes=%s"
               % (MSCI_ENDPOINT, currency, variant, year,
                  min(year + 2, end_year), index_code))
        try:
            payload = json.loads(_get(url, referer=MSCI_REFERER))
        except Exception as exc:  # noqa: BLE001 - network is best-effort here
            print("    [msci %s] chunk %d failed: %s" % (index_code, year, exc))
            continue
        levels = payload.get("indexes", {}).get("INDEX_LEVELS", [])
        rows += [(str(r["calc_date"]), r["level_eod"]) for r in levels]
        time.sleep(pause)

    if not rows:
        raise ValueError("MSCI returned no data for index_code=%r" % index_code)
    s = pd.Series(dict(rows))
    s.index = pd.to_datetime(s.index, format="%Y%m%d")
    return _to_month_end(s)


def fetch_french(dataset="F-F_Research_Data_Factors"):
    """Monthly rows of a Kenneth French CSV, as decimal returns.

    Works for the US factor file and the regional ones
    (Developed_ex_US_3_Factors, Emerging_5_Factors, ...). The annual block at
    the bottom of each file is dropped by keeping only 6-digit YYYYMM keys.
    """
    blob = _get("%s/%s_CSV.zip" % (FRENCH_BASE, dataset))
    zf = zipfile.ZipFile(io.BytesIO(blob))
    text = zf.read(zf.namelist()[0]).decode("latin1").splitlines()

    header, rows = None, []
    for line in text:
        parts = [p.strip() for p in line.split(",")]
        if header is None:
            # The real header is the first line whose leading cell is empty.
            if parts and parts[0] == "" and len(parts) > 2:
                header = [p for p in parts[1:] if p]
            continue
        key = parts[0]
        if len(key) == 6 and key.isdigit():        # YYYYMM -> monthly block
            rows.append((key, parts[1:1 + len(header)]))

    if not rows:
        raise ValueError("no monthly rows parsed from %s" % dataset)
    idx = pd.PeriodIndex([r[0] for r in rows], freq="M").to_timestamp("M")
    df = pd.DataFrame([[float(v) for v in r[1]] for r in rows],
                      index=idx, columns=header)
    return df.replace(-99.99, np.nan) / 100.0


def fetch_fred(series_id, start="1900-01-01"):
    """A FRED series as a month-end Series (values left in their native units)."""
    url = ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s"
           % (series_id, start))
    df = pd.read_csv(io.StringIO(_get(url, headers=PLAIN_UA, timeout=30).decode()))
    df.columns = ["date", "value"]
    s = pd.Series(
        pd.to_numeric(df["value"], errors="coerce").values,
        index=pd.to_datetime(df["date"]),
    ).dropna()
    return _to_month_end(s)


def cached(name, loader, cache_dir, refresh=True):
    """Fetch a series, keeping a disk copy as a fallback.

    Providers here are free and unmetered, so they throttle. MSCI in particular
    starts timing out after a burst of requests. Without a fallback a single
    throttled fetch would leave a column short, and the final dropna() would
    then silently truncate the WHOLE dataset back to the last month every
    column has -- turning a network hiccup into 10 years of missing data.

    Returns (series, source) where source is "live" or "cache".
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, "%s.csv" % name)

    prior = None
    if os.path.exists(path):
        prior = pd.read_csv(path, index_col=0, parse_dates=True)["value"].dropna()

    if refresh:
        try:
            fresh = loader().dropna()
        except Exception as exc:  # noqa: BLE001
            print("          live fetch failed (%s)" % str(exc)[:70])
            fresh = None

        if fresh is not None and len(fresh):
            # A throttled provider can answer with HOLES rather than an error --
            # MSCI drops whole pages and still returns 200. Filling those from
            # the cached copy is safe because it is the same series from the
            # same provider on the same base, and it stops a partial answer
            # from being mistaken for a complete one downstream.
            merged = fresh if prior is None else fresh.combine_first(prior)
            merged = merged.sort_index()
            merged.to_frame("value").to_csv(path)
            filled = len(merged) - len(fresh)
            return merged, "live" if not filled else "live+%d from cache" % filled

    if prior is not None:
        return prior, "cache"
    raise RuntimeError(
        "%s unavailable: live fetch failed and no cached copy at %s" % (name, path)
    )


def compound(returns, base=100.0):
    """Turn a series of periodic returns into a total-return index level."""
    return base * (1.0 + returns.dropna()).cumprod()
