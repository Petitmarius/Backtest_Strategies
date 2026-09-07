# Research paper — agreed outline

Working blueprint for the paper. Section titles and figure captions below are
the actual English wording intended for the manuscript.

**Language** English · **Target length** ~16 pages including exhibits ·
**Format** working paper: abstract, numbered sections, BibTeX bibliography

## Positioning

The paper shows the work: what the strategy is, how it was replicated, what came
out, and what it means. It is a demonstration of method and result, not a
polemic. The recent underperformance is treated honestly, at the end, as one
limitation among several — not as the thesis.

The data work establishes credibility; it is not the subject. Sources and
construction belong in the body, the audit apparatus in the appendix.

## Writing conventions

Guidance, not rules to be enforced mechanically. The aim is a document that is
as informative as it can be; nothing here should get in the way of that.

- **Prose serves the exhibits.** Write as long as the argument needs, but say
  the thing rather than circling it. Avoid paragraphs that restate what a table
  already shows.
- **Every exhibit is read where it appears.** Show it, say what it shows, say
  what it means. Avoid a block of tables followed by a block of commentary.
- Illustrate wherever illustration helps. There is no quota either way.
- Numbers in the text always carry their unit and period.
- First person plural, past tense for what was done, present for what holds.

## Structure

| § | Section | Pages | Content |
|---|---|---:|---|
| — | Abstract | 0.5 | ~200 words |
| 1 | Introduction | 1.5 | Question, what was built, what was found |
| 2 | The strategy | 2 | Absolute and relative momentum, their combination, the GEM rule |
| 3 | Data and methodology | 2.5 | Free sources, series construction, implementation, statistics |
| 4 | Results | 5 | Five subsections, each an exhibit read on the spot |
| 5 | Robustness | 2 | Lookback, transaction costs, bond proxy, subperiods |
| 6 | Limitations and discussion | 1.5 | Post-2009 shortfall, parameter choice, data caveats |
| 7 | Conclusion | 0.5 | |
| A | Appendix | 2.5 | Data audit, full provenance, detailed tables |

### 2. The strategy

What absolute momentum does (a risk filter: be in equities at all?) and what
relative momentum does (a return filter: which equities?). Why Antonacci
combines them in that order. The rule as implemented, with **Figure 1**.

Origins and prior evidence go here rather than in a standalone literature
review: Jegadeesh & Titman for relative momentum, Moskowitz, Ooi & Pedersen for
absolute, Antonacci for the combination.

### 3. Data and methodology

Four monthly total-return index levels in USD, 1969-12 to 2026-07: US equity,
ex-US equity, US aggregate bonds, T-bills.

Where each series comes from and why: the historical core, and the free live
sources that extend it. **Table 1** gives the provenance segment by segment and
**Figure 2** shows it as a timeline — the reader must be able to see that the
ex-US leg changes universe in 1988 and that the Aggregate index does not exist
before 1976.

State plainly that the series were checked against independent sources and that
one defect was found and repaired; give the result in two sentences and send the
apparatus to Appendix A. **Do not narrate the audit here.**

Then the implementation: signal formed on month *t-1*, position earns month *t*
(no look-ahead by construction), monthly rebalancing, benchmarks used, and
Newey-West standard errors with the reason for them.

### 4. Results

Each subsection presents its exhibit and reads it immediately.

**4.1 Headline performance** — Figure 3 (equity curves), Figure 4 (drawdowns),
Table 3. GEM 15.18% vs S&P 500 11.27%, max drawdown −21.7% vs −51.0%.

**4.2 Where the return comes from** — Table 4. Absolute alone +77 bps, relative
alone +203 bps, combined +391 bps. The two do not add up; explain why the
absolute filter makes the relative choice worth more.

**4.3 Allocation or timing?** — Table 5. The static portfolio holding GEM's own
average mix returns 10.03%, *below* the S&P 500. The asset basket is a drag; the
whole excess comes from switching. Drawdown splits the other way: −9.0 pt from
allocation, −20.3 pt from timing.

**4.4 Risk-adjusted performance** — Table 6. Annualised alpha 6.61% (t = 4.31),
beta 0.57, R² 0.45.

**4.5 Behaviour through time** — Figure 5 (annual returns), Figure 6
(allocation), Figure 7 (rolling 36-month excess), Table 7 (decades). Where the
edge came from, and the fact that it is concentrated in 1971-2009.

