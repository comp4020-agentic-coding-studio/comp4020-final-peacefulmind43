// The replay page: plays a finished match's saved turns (ADR 0014). The
// server rebuilds every turn with the engine; this only draws them.

(() => {
  const $ = (name) => document.querySelector(`[data-field="${name}"]`);
  const id = document.querySelector("[data-match]").dataset.match;
  const WHAT = { tag: "got caught", pickup: "picked up the flag", capture: "scored!" };
  let data = null, draw = null, at = 0, timer = null;

  function who(seat, tick) {
    const span = data.seats[seat].people.find((p) => p.from <= tick && tick < p.to);
    return span ? span.label : "a bot";
  }

  function show(i) {
    at = Math.max(0, Math.min(i, data.frames.length - 1));
    const f = data.frames[at];
    draw(f.players, { bots: data.seats.map((s) => !s.people.some((p) => p.from <= f.tick && f.tick < p.to)) });
    $("score-blue").textContent = f.score[0];
    $("score-red").textContent = f.score[1];
    $("clock").textContent = `Turn ${f.tick} of ${data.frames.length - 1}`;
    $("turn").value = String(at);
    $("turn-number").textContent = String(f.tick);
    const moments = [];
    for (const g of data.frames.slice(1, at + 1)) {
      for (const [name, seat] of g.events) moments.push(`Turn ${g.tick}: player ${seat + 1} (${who(seat, g.tick - 1)}) ${WHAT[name]}`);
    }
    $("moments").replaceChildren(...moments.slice(-8).reverse().map((t) => Object.assign(document.createElement("li"), { textContent: t })));
    if (at === data.frames.length - 1) {
      stop();
      const [b, r] = data.score;
      $("status").textContent = `Final score ${b}–${r}: ${b === r ? "a draw" : b > r ? "blue wins" : "red wins"}.`;
    }
  }

  function stop() {
    clearInterval(timer);
    timer = null;
    $("play").textContent = "Play";
  }

  function play() {
    if (timer) return stop();
    if (at >= data.frames.length - 1) show(0);
    $("play").textContent = "Pause";
    $("status").textContent = "";
    timer = setInterval(() => show(at + 1), 1000 / Number($("speed").value));
  }

  $("play").addEventListener("click", play);
  $("back").addEventListener("click", () => { stop(); show(at - 1); });
  $("next").addEventListener("click", () => { stop(); show(at + 1); });
  $("turn").addEventListener("input", (e) => { stop(); show(Number(e.target.value)); });
  $("speed").addEventListener("change", () => { if (timer) { stop(); play(); } });
  document.addEventListener("keydown", (e) => {
    if (!data || e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLButtonElement) return;
    if (e.key === "ArrowLeft") { stop(); show(at - 1); }
    else if (e.key === "ArrowRight") { stop(); show(at + 1); }
    else if (e.key === " ") { e.preventDefault(); play(); }
    else return;
  });

  fetch(`/api/matches/${id}/frames`)
    .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
    .then((d) => {
      data = d;
      draw = window.CtfBoard.create($("board"), d.map, d.seats.map((s) => s.team));
      $("turn").max = String(d.frames.length - 1);
      $("roster").replaceChildren(...d.seats.map((s) => {
        const li = document.createElement("li");
        li.className = s.team;
        const names = [...new Set(s.people.map((p) => p.label))];
        li.textContent = `${s.seat + 1}. ${names.length ? names.join(", then ") : "Bot"}`;
        return li;
      }));
      show(0);
    })
    .catch(() => ($("status").textContent = "This replay couldn't be loaded. Try reloading the page."));
})();
