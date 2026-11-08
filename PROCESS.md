# Process overview

How I got from the brief to the game. The daily record is the [process log](doc/process-log.md), decisions are in [doc/adr/](doc/adr/), and my rules for the agent are in [CLAUDE.md](CLAUDE.md).

## Why the project changed

Until crit 8 this was the Overlay Room, a place to test rules on a momentum ETF. At crit 8 someone said it felt static, and I agreed. People could change numbers, but nothing they did changed what I did next.

Rather than improve it (ADR 0009), in [7dc8bb4](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/7dc8bb4) I started over with a team game where people and bots play together, because I felt more interested in what makes a bot a good teammate?

## The stack, and what it costs

The server is Python and FastAPI, with SQLite on the Fly volume. The board goes out by server-sent events and moves come in by POST, all in one uvicorn process (ADRs 0001, 0011).

ADR 0001 chose it over Django, Phoenix and Node. At the pivot I kept Python so the server and RL training share one engine. One process keeps live updates simple. It cannot run on two machines, which is fine for a few friends.

And I chose SSE plus POST over a WebSocket. Each move is one request and one log line, so adding request ids and access rules later became easy. A WebSocket would be faster, but it needed its own rules for who sent what.

A second engine in TypeScript, written from the same ADR, checks the Python one tick by tick. To validate the check, I broke it on purpose (respawn 8 to 9). It failed at tick 11 and named the field ([afa57ba](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/afa57ba)). The cost is that every rule change is made twice.

The trained bot runs in NumPy because PyTorch does not fit in the Fly machine's 256MB ([ec7237e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ec7237e)). That costs an export step, so CLAUDE.md asks for a test that NumPy and PyTorch agree before any bot ships.

## How I worked with the agent

The agent wrote most of the code. And I decided and checked with four habits.

Firstly, the agent listed a significant number of options and their costs, I picked the most interesting one, and it became an ADR. Rereading ADR 0011 before building the server found two holes ([39c9047](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/39c9047)). I did not edit a merged ADR and used a new one replaces it, as ADR 0021 did for a wrong sentence in ADR 0012 ([f550ebc](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f550ebc)).

Secondly, I set the bar before training. Each new bot got a pass mark in its ADR before it is trained. fcp1 passed and bacame live in [8b01211](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8b01211). team1 was meant to help its partners score more, and I wrote that bar first ([574235e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/574235e)). It failed though. It won 97% against the scripted bot, but by itself, not better as a teammate and too strong for humans. I did not deploy it ([06d4919](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/06d4919)). Without the bar I think I would have thought of 97% as wins.

Eight hour training runs went on worktree branches and was merged ([452628d](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/452628d), [e5c5ff1](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e5c5ff1)).

Then, I played it myself. The first real time version ran at four moves each second. Every check passed, but I could not keep up with the bots. Since [feb9602](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/feb9602) a turn waits for everyone, up to 2 seconds. When I played again, one key press walked two steps ([b0baeab](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/b0baeab)). Then I added a pause button ([09d04d2](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/09d04d2)), and pressing it did nothing. The browser kept an old script, which the spec could not see because it did not run the page. Since [1f83298](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1f83298) scripts load by a content hash. After that, a green test told me about the layer it tests.

Lastly I fixed the harness, not the prompt. Agent mistakes were fixed in CLAUDE.md or a test, so they stayed fixed. Once after the spec wrote test data into the live app, CLAUDE.md forbids it ([38a4f9f](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/38a4f9f)). A flaky test was two bugs. Arenas played matches for nobody, and the test was wrong too ([312363f](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/312363f)). The worst was in training. Red's view was flipped but its action was not, so half of every batch taught the opposite of the other half. A mirror test now fails without the fix ([034a144](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/034a144)), and CLAUDE.md says the action is mirrored too ([1d51c17](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1d51c17)).

## Checking against the code, not my memory

Before writing down who can see and change what, I had the code audited against each rule. Each of the two holes had a test that failed first. A reload could give your seat to a newcomer ([ba7700a](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ba7700a)), and a live match's moves could be read before the turn ended ([e573e75](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e573e75)). A pass against the week 10 lecture found three more: pause was a toggle, so two people pressing at once cancelled out ([c7a2a6b](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/c7a2a6b)), requests had no id ([1b822aa](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1b822aa)), and the cookie was not secure ([8044a2a](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8044a2a)).

A person rarely beat two fcp1 bots, as my README lists. Since [f1d9635](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f1d9635) an all bot team facing a person gets a weaker bot, chosen with a stand in player on 400 unseen maps. Chrome with two profiles found six more problems, like arrow keys that needed a click first ([f78d2f0](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f78d2f0)). It also caught my own advice. A second window shares the cookie and the seat, so the pages now say two Chrome profiles, checked by the spec ([02a1851](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/02a1851)).

At crit 10 a classmate said it was not easy for him to follow. Since [d0b86fc](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/d0b86fc) the page opens with four short rules, also on a phone, and a test keeps them short and above the board.

For RL I measured first. Path searches took 92% of the time, and caching them made training 13 times faster ([ec7237e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ec7237e)). A bot never scored. I observed it, found it never left home, and added a curriculum instead of a new reward ([4f32a7b](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/4f32a7b)). The summary is in [doc/rl/README.md](doc/rl/README.md).

## Dropping the ratings

I first built a blind study where people rated "Bot A" or "Bot B" ([80d7c5a](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/80d7c5a)), then removed it in [9b2534e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/9b2534e), because a few short, casual sessions would give ratings too noisy to use. Every bot is named and judged by behaviour, which is random like epsilon.

## Where I stand

Sloan's ["home-cooked meal"](https://www.robinsloan.com/notes/home-cooked-app/) and Shirky's ["Situated Software"](https://shirky.com/essays/situated-software/) let me skip accounts, chat and rankings. But Elhage's ["Situated Social Software"](https://buttondown.com/nelhage/archive/situated-social-software/) and my crit 9 pod, who never opened each other's sites, say small is not the value by itself. The real question is a fair bot teammate, and I have about half an answer: fcp1 holds up next to weak partners, but it still plays alone.


