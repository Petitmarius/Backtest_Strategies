"""
Build the master monthly dataset for the GEM backtest.

Assembles four total-return index levels -- US equity, ex-US equity, US
aggregate bonds and T-bills -- from 1969-12 to the present, using only free
sources, and writes them to data/gem_dataset.csv.

Construction
------------
Historical core (1969-12 -> 2016-12) comes from the redistributed CSV audited
in data/VALIDATION.md. It is extended to the present with live free sources,
each rescaled so that it agrees with the core at the junction month. Rescaling
is level-only: it changes no return, it just removes the arbitrary difference
in index base between two providers.

Run:  python src/build_dataset.py
Out:  data/gem_dataset.csv, data/SOURCES.md
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date, datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_sources import (  # noqa: E402
    GEM_COLUMNS,
    GEM_SEGMENTS,
    fetch_gem_components,
    cached,
    GEM_CSV_URL,
    compound,
    fetch_french,
    fetch_gem_core,
    fetch_msci,
    fetch_yahoo,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
OUT_CSV = os.path.join(DATA_DIR, "gem_dataset.csv")
OUT_DETAILED = os.path.join(DATA_DIR, "gem_dataset_detailed.csv")
OUT_COMPONENTS = os.path.join(DATA_DIR, "gem_dataset_components.csv")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
OUT_MANIFEST = os.path.join(DATA_DIR, "gem_dataset.manifest.json")

# Every numeric output is written with this format, so the committed file is
# byte-reproducible and its hash is meaningful.
FLOAT_FMT = "%.6f"

# Last month for which every column of the historical core is populated. The
# core file runs to 2017-05 but its T-bill column stops in 2016-12, so this is
# the latest date at which all four series can be joined cleanly.
SPLICE_DATE = pd.Timestamp("2016-12-31")

# MSCI index code used to extend the ex-US leg. Chosen on evidence, not on the
# name: over the identical window 1997-02..2016-12 its monthly returns track the
# core's own ex-US column with a 1.14% annualised tracking error, against 4.25%
# for both 899901 (ACWI ex USA) and 991000 (World ex USA). It is therefore the
# continuation that introduces the least discontinuity at the junction.
MSCI_EXUS_CODE = "664211"

# Records which source _exus_live() actually returned, so the provenance files
# name the series that was really used rather than the one we asked for.
EXUS_LIVE_USED = {"key": "msci_api_%s" % "664211",
                  "index": "MSCI ACWI ex USA IMI, gross total return, USD",
                  "provider": "MSCI (public API)",
                  "source": "index_code 664211"}

# Live sources used to extend each series past SPLICE_DATE.
# (label, index actually measured, provider, source identifier, loader)
LIVE_SOURCES = {
    "US": ("Yahoo Finance, ^SP500TR (S&P 500 Total Return index)",
           "S&P 500 Total Return", "Yahoo Finance", "^SP500TR",
           lambda: fetch_yahoo("^SP500TR", "1987-01-01")),
    "EXUS": ("MSCI public API, index %s (ACWX ETF fallback)" % MSCI_EXUS_CODE,
             "MSCI ACWI ex USA IMI, gross total return, USD",
             "MSCI (public API)", "index_code %s" % MSCI_EXUS_CODE,
             lambda: _exus_live()),
    "BOND": ("Yahoo Finance, AGG (iShares Core US Aggregate Bond ETF)",
             "Bloomberg US Aggregate Bond (via ETF, net of fees)",
             "Yahoo Finance", "AGG, dividend-adjusted price",
             lambda: fetch_yahoo("AGG", "2003-01-01")),
}

# The T-bill leg is NOT spliced. Kenneth French's RF series is a single
# continuous source from 1926 to today, and it reproduces the published CSV's
# T-bill column to 0.00 percentage points a year over 1970-2012. Where the two
# disagree -- 2013-2016, where the CSV switches to a mis-scaled 4-week bill and
# implies 0.95%/yr against a true 0.06% -- French is the one that is right.
# Using it throughout removes both a splice seam and a known defect.
TBILL_SOURCE = ("Kenneth French Data Library, F-F_Research_Data_Factors, "
                "RF column (1-month Treasury bill), 1926-07 to date")


def _exus_live():
    """Ex-US extension: MSCI's gross index first, the ACWX ETF as a fallback.

    MSCI's free endpoint is the right series conceptually -- a gross total
    return index, directly comparable with the gross indices used before 2017.
    But it is unmetered and throttles hard, and when throttled it returns 200
    with whole pages missing rather than an error.

    ACWX tracks the same index family, so it is a faithful substitute, with one
    documented bias: being a fund it is net of a 0.32% fee and of dividend
    withholding, so it understates the gross index by roughly half a point a
    year. That matters only for the 2017+ segment, and the build prints which
    one it used.
    """
    try:
        s = fetch_msci(MSCI_EXUS_CODE, 2015, date.today().year)
        needed = pd.date_range(SPLICE_DATE, s.index[-1], freq="ME")
        if not len(needed.difference(s.index)):
            return s
        print("          MSCI answered with %d gap(s) -- falling back to ACWX"
              % len(needed.difference(s.index)))
    except Exception as exc:  # noqa: BLE001
        print("          MSCI unavailable (%s) -- falling back to ACWX"
              % str(exc)[:60])
    EXUS_LIVE_USED.update(
        key="acwx_etf",
        index="MSCI ACWI ex USA via the ACWX ETF (net of fees and withholding)",
        provider="Yahoo Finance",
        source="ACWX, dividend-adjusted price")
    return fetch_yahoo("ACWX", "2008-01-01")


def splice(core, live, cut):
    """Extend ``core`` past ``cut`` with ``live``, rescaled to match at ``cut``.

    The two providers use unrelated index bases, so the live series is
    multiplied by the ratio of the two levels at the junction. Only levels are
    touched -- every monthly return on either side is preserved exactly.
    """
    core = core.dropna()
    core = core[core.index <= cut]
    live = live.dropna()

    if cut not in live.index:
        # Do NOT quietly fall back to an earlier junction: that would throw away
        # good core data and splice onto whatever the provider happened to
        # return. Refuse instead, and let the caller keep the core.
        raise ValueError(
            "live series does not cover the junction month %s (it runs %s to %s)"
            % (cut.date(), live.index[0].date(), live.index[-1].date()))

    tail = live[live.index > cut]
    if len(tail):
        # A throttled provider can return 200 with whole pages missing. Splicing
        # a gapped tail silently shortens the final dataset, because the join
        # across columns drops every month any one of them lacks.
        expected = pd.date_range(tail.index[0], tail.index[-1], freq="ME")
        missing = expected.difference(tail.index)
        if len(missing):
            raise ValueError(
                "live series has %d gap(s) after %s, first at %s"
                % (len(missing), cut.date(), missing[0].date()))

    scale = core.loc[cut] / live.loc[cut]
    return pd.concat([core, tail * scale]), (cut, scale, len(tail))


def build_panel():
    """Assemble the four series from source. Requires network access."""
    print("1. Historical core")
    core = fetch_gem_core(repair=True)
    repairs = [r for r in core.attrs.get("repairs", []) if r["kind"] == "material"]
    print("   %s -> %s (%d months), %d material repair(s) applied"
          % (core.index[0].date(), core.index[-1].date(), len(core), len(repairs)))

    print("\n2. Live extension sources")
    columns, notes, live_raw = {}, {}, {}
    for key, (label, _idx, _prov, _src, loader) in LIVE_SOURCES.items():
        print("   %-6s %s" % (key, label))
        try:
            live, origin = cached(key, loader, CACHE_DIR)
            live_raw[key] = live
            print("          %-5s %s -> %s (%d months)"
                  % (origin, live.index[0].date(), live.index[-1].date(),
                     len(live)))
        except Exception as exc:  # noqa: BLE001
            print("          UNAVAILABLE (%s)" % exc)
            print("          !! %s will stop at %s, truncating the whole dataset"
                  % (key, SPLICE_DATE.date()))
            columns[key] = core[key].dropna()
            notes[key] = None
            continue
        try:
            merged, info = splice(core[key], live, SPLICE_DATE)
        except ValueError as exc:
            print("          REFUSED to splice: %s" % exc)
            print("          -> keeping core only for %s" % key)
            columns[key] = core[key].dropna()
            notes[key] = None
            continue
        columns[key] = merged
        notes[key] = info
        cut, scale, n = info
        print("          spliced at %s (scale %.6f), +%d months"
              % (cut.date(), scale, n))

    print("\n3. T-bill leg (single continuous source, no splice)")
    print("   %s" % TBILL_SOURCE)
    rf = fetch_french("F-F_Research_Data_Factors")["RF"].dropna()
    tbill = compound(rf)
    # Keep the historical base level so the column stays comparable with the
    # earlier build; this is a rescale only and changes no return.
    anchor = core["TBILL"].dropna().index[0]
    tbill = tbill * (core["TBILL"].loc[anchor] / tbill.loc[anchor])
    columns["TBILL"] = tbill[tbill.index >= core.index[0]]
    print("   %s -> %s (%d months)"
          % (tbill.index[0].date(), tbill.index[-1].date(), len(tbill)))

    df = pd.DataFrame(columns).dropna()
    df.index.name = "Date"

    print("\n4. Assembled panel")
    print("   %s -> %s, %d months, %d columns"
          % (df.index[0].date(), df.index[-1].date(), len(df), df.shape[1]))

    expected = pd.date_range(df.index[0], df.index[-1], freq="ME")
    holes = expected.difference(df.index)
    if len(holes):
        raise SystemExit(
            "ABORT: %d month(s) missing from the panel, first at %s.\n"
            "Columns are joined on their common index, so any month a single "
            "source lacks disappears from all four. That is a truncated "
            "dataset, not a shorter sample. Re-run when the provider answers "
            "in full." % (len(holes), holes[0].date()))
    print("   continuity check: no missing month")
    return df, core, repairs, notes, live_raw


def write_outputs(df, core, repairs, notes, live_raw):
    """Write the dataset and every file derived from it."""
    df.to_csv(OUT_CSV, float_format=FLOAT_FMT)
    print("   wrote %s" % OUT_CSV)

    segments = build_segment_map(df)
    detailed = build_detailed(df, segments, repairs)
    detailed.to_csv(OUT_DETAILED, index=False, float_format=FLOAT_FMT)
    print("   wrote %s (%d rows, long format)" % (OUT_DETAILED, len(detailed)))

    comps = build_components(df, segments, live_raw)
    comps.to_csv(OUT_COMPONENTS, float_format=FLOAT_FMT)
    print("   wrote %s (%d columns, components + computed column)"
          % (OUT_COMPONENTS, comps.shape[1]))

    _write_sources(df, core, repairs, notes)
    print("   wrote %s" % os.path.join(DATA_DIR, "SOURCES.md"))
    _write_segments(df, segments)
    print("   wrote %s" % os.path.join(DATA_DIR, "SEGMENTS.md"))
    write_manifest(df)
    print("   wrote %s" % OUT_MANIFEST)

    print("\n   Annualised returns over the full sample, sanity check:")
    for col in df.columns:
        r = df[col].pct_change().dropna()
        cagr = (1 + r).prod() ** (12 / len(r)) - 1
        print("     %-6s %6.2f%%  (vol %5.2f%%)"
              % (col, cagr * 100, r.std() * 12 ** 0.5 * 100))


# --------------------------------------------------------------------------
# Freeze: the dataset is an artefact, not a build product
# --------------------------------------------------------------------------

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _fingerprint(df):
    """Per-column summary statistics, stored so a drift is legible, not just
    detected. A hash tells you something changed; these tell you what."""
    out = {}
    for col in df.columns:
        r = df[col].pct_change().dropna()
        out[col] = {
            "first_level": round(float(df[col].iloc[0]), 6),
            "last_level": round(float(df[col].iloc[-1]), 6),
            "cagr": round(float((1 + r).prod() ** (12 / len(r)) - 1), 8),
            "vol": round(float(r.std() * 12 ** 0.5), 8),
        }
    return out


def write_manifest(df):
    manifest = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rows": int(len(df)),
        "start": str(df.index[0].date()),
        "end": str(df.index[-1].date()),
        "columns": list(df.columns),
        "float_format": FLOAT_FMT,
        "sha256": _sha256(OUT_CSV),
        "fingerprint": _fingerprint(df),
    }
    with open(OUT_MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


def verify():
    """Offline check of the committed dataset against its manifest."""
    if not os.path.exists(OUT_CSV) or not os.path.exists(OUT_MANIFEST):
        raise SystemExit("missing %s or %s -- run with --rebuild"
                         % (OUT_CSV, OUT_MANIFEST))
    with open(OUT_MANIFEST, encoding="utf-8") as fh:
        m = json.load(fh)
    df = pd.read_csv(OUT_CSV, index_col="Date", parse_dates=True)

    print("Dataset : %s" % OUT_CSV)
    print("  frozen on    %s" % m["generated"])
    print("  period       %s -> %s (%d months)" % (m["start"], m["end"], m["rows"]))

    problems = []
    actual = _sha256(OUT_CSV)
    if actual != m["sha256"]:
        problems.append("sha256 %s expected, %s found" % (m["sha256"][:16], actual[:16]))
    if len(df) != m["rows"]:
        problems.append("%d rows expected, %d found" % (m["rows"], len(df)))
    for col, exp in m["fingerprint"].items():
        if col not in df.columns:
            problems.append("column %s missing" % col)
            continue
        r = df[col].pct_change().dropna()
        got = round(float((1 + r).prod() ** (12 / len(r)) - 1), 8)
        if abs(got - exp["cagr"]) > 1e-8:
            problems.append("%s: CAGR %.6f expected, %.6f found"
                            % (col, exp["cagr"], got))

    if problems:
        print("\n  FAILED:")
        for p in problems:
            print("    - %s" % p)
        raise SystemExit(1)
    print("  sha256       %s" % m["sha256"])
    print("\n  OK — the file is identical to its frozen version.")
    for col, exp in m["fingerprint"].items():
        print("    %-6s CAGR %6.2f%%  vol %5.2f%%"
              % (col, exp["cagr"] * 100, exp["vol"] * 100))


def assert_history_unchanged(existing, candidate, rtol=1e-5):
    """Refuse a refresh that would materially rewrite an already published month.

    Months already in the dataset are frozen: they have been audited, cited and
    committed. A provider revising its history, or a silent fallback to a
    different index, must surface as a refusal rather than as a quiet edit.

    The comparison is RELATIVE, not exact, because dividend-adjusted prices are
    not bit-reproducible: Yahoo re-derives its adjustment factors on every
    request, which moves a level of ~2000 by ~1e-4 in absolute terms (8e-8
    relative, measured up to 1.4e-6 on AGG). Requiring exact equality would
    flag that noise on every run and train the reader to ignore the guard.

    The threshold is 1e-5 relative -- 0.001%, a tenth of a basis point. That is
    about seven times the observed noise and two orders of magnitude below
    anything economically meaningful: the MSCI-to-ACWX substitution, by way of
    comparison, moved the series by roughly 0.5% a year.
    """
    shared = existing.index.intersection(candidate.index)
    old = existing.loc[shared]
    new = candidate.loc[shared].reindex(columns=old.columns)
    scale = old.abs().where(old.abs() > 0, 1.0)
    drift = (new - old).abs() / scale
    diff = drift > rtol
    if not diff.to_numpy().any():
        worst = float(drift.to_numpy().max()) if len(shared) else 0.0
        print("   largest drift over the history: %.1e (tolerance %.0e)"
              % (worst, rtol))
        return len(shared)

    print("\nREFUSED: the refresh would alter months already published.")
    rows = diff.any(axis=1)
    for date in existing.index[rows][:10]:
        for col in existing.columns:
            if diff.loc[date, col]:
                print("  %s  %-6s  %.6f -> %.6f"
                      % (date.date(), col, old.loc[date, col], new.loc[date, col]))
    total = int(rows.sum())
    if total > 10:
        print("  ... and %d further month(s)" % (total - 10))
    raise SystemExit(
        "\n%d months would be rewritten. The history is frozen: if the change "
        "is intended (a provider having revised its series, or a deliberate "
        "change of source), rerun with --rebuild --force and document it."
        % total)


def build_components(df, segments, live_raw):
    """Wide table laying each vendor component next to the series it feeds.

    Same idea as the published source file: one column per raw vendor series,
    then the computed column that chains them. Reading a row left to right, the
    computed column is exactly equal to whichever component was in force that
    month, so the splice can be checked by eye rather than taken on trust.

    Every component is rescaled onto the base of its own computed series. That
    is a change of unit only -- no monthly return is altered -- and it is what
    makes the columns comparable at all, since MSCI, Ibbotson and Yahoo each
    publish on an unrelated index base.
    """
    raw = fetch_gem_components()

    def blended(a, b, wa, wb):
        """Level series for a monthly-rebalanced blend of two level series."""
        r = wa * raw[a].pct_change() + wb * raw[b].pct_change()
        return compound(r.dropna())

    def chain(*parts):
        """Concatenate level series, each rescaled onto the previous one."""
        out = None
        for part in parts:
            part = part.dropna()
            if out is None:
                out = part
                continue
            overlap = out.index.intersection(part.index)
            if len(overlap):
                part = part * (out.loc[overlap[-1]] / part.loc[overlap[-1]])
                part = part[part.index > overlap[-1]]
            out = pd.concat([out, part])
        return out

    # (column name, level series, segments over which this component drives).
    # The segment list is what anchors the rescaling: a component is put on the
    # base of the computed series using the months where it is actually in
    # force, so the two columns coincide exactly there.
    specs = {
        "US": [
            ("US_ibbotson_large_cap", raw["Large Caps"], ["US-1"]),
            ("US_sp500_total_return",
             chain(raw["SP500TR"], live_raw.get("US")), ["US-2", "US-3"]),
        ],
        "EXUS": [
            ("EXUS_msci_world_ex_usa", raw["WORLD ex USA"], ["EXUS-1"]),
            ("EXUS_msci_acwi_ex_usa", raw["ACWI ex USA"], ["EXUS-2"]),
            ("EXUS_live_%s" % EXUS_LIVE_USED["key"],
             live_raw.get("EXUS"), ["EXUS-3"]),
        ],
        "BOND": [
            ("BOND_ibbotson_40treas_60corp",
             blended("Mid-Treasuries", "Mid-Corporate Bonds", 0.40, 0.60),
             ["BOND-1"]),
            ("BOND_barclays_us_agg", raw["AGG"], ["BOND-2"]),
            ("BOND_agg_etf", live_raw.get("BOND"), ["BOND-3"]),
        ],
        # Never drives anything: the published T-bill column is shown only so
        # that its 2013-2016 divergence from the retained series is visible.
        "TBILL": [
            ("TBILL_csv_published_not_used", raw["Spliced M+R"], []),
        ],
    }

    out = pd.DataFrame(index=df.index)
    for series in ["US", "EXUS", "BOND", "TBILL"]:
        target = df[series]
        segs = segments[segments["series"] == series]
        active = _active_labels(df.index, segs)

        for name, comp, drives in specs.get(series, []):
            if comp is None:
                continue
            comp = comp.dropna().reindex(df.index)
            anchor = active.isin(drives) & comp.notna() & target.notna()
            if not anchor.any():                      # never drives: whole overlap
                anchor = comp.notna() & target.notna()
            if not anchor.any():
                continue
            out[name] = comp * float((target[anchor] / comp[anchor]).median())

        out[series] = target
        out["%s_source" % series] = active
    return out


def _active_labels(index, segs):
    """Which segment is in force for each month."""
    labels = pd.Series("", index=index, dtype=object)
    for _, s in segs.iterrows():
        labels[(index >= s["start"]) & (index <= s["end"])] = s["segment"]
    return labels


def build_segment_map(df):
    """One row per (series, contiguous vendor segment) covering the whole sample.

    Combines the historical boundaries recovered from the source file with the
    live extension used past SPLICE_DATE.
    """
    end = df.index[-1]
    rows = []
    for key, segs in GEM_SEGMENTS.items():
        if key == "TBILL":
            continue                       # rebuilt from a single source below
        for i, (start, stop, index_name, provider, source) in enumerate(segs, 1):
            rows.append({
                "series": key,
                "segment": "%s-%d" % (key, i),
                "start": pd.Timestamp(start),
                "end": pd.Timestamp(stop),
                "index_name": index_name,
                "provider": provider,
                "source_series": source,
                "origin": "historical core (redistributed CSV)",
            })
        _label, index_name, provider, source, _loader = LIVE_SOURCES[key]
        if key == "EXUS":
            index_name = EXUS_LIVE_USED["index"]
            provider = EXUS_LIVE_USED["provider"]
            source = EXUS_LIVE_USED["source"]
        rows.append({
            "series": key,
            "segment": "%s-%d" % (key, len(segs) + 1),
            "start": SPLICE_DATE + pd.offsets.MonthEnd(1),
            "end": end,
            "index_name": index_name,
            "provider": provider,
            "source_series": source,
            "origin": "extension (live source)",
        })
    rows.append({
        "series": "TBILL",
        "segment": "TBILL-1",
        "start": df.index[0],
        "end": end,
        "index_name": "US 1-month Treasury bill",
        "provider": "Kenneth French Data Library",
        "source_series": "F-F_Research_Data_Factors, RF column",
        "origin": "single continuous source (no splice)",
    })
    seg = pd.DataFrame(rows).sort_values(["series", "start"]).reset_index(drop=True)
    # Clip to the sample actually produced.
    seg["start"] = seg["start"].clip(lower=df.index[0])
    seg["end"] = seg["end"].clip(upper=end)
    return seg[seg["start"] <= seg["end"]].reset_index(drop=True)


def build_detailed(df, segments, repairs):
    """Long-format dataset: one row per (date, series) carrying its provenance."""
    repaired = {(r["series"], pd.Timestamp(r["date"])) for r in repairs}
    out = []
    for series in df.columns:
        level = df[series]
        ret = level.pct_change()
        segs = segments[segments["series"] == series]
        for date in df.index:
            match = segs[(segs["start"] <= date) & (segs["end"] >= date)]
            row = match.iloc[0] if len(match) else None
            out.append({
                "date": date.date(),
                "series": series,
                "level": level.loc[date],
                "monthly_return": ret.loc[date],
                "index_name": row["index_name"] if row is not None else "",
                "provider": row["provider"] if row is not None else "",
                "source_series": row["source_series"] if row is not None else "",
                "segment": row["segment"] if row is not None else "",
                "origin": row["origin"] if row is not None else "",
                "repaired": int((series, date) in repaired),
            })
    detailed = pd.DataFrame(out)
    return detailed.sort_values(["date", "series"]).reset_index(drop=True)


def _write_segments(df, segments):
    """Human-readable provenance map -- the table to reproduce in the paper."""
    out = []
    out.append("# Provenance map, segment by segment\n")
    out.append("*Generated automatically by `src/build_dataset.py`.*\n")
    out.append("Every series in the dataset is a **chain of series from "
               "different providers**. This document states, for each month, "
               "which real index is actually being measured.\n")
    out.append("The boundaries of the historical core are not taken from any "
               "documentation: they were **recovered from the file itself**, "
               "by searching for the contiguous range over which the ratio of "
               "spliced series to component is constant, then confirmed by the "
               "month in which the incoming component is rebased to 100.\n")

    labels = {"US": "US equity", "EXUS": "Non-US equity",
              "BOND": "US aggregate bonds", "TBILL": "Cash (T-bills)"}
    for series in ["US", "EXUS", "BOND", "TBILL"]:
        segs = segments[segments["series"] == series]
        if segs.empty:
            continue
        out.append("\n## `%s` — %s\n" % (series, labels.get(series, series)))
        out.append("| Segment | Start | End | Months | Index actually measured | Provider | Source series |")
        out.append("|---|---|---|---:|---|---|---|")
        for _, r in segs.iterrows():
            months = (r["end"].to_period("M") - r["start"].to_period("M")).n + 1
            out.append("| `%s` | %s | %s | %d | %s | %s | %s |"
                       % (r["segment"], r["start"].date(), r["end"].date(),
                          months, r["index_name"], r["provider"],
                          r["source_series"]))

    out.append("\n## What these splices imply\n")
    out.append("- **`EXUS` changes universe in 1988**: before, MSCI World ex "
               "USA covers developed markets only; after, MSCI ACWI ex USA "
               "adds emerging markets (roughly a quarter of the index today). "
               "The series is therefore not homogeneous: volatility and "
               "geographic composition change at that date. This is the "
               "construction Antonacci himself uses, and it reflects what an "
               "investor could actually buy at each date, but it must be "
               "disclosed in the paper.\n")
    out.append("- **`BOND` changes nature in 1976**: before, a 40/60 blend of "
               "intermediate Treasuries and corporates; after, the Bloomberg "
               "Barclays US Aggregate, which includes securitised debt and "
               "carries a different duration. The Aggregate index does not "
               "exist before January 1976 — a limit of the real world, not a "
               "choice.\n")
    out.append("- **`US` does not change index in 2013**, only provider: the "
               "Ibbotson Large Cap series and the S&P 500 Total Return series "
               "measure the same index. The handover has no economic "
               "content.\n")
    out.append("- **`TBILL` has no splice at all**: a single continuous source "
               "from 1926 to today.\n")

    out.append("\n## Checking the splices yourself\n")
    out.append("`gem_dataset_components.csv` follows the format of the source "
               "file: **one column per vendor series, then the computed column "
               "that chains them**, plus a `<series>_source` column naming the "
               "segment active in that month.\n")
    out.append("Each component is rescaled to the computed series (a change of "
               "unit only, no monthly return is altered), so that reading a "
               "row from left to right the computed column is **exactly "
               "equal** to the active component. Example at the 1988 "
               "splice:\n")
    out.append("```")
    out.append("Date        World ex USA   ACWI ex USA      EXUS   source")
    out.append("1987-12-31       100.000       100.000   100.000   EXUS-1")
    out.append("1988-01-31       101.572       101.680   101.680   EXUS-2   <- switch")
    out.append("```")
    out.append("\nResidual differences between the computed column and the "
               "active component: nil on segments carried over as they stand, "
               "and of the order of 1e-5 on segments before 1988, where the "
               "published file carries only three decimals. The one exception "
               "is `BOND-1` (3.7e-3): the 40/60 blend is **reconstructed** "
               "there by compounding monthly returns, and the rounding of the "
               "source file accumulates over 73 months.\n")
    out.append("The column `TBILL_csv_published_not_used` is present but "
               "unused: it makes visible the 2013-2016 divergence that led to "
               "abandoning that column in favour of Kenneth French's.\n")

    with open(os.path.join(DATA_DIR, "SEGMENTS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


def _write_sources(df, core, repairs, notes):
    """Provenance sheet -- this is what gets cited in the paper."""
    out = []
    out.append("# Data provenance\n")
    out.append("*Generated automatically by `src/build_dataset.py`.*\n")
    out.append("Dataset: `data/gem_dataset.csv` — "
               "**%s → %s**, %d monthly observations, "
               "total-return index levels, USD.\n"
               % (df.index[0].date(), df.index[-1].date(), len(df)))

    out.append("\n## Historical core (%s → %s)\n"
               % (core.index[0].date(), SPLICE_DATE.date()))
    out.append("The file `msci_all_gross.csv` from the "
               "[alexjansenhome/GEM](https://github.com/alexjansenhome/GEM) "
               "repository, which reproduces Antonacci's construction.\n")
    out.append("Exact URL: `%s`\n" % GEM_CSV_URL)
    out.append("| Key | Original column | Contents |")
    out.append("|---|---|---|")
    for key, (col, desc) in GEM_COLUMNS.items():
        out.append("| `%s` | `%s` | %s |" % (key, col, desc))
    out.append("\nThis file is a **redistribution**, not a primary source. It "
               "is audited against nine independent references in "
               "[`VALIDATION.md`](VALIDATION.md).\n")

    if repairs:
        out.append("\n### Repair applied\n")
        out.append("%d observation(s) of the cash leg had lost their leading "
                   "digit in the published file. Repaired by taking the "
                   "geometric mean of the neighbouring months:\n" % len(repairs))
        out.append("| Month | Published | Used |")
        out.append("|---|---:|---:|")
        for r in repairs:
            out.append("| %s | %.3f | %.3f |"
                       % (r["date"].date(), r["observed"], r["repaired"]))

    out.append("\n## Extension (%s → %s)\n"
               % (SPLICE_DATE.date(), df.index[-1].date()))
    out.append("| Key | Source | Junction | Scale factor | Months added |")
    out.append("|---|---|---|---:|---:|")
    for key, (label, _idx, _prov, _src, _loader) in LIVE_SOURCES.items():
        info = notes.get(key)
        if info is None:
            out.append("| `%s` | %s | — | — | 0 |" % (key, label))
        else:
            cut, scale, n = info
            out.append("| `%s` | %s | %s | %.6f | %d |"
                       % (key, label, cut.date(), scale, n))
    out.append("\nThe splice is a **change of base only**: the live series is "
               "multiplied by a constant so that it coincides with the core in "
               "the junction month. No monthly return is altered, either "
               "before or after the junction.\n")

    out.append("\n## Reproducing\n")
    out.append("```bash\npython src/build_dataset.py     "
               "# rebuilds data/gem_dataset.csv\n"
               "python src/validate_dataset.py  "
               "# regenerates data/VALIDATION.md\n```\n")


    with open(os.path.join(DATA_DIR, "SOURCES.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


USAGE = """\
Usage: python src/build_dataset.py [--verify | --refresh | --rebuild [--force]]

  --verify   (default) checks the frozen dataset offline against its manifest.
             Writes nothing, calls nothing.
  --refresh  ADDS new months only. Refuses to write if a month already
             published changes value.
  --rebuild  rebuilds everything from the sources. Refuses to overwrite an
             existing dataset without --force.

