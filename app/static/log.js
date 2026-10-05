// Live updates for the activity log (doc/adr/0006). The server has already
// redacted each entry for this visitor; this only draws it.

(() => {
  const list = document.querySelector('[data-field="log"]');
  const status = document.querySelector('[data-field="status"]');
  if (!list || !("EventSource" in window)) return;

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

  function drawCounts(counts) {
    for (const [key, value] of Object.entries(counts || {})) {
      const el = document.querySelector(`[data-count="${key}"]`);
      if (el) el.textContent = value;
    }
  }

  const stream = new EventSource("/log/events");
  stream.addEventListener("snapshot", (e) => {
    drawCounts(JSON.parse(e.data));
    if (status) status.textContent = "Live: new activity appears at the top.";
  });
  stream.addEventListener("log", (e) => {
    const entry = JSON.parse(e.data);
    drawCounts(entry.counts);
    list.querySelector(".empty")?.remove();
    const li = document.createElement("li");
    li.dataset.eventId = entry.id;
    li.dataset.at = entry.at;
    const mine = entry.detail && entry.detail.mine;
    li.className = `log-${entry.event}${mine ? " me" : ""}`;
    li.append(span("who", entry.visitor + (mine ? " (you)" : "")), span("what", entry.text), span("when", ago(entry.at)));
    list.prepend(li);
    while (list.children.length > 100) list.lastElementChild.remove();
  });
  stream.onerror = () => {
    if (status) status.textContent = "Reconnecting…";
  };

  // keep "x min ago" honest without a reload
  setInterval(() => {
    for (const li of list.querySelectorAll("[data-at]")) {
      li.querySelector(".when").textContent = ago(Number(li.dataset.at));
    }
  }, 30000);
})();
