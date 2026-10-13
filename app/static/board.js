// Drawing the board, shared by the game page and the replay page. It only
// draws what it is given; nothing here decides anything about the game.

window.CtfBoard = (() => {
  const SVG = "http://www.w3.org/2000/svg";
  const TEAM = ["blue", "red"];

  function el(name, attrs, parent) {
    const node = document.createElementNS(SVG, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.append(node);
    return node;
  }

  const place = (g, x, y) => g.setAttribute("transform", `translate(${x} ${y})`);

  // Draw the map and one token per seat (teams: "blue"/"red" per seat).
  // Returns draw(players, options) to move tokens and flags.
  function create(board, map, teams) {
    board.setAttribute("viewBox", `0 0 ${map.width} ${map.height}`);
    board.replaceChildren();
    el("rect", { x: 0, y: 0, width: map.width / 2, height: map.height, class: "half blue" }, board);
    el("rect", { x: map.width / 2, y: 0, width: map.width / 2, height: map.height, class: "half red" }, board);
    map.bases.forEach((base, team) => {
      for (const [x, y] of base) el("rect", { x, y, width: 1, height: 1, class: `base ${TEAM[team]}` }, board);
    });
    for (const [x, y] of map.walls) el("rect", { x, y, width: 1, height: 1, class: "wall" }, board);
    const flagMarks = map.flags.map((_, team) => {
      const g = el("g", { class: `flag ${TEAM[team]}` }, board);
      el("path", { d: "M0.35 0.2 V0.85 M0.35 0.2 L0.8 0.38 L0.35 0.56 Z" }, g);
      return g;
    });
    const tokens = teams.map((team, i) => {
      const g = el("g", { class: `player ${team}` }, board);
      el("circle", { cx: 0.5, cy: 0.5, r: 0.36 }, g);
      el("text", { x: 0.5, y: 0.62, "text-anchor": "middle" }, g).textContent = String(i + 1);
      return g;
    });

    // players: [{x, y, respawn, carrying}]; you: your seat or null; bots: seat -> is a bot
    return function draw(players, { you = null, bots = [] } = {}) {
      const carried = [null, null];
      players.forEach((p, i) => {
        const g = tokens[i];
        if (!g) return;
        g.style.display = p.respawn ? "none" : "";
        if (!p.respawn) place(g, p.x, p.y);
        g.classList.toggle("you", i === you);
        g.classList.toggle("bot", !!bots[i]);
        g.classList.toggle("carrying", !!p.carrying);
        if (p.carrying) carried[teams[i] === "blue" ? 1 : 0] = p;
      });
      map.flags.forEach(([x, y], team) => {
        const c = carried[team];
        place(flagMarks[team], c ? c.x : x, c ? c.y - 0.3 : y);
      });
    };
  }

  return { create };
})();
