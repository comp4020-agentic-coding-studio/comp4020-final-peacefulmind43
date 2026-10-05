# 0005. Discount what a rule adds over holding, not the portfolio itself

Status: accepted (2026-10-06). Supersedes the "luck discount" section of
ADR 0004; its rules and costs stand.

## Context

ADR 0004 applied the deflated Sharpe ratio to each rule's own returns. Built
and run, every rule scored 100% "chance it beats luck", and the luck bar was
0.03. The reason is in the question it answers: is this rule's true Sharpe
ratio above zero? A momentum portfolio over 89 years has a Sharpe ratio near
0.6, so every rule on top of it clears zero easily, however many rules are
tried. The discount was correct and useless.

The question a holder actually asks is different: does this rule do anything
beyond holding more or less of the portfolio? Leverage alone can't: 2× is the
same bet, twice as big. A volatility target or a trend filter might, by holding
more at good times and less at bad ones. That is the part that can be luck, and
the part a room of people searching for rules can overfit.

## Options

1. **Keep testing each rule's Sharpe ratio against zero.** Simple, but it says
   100% for everything, as above.
2. **Test the difference in Sharpe ratio between the rule and holding at 1×.**
   Closer to the question, but leverage changes the comparison through costs
   alone, and tests of a Sharpe-ratio difference need the correlation between
   the two series, which the deflated Sharpe ratio doesn't use.
3. **Test the rule's timing: what is left after taking out holding.** Regress
   the rule's monthly excess returns on those of "always 1×" and keep what the
   holding part can't explain. This is the comparison Barroso and Santa-Clara
   (2015) use for volatility-scaled momentum. Its Sharpe ratio (an appraisal
   ratio) is what gets deflated.

## Decision

Option 3.

- The **baseline** is "always 1×", with the same costs, over the same months.
- For each **timing rule** (volatility target, trend filter): take its monthly
  excess returns `x` and the baseline's `b`, fit `x = a + β·b` by least squares,
  and form the timing series `x − β·b`. Its per-month Sharpe ratio, skewness and
  kurtosis go into the deflated Sharpe ratio.
- `N` is the number of **distinct timing rules** in the round, and the variance
  is the sample variance of their timing Sharpe ratios.
- **Fixed-leverage rules get no discount.** They only scale the portfolio, so
  there is no timing to test, and they don't count towards `N`. How much
  leverage to use is a question of how much risk to take, which their growth and
  worst fall already show.
- The page calls the result **"chance the timing helps"**: the probability that
  the rule really adds something beyond holding, after allowing for how many
  timing rules the room has tried.

## Consequences

- The scores now differ between rules and move as the room grows. In a trial
  run, one volatility rule went from 70% with 7 rules tried to 25% with all 66.
- A rule can grow less than "always 2×" and still score well, because it is
  judged on timing, not on size. The page has to make that clear.
- Version two's trials already in a round carry no timing figures. Migration
  0003 closes any such round and opens a fresh one, as 0002 did for version one.
  None are deleted.
- `spec/discount.test.ts` recomputes the regression, the timing series and the
  discount from what the app publishes, independently of the app.
