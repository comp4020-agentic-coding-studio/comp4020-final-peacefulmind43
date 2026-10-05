// Live updates for the room (doc/adr/0001, 0003). The server decides what each
// visitor may see; this only draws what it sends. Without JavaScript the page
// still works, it just needs a reload to catch up.

(() => {
  const $ = (name) => document.querySelector(`[data-field="${name}"]`);
  const pct = (x, digits = 1) => `${(x * 100).toFixed(digits)}%`;

  function text(tag, value) {
    const el = document.createElement(tag);
    el.textContent = value;
    return el;
  }

  function drawRound(r) {
    for (const key of ["trial_count", "distinct_rules", "visitor_count"]) {
      const el = $(key);
      if (el) el.textContent = r[key];
    }
    const luck = $("luck_text");
    if (luck) {
      luck.replaceChildren();
      if (r.luck_bar === null) {
        luck.append("The luck bar appears once two different timing rules have been tried.");
      } else {
        luck.append("The luck bar is ", text("strong", r.luck_bar.toFixed(2)),
          `: with ${r.timing_rules} different timing rules tried, the best one would seem to add about this much by luck alone.`);
      }
    }
  }

  function ago(seconds) {
    const s = Math.max(Math.floor(Date.now() / 1000) - seconds, 0);
    if (s >= 86400) return `${Math.floor(s / 86400)} day${s >= 172800 ? "s" : ""} ago`;
    if (s >= 3600) return `${Math.floor(s / 3600)} hour${s >= 7200 ? "s" : ""} ago`;
    if (s >= 60) return `${Math.floor(s / 60)} min ago`;
    return "just now";
  }

  function drawTrials({ trials, hidden, unlocked }) {
    const rows = $("rows");
    if (rows) {
      rows.replaceChildren(...trials.map((t) => {
        const tr = document.createElement("tr");
        tr.dataset.trialId = t.id;
        if (t.is_me) tr.className = "me";
        tr.append(
          text("td", t.visitor + (t.is_me ? " (you)" : "")),
          text("td", t.rule.label),
          text("td", pct(t.stats.cagr)),
          text("td", pct(t.stats.max_drawdown, 0)),
          text("td", t.stats.sharpe.toFixed(2)),
          text("td", t.confidence === null ? "–" : pct(t.confidence, 0)),
          text("td", ago(t.created_at)),
        );
        return tr;
      }));
      rows.closest(".table-wrap").hidden = trials.length === 0;
    }
    const locked = $("locked");
    if (locked) {
      locked.hidden = unlocked || hidden === 0;
      $("hidden").textContent = hidden;
    }
    const empty = $("empty");
    if (empty) empty.hidden = trials.length > 0 || hidden > 0;
    for (const t of trials) {
      const mine = document.querySelector(`[data-confidence-for="${t.id}"]`);
      if (mine) mine.textContent = t.confidence !== null ? pct(t.confidence, 0) : t.rule.type === "fixed" ? "no timing" : "not yet";
    }
  }

  async function refreshTrials() {
    const res = await fetch("/api/rounds/current/trials", { credentials: "same-origin" });
    if (res.ok) drawTrials(await res.json());
  }

  if (!("EventSource" in window)) return;
  const status = $("status");
  const stream = new EventSource("/events");
  stream.addEventListener("snapshot", (e) => {
    drawRound(JSON.parse(e.data));
    refreshTrials(); // after a reconnect, catch up on anything missed
    if (status) status.textContent = "Live: new tests appear here as people run them.";
  });
  stream.addEventListener("update", (e) => {
    drawRound(JSON.parse(e.data));
    refreshTrials();
  });
  stream.addEventListener("reveal", (e) => {
    const { revealed_round_id: id, round } = JSON.parse(e.data);
    drawRound(round);
    const reveal = $("reveal_text");
    if (reveal) reveal.textContent = round.reveal_text;
    const heading = document.getElementById("round-heading");
    if (heading) heading.textContent = round.name;
    const banner = $("revealed");
    if (banner) {
      const link = document.createElement("a");
      link.href = `/rounds/${id}`;
      link.textContent = "See how every rule did in the locked years";
      banner.replaceChildren("The last round was just revealed, and a new one has opened. ", link, ".");
      banner.hidden = false;
    }
    refreshTrials();
  });
  stream.onerror = () => {
    if (status) status.textContent = "Reconnecting…";
  };
})();
