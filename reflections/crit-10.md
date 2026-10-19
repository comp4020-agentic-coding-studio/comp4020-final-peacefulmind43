# Crit 10 reflection

## What was the breakthrough that moved the work forward?

A pause button that did nothing. Its spec checks passed, but when I
pressed it nothing happened. The browser had kept the old script, and the
spec could not see this because it never runs the page. Now scripts load by
a hash of their contents.

After that I stopped reading "the checks pass" as "it works". The checks
only cover one layer, so I started checking other layers on purpose. Before
I wrote down who may see and change what, I had the agent audit the code
against each rule. It found two holes. A reload could give your seat to a
newcomer, and a live match's choices could be read early. Later I had the
app checked against the week 10 lecture, and that found three more gaps. Two
people pressing Pause at once cancelled out, requests had no ids, and the
cookie was not Secure. Each fix has a spec check that failed first.

## What did this work change about who I want to be as a software developer?

I want to write down what success means before I see the result. For team1,
the team-play bot, I wrote its bar in the ADR before training. It failed.
Its partners scored less, even though it won 97% against the scripted bot.
Without the bar I think I would have called that a success. I kept fcp1 and
recorded team1 as a negative result.

I also want to think about who reads what I build. This crit the logs got a
new reader, someone telling the story of a game they are not playing in.
Bots showed up as "a new visitor", and closing the page was not logged. Now each line says in a plain sentence who did what, and where. I want
to check things like this from the reader's side, not only from mine.
