# Data provenance

*Generated automatically by `src/build_dataset.py`.*

Dataset: `data/gem_dataset.csv` — **1969-12-31 → 2026-07-31**, 680 monthly observations, total-return index levels, USD.


## Historical core (1969-12-31 → 2016-12-31)

The file `msci_all_gross.csv` from the [alexjansenhome/GEM](https://github.com/alexjansenhome/GEM) repository, which reproduces Antonacci's construction.

Exact URL: `https://raw.githubusercontent.com/alexjansenhome/GEM/master/msci_all_gross.csv`

| Key | Original column | Contents |
|---|---|---|
| `US` | `Spliced H+G` | Ibbotson US Large Cap TR spliced to S&P 500 Total Return (Yahoo) |
| `EXUS` | `Spliced C and D` | MSCI World ex USA gross TR spliced to MSCI ACWI ex USA gross TR |
| `BOND` | `Spliced F+40%J+60%K` | 40% Ibbotson Intermediate Treasuries + 60% Ibbotson Intermediate Corporates, spliced to Bloomberg Barclays US Aggregate TR |
| `TBILL` | `Spliced M+R` | Ibbotson 30-day T-bills spliced to FRED 4-week T-bill |

This file is a **redistribution**, not a primary source. It is audited against nine independent references in [`VALIDATION.md`](VALIDATION.md).


### Repair applied

3 observation(s) of the cash leg had lost their leading digit in the published file. Repaired by taking the geometric mean of the neighbouring months:

| Month | Published | Used |
|---|---:|---:|
| 1990-11-30 | 0.366 | 10.368 |
| 1991-11-30 | 0.970 | 10.970 |
| 1992-11-30 | 1.366 | 11.369 |

## Extension (2016-12-31 → 2026-07-31)

| Key | Source | Junction | Scale factor | Months added |
|---|---|---|---:|---:|
| `US` | Yahoo Finance, ^SP500TR (S&P 500 Total Return index) | 2016-12-31 | 1.000000 | 117 |
| `EXUS` | MSCI public API, index 664211 (ACWX ETF fallback) | 2016-12-31 | 0.471889 | 116 |
| `BOND` | Yahoo Finance, AGG (iShares Core US Aggregate Bond ETF) | 2016-12-31 | 24.131483 | 117 |

The splice is a **change of base only**: the live series is multiplied by a constant so that it coincides with the core in the junction month. No monthly return is altered, either before or after the junction.


## Reproducing

```bash
python src/build_dataset.py     # rebuilds data/gem_dataset.csv
python src/validate_dataset.py  # regenerates data/VALIDATION.md
```

