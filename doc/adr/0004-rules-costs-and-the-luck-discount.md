# 0004. Two overlay rules, trading costs, and the deflated Sharpe ratio

Status: accepted (2026-10-06)

## Context

Version one only offered fixed leverage. Leverage barely changes a Sharpe
ratio, so every test had almost the same Sharpe, and a discount for "many
tests" had nothing to discount. The room needs rules that genuinely differ, and
a stated way to judge them against the number of tests. The results also
ignored trading costs, which flatters any rule that trades more.

## Decision

### The rules

Each test picks one rule and a **leverage cap** (1× to 3×). All rules decide
how much to hold at the end of a month, using only data up to that month, and
hold it for the next month. Money not in the portfolio earns the T-bill rate;
money borrowed costs the T-bill rate plus 1.5% a year (ADR 0002).

- **Fixed:** always hold the cap.
- **Volatility target:** hold `target ÷ recent volatility`, never more than the
  cap. Recent volatility is the standard deviation of the portfolio's last 6 or
  12 monthly returns, annualised. Targets: 10%, 15%, 20% or 25% a year. This
  follows Barroso and Santa-Clara (2015), who scale momentum by its own recent
  volatility; they use daily data, and this room only has monthly.
- **Trend filter:** hold the cap while the US market is at or above its average
  level over the last 6, 10 or 12 months; otherwise hold cash.

In the first months of the data, before a rule has its full lookback, it uses
the history that exists; in the very first month every rule holds the cap.

That is 72 possible rules (6 fixed, 48 volatility, 18 trend).

### Costs

Two stated allowances, not measurements:

- **Holding cost: 1% a year** on the amount held in the portfolio, a rough
  allowance for a fund's fees and the portfolio's own trading.
- **Switching cost: 0.1% of the amount moved** whenever a rule changes how much
  is held, including the first purchase.

Monthly resetting of a fixed leverage is not charged.

### The luck discount

Each test's result is judged with the **deflated Sharpe ratio** (Bailey and
López de Prado, 2014): the probability that the rule's true Sharpe ratio is
above zero, after allowing for how many different rules the room tried, for
how much their results varied, and for skewed, fat-tailed returns.

- `N` is the number of **distinct rules** tested in the round. Running the same
  rule twice is kept and shown, but adds no new chance of a lucky find, so it
  doesn't raise `N`.
- The variance across rules is the sample variance of the distinct rules'
  monthly Sharpe ratios.
- The **luck bar** is the expected best Sharpe ratio among `N` rules with no
  skill at all. A rule's Sharpe needs to clear it before luck stops being the
  easy explanation. It is shown annualised; the calculation uses monthly
  figures.
- With fewer than two distinct rules there is nothing to compare, so no discount
  is shown.

The page calls the deflated Sharpe ratio "chance it beats luck", in plain words,
with the full name in the details.

## Consequences

- Every result changes whenever someone tests a new rule, because `N` and the
  variance change. That is the point, and it is why the discount goes out over
  the real-time stream to every open page.
- The costs make every result lower than version one's, and the rules that
  switch often pay the most. The numbers are assumptions; the README says so.
- Counting distinct rules, not tests, means one person can't inflate the
  discount by repeating a rule, and also can't escape it by repeating one.
- The formula is checked in `spec/` against the paper's own worked example, and
  the app's figures are recomputed independently from what it publishes.
