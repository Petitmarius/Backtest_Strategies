# Provenance map, segment by segment

*Generated automatically by `src/build_dataset.py`.*

Every series in the dataset is a **chain of series from different providers**. This document states, for each month, which real index is actually being measured.

The boundaries of the historical core are not taken from any documentation: they were **recovered from the file itself**, by searching for the contiguous range over which the ratio of spliced series to component is constant, then confirmed by the month in which the incoming component is rebased to 100.


## `US` — US equity

| Segment | Start | End | Months | Index actually measured | Provider | Source series |
|---|---|---|---:|---|---|---|
| `US-1` | 1969-12-31 | 2012-12-31 | 517 | Ibbotson US Large Cap total return | Morningstar / Ibbotson SBBI | Large Caps (col. H) |
| `US-2` | 2013-01-31 | 2016-12-31 | 48 | S&P 500 Total Return | Yahoo Finance | SP500TR (col. G) |
| `US-3` | 2017-01-31 | 2026-07-31 | 115 | S&P 500 Total Return | Yahoo Finance | ^SP500TR |

## `EXUS` — Non-US equity

| Segment | Start | End | Months | Index actually measured | Provider | Source series |
|---|---|---|---:|---|---|---|
| `EXUS-1` | 1969-12-31 | 1987-12-31 | 217 | MSCI World ex USA, gross total return, USD | MSCI | WORLD ex USA (col. C) |
| `EXUS-2` | 1988-01-31 | 2016-12-31 | 348 | MSCI ACWI ex USA, gross total return, USD | MSCI | ACWI ex USA (col. D) |
| `EXUS-3` | 2017-01-31 | 2026-07-31 | 115 | MSCI ACWI ex USA IMI, gross total return, USD | MSCI (public API) | index_code 664211 |

## `BOND` — US aggregate bonds

| Segment | Start | End | Months | Index actually measured | Provider | Source series |
|---|---|---|---:|---|---|---|
| `BOND-1` | 1969-12-31 | 1975-12-31 | 73 | 40% Ibbotson Intermediate Treasuries + 60% Ibbotson Intermediate Corporates, rebalanced monthly | Morningstar / Ibbotson SBBI | Mid-Treasuries + Mid-Corporate (col. J, K) |
| `BOND-2` | 1976-01-31 | 2016-12-31 | 492 | Bloomberg Barclays US Aggregate Bond, total return | Morningstar | AGG (col. F) |
| `BOND-3` | 2017-01-31 | 2026-07-31 | 115 | Bloomberg US Aggregate Bond (via ETF, net of fees) | Yahoo Finance | AGG, dividend-adjusted price |

## `TBILL` — Cash (T-bills)

| Segment | Start | End | Months | Index actually measured | Provider | Source series |
|---|---|---|---:|---|---|---|
| `TBILL-1` | 1969-12-31 | 2026-07-31 | 680 | US 1-month Treasury bill | Kenneth French Data Library | F-F_Research_Data_Factors, RF column |

## What these splices imply

- **`EXUS` changes universe in 1988**: before, MSCI World ex USA covers developed markets only; after, MSCI ACWI ex USA adds emerging markets (roughly a quarter of the index today). The series is therefore not homogeneous: volatility and geographic composition change at that date. This is the construction Antonacci himself uses, and it reflects what an investor could actually buy at each date, but it must be disclosed in the paper.

- **`BOND` changes nature in 1976**: before, a 40/60 blend of intermediate Treasuries and corporates; after, the Bloomberg Barclays US Aggregate, which includes securitised debt and carries a different duration. The Aggregate index does not exist before January 1976 — a limit of the real world, not a choice.

- **`US` does not change index in 2013**, only provider: the Ibbotson Large Cap series and the S&P 500 Total Return series measure the same index. The handover has no economic content.

- **`TBILL` has no splice at all**: a single continuous source from 1926 to today.


## Checking the splices yourself

`gem_dataset_components.csv` follows the format of the source file: **one column per vendor series, then the computed column that chains them**, plus a `<series>_source` column naming the segment active in that month.

Each component is rescaled to the computed series (a change of unit only, no monthly return is altered), so that reading a row from left to right the computed column is **exactly equal** to the active component. Example at the 1988 splice:

```
Date        World ex USA   ACWI ex USA      EXUS   source
1987-12-31       100.000       100.000   100.000   EXUS-1
1988-01-31       101.572       101.680   101.680   EXUS-2   <- switch
```

Residual differences between the computed column and the active component: nil on segments carried over as they stand, and of the order of 1e-5 on segments before 1988, where the published file carries only three decimals. The one exception is `BOND-1` (3.7e-3): the 40/60 blend is **reconstructed** there by compounding monthly returns, and the rounding of the source file accumulates over 73 months.

The column `TBILL_csv_published_not_used` is present but unused: it makes visible the 2013-2016 divergence that led to abandoning that column in favour of Kenneth French's.

