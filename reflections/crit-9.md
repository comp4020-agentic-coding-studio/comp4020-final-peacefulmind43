# Crit 9 reflection

## What was the breakthrough that moved the work forward?

It came from playing my own game. After crit 8 I changed the project to
capture the flag. The first version ran at four moves a second, like most
real-time games, and every check passed. Then I played it and could not keep
up with the bots. The rules were fair to both sides but the clock was not. A
bot decides instantly and a person is always a little behind. That broke the
main promise in my README, that a bot is a fair teammate.

So I changed how a turn works. It now resolves as soon as everyone has
chosen, or after two seconds. It still feels real-time to the people
playing. Each person sees within a second that another one has chosen, and
the new board arrives as soon as the turn ends. Playing it again also showed
a bug no test could see. One key press walked two steps.

## What did this work change about who I want to be as a software developer?

At the start of this project I trusted tests too much. They told me the
system followed its rules. They did not tell me if the rules were good. Bots playing
bots showed that standing on your own flag made it impossible to take, and
my own play showed the clock was unfair. I want to test a
design by using it, and not only by checking it. When I find a problem I
want to fix it where it starts, which might be the rules, the decision
record or the harness, and not just the code.
