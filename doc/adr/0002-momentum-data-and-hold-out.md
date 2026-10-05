# 0002. Momentum data from the Kenneth French library, with a locked hold-out

Status: accepted (2026-10-06)

## Context

The rules this room tests are overlays on a momentum portfolio: how much
leverage to use, and later when to raise or cut it. The motivating case is
holding SPMO (Invesco S&P 500 Momentum ETF), whose stock selection a holder
cannot change; the levers a holder does control are the overlays.

That needs a monthly return series for a long-only momentum portfolio, a
risk-free rate (for Sharpe ratios and for the cost of borrowing), and a market
series to compare against. It also needs a period that nobody in the room can
test on until the round is revealed.

## Options

1. **SPMO prices** (e.g. from Yahoo Finance). The real thing, but only from
   October 2015: about ten years, with one real momentum crash at most. Far too
   short to say anything about leverage, and Yahoo's terms don't clearly allow
   redistributing the data in a public repo.
2. **Stock-level data, rebuilding the S&P 500 Momentum index.** Closest to SPMO's
   actual rules, but free stock data only covers companies that still exist
   (survivorship bias), which flatters momentum. Bias-free data (CRSP) is paid.
3. **Kenneth French's "10 portfolios formed on prior (12-2) return"**, monthly,
   value-weighted, top decile, from 1927. Free to download, built from CRSP so
   there's no survivorship bias, and long-only. It is not SPMO: it is the top
   10% of all US stocks by past return, while SPMO is about 100 S&P 500 stocks
   with its own weighting and twice-yearly rebalancing.

## Decision

Option 3, with the Fama-French research factors file for the one-month T-bill
rate and the market return.

- `scripts/build_data.py` downloads both files and writes `data/momentum.csv`
  (month, momentum top-decile return, market return, T-bill rate, all monthly,
  in percent). The CSV is committed so builds don't depend on the French site
  being up, and the script records exactly how it was made.
- **Borrowing cost** for leverage above 1x is the T-bill rate plus a fixed
  spread of 1.5% a year, roughly what a retail margin account charges on a
  small balance. It is a parameter, not a claim about any one broker.
- **The first round's hold-out is January 2016 to the end of the data.** That is
  roughly the period SPMO has actually existed, so the reveal answers a real
  question: did a rule chosen on 1927–2015 still help in the years a holder
  could have used it? Everything a page or an API sends during the round stops
  at December 2015.

## Consequences

- Results describe a momentum *portfolio*, not SPMO itself. The README has to
  say so plainly, and nothing in the app may present a result as advice about
  SPMO.
- The French data is public, so the hold-out isn't secret: anyone could download
  it. What the app enforces is that the *room* never shows it before the reveal.
  It is a commitment device for the people testing, not a security boundary.
  That promise is checked in `spec/`: no response during a round may contain a
  month after the round's in-sample end.
- The French library publishes no formal licence; its data is widely
  redistributed in academic tools, and the app credits the source wherever the
  data appears. If that ever becomes a problem, the CSV can be fetched at build
  time instead of committed.
- Updating the data (French updates it monthly) changes the hold-out of any
  round not yet revealed, so a round's data is fixed when the round is created.
