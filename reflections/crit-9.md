# Crit 9 reflection

## What was the breakthrough that moved the work forward?

The breakthrough came from playing my own game. After crit 8 I changed the
project to capture the flag, and the first version ran at four moves a second,
like most real-time games. Every check passed. Then I played it, and I could not
keep up with the bots. The rules were fair to both sides, but the clock was
not: a bot decides instantly, and a person is always a little behind. That broke
the main promise in my README, that a bot is a fair teammate.

So I changed how a turn works: it resolves as soon as everyone has chosen, or
after two seconds. The game is still real-time for the people in it, because
each person sees within a second that another has chosen, and the new board
arrives as soon as the turn ends. Playing it again also found a bug no test
could see: one key press walked two steps.

## What did this work change about who I want to be as a software developer?

I trusted tests too much at the start of this project. They told me the system
followed its rules, but not whether the rules were good. Bots playing bots
showed that standing on your own flag made it untakeable, and playing it myself
showed the clock was unfair. I want to test a design by using it, not only by
checking it, and when I find a problem, fix it where it lives: in the rules, the
decision record, or the harness, not just in the code.