The dataset is a versioned artefact, not a build output: `gem_backtest.py`
reads the CSV and never touches the network.
"""


def main():
    args = sys.argv[1:]
    unknown = [a for a in args if a not in
               ("--verify", "--refresh", "--rebuild", "--force", "-h", "--help")]
    if unknown or "-h" in args or "--help" in args:
        if unknown:
            print("unknown argument: %s\n" % " ".join(unknown))
        raise SystemExit(USAGE)

    os.makedirs(DATA_DIR, exist_ok=True)
    force = "--force" in args

    if "--rebuild" in args:
        if os.path.exists(OUT_CSV) and not force:
            raise SystemExit(
                "%s already exists.\nThe dataset is frozen: use --refresh to "
                "add new months, or --rebuild --force to rewrite everything "
                "deliberately." % OUT_CSV)
        print("MODE rebuild — full reconstruction from the sources\n")
        df, core, repairs, notes, live_raw = build_panel()
        print("\n5. Writing")
        write_outputs(df, core, repairs, notes, live_raw)
        return

    if "--refresh" in args:
        print("MODE refresh — new months only\n")
        if not os.path.exists(OUT_CSV):
            raise SystemExit("%s missing: use --rebuild" % OUT_CSV)
        existing = pd.read_csv(OUT_CSV, index_col="Date", parse_dates=True)
        df, core, repairs, notes, live_raw = build_panel()

        print("\n5. Immutability check")
        shared = assert_history_unchanged(existing, df)
        added = df.index.difference(existing.index)
        print("   %d months already published, unchanged" % shared)
        if not len(added):
            print("   no new month — nothing to write")
            return
        print("   %d months added: %s -> %s"
              % (len(added), added[0].date(), added[-1].date()))

        # Append-only in the literal sense: published rows are carried over
        # verbatim from the committed file, never re-derived. Only the new
        # months come from this build.
        df = pd.concat([existing, df.loc[added]]).sort_index()
        df.index.name = "Date"

        print("\n6. Writing")

        write_outputs(df, core, repairs, notes, live_raw)
        return

    verify()


if __name__ == "__main__":
    main()