### 5. Robustness

Lookback sensitivity (Figure 8, Table 8): CAGR ranges 12.3-15.2% across 3-24
months, and 12 months is the maximum of the grid — say so. Transaction costs.
Bond proxy. Subperiod stability.

### 6. Limitations and discussion

The post-2009 shortfall with its attribution (26% of months out of the S&P 500,
but the S&P returned +34%/yr annualised during the 21 defensive months, against
+5.3%/yr during the 149 defensive months of 1971-2009). Parameter choice and
the risk it was picked ex post. Data caveats: spliced universes, redistributed
core. No taxes.

## Figures

| # | Caption | Status |
|---|---|---|
| 1 | The Global Equities Momentum decision rule | **done** |
| 2 | Provenance of each series over time | **done** |
| 3 | Growth of $100, log scale, 1971-2026 | exists |
| 4 | Drawdowns from prior peak | exists |
| 5 | Annual returns, GEM vs S&P 500 | **done** |
| 6 | Asset held by the rule over time | exists |
| 7 | Rolling 36-month excess return vs S&P 500 | exists |
| 8 | Sensitivity to the momentum lookback | exists |

Figures 1 and 5 carry the most explanatory weight: the first lets a reader grasp
the rule in ten seconds, the second shows visually that GEM earns its edge by
avoiding bad years rather than by winning good ones.

All figures export to **vector PDF**, not PNG.

## Tables

| # | Title | Location | Status |
|---|---|---|---|
| 1 | Provenance of each series, by segment | §3 | from SEGMENTS.md |
| 2 | Summary statistics of the four series | §3 | **done** |
| 3 | Performance, 1971-2026 | §4.1 | exists |
| 4 | Decomposition: absolute, relative, combined | §4.2 | exists |
| 5 | Allocation effect versus timing effect | §4.3 | exists |
| 6 | Regression on the benchmark, Newey-West | §4.4 | exists |
| 7 | Performance by decade | §4.5 | exists |
| 8 | Robustness: lookback and transaction costs | §5 | exists |
| A1 | Independent verification of the dataset | Appendix | from VALIDATION.md |

## References

To verify before citing — no approximate bibliography.

**Foundations** — Jegadeesh & Titman (1993, *Journal of Finance*); Moskowitz,
Ooi & Pedersen (2012, *JFE*); Asness, Moskowitz & Pedersen (2013, *JF*).

**GEM** — Antonacci, Gary. "Risk Premia Harvesting Through Dual Momentum."
Portfolio Management Consultants. First version 18 April 2012, this version
1 October 2016. SSRN 2042750. First-place winner of the 2012 NAAIM Wagner
Awards. *Verified against the PDF in the repository.*
Also: Antonacci, *Dual Momentum Investing* (McGraw-Hill, 2014);
*Extended Backtest of Global Equities Momentum* (Medium / optimalmomentum.com,
2018); ReSolve, *Global Equity Momentum: A Craftsman's Perspective* (2019);
Link, Grzegorz, *Dual Momentum and Global Growth Cycle Enhanced*
(grzegorz.link/momentum-enhanced).

**Critical frame** — McLean & Pontiff (2016, *JF*); Harvey, Liu & Zhu (2016,
*RFS*); Novy-Marx (2012).

**Data** — Kenneth French Data Library; MSCI; Bloomberg/Barclays;
Ibbotson/Morningstar.

## Status

First complete draft written, 15 pages. All sections and all exhibits are in
place; what remains is revision rather than composition.

## Work order

The introduction is written last: a result must be settled before it can be
announced well.

1. ~~Vector figure export~~ done — every figure now writes PNG and PDF
2. ~~Figures 1, 2, 5 and Table 2~~ done — `src/paper_exhibits.py`
3. ~~LaTeX skeleton and bibliography~~ done — Tectonic, `research_paper/Petit_2026_Global_Equities_Momentum.tex`
4. ~~§3 Data and methodology, §2 The strategy~~ done
5. ~~§4 Results, §5 Robustness~~ done
6. ~~§6 Limitations, §7 Conclusion~~ done
7. ~~§1 Introduction, then the abstract~~ done
8. Reference verification and proofreading — **next**

## Reproducibility statement

The paper cites the public repository as the source of the dataset and the
code, so that any result can be reproduced without paid data. To be added once
the repository is made public.

## Open items

- Author name and affiliation for the title block.
