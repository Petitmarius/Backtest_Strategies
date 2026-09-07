# GEM dataset — 1969-12 to 2026-07

Four monthly series of **total-return index levels, in USD**, built entirely
from free sources.

**The dataset is frozen.** It is not a build output waiting to be regenerated:
it is a versioned artefact with a fingerprint. You can use it as it stands, with
no network, no API key and nothing to rebuild.

## Using the dataset

```python
import pandas as pd
px = pd.read_csv("data/gem_dataset.csv", index_col="Date", parse_dates=True)
```

| Column | Contents |
|---|---|
| `US` | US equity |
| `EXUS` | Non-US equity |
| `BOND` | US aggregate bonds |
| `TBILL` | One-month Treasury bills |

These are **index levels**, not returns: `px.pct_change()` gives the monthly
returns. The levels are meaningless in absolute terms — each provider has its
own base — only their movements carry information.

## The four files

| File | What it is for |
|---|---|
| `gem_dataset.csv` | **The dataset.** Wide format, 4 columns. This is what the backtest reads. |
| `gem_dataset_components.csv` | Each vendor series beside the computed column, so a splice can be checked by eye. |
| `gem_dataset_detailed.csv` | Long format: one row per (date, series), with its provenance. |
| `gem_dataset.manifest.json` | SHA-256 fingerprint, row count, period, CAGR and volatility per column. |

Plus three documents: [`SEGMENTS.md`](SEGMENTS.md) (which index is measured over
which period), [`SOURCES.md`](SOURCES.md) (provenance) and
[`VALIDATION.md`](VALIDATION.md) (the audit).

## Checking that it is intact

```bash
python src/build_dataset.py          # --verify is the default mode
```

An offline check of the file against its manifest: hash, row count, and the CAGR
of each column. It writes nothing and calls nothing. This is what makes the
figures in the paper checkable by a third party.

## Updating it

```bash
python src/build_dataset.py --refresh
```

**Adds new months only.** Months already published are copied verbatim from the
existing file, never recomputed. Should a source ever return different values
for a month already published, the script **refuses to write** and prints the
discrepancies.

Rebuilding everything from scratch takes an explicit gesture:

```bash
python src/build_dataset.py --rebuild --force
```

Use it only when a change to the history is intended and documented — a provider
having revised its series, for instance.

## What to know before using it

**The series change index over time.** `EXUS` measures MSCI World ex USA until
1987 and MSCI ACWI ex USA from 1988: the universe changes, emerging markets
enter. `BOND` is an Ibbotson blend until 1975 and then the Bloomberg Barclays US
Aggregate, which does not exist before January 1976. These splices are not
conveniences — they reflect what actually existed at each date — but they must
be disclosed in any published work. The detail is in
[`SEGMENTS.md`](SEGMENTS.md).

**The historical core is a redistribution, not a primary source.** It comes from
the file `msci_all_gross.csv` in the
[alexjansenhome/GEM](https://github.com/alexjansenhome/GEM) repository, which
reproduces Antonacci's construction. That is why it is set against nine
independent references in [`VALIDATION.md`](VALIDATION.md) — an audit which did
in fact turn up a genuine defect, since repaired.

**No paid data.** Everything comes from Yahoo Finance, MSCI's public index
endpoint and the Kenneth French Data Library.
