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

import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_sources import (  # noqa: E402
    GEM_COLUMNS,
    GEM_SEGMENTS,
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

# Live sources used to extend each series past SPLICE_DATE.
# (label, index actually measured, provider, source identifier, loader)
LIVE_SOURCES = {
    "US": ("Yahoo Finance, ^SP500TR (S&P 500 Total Return index)",
           "S&P 500 Total Return", "Yahoo Finance", "^SP500TR",
           lambda: fetch_yahoo("^SP500TR", "1987-01-01")),
    "EXUS": ("MSCI public API, index %s, gross total return, USD"
             % MSCI_EXUS_CODE,
             "MSCI ACWI ex USA IMI, gross total return, USD",
             "MSCI (API publique)", "index_code %s" % MSCI_EXUS_CODE,
             lambda: fetch_msci(MSCI_EXUS_CODE, 1997, date.today().year)),
    "BOND": ("Yahoo Finance, AGG (iShares Core US Aggregate Bond ETF)",
             "Bloomberg US Aggregate Bond (via ETF, net de frais)",
             "Yahoo Finance", "AGG, cours ajusté des dividendes",
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
        available = live.index[live.index <= cut]
        if len(available) == 0:
            print("    no overlap, keeping core only")
            return core, None
        cut = available[-1]

    scale = core.loc[cut] / live.loc[cut]
    tail = live[live.index > cut] * scale
    return pd.concat([core, tail]), (cut, scale, len(tail))


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("1. Historical core")
    core = fetch_gem_core(repair=True)
    repairs = [r for r in core.attrs.get("repairs", []) if r["kind"] == "material"]
    print("   %s -> %s (%d months), %d material repair(s) applied"
          % (core.index[0].date(), core.index[-1].date(), len(core), len(repairs)))

    print("\n2. Live extension sources")
    columns, notes = {}, {}
    for key, (label, _idx, _prov, _src, loader) in LIVE_SOURCES.items():
        print("   %-6s %s" % (key, label))
        try:
            live = loader()
            print("          fetched %s -> %s (%d months)"
                  % (live.index[0].date(), live.index[-1].date(), len(live)))
        except Exception as exc:  # noqa: BLE001
            print("          FAILED (%s) -- keeping historical core only" % exc)
            columns[key] = core[key].dropna()
            notes[key] = None
            continue
        merged, info = splice(core[key], live, SPLICE_DATE)
        columns[key] = merged
        notes[key] = info
        if info:
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

    print("\n4. Master dataset")
    print("   %s -> %s, %d months, %d columns"
          % (df.index[0].date(), df.index[-1].date(), len(df), df.shape[1]))
    df.to_csv(OUT_CSV, float_format="%.6f")
    print("   wrote %s" % OUT_CSV)

    segments = build_segment_map(df)
    detailed = build_detailed(df, segments, repairs)
    detailed.to_csv(OUT_DETAILED, index=False, float_format="%.6f")
    print("   wrote %s (%d rows, long format)" % (OUT_DETAILED, len(detailed)))

    _write_sources(df, core, repairs, notes)
    print("   wrote %s" % os.path.join(DATA_DIR, "SOURCES.md"))
    _write_segments(df, segments)
    print("   wrote %s" % os.path.join(DATA_DIR, "SEGMENTS.md"))

    print("\n   Annualised returns over the full sample, sanity check:")
    for col in df.columns:
        r = df[col].pct_change().dropna()
        cagr = (1 + r).prod() ** (12 / len(r)) - 1
        print("     %-6s %6.2f%%  (vol %5.2f%%)"
              % (col, cagr * 100, r.std() * 12 ** 0.5 * 100))


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
                "origin": "socle historique (CSV redistribué)",
            })
        _label, index_name, provider, source, _loader = LIVE_SOURCES[key]
        rows.append({
            "series": key,
            "segment": "%s-%d" % (key, len(segs) + 1),
            "start": SPLICE_DATE + pd.offsets.MonthEnd(1),
            "end": end,
            "index_name": index_name,
            "provider": provider,
            "source_series": source,
            "origin": "prolongement (source live)",
        })
    rows.append({
        "series": "TBILL",
        "segment": "TBILL-1",
        "start": df.index[0],
        "end": end,
        "index_name": "US 1-month Treasury bill",
        "provider": "Kenneth French Data Library",
        "source_series": "F-F_Research_Data_Factors, colonne RF",
        "origin": "source unique continue (aucun raccord)",
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
    out.append("# Carte de provenance, segment par segment\n")
    out.append("*Généré automatiquement par `src/build_dataset.py`.*\n")
    out.append("Chaque série du jeu de données est un **enchaînement de séries "
               "de fournisseurs différents**. Ce document dit, pour chaque mois, "
               "quel indice réel est effectivement mesuré.\n")
    out.append("Les bornes du socle historique ne sont pas reprises d'une "
               "documentation : elles ont été **retrouvées dans le fichier "
               "lui-même**, en cherchant la plage contiguë sur laquelle le "
               "rapport série épissée / composante est constant, puis "
               "confirmées par le mois où la composante entrante est rebasée "
               "à 100.\n")

    labels = {"US": "Actions américaines", "EXUS": "Actions hors États-Unis",
              "BOND": "Obligations agrégées US", "TBILL": "Monétaire (T-bills)"}
    for series in ["US", "EXUS", "BOND", "TBILL"]:
        segs = segments[segments["series"] == series]
        if segs.empty:
            continue
        out.append("\n## `%s` — %s\n" % (series, labels.get(series, series)))
        out.append("| Segment | Début | Fin | Mois | Indice réellement mesuré | Fournisseur | Série source |")
        out.append("|---|---|---|---:|---|---|---|")
        for _, r in segs.iterrows():
            months = (r["end"].to_period("M") - r["start"].to_period("M")).n + 1
            out.append("| `%s` | %s | %s | %d | %s | %s | %s |"
                       % (r["segment"], r["start"].date(), r["end"].date(),
                          months, r["index_name"], r["provider"],
                          r["source_series"]))

    out.append("\n## Ce que ces raccords impliquent\n")
    out.append("- **`EXUS` change d'univers en 1988** : avant, MSCI World ex USA "
               "ne couvre que les marchés développés ; après, MSCI ACWI ex USA "
               "ajoute les marchés émergents (environ un quart de l'indice "
               "aujourd'hui). La série n'est donc pas homogène : la volatilité "
               "et la composition géographique changent à cette date. "
               "C'est la construction retenue par Antonacci lui-même, et elle "
               "reflète ce qu'un investisseur pouvait réellement acheter à "
               "chaque époque, mais elle doit être signalée dans le paper.\n")
    out.append("- **`BOND` change de nature en 1976** : avant, un mélange "
               "40/60 Treasuries/corporates intermédiaires ; après, le "
               "Bloomberg Barclays US Aggregate, qui inclut du titrisé et une "
               "duration différente. L'indice Aggregate n'existe pas avant "
               "janvier 1976 — c'est une limite du monde réel, pas un choix.\n")
    out.append("- **`US` ne change pas d'indice en 2013**, seulement de "
               "fournisseur : la série Ibbotson Large Cap et le S&P 500 Total "
               "Return mesurent le même indice. Le raccord est sans effet "
               "économique.\n")
    out.append("- **`TBILL` ne comporte aucun raccord** : une seule source "
               "continue de 1926 à aujourd'hui.\n")

    with open(os.path.join(DATA_DIR, "SEGMENTS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


def _write_sources(df, core, repairs, notes):
    """Provenance sheet -- this is what gets cited in the paper."""
    out = []
    out.append("# Provenance des données\n")
    out.append("*Généré automatiquement par `src/build_dataset.py`.*\n")
    out.append("Jeu de données : `data/gem_dataset.csv` — "
               "**%s → %s**, %d observations mensuelles, "
               "niveaux d'indices en rendement total, USD.\n"
               % (df.index[0].date(), df.index[-1].date(), len(df)))

    out.append("\n## Socle historique (%s → %s)\n"
               % (core.index[0].date(), SPLICE_DATE.date()))
    out.append("Fichier `msci_all_gross.csv` du dépôt "
               "[alexjansenhome/GEM](https://github.com/alexjansenhome/GEM), "
               "qui reproduit la construction d'Antonacci.\n")
    out.append("URL exacte : `%s`\n" % GEM_CSV_URL)
    out.append("| Clé | Colonne d'origine | Contenu |")
    out.append("|---|---|---|")
    for key, (col, desc) in GEM_COLUMNS.items():
        out.append("| `%s` | `%s` | %s |" % (key, col, desc))
    out.append("\nCe fichier est une **redistribution**, pas une source "
               "primaire. Il est audité contre neuf références indépendantes "
               "dans [`VALIDATION.md`](VALIDATION.md).\n")

    if repairs:
        out.append("\n### Correction appliquée\n")
        out.append("%d observation(s) de la jambe monétaire avaient perdu leur "
                   "chiffre de tête dans le fichier publié. Corrigées par "
                   "moyenne géométrique des mois voisins :\n" % len(repairs))
        out.append("| Mois | Publié | Retenu |")
        out.append("|---|---:|---:|")
        for r in repairs:
            out.append("| %s | %.3f | %.3f |"
                       % (r["date"].date(), r["observed"], r["repaired"]))

    out.append("\n## Prolongement (%s → %s)\n"
               % (SPLICE_DATE.date(), df.index[-1].date()))
    out.append("| Clé | Source | Raccord | Facteur d'échelle | Mois ajoutés |")
    out.append("|---|---|---|---:|---:|")
    for key, (label, _idx, _prov, _src, _loader) in LIVE_SOURCES.items():
        info = notes.get(key)
        if info is None:
            out.append("| `%s` | %s | — | — | 0 |" % (key, label))
        else:
            cut, scale, n = info
            out.append("| `%s` | %s | %s | %.6f | %d |"
                       % (key, label, cut.date(), scale, n))
    out.append("\nLe raccord est un **changement de base uniquement** : la "
               "série live est multipliée par une constante pour coïncider avec "
               "le socle au mois de jonction. Aucun rendement mensuel n'est "
               "modifié, ni avant ni après le raccord.\n")

    out.append("\n## Reproduire\n")
    out.append("```bash\npython src/build_dataset.py     "
               "# reconstruit data/gem_dataset.csv\n"
               "python src/validate_dataset.py  "
               "# régénère data/VALIDATION.md\n```\n")

    with open(os.path.join(DATA_DIR, "SOURCES.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
