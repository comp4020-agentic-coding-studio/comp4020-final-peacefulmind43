// The game page (doc/adr/0011). The server runs the game; this draws what it
// sends and sends what you press. Nothing here decides anything about the game.

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
  let tickHz = 4;
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
    $("score-blue").textContent = t.score[0];
    $("score-red").textContent = t.score[1];
    const left = Math.max(0, Math.ceil((match.max_ticks - t.tick) / tickHz));
    $("clock").textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
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
        ? `You were caught. Back in ${Math.ceil(me.respawn / tickHz)} s.`
        : `You are player ${you + 1}, on ${seats[you].team}.${me.carrying ? " You have their flag: get home!" : ""}`;
    }
    if (t.break) notice(`Next match in ${Math.ceil(t.break)} s.`);
  }

  function drawSeats() {
    const list = $("roster");
    list.replaceChildren(
      ...seats.map((s, i) => {
        const li = document.createElement("li");
        li.className = `${s.team}${i === you ? " me" : ""}`;
        const who = s.kind === "human" ? s.label : s.covering ? `Bot, covering for ${s.covering}` : "Bot";
        li.textContent = `${i + 1}. ${who}${i === you ? " (you)" : ""}`;
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
    match = snap.match;
    tickHz = match.tick_hz;
    seats = snap.seats;
    you = snap.you;
    drawMap();
    drawSeats();
    drawTick(snap.tick);
    if (snap.bench) {
      $("you").textContent = "Every seat has a person in it.";
      notice("You're on the bench: you'll play from the next match, which grows to 3 a side.");
    } else if (!snap.tick.break) {
      notice(snap.tick.tick > 0 && you !== null ? "You joined a match already under way, taking over from a bot." : "");
    }
  }

  // --- the connection ---------------------------------------------------------

  const params = new URLSearchParams(location.search);
  const stream = new EventSource(`/arena/events${params.get("arena") ? `?arena=${encodeURIComponent(params.get("arena"))}` : ""}`);
  stream.addEventListener("snapshot", (e) => begin(JSON.parse(e.data)));
  stream.addEventListener("match", (e) => {
    begin(JSON.parse(e.data));
    moment("A new match started.");
  });
  stream.addEventListener("tick", (e) => drawTick(JSON.parse(e.data)));
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
  setInterval(() => {
    if (!lastTick) return;
    const quiet = (performance.now() - lastTick) / 1000;
    $("status").textContent = quiet > 1.5 ? `Slow connection: last update ${quiet.toFixed(0)} s ago.` : "Connected.";
  }, 500);

  // --- input ------------------------------------------------------------------

  function send(dir, held) {
    seq += 1;
    fetch("/arena/input", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ dir, held, seq }),
      keepalive: true,
    }).catch(() => {});
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
    if (!e.repeat) send(KEYS[e.key], true);
  });
  focus.addEventListener("keyup", (e) => {
    if (e.key in KEYS && KEYS[e.key] !== STAY) send(STAY, true);
  });
  focus.addEventListener("blur", () => send(STAY, true)); // never keep walking after leaving the board

  for (const button of document.querySelectorAll(".pad button")) {
    const dir = Number(button.dataset.dir);
    // touch and mouse: hold to keep moving
    button.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      button.setPointerCapture(e.pointerId);
      send(dir, true);
    });
    for (const end of ["pointerup", "pointercancel"]) button.addEventListener(end, () => send(STAY, true));
    // keyboard (Enter or Space on the button): one step per press
    button.addEventListener("click", (e) => {
      if (e.detail === 0) send(dir, false);
    });
  }
})();
