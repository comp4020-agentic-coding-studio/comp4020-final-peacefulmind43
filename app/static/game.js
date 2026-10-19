// The game page (doc/adr/0011, 0012). The server runs the game; this draws
// what it sends and sends what you choose. Nothing here decides anything about
// the game. A turn resolves once everyone has chosen, or at the deadline.

(() => {
  const $ = (name) => document.querySelector(`[data-field="${name}"]`);
  const STAY = 0, NORTH = 1, SOUTH = 2, EAST = 3, WEST = 4;

  const board = $("board");
  let match = null; // the match's static parts: map, team size
  let seats = [];
  let you = null;
  let me = ""; // your public label, the name others and the log see (never your cookie)
  let lastTick = 0; // when the last state arrived
  let turn = 0; // the turn now open
  let deadline = 2; // seconds a turn waits for people
  let chosen = new Set(); // seats that have chosen this turn
  let breakUntil = 0; // when the break between matches ends
  let pausedBy = null; // who paused the match, if it's paused (ADR 0015)
  let held = null; // a direction held down (key or pad): chosen again each turn
  let heldSince = 0; // when it was pressed
  // A press only counts as holding after this long, like a keyboard's own
  // repeat delay. Without it, an ordinary press was still down when the next
  // turn arrived (a solo turn resolves in 0.15 s), and walked two steps.
  const HOLD_DELAY = 350;
  let seq = Date.now(); // inputs are numbered; a newer page never reuses an older number

  // --- drawing ----------------------------------------------------------------

  let drawPlayers = () => {}; // set by drawMap, from board.js (shared with the replay page)

  function drawMap() {
    drawPlayers = window.CtfBoard.create(board, match.map, seats.map((s) => s.team));
  }

  function drawTick(t) {
    lastTick = performance.now();
    turn = t.tick;
    showPause(t.paused);
    chosen = new Set(t.chosen || []);
    $("score-blue").textContent = t.score[0];
    $("score-red").textContent = t.score[1];
    $("clock").textContent = `${Math.max(0, match.max_ticks - t.tick)} turns left`;
    drawPlayers(t.players, { you, bots: seats.map((s) => s.kind === "bot") });
    if (you !== null) {
      const p = t.players[you];
      $("you").textContent = `You are ${me}, player ${you + 1} on ${seats[you].team}.` +
        (p.respawn ? ` You were caught. Back in ${p.respawn} turns.` : p.carrying ? " You have their flag: get home!" : "");
    }
    if (t.break) {
      notice(`Next match in ${Math.ceil(t.break)} s.`);
      breakUntil = performance.now() + t.break * 1000;
    }
    drawSeats();
    if (held !== null && !t.break) walkOn(held, t.tick); // a held direction walks on, one step a turn
  }

  function walkOn(dir, forTurn) {
    const wait = HOLD_DELAY - (performance.now() - heldSince);
    if (wait <= 0) return send(dir);
    setTimeout(() => {
      if (held === dir && turn === forTurn) send(dir); // still held, and still this turn
    }, wait);
  }

  function drawSeats() {
    const list = $("roster");
    list.replaceChildren(
      ...seats.map((s, i) => {
        const li = document.createElement("li");
        li.className = `${s.team}${i === you ? " me" : ""}`;
        // every bot seat names its bot (CLAUDE.md, ADR 0019)
        const kind = s.bot === "scripted" ? "scripted bot" : s.bot ? `trained bot (${s.bot})` : "bot";
        const who = s.kind === "human" ? s.label : s.covering ? `${kind}, covering for ${s.covering}` : kind[0].toUpperCase() + kind.slice(1);
        const ready = s.kind === "human" ? (chosen.has(i) ? " ✓ chosen" : " … choosing") : "";
        li.textContent = `${i + 1}. ${who}${i === you ? " (you)" : ""}${ready}`;
        return li;
      }),
    );
  }

  function notice(text) {
    const n = $("notice");
    n.textContent = text;
    n.hidden = !text;
  }

  function moment(text) {
    const list = $("moments");
    const li = document.createElement("li");
    li.textContent = text;
    list.prepend(li);
    while (list.children.length > 6) list.lastElementChild.remove();
  }

  function begin(snap) {
    breakUntil = 0;
    match = snap.match;
    deadline = match.deadline_seconds;
    seats = snap.seats;
    you = snap.you;
    me = snap.label;
    drawMap();
    drawSeats();
    drawTick(snap.tick);
    if (watching) {
      const blue = seats.find((s) => s.team === "blue")?.bot;
      const red = seats.find((s) => s.team === "red")?.bot;
      $("you").textContent = `Watching: blue is the ${blue === "scripted" ? "scripted" : `trained bot (${blue})`}, red the ${red === "scripted" ? "scripted bot" : red}.`;
      notice("");
    } else if (snap.bench) {
      $("you").textContent = `You are ${me}. Every seat has a person in it.`;
      notice("You're on the bench: you'll play from the next match, which grows to 3 a side.");
    } else if (!snap.tick.break) {
      notice(you === null || snap.tick.tick === 0 ? ""
        : snap.returning ? "Welcome back. You have your seat again."
        : "You joined a match already under way, taking over from a bot.");
    }
  }

  // --- the connection ---------------------------------------------------------

  const params = new URLSearchParams(location.search);
  const watching = params.has("watch"); // bots only: nobody sits
  const arenaId = watching ? "watch" : params.get("arena");
  if (watching) {
    document.querySelector(".pad").hidden = true;
    document.querySelector(".board-hint").hidden = true;
  }
  // Every listener is kept here, so a new connection gets them all again.
  const handlers = {};
  const on = (event, fn) => (handlers[event] = fn);
  let stream = null;
  on("snapshot", (e) => begin(JSON.parse(e.data)));
  on("match", (e) => {
    begin(JSON.parse(e.data));
    moment("A new match started.");
  });
  on("tick", (e) => drawTick(JSON.parse(e.data)));
  function showPause(by) {
    pausedBy = by || null;
    const button = $("pause");
    if (button) {
      button.textContent = pausedBy ? "Resume" : "Pause";
      button.hidden = watching || you === null;
    }
    if (pausedBy) notice(`Paused by ${pausedBy}. Anyone in the match can press Resume (or P) to carry on.`);
    else if ($("notice").textContent.startsWith("Paused by")) notice("");
  }
  on("pause", (e) => {
    const p = JSON.parse(e.data);
    showPause(p.paused ? p.by : null);
    if (!p.paused) lastTick = performance.now(); // the turn starts again from now
    moment(`${p.by} ${p.paused ? "paused" : "resumed"} the match`);
  });
  // The request says what the button shows (ADR 0022): Pause asks for a
  // paused match, Resume for a running one, so two people pressing Pause at
  // once both get a paused match instead of undoing each other.
  async function askPause() {
    if (you === null) return;
    const res = await fetch("/arena/pause", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ paused: !pausedBy }),
    });
    if (res.ok) {
      const p = await res.json();
      showPause(p.paused ? (p.by === me ? "you" : p.by) : null);
    }
  }
  $("pause")?.addEventListener("click", askPause);
  document.addEventListener("keydown", (e) => {
    if ((e.key === "p" || e.key === "P") && !e.repeat && !(e.target instanceof HTMLInputElement)) askPause();
  });

  on("chosen", (e) => {
    const c = JSON.parse(e.data);
    if (c.turn === turn) {
      chosen.add(c.seat);
      drawSeats();
    }
  });
  on("seats", (e) => {
    seats = JSON.parse(e.data).seats;
    drawSeats();
  });
  on("moment", (e) => {
    const m = JSON.parse(e.data);
    const who = m.seat === you ? "You" : `${m.label} (player ${m.seat + 1})`;
    const what = {
      tag: "got caught",
      pickup: "picked up the flag",
      capture: "scored!",
      join: "joined",
      takeover: "went quiet; a bot is covering",
      reclaim: "is back",
    }[m.kind] ?? m.kind;
    moment(`${who} ${what}`);
  });
  on("over", (e) => {
    const over = JSON.parse(e.data);
    const [b, r] = over.score;
    const result = b === r ? "a draw" : b > r ? "blue wins" : "red wins";
    notice(`Match over, ${b}–${r}: ${result}.`);
    moment(`Match over, ${b}–${r}.`);
  });
  // The browser reconnects by itself after a dropped connection, but gives up
  // for good if the server answers with an error, as a proxy may while the
  // app restarts. Then this page starts a new connection itself, every few
  // seconds, and the snapshot that arrives puts the game back on screen.
  function connect() {
    stream = new EventSource(`/arena/events${arenaId ? `?arena=${encodeURIComponent(arenaId)}` : ""}`);
    for (const [event, fn] of Object.entries(handlers)) stream.addEventListener(event, fn);
    stream.onopen = () => ($("status").textContent = "Connected.");
    stream.onerror = () => {
      $("status").textContent = "Connection lost. Reconnecting…";
      if (stream.readyState === EventSource.CLOSED) setTimeout(connect, 3000);
    };
  }
  // The countdown to the next move, to a tenth of a second. It counts from when
  // this turn's board arrived, not from the server's clock, so clocks that
  // disagree don't matter. (The screen-reader status below updates less often.)
  setInterval(() => {
    const text = $("countdown");
    const bar = $("timer-bar");
    if (!lastTick || !match) return;
    const now = performance.now();
    if (pausedBy) {
      text.textContent = "Paused";
      bar.style.width = "0%";
      return;
    }
    if (breakUntil > now) {
      text.textContent = `Next match in ${((breakUntil - now) / 1000).toFixed(1)} s`;
      bar.style.width = "0%";
      return;
    }
    const left = Math.max(0, deadline - (now - lastTick) / 1000);
    const waiting = seats.some((s, i) => s.kind === "human" && !chosen.has(i));
    text.textContent = waiting ? `Next move in ${left.toFixed(1)} s` : "Moving…";
    bar.style.width = `${(left / deadline) * 100}%`;
  }, 100);

  setInterval(() => {
    if (!lastTick) return;
    const quiet = (performance.now() - lastTick) / 1000;
    if (!stream || stream.readyState !== EventSource.OPEN) {
      $("status").textContent = "Connection lost. Reconnecting…";
    } else if (pausedBy) {
      $("status").textContent = `Turn ${turn + 1}: paused.`;
    } else if (breakUntil > performance.now()) {
      $("status").textContent = "Between matches.";
    } else if (quiet > deadline + 1.5) {
      $("status").textContent = `Slow connection: last update ${quiet.toFixed(0)} s ago.`;
    } else {
      const waiting = seats.filter((s, i) => s.kind === "human" && !chosen.has(i)).length;
      const left = Math.max(0, deadline - quiet).toFixed(1);
      $("status").textContent = waiting
        ? `Turn ${turn + 1}: waiting for ${waiting} ${waiting === 1 ? "person" : "people"}, at most ${left} s more.`
        : `Turn ${turn + 1}.`;
    }
  }, 200);

  // --- input ------------------------------------------------------------------

  let sentFor = -1; // the turn the held direction was last sent for

  function send(dir) {
    if (you === null) return;
    if (held !== null && dir === held && sentFor === turn) return; // once per turn while held
    sentFor = turn;
    seq += 1;
    fetch("/arena/input", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ dir, seq, turn }),
      keepalive: true,
    }).catch(() => {});
    if (you !== null) {
      chosen.add(you);
      drawSeats();
    }
  }

  const KEYS = {
    ArrowUp: NORTH, w: NORTH, W: NORTH,
    ArrowDown: SOUTH, s: SOUTH, S: SOUTH,
    ArrowRight: EAST, d: EAST, D: EAST,
    ArrowLeft: WEST, a: WEST, A: WEST,
    " ": STAY,
  };
  const focus = $("board-focus");
  // The keys work on the board, and also anywhere on the page that is not a
  // control, so someone who just opened it can press an arrow at once.
  const forGame = (e) => e.target === focus || e.target === document.body || e.target === document.documentElement;
  document.addEventListener("keydown", (e) => {
    if (!(e.key in KEYS) || !forGame(e) || e.ctrlKey || e.metaKey || e.altKey) return;
    e.preventDefault(); // arrows and space would scroll the page
    if (e.repeat) return; // holding is handled turn by turn, not by key repeat
    held = KEYS[e.key] === STAY ? null : KEYS[e.key];
    heldSince = performance.now();
    sentFor = -1;
    send(KEYS[e.key]);
  });
  document.addEventListener("keyup", (e) => {
    if (e.key in KEYS && KEYS[e.key] === held) held = null;
  });
  window.addEventListener("blur", () => (held = null)); // never keep walking in a window you left
  focus.addEventListener("blur", () => (held = null)); // nor after leaving the board

  for (const button of document.querySelectorAll(".pad button")) {
    const dir = Number(button.dataset.dir);
    // touch and mouse: hold to keep walking, one step a turn
    button.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      button.setPointerCapture(e.pointerId);
      held = dir === STAY ? null : dir;
      heldSince = performance.now();
      sentFor = -1;
      send(dir);
    });
    for (const end of ["pointerup", "pointercancel"]) button.addEventListener(end, () => (held = null));
    // keyboard (Enter or Space on the button): one choice per press
    button.addEventListener("click", (e) => {
      if (e.detail === 0) {
        held = null;
        send(dir);
      }
    });
  }

  connect();
})();
