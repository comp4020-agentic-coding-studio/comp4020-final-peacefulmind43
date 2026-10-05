# Overlay Room

A shared room for testing simple rules on top of a momentum stock portfolio,
where every test anyone runs is kept and counted.

## Who it is for

This is for a small group of friends who hold a momentum fund, like SPMO (the
Invesco S&P 500 Momentum ETF), or who are thinking about it. Some of us also
borrow money to hold more of it. We cannot change which stocks the fund buys.
What we can change is how much we hold, and when. So the questions we argue
about are rules on top of the fund: "Should I use 1.5x leverage?", "Should I
hold less when the market is wild?", "Should I sell after a big fall?"

## What good means here

The danger with these questions is not that they are hard. The danger is that
they are easy to answer wrongly. If you try twenty rules on old data, one of
them will look great by luck. A normal backtest website lets you try as many
rules as you like and never tells you how many you tried. So for this room,
good means:

1. **Every test counts.** Every test anyone runs is saved and shown to everyone.
   Nobody can delete or hide a test, not even me. The more tests the room runs,
   the less any single good result should be trusted. (Next step: the room will
   discount everyone's results by the number of tests, using the deflated Sharpe
   ratio.)
2. **Some years stay locked.** Tests use 1927 to 2015. The years from 2016 are
   kept back until the round is revealed. Those are roughly the years SPMO has
   existed, so the reveal answers a real question: would a rule picked on old
   data have helped in the years we could have used it?
3. **The numbers are right.** Every number on the page can be checked by hand
   from the data.
4. **A friend with no finance background can use it in one minute.** The main
   page uses plain words. The details are there for people who want them.
5. **It never gives advice.** It shows what a rule did in the past. It does not
   say what anyone should do.

## Which promises are checked, and which are judged

Checked by tests in `spec/` on every change: tests are kept and shared, a test
can never be changed or deleted (the database itself refuses), no page or API
response contains a locked month, and the results match a separate calculation
from the data file.

Judged by people: whether a first-time visitor understands the page, and
whether the page ever sounds like advice. My crit group will be the first test
of both.

## What I read

- Robin Sloan, "An app can be a home-cooked meal" (2020). An app can be made for
  a few people you know, and that is enough. This room is for a handful of
  friends, not for the public.
- David Bailey and Marcos López de Prado, "The Deflated Sharpe Ratio" (2014).
  A Sharpe ratio must be judged against how many strategies were tried to find
  it. This is the idea behind "every test counts".
- Campbell Harvey, Yan Liu and Heqing Zhu, "...and the Cross-Section of Expected
  Returns" (2016). Many published stock-return "discoveries" do not survive
  once you count how many were tested.
- Kent Daniel and Tobias Moskowitz, "Momentum Crashes" (2016). Momentum can
  lose a lot very fast, especially when a falling market turns up. This is why
  leverage on momentum needs care.
- The Kenneth R. French data library, where the data comes from.

## What I chose not to build

- **No accounts.** A visitor is an anonymous browser. The room only needs to tell
  people apart, not know who they are.
- **No stock picking.** The fund's stock list is not ours to change, so the room
  only tests rules on top of it.
- **No advice and no "best rule" ranking.** A ranking would reward the luckiest
  test, which is the exact problem this room is about.

## Limits

- The portfolio is the top 10% of US stocks by past return, from the French
  data library. It is like SPMO, but it is not SPMO.
- Trading costs are not included yet. A momentum portfolio trades a lot, so real
  returns would be lower.
- The data is public, so the locked years are not secret. The room only promises
  that it will not show them before the reveal.
- Borrowing costs the US one-month Treasury bill rate plus 1.5% a year. Real
  brokers charge different rates.
