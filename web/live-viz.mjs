// Only real dispatched tasks and durably saved results drive these displays.
// No simulated work, random activity, or animation timer.
const NS = "http://www.w3.org/2000/svg";
const number = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 2,
});
const fmt = (v) => number.format(v || 0);
function node(tag, attrs = {}, value) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (value != null) e.textContent = value;
  return e;
}
function html(tag, cls, value) {
  const e = document.createElement(tag);
  e.className = cls;
  if (value != null) e.textContent = value;
  return e;
}
const polar = (r, a) => [200 + r * Math.cos(a), 200 + r * Math.sin(a)];

export function createLiveVisuals(contexts) {
  const $ = (id) => document.getElementById(id),
    root = $("run-wheel");
  if (!root) return null;
  const label = (id, t) => {
    if ($(id)) $(id).textContent = t;
  };
  let running = false,
    runState = "idle",
    active = null,
    started = 0,
    lastFrame = 0,
    lastSample = 0,
    lastCurves = 0;
  let totals = {},
    lanes = new Map(),
    recent = [],
    points = [],
    rate = 0,
    wheelKey = "";
  let weights = contexts.map((c) => ({
      id: c.id,
      weight: 1 / contexts.length,
    })),
    arcs = [],
    angles = new Map(),
    ball,
    marker,
    markerAngle = 0,
    wheelStatus;
  const cells = new Map();
  function mark() {
    if (!active) {
      arcs.forEach((a, i) =>
        a.setAttribute("class", `wheel-sector ${i % 2 ? "black" : "red"}`),
      );
      ball.setAttribute("visibility", "hidden");
      wheelStatus.textContent = "UNCLAIMED";
      return;
    }
    arcs.forEach((a, i) =>
      a.setAttribute(
        "class",
        `wheel-sector ${i % 2 ? "black" : "red"}${contexts[i].id === active.context ? " selected" : ""}`,
      ),
    );
    const degrees =
      (((angles.get(active.context) ?? -Math.PI / 2) + Math.PI / 2) * 180) /
      Math.PI;
    const turn = (((degrees - markerAngle) % 360) + 360) % 360;
    // Floating-point roundoff must not invent another revolution at rest.
    if (turn > 1e-7 && turn < 360 - 1e-7) markerAngle += turn;
    marker.style.transform = `rotate(${markerAngle}deg)`;
    ball.setAttribute("visibility", "visible");
    wheelStatus.textContent = running
      ? `${active.context} IN PLAY`
      : runState === "paused"
        ? "PAUSED"
        : "AT REST";
  }
  function wheel() {
    const svg = node("svg", {
      viewBox: "0 0 400 400",
      role: "img",
      "aria-label":
        "Roulette map of 81 real search lanes. Sector sizes show allocation, not discovery odds.",
    });
    svg.append(
      node("circle", { cx: 200, cy: 200, r: 192, class: "wheel-rim" }),
    );
    arcs = [];
    angles = new Map();
    let angle = -Math.PI / 2;
    for (let i = 0; i < contexts.length; i++) {
      const c = contexts[i],
        weight = weights.find((w) => w.id === c.id)?.weight || 1 / 81,
        end = angle + weight * 2 * Math.PI;
      const a = polar(180, angle),
        b = polar(180, end),
        d = polar(139, end),
        e = polar(139, angle);
      const path = node("path", {
        d: `M${a} A180 180 0 ${end - angle > Math.PI ? 1 : 0} 1 ${b} L${d} A139 139 0 ${end - angle > Math.PI ? 1 : 0} 0 ${e} Z`,
        class: `wheel-sector ${i % 2 ? "black" : "red"}`,
      });
      path.append(
        node("title", {}, `${c.id}: ${(100 * weight).toFixed(2)}% allocation`),
      );
      svg.append(path);
      arcs.push(path);
      angles.set(c.id, (angle + end) / 2);
      if (i % 9 === 0) {
        const p = polar(160, (angle + end) / 2);
        svg.append(
          node(
            "text",
            {
              x: p[0],
              y: p[1] + 3,
              "text-anchor": "middle",
              class: "wheel-number",
            },
            c.id.slice(1),
          ),
        );
      }
      angle = end;
    }
    svg.append(
      node("circle", { cx: 200, cy: 200, r: 130, class: "wheel-inner" }),
    );
    svg.append(
      node(
        "text",
        { x: 200, y: 174, "text-anchor": "middle", class: "wheel-small" },
        "SUM OF THREE CUBES",
      ),
    );
    svg.append(
      node(
        "text",
        { x: 200, y: 246, "text-anchor": "middle", class: "wheel-jackpot" },
        "114",
      ),
    );
    wheelStatus = node(
      "text",
      { x: 200, y: 276, "text-anchor": "middle", class: "wheel-small" },
      "UNCLAIMED",
    );
    svg.append(wheelStatus);
    ball = node("circle", {
      cx: 200,
      cy: 12,
      r: 5,
      class: "wheel-ball",
      visibility: "hidden",
    });
    marker = node("g", { class: "wheel-marker" });
    marker.style.transform = `rotate(${markerAngle}deg)`;
    marker.append(ball);
    svg.append(marker);
    root.replaceChildren(svg);
    mark();
  }
  const grid = $("run-lanes");
  if (grid) {
    grid.replaceChildren();
    for (const c of contexts) {
      const b = html("button", "lane-cell", c.id.slice(1));
      b.type = "button";
      b.setAttribute("aria-label", `${c.id}: no completed work this session`);
      b.addEventListener("click", () => {
        const n = lanes.get(c.id) || { tasks: 0, curves: 0 };
        label(
          "lane-detail",
          `${c.id} · ${n.tasks} batches · ${fmt(n.curves)} intervals · ℓ=${c.ell} · shape ${c.shape + 1} · shell ${c.shell + 1} · quotient band ${c.low}–${c.high}`,
        );
      });
      grid.append(b);
      cells.set(c.id, b);
    }
  }
  function pulse() {
    const el = $("run-pulse");
    if (!el || points.length < 2) return;
    const W = Math.max(280, Math.min(760, el.clientWidth || 760)),
      H = 190,
      pl = 50,
      pb = 27,
      max = Math.max(...points.map((p) => p.rate), 1),
      first = points[0].at,
      last = points.at(-1).at;
    const X = (x) =>
        pl + ((x - first) / Math.max(1, last - first)) * (W - pl - 12),
      Y = (y) => 10 + (1 - y / max) * (H - pb - 10);
    const svg = node("svg", {
      viewBox: `0 0 ${W} ${H}`,
      role: "img",
      "aria-label":
        "Measured curve intervals per wall-clock second across completed batches. Zero-based vertical axis.",
    });
    for (let i = 0; i < 4; i++) {
      const y = (max * i) / 3;
      svg.append(
        node("line", {
          x1: pl,
          y1: Y(y),
          x2: W - 12,
          y2: Y(y),
          class: "chart-grid",
        }),
      );
      svg.append(
        node(
          "text",
          {
            x: pl - 8,
            y: Y(y) + 4,
            "text-anchor": "end",
            class: "chart-label",
          },
          fmt(y),
        ),
      );
    }
    const path = points
      .map(
        (p, i) =>
          `${i ? "L" : "M"}${X(p.at).toFixed(1)},${Y(p.rate).toFixed(1)}`,
      )
      .join(" ");
    svg.append(
      node("path", {
        d: path + ` L${X(last)},${H - pb} L${X(first)},${H - pb} Z`,
        class: "pulse-area",
      }),
    );
    svg.append(node("path", { d: path, class: "pulse-line" }));
    for (const [at, anchor] of [
      [first, "start"],
      [last, "end"],
    ])
      svg.append(
        node(
          "text",
          { x: X(at), y: H - 4, "text-anchor": anchor, class: "chart-label" },
          `${Math.max(0, (at - started) / 1000).toFixed(1)}s`,
        ),
      );
    el.replaceChildren(svg);
  }
  function sieve() {
    const el = $("run-sieve");
    if (!el || !totals.quotient_points) return;
    const q = totals.quotient_points,
      a = q - (totals.rejected_mod243 || 0),
      b = a - (totals.rejected_parity || 0),
      c = b - (totals.rejected_prime || 0);
    const rows = [
      ["Candidates", q],
      ["After mod 243", a],
      ["After parity", b],
      ["After prime filters", c],
      ["Exact square tests", totals.exact_tests || 0],
    ];
    el.replaceChildren();
    for (const [name, value] of rows) {
      const row = html("div", "sieve-row");
      row.append(html("span", "", name), html("strong", "", fmt(value)));
      const track = html("div", "sieve-track"),
        bar = html("div", "sieve-bar");
      bar.style.width = `${value ? (Math.log1p(value) / Math.log1p(q)) * 100 : 0}%`;
      track.append(bar);
      row.append(track);
      el.append(row);
    }
    label(
      "filter-cut",
      `${(100 * (1 - (totals.exact_tests || 0) / q)).toFixed(4)}% filtered`,
    );
  }
  function paint(force = false) {
    const now = Date.now();
    if (!force && now - lastFrame < 180) return;
    lastFrame = now;
    mark();
    pulse();
    sieve();
    label("run-rate", running ? fmt(rate) : "—");
    label("lane-total", `${lanes.size} / 81 lanes played`);
    const max = Math.max(1, ...[...lanes.values()].map((v) => v.curves));
    for (const c of contexts) {
      const b = cells.get(c.id);
      if (!b) continue;
      const n = lanes.get(c.id),
        strength = n ? Math.log1p(n.curves) / Math.log1p(max) : 0;
      b.style.setProperty("--lane-light", String(strength));
      b.className = `lane-cell${n ? " played" : ""}${active?.context === c.id && running ? " current" : ""}`;
      b.setAttribute(
        "aria-label",
        `${c.id}: ${n?.tasks || 0} completed batches, ${n?.curves || 0} curve intervals`,
      );
    }
    const stream = $("run-stream");
    if (stream && recent.length) {
      stream.replaceChildren();
      for (const r of recent) {
        const row = html("div", "recent-hand");
        row.append(
          html("strong", "", r.context),
          html("span", "", `${fmt(r.curves)} intervals`),
          html("span", "", `${r.exact} exact tests`),
          html("span", "", `${r.ms.toFixed(1)} ms`),
        );
        stream.append(row);
      }
    }
  }
  wheel();
  return {
    reset() {
      totals = {};
      lanes = new Map();
      recent = [];
      points = [];
      active = null;
      rate = 0;
      started = Date.now();
      lastSample = started;
      lastCurves = 0;
      running = true;
      label("filter-cut", "—");
      $("run-pulse").replaceChildren(html("p", "", "—"));
      $("run-sieve").replaceChildren(html("p", "", "—"));
      $("run-stream").replaceChildren();
      paint(true);
    },
    dispatch(task) {
      active = task;
      running = true;
      paint();
    },
    result({ result, elapsedMs }) {
      for (const [k, v] of Object.entries(result.counters))
        totals[k] = (totals[k] || 0) + v;
      const c = result.task.context,
        n = lanes.get(c) || { tasks: 0, curves: 0 };
      n.tasks++;
      n.curves += result.counters.curves;
      lanes.set(c, n);
      recent.unshift({
        context: c,
        curves: result.counters.curves,
        exact: result.counters.exact_tests,
        ms: Number.isFinite(elapsedMs) ? Math.max(0, elapsedMs) : 0,
      });
      recent = recent.slice(0, 8);
      const now = Date.now();
      if (now - lastSample >= 250) {
        rate = ((totals.curves - lastCurves) * 1000) / (now - lastSample);
        points.push({ at: now, rate });
        if (points.length > 100) points.shift();
        lastSample = now;
        lastCurves = totals.curves;
      }
      paint();
    },
    state(state) {
      runState = state;
      running = state === "running";
      paint(true);
      if (state === "paused") label("run-rate", "Paused");
    },
    policy(policy) {
      const next =
          policy?.contexts ||
          contexts.map((c) => ({ id: c.id, weight: 1 / 81 })),
        key = next.map((w) => `${w.id}:${w.weight}`).join("|");
      if (key !== wheelKey) {
        weights = next;
        wheelKey = key;
        wheel();
      }
    },
  };
}
