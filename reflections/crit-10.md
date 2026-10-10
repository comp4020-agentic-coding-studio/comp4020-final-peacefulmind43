# Crit 10 reflection

## What was the breakthrough that moved the work forward?

The breakthrough was a pause button that did nothing. I added it, its spec
checks passed, and then I pressed it and nothing happened. The browser had
kept the old game script, which had no code for the button. The spec could not
see this, because it talks to the server directly and never runs the page.
Now scripts load by a hash of their contents, so a new page gets new code.

This taught me that "the checks pass" is a claim about one layer. So for this
crit I checked the other layers on purpose. Before I wrote down who may see
and change what, I read the server code against each rule instead of trusting
my memory of it. That found two real holes: a reload in a full match could
give your seat to a newcomer, and a live match's choices could be read before
the turn ended. Each now has a spec check that failed before the fix.

## What did this work change about who I want to be as a software developer?

It is easy to write logs only for yourself, for when something breaks. This
crit the logs have another reader: someone telling the story of a game they
are not playing. When I read the real lines with that reader in mind, they
were not good enough. Bots were called "a new visitor", and nothing was logged
when someone closed the page. Now each line says who, where and what in a
plain sentence, and the page tells each person their label.

I want to build for the person who reads the output, not only for the person
who writes the code. A permission rule, a log line and a test are all promises
to someone, and I want to check each one from where that person stands.
