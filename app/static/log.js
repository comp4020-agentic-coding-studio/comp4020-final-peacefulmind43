// Live updates for the activity log (doc/adr/0006). The server sends each
// entry ready to show; this only draws it.

(() => {
  const list = document.querySelector('[data-field="log"]');
  const status = document.querySelector('[data-field="status"]');
  if (!list) return;

  function ago(at) {
    const s = Math.max(Math.floor(Date.now() / 1000) - at, 0);
    if (s >= 3600) return `${Math.floor(s / 3600)} hour${s >= 7200 ? "s" : ""} ago`;
    if (s >= 60) return `${Math.floor(s / 60)} min ago`;
    return "just now";
  }

  function span(cls, text) {
    const el = document.createElement("span");
    el.className = cls;
    el.textContent = text;
    return el;
  }

  // keep "x min ago" honest without a reload
  const refreshTimes = () => {
    for (const li of list.querySelectorAll("li[data-at]")) {
      li.querySelector(".when").textContent = ago(Number(li.dataset.at));
    }
  };
  refreshTimes();
  setInterval(refreshTimes, 30000);

  // "Right now": every arena's seats, refreshed every 2 seconds
  const now = document.querySelector('[data-field="now"]');
  function cell(tag, text) {
    const el = document.createElement(tag);
    el.textContent = text;
    return el;
  }
  async function drawNow() {
    const res = await fetch("/api/now");
    if (!res.ok || !now) return;
    const arenas = await res.json();
    if (!arenas.length) return now.replaceChildren(cell("p", "Nobody is playing."));
    now.replaceChildren(...arenas.map((a) => {
      const box = document.createElement("div");
      box.className = "now-arena";
      box.append(cell("h3", `${a.arena}: blue ${a.score[0]}, red ${a.score[1]}, turn ${a.turn}` +
        `${a.watching ? ` · ${a.watching} watching` : ""}${a.bench ? ` · ${a.bench} on the bench` : ""}`));
      const table = document.createElement("table");
      const head = document.createElement("tr");
      for (const h of ["Seat", "Team", "Who", "Choices in the last minute", "Pickups", "Captures", "Caught"]) {
        const th = cell("th", h);
        th.scope = "col";
        head.append(th);
      }
      table.append(head);
      for (const s of a.seats) {
        const tr = document.createElement("tr");
        const who = s.kind === "human" ? s.label : s.covering ? `bot covering ${s.covering}` : `${s.bot} bot`;
        for (const v of [s.seat + 1, s.team, who, s.kind === "human" ? s.choices_last_minute : "–", s.pickups, s.captures, s.caught]) {
          tr.append(cell("td", String(v)));
        }
        table.append(tr);
      }
      const wrap = document.createElement("div");
      wrap.className = "table-wrap";
      wrap.append(table);
      box.append(wrap);
      return box;
    }));
  }
  drawNow();
  setInterval(drawNow, 2000);

  if (!("EventSource" in window)) return;
  const stream = new EventSource("/log/events");
  stream.addEventListener("snapshot", () => {
    if (status) status.textContent = "Live: new activity appears at the top.";
  });
  stream.addEventListener("log", (e) => {
    const entry = JSON.parse(e.data);
    list.querySelector(".empty")?.remove();
    const li = document.createElement("li");
    li.dataset.eventId = entry.id;
    li.dataset.at = entry.at;
    li.className = `log-${entry.event}`;
    li.append(span("who", entry.visitor), span("what", entry.text), span("when", ago(entry.at)));
    list.prepend(li);
    while (list.children.length > 100) list.lastElementChild.remove();
  });
  stream.onerror = () => {
    if (status) status.textContent = "Reconnecting…";
  };
})();
