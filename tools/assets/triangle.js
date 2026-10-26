// The source triangle, shared by the share-card, icon and video renderers.
// Same geometry as the homepage: six item tiles in rows of 1, 2 and 3, three
// connectors between them, and a base mosaic of 112 small triangles.
const TRI = (() => {
  const S = 150, H = S * Math.sqrt(3) / 2, CX = 300, NS = "http://www.w3.org/2000/svg";
  const P = (r, k, side = S) => [CX - r * side / 2 + k * side, r * side * Math.sqrt(3) / 2];
  const up = (r, j, side = S) => [P(r, j, side), P(r + 1, j, side), P(r + 1, j + 1, side)];
  const down = (r, j, side = S) => [P(r, j, side), P(r, j + 1, side), P(r + 1, j + 1, side)];
  const centroid = t => [(t[0][0] + t[1][0] + t[2][0]) / 3, (t[0][1] + t[1][1] + t[2][1]) / 3];
  function inset(t, g) {
    const c = centroid(t);
    const rin = Math.hypot(t[1][0] - t[0][0], t[1][1] - t[0][1]) / (2 * Math.sqrt(3));
    const f = (rin - g) / rin;
    return t.map(([x, y]) => [c[0] + (x - c[0]) * f, c[1] + (y - c[1]) * f]);
  }
  const pts = t => t.map(([x, y]) => x.toFixed(2) + "," + y.toFixed(2)).join(" ");
  const ITEMS = [
    { id: "story", name: "Story", act: "Rewrite", r: 0, j: 0 },
    { id: "coordination", name: "Coordination", act: "Route", r: 1, j: 0 },
    { id: "vision", name: "Vision", act: "Preview", r: 1, j: 1 },
    { id: "attention", name: "Attention", act: "Bloom", r: 2, j: 0 },
    { id: "status", name: "Status", act: "Give", r: 2, j: 1 },
    { id: "gatekeepers", name: "Gatekeepers", act: "Open", r: 2, j: 2 },
  ];
  const CONNECTORS = [[1, 0], [2, 0], [2, 1]];

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.append(e);
    return e;
  }

  // Draws the triangle into an <svg>. Returns handles so callers can animate it.
  function draw(svg, { labels = true, tileFont = 19 } = {}) {
    svg.setAttribute("viewBox", "0 -8 600 536");
    const gBase = el("g", {}, svg), gConn = el("g", {}, svg), gTiles = el("g", {}, svg), gFx = el("g", {}, svg);
    const q = S / 4, mosaic = [];
    for (let r = 12; r < 16; r++) {
      for (let j = 0; j <= r; j++) mosaic.push(up(r, j, q));
      for (let j = 0; j < r; j++) mosaic.push(down(r, j, q));
    }
    let seed = 20261025;
    const rand = () => {
      seed = (seed + 0x6D2B79F5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const mo = mosaic.map(t => ({ el: el("polygon", { class: "mo", points: pts(inset(t, 1.6)) }, gBase), c: centroid(t), rank: rand() }));
    const conns = CONNECTORS.map(([r, j]) => {
      const p = pts(inset(down(r, j), 3.5));
      el("polygon", { class: "conn", points: p }, gConn);
      return el("polygon", { class: "conn-glow", points: p, opacity: 0 }, gConn);
    });
    const tiles = ITEMS.map(it => {
      const t = up(it.r, it.j), c = centroid(t), top = it.r * H;
      const g = el("g", { class: "tile" + (it.r === 0 ? " is-apex" : "") }, gTiles);
      const shape = el("polygon", { class: "tile-shape", points: pts(inset(t, 3.5)) }, g);
      if (labels) {
        const name = el("text", { class: "tile-name", x: c[0].toFixed(1), y: (top + 98).toFixed(1), "font-size": tileFont }, g);
        name.textContent = it.name;
      }
      return { ...it, g, shape, c };
    });
    return { svg, mo, conns, tiles, fx: gFx, el };
  }

  return { draw, ITEMS, S, H };
})();
