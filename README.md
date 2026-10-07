# Overlay Room

A shared room for testing simple rules on top of a momentum stock portfolio,
where every test anyone runs is kept and counted against the room.

## Who it is for

A few friends who hold a momentum fund like SPMO, some with borrowed money. We
cannot change which stocks the fund buys, only how much we hold and when. So
we argue about rules: "Should I use 1.5×?", "Should I hold less when the market
is wild?"

## What good means here

Try twenty rules on old data and one will look great by luck. Normal backtest
sites let you try forever and never count. So here, good means:

1. **Every test counts.** Tests are saved and can never be deleted, not even by
   me. Each timing rule shows a "chance the timing helps": the deflated Sharpe
   ratio of what it adds over just holding, which falls as the room tries more
   rules.
2. **Your first idea is your own.** You see other people's results only after
   your first test in a round, so you don't start by copying the leader.
3. **Some years stay locked.** Tests use 1927–2015. The years from 2016, roughly
   the years SPMO has existed, unlock at a time published when the round opens.
   The reveal shows which rules still helped when a holder could have used them.
4. **You back what you would hold.** Testing is cheap. Before the reveal, each
   person backs one rule the room tried, and the reveal scores every pick.
5. **The numbers can be checked**, and **a friend with no finance background
   can use it** in a minute.
6. **It never gives advice.** It shows what a rule did, not what to do.

## Checked and judged

Tests in `spec/` check, on every change: tests are never changed or deleted;
a newcomer gets no one else's results from any page, API or live stream; no
locked month is sent early; live updates arrive within a second; and every
number matches a separate calculation, including the deflated Sharpe paper's
worked example.

People judge the rest: my crit group, on whether a first-time visitor
understands the page and whether anything sounds like advice; the activity log
(`/log`), on whether first tests come before seeing others and whether picks
follow the crowd.

## What I read

- Robin Sloan, "An app can be a home-cooked meal" (2020).
- David Bailey and Marcos López de Prado, "The Deflated Sharpe Ratio" (2014):
  judge a result against how many tries it took. My first version tested each
  rule against zero, and every rule scored 100%. The useful question is what a
  rule adds over holding.
- Campbell Harvey, Yan Liu and Heqing Zhu, "...and the Cross-Section of
  Expected Returns" (2016): many findings fail once tries are counted.
- Kent Daniel and Tobias Moskowitz, "Momentum Crashes" (2016): leverage on
  momentum needs care.
- Pedro Barroso and Pedro Santa-Clara, "Momentum Has Its Moments" (2015): the
  idea behind the volatility rule.
- Data: the Kenneth R. French data library.

## What I chose not to build

- **No accounts.** The room only needs to tell people apart.
- **No "best rule" ranking.** It would reward the luckiest test.

## Limits

- The portfolio is the top 10% of US stocks by past return. It is like SPMO,
  but it is not SPMO.
- Costs are rough allowances: 1% a year to hold, 0.1% of any amount moved, and
  borrowing at the T-bill rate plus 1.5%.
- The data is public, so the locked years are not secret. The room only
  promises not to show them early.
