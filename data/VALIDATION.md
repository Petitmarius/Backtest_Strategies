# Reliability audit of the historical dataset

*Generated automatically by `src/validate_dataset.py` — do not edit by hand.*

Source audited: `msci_all_gross.csv` ([alexjansenhome/GEM](https://github.com/alexjansenhome/GEM)), **1969-12-31 → 2017-05-31** (570 months).


## 1. Columns used

| Key | CSV column | Contents |
|---|---|---|
| `US` | `Spliced H+G` | Ibbotson US Large Cap TR spliced to S&P 500 Total Return (Yahoo) |
| `EXUS` | `Spliced C and D` | MSCI World ex USA gross TR spliced to MSCI ACWI ex USA gross TR |
| `BOND` | `Spliced F+40%J+60%K` | 40% Ibbotson Intermediate Treasuries + 60% Ibbotson Intermediate Corporates, spliced to Bloomberg Barclays US Aggregate TR |
| `TBILL` | `Spliced M+R` | Ibbotson 30-day T-bills spliced to FRED 4-week T-bill |

## 2. Comparison against independent sources

Compared in **monthly returns** (index levels are not comparable across providers: different bases and reference dates). `TE` = annualised tracking error of the return difference.

| Series | Independent reference | Period | Months | Corr. | Ann. TE | Audited CAGR | Reference CAGR | Gap |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `BOND` | Vanguard Total Bond Market Index (Yahoo VBMFX) | 1987-01-31 → 2017-05-31 | 365 | 0.9923 | 0.48% | 6.30% | 6.09% | +0.21 pt |
| `BOND` | iShares Core US Aggregate Bond ETF (Yahoo AGG) | 2003-10-31 → 2017-05-31 | 164 | 0.9611 | 1.09% | 4.13% | 3.99% | +0.14 pt |
| `EXUS` | MSCI World ex USA gross TR (MSCI public API, code 991000) | 1997-02-28 → 2017-05-31 | 233 | 0.9701 | 4.23% | 6.93% | 5.77% | +1.16 pt |
| `EXUS` | Developed ex-US market TR (Ken French) | 1990-08-31 → 2017-05-31 | 322 | 0.9862 | 2.81% | 5.65% | 5.43% | +0.22 pt |
| `EXUS` | MSCI EAFE ETF (Yahoo EFA, adj. close) | 2001-09-30 → 2017-05-31 | 189 | 0.9749 | 3.91% | 6.65% | 5.54% | +1.10 pt |
| `TBILL` | 1-month T-bill (Ken French RF) | 1970-01-31 → 2016-12-31 | 564 | 0.9938 | 0.11% | 4.92% | 4.84% | +0.08 pt |
| `TBILL` | 3-month T-bill secondary market (FRED TB3MS) | 1970-01-31 → 2016-12-31 | 564 | 0.9804 | 0.19% | 4.92% | 4.94% | -0.02 pt |
| `US` | S&P 500 Total Return (Yahoo ^SP500TR) | 1988-02-29 → 2017-05-31 | 352 | 0.9999 | 0.19% | 10.33% | 10.37% | -0.04 pt |
| `US` | CRSP US total market TR (Ken French Mkt-RF + RF) | 1970-01-31 → 2017-05-31 | 569 | 0.9883 | 2.41% | 10.38% | 10.42% | -0.04 pt |

### Notes on independence

- `BOND` vs Vanguard Total Bond Market Index (Yahoo VBMFX) — independent, tracks the same Aggregate index
- `BOND` vs iShares Core US Aggregate Bond ETF (Yahoo AGG) — independent, net-of-fee fund NAV
- `EXUS` vs MSCI World ex USA gross TR (MSCI public API, code 991000) — independent path to the same index family
- `EXUS` vs Developed ex-US market TR (Ken French) — independent, developed-only universe (no EM)
- `EXUS` vs MSCI EAFE ETF (Yahoo EFA, adj. close) — independent, net-of-fee fund NAV
- `TBILL` vs 1-month T-bill (Ken French RF) — SHARED LINEAGE (both Ibbotson) - confirms transcription only
- `TBILL` vs 3-month T-bill secondary market (FRED TB3MS) — independent, different maturity
- `US` vs S&P 500 Total Return (Yahoo ^SP500TR) — independent
- `US` vs CRSP US total market TR (Ken French Mkt-RF + RF) — independent, broader universe (incl. small caps)

## 3. Timing-shift test

A redistributed file shifted by one month would pass unnoticed on a chart but would corrupt any momentum backtest. **Correlation must peak at lag 0.**

| Series | Reference | lag -2 | lag -1 | lag 0 | lag +1 | lag +2 | Max | Expected |
|---|---|---:|---:|---:|---:|---:|:--:|:--:|
| `BOND` | Vanguard Total Bond Market Index (Yahoo  | -0.094 | 0.133 | 0.992 | 0.138 | -0.092 | +0 | OK |
| `BOND` | iShares Core US Aggregate Bond ETF (Yaho | -0.190 | 0.097 | 0.961 | 0.053 | -0.133 | +0 | OK |
| `EXUS` | MSCI World ex USA gross TR (MSCI public  | -0.029 | 0.151 | 0.970 | 0.165 | 0.000 | +0 | OK |
| `EXUS` | Developed ex-US market TR (Ken French) | -0.029 | 0.103 | 0.986 | 0.076 | -0.048 | +0 | OK |
| `EXUS` | MSCI EAFE ETF (Yahoo EFA, adj. close) | -0.015 | 0.184 | 0.975 | 0.170 | -0.020 | +0 | OK |
| `TBILL` | 1-month T-bill (Ken French RF) | 0.946 | 0.966 | 0.994 | 0.965 | 0.945 | +0 | OK |
| `TBILL` | 3-month T-bill secondary market (FRED TB | 0.948 | 0.964 | 0.980 | 0.983 | 0.968 | +1 | OK |
| `US` | S&P 500 Total Return (Yahoo ^SP500TR) | -0.027 | 0.032 | 1.000 | 0.032 | -0.027 | +0 | OK |
| `US` | CRSP US total market TR (Ken French Mkt- | -0.039 | 0.058 | 0.988 | 0.052 | -0.041 | +0 | OK |

Every reference is aligned at lag 0, with one documented exception: `TB3MS` is the **monthly average of a yield**, and the yield quoted in month *t* is earned over month *t+1*, so its peak at lag +1 is the correct economic relationship. The strictly comparable reference for the cash leg is Kenneth French's one-month bill, aligned at lag 0.


## 4. Defect found in the published file, and its repair

The structural audit of the file **as published** reports 6 anomaly(ies). A cash total-return index accrues a positive yield every month: it can never mechanically fall. Any fall is therefore a data error, not a market movement.

Three November observations have **lost their leading digit**. The correct value is reconstructed as the geometric mean of the two neighbouring months, which recovers the missing digit to four significant figures with no arbitrary constant.

| Series | Month | Published value | Value used | Neighbours | Fall | Kind |
|---|---|---:|---:|---|---:|:--:|
| `TBILL` | 1990-11-30 | 0.366 | **10.368** | 10.3080 / 10.4290 | 96.449% | material |
| `TBILL` | 1991-11-30 | 0.970 | **10.970** | 10.9280 / 11.0120 | 91.124% | material |
| `TBILL` | 1992-11-30 | 1.366 | **11.369** | 11.3400 / 11.3980 | 87.954% | material |
| `TBILL` | 2011-07-31 | 20.560 | **20.561** | 20.5610 / 20.5620 | 0.005% | rounding |

The `rounding` rows are plain three-decimal roundings in the published file (fall < 0.1 %) and have no effect; only the `material` rows repair the missing leading digit.


Impact: left uncorrected, this defect injects a monthly return of −96 % followed by +2,749 % into the cash leg, which corrupts the absolute momentum signal for the twelve months following each occurrence (that is, 1990-1993). The repair is applied upstream, in `repair_monotone_index()`.


### Structural checks after repair

No residual anomaly: continuous monthly index, sorted, no duplicates, strictly positive levels, no monthly return beyond 40 % in absolute value.


## 5. Splice-joint check

A badly made splice typically shows up as one freak month at the junction. z-score of the junction month within the distribution of its own series; |z| < 3 expected.

| Series | Month | Splice | z | Verdict |
|---|---|---|---:|:--:|
| `US` | 1988-01-31 | Ibbotson large cap -> S&P 500 TR | +0.75 | OK |
| `EXUS` | 1987-12-31 | MSCI World ex USA -> MSCI ACWI ex USA | +0.44 | OK |
| `BOND` | 1975-12-31 | Ibbotson gov/corp -> Bloomberg Barclays US Agg | +1.79 | OK |
| `TBILL` | 2001-07-31 | Ibbotson 30-day bills -> FRED 4-week bill | -0.35 | OK |
