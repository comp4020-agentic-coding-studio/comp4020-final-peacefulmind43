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
