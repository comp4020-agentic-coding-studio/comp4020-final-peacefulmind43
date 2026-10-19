# Crit 10 reflection

## What was the breakthrough that moved the work forward?

The breakthrough was a pause button that did nothing. Its spec checks passed,
then I pressed it and nothing happened. The browser had kept the old script.
The spec could not see this, because it never runs the page. Now scripts load
by a hash of their contents.

This taught me that "the checks pass" is a claim about one layer. So I started
checking other layers on purpose. Before I wrote down who may see and change
what, I had the agent audit the code against each rule. That found two holes:
a reload could give your seat to a newcomer, and a live match's choices could
be read early. Later I had the app checked against the week 10 lecture and
found three more gaps: two people pressing Pause at once cancelled out,
requests had no ids, and the cookie was not Secure. Each fix has a spec check that failed first.

## What did this work change about who I want to be as a software developer?

I want to write down what success means before I see the result. For the
team-play bot, team1, I wrote its bar in the ADR before training. It failed:
its partners scored less, though it won 97% against the scripted
bot. Without the bar, I think I would have called that a success. I kept fcp1 and recorded team1 as a negative result.

I also want to build for the person who reads the output. This crit, the logs
had a new reader: someone telling the story of a game they are not playing.
Bots were called "a new visitor", and closing the page was not logged. Now
each line says who, where and what in a plain sentence. A log line, a rule
and a test are all promises to someone, and I want to check each one from
where that person stands.
