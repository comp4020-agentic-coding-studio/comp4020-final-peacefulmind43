// The game page (doc/adr/0011, 0012). The server runs the game; this draws
// what it sends and sends what you choose. Nothing here decides anything about
// the game. A turn resolves once everyone has chosen, or at the deadline.

(() => {
  const $ = (name) => document.querySelector(`[data-field="${name}"]`);
  const SVG = "http://www.w3.org/2000/svg";
  const STAY = 0, NORTH = 1, SOUTH = 2, EAST = 3, WEST = 4;
  const TEAM = ["blue", "red"];

  const board = $("board");
  let match = null; // the match's static parts: map, team size
  let seats = [];
  let you = null;
  let lastTick = 0; // when the last state arrived
  let turn = 0; // the turn now open
  let deadline = 2; // seconds a turn waits for people
  let chosen = new Set(); // seats that have chosen this turn
  let breakUntil = 0; // when the break between matches ends
  let held = null; // a direction held down (key or pad): chosen again each turn
  let heldSince = 0; // when it was pressed
  // A press only counts as holding after this long, like a keyboard's own
  // repeat delay. Without it, an ordinary press was still down when the next
  // turn arrived (a solo turn resolves in 0.15 s), and walked two steps.
  const HOLD_DELAY = 350;
  let seq = Date.now(); // inputs are numbered; a newer page never reuses an older number
  const tokens = []; // one SVG group per seat
  const flagMarks = [];

  // --- drawing ----------------------------------------------------------------

  function el(name, attrs, parent) {
    const node = document.createElementNS(SVG, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.append(node);
    return node;
  }

  function drawMap() {
    const m = match.map;
    board.setAttribute("viewBox", `0 0 ${m.width} ${m.height}`);
    board.replaceChildren();
    el("rect", { x: 0, y: 0, width: m.width / 2, height: m.height, class: "half blue" }, board);
    el("rect", { x: m.width / 2, y: 0, width: m.width / 2, height: m.height, class: "half red" }, board);
    m.bases.forEach((base, team) => {
      for (const [x, y] of base) el("rect", { x, y, width: 1, height: 1, class: `base ${TEAM[team]}` }, board);
    });
    for (const [x, y] of m.walls) el("rect", { x, y, width: 1, height: 1, class: "wall" }, board);
    tokens.length = 0;
    flagMarks.length = 0;
    m.flags.forEach((_, team) => {
      const g = el("g", { class: `flag ${TEAM[team]}` }, board);
      el("path", { d: "M0.35 0.2 V0.85 M0.35 0.2 L0.8 0.38 L0.35 0.56 Z" }, g);
      flagMarks.push(g);
    });
    seats.forEach((seat, i) => {
      const g = el("g", { class: `player ${seat.team}` }, board);
      el("circle", { cx: 0.5, cy: 0.5, r: 0.36 }, g);
      const label = el("text", { x: 0.5, y: 0.62, "text-anchor": "middle" }, g);
      label.textContent = String(i + 1);
      tokens.push(g);
    });
  }

  function place(g, x, y) {
    g.setAttribute("transform", `translate(${x} ${y})`);
  }

  function drawTick(t) {
    lastTick = performance.now();
    turn = t.tick;
    chosen = new Set(t.chosen || []);
    $("score-blue").textContent = t.score[0];
    $("score-red").textContent = t.score[1];
    $("clock").textContent = `${Math.max(0, match.max_ticks - t.tick)} turns left`;
    const carried = [null, null];
    t.players.forEach((p, i) => {
      const g = tokens[i];
      if (!g) return;
      g.style.display = p.respawn ? "none" : "";
      if (!p.respawn) place(g, p.x, p.y);
      g.classList.toggle("you", i === you);
      g.classList.toggle("bot", seats[i]?.kind === "bot");
      g.classList.toggle("carrying", p.carrying);
      if (p.carrying) carried[seats[i].team === "blue" ? 1 : 0] = p;
    });
    match.map.flags.forEach(([x, y], team) => {
      const c = carried[team];
      place(flagMarks[team], c ? c.x : x, c ? c.y - 0.3 : y);
    });
    if (you !== null) {
      const me = t.players[you];
      $("you").textContent = me.respawn
        ? `You were caught. Back in ${me.respawn} turns.`
        : `You are player ${you + 1}, on ${seats[you].team}.${me.carrying ? " You have their flag: get home!" : ""}`;
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
    drawMap();
    drawSeats();
    drawTick(snap.tick);
    if (watching) {
      const blue = seats.find((s) => s.team === "blue")?.bot;
      const red = seats.find((s) => s.team === "red")?.bot;
      $("you").textContent = `Watching: blue is the ${blue === "scripted" ? "scripted" : `trained bot (${blue})`}, red the ${red === "scripted" ? "scripted bot" : red}.`;
      notice("");
    } else if (snap.bench) {
      $("you").textContent = "Every seat has a person in it.";
      notice("You're on the bench: you'll play from the next match, which grows to 3 a side.");
    } else if (!snap.tick.break) {
      notice(snap.tick.tick > 0 && you !== null ? "You joined a match already under way, taking over from a bot." : "");
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
  const stream = new EventSource(`/arena/events${arenaId ? `?arena=${encodeURIComponent(arenaId)}` : ""}`);
  stream.addEventListener("snapshot", (e) => begin(JSON.parse(e.data)));
  stream.addEventListener("match", (e) => {
    begin(JSON.parse(e.data));
    moment("A new match started.");
  });
  stream.addEventListener("tick", (e) => drawTick(JSON.parse(e.data)));
  stream.addEventListener("chosen", (e) => {
    const c = JSON.parse(e.data);
    if (c.turn === turn) {
      chosen.add(c.seat);
      drawSeats();
    }
  });
  stream.addEventListener("seats", (e) => {
    seats = JSON.parse(e.data).seats;
    drawSeats();
  });
  stream.addEventListener("moment", (e) => {
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
  stream.addEventListener("over", (e) => {
    const [b, r] = JSON.parse(e.data).score;
    const result = b === r ? "a draw" : b > r ? "blue wins" : "red wins";
    notice(`Match over, ${b}–${r}: ${result}.`);
    moment(`Match over, ${b}–${r}.`);
  });
  stream.onopen = () => ($("status").textContent = "Connected.");
  stream.onerror = () => ($("status").textContent = "Connection lost. Reconnecting…");
  // The countdown to the next move, to a tenth of a second. It counts from when
  // this turn's board arrived, not from the server's clock, so clocks that
  // disagree don't matter. (The screen-reader status below updates less often.)
  setInterval(() => {
    const text = $("countdown");
    const bar = $("timer-bar");
    if (!lastTick || !match) return;
    const now = performance.now();
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
    if (quiet > deadline + 1.5) {
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
  focus.addEventListener("keydown", (e) => {
    if (!(e.key in KEYS)) return;
    e.preventDefault(); // arrows and space would scroll the page
    if (e.repeat) return; // holding is handled turn by turn, not by key repeat
    held = KEYS[e.key] === STAY ? null : KEYS[e.key];
    heldSince = performance.now();
    sentFor = -1;
    send(KEYS[e.key]);
  });
  focus.addEventListener("keyup", (e) => {
    if (e.key in KEYS && KEYS[e.key] === held) held = null;
  });
  focus.addEventListener("blur", () => (held = null)); // never keep walking after leaving the board

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
})();
