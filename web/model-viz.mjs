// Published, replay-derived policies only; no invented epoch observations.
const NS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const node = (tag, attrs = {}, text) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text != null) n.textContent = text;
  return n;
};
export function renderModelEvolution(cluster, strategy) {
  const root = $("model-history"),
    slider = $("model-epoch");
  if (!root || !slider) return;
  const history = (cluster.calibration_history || []).filter(
    (h) =>
      Number.isInteger(h.epoch) &&
      h.weights &&
      Object.values(h.weights).every((w) => Number.isFinite(w) && w >= 0),
  );
  const records = [
    {
      epoch: 0,
      through_verified_tasks: 0,
      weights: Object.fromEntries(
        Array.from({ length: 81 }, (_, i) => [
          `c${String(i).padStart(2, "0")}`,
          1 / 81,
        ]),
      ),
    },
    ...history,
  ];
  const previousMax = Number(slider.max),
    followLatest = Number(slider.value) === previousMax;
  slider.max = String(records.length - 1);
  slider.disabled = records.length < 2;
  if (followLatest) slider.value = slider.max;
  const text = (id, t) => {
    if ($(id)) $(id).textContent = t;
  };
  text(
    "model-trained",
    String((strategy?.contexts || []).filter((c) => c.sample_size >= 3).length),
  );
  text(
    "strategy-epoch",
    `Epoch ${strategy?.epoch ?? history.at(-1)?.epoch ?? 0}`,
  );
  const verified = Number(cluster.totals?.verified_unique_tasks || 0);
  if ($("model-progress")) $("model-progress").value = verified % 64;
  text(
    "model-progress-note",
    `${verified % 64} / 64 verified batches toward the next update. ${verified.toLocaleString()} verified so far.`,
  );
  function draw() {
    const record =
      records[Math.min(records.length - 1, Math.max(0, Number(slider.value)))];
    if (!record) return;
    const entries = Object.entries(record.weights).sort(([a], [b]) =>
        a.localeCompare(b),
      ),
      max = Math.max(1 / 81, ...entries.map(([, w]) => w)) * 1.12;
    const width = Math.max(340, Math.min(1000, root.clientWidth || 1000)),
      spacing = (width - 70) / 81;
    const svg = node("svg", {
      viewBox: `0 0 ${width} 240`,
      role: "img",
      "aria-label": `Recorded allocation at epoch ${record.epoch}. Zero-based vertical axis; dashed line is uniform prior.`,
    });
    const X = (i) => 56 + i * spacing,
      Y = (w) => 200 - (w / max) * 180;
    for (let i = 0; i <= 3; i++) {
      const v = (max * i) / 3;
      svg.append(
        node("line", {
          x1: 52,
          x2: width - 14,
          y1: Y(v),
          y2: Y(v),
          class: "chart-grid",
        }),
      );
      svg.append(
        node(
          "text",
          { x: 44, y: Y(v) + 4, "text-anchor": "end", class: "chart-label" },
          `${(100 * v).toFixed(1)}%`,
        ),
      );
    }
    entries.forEach(([id, weight], i) => {
      const bar = node("rect", {
        x: X(i),
        y: Y(weight),
        width: Math.max(1, spacing - 2),
        height: 200 - Y(weight),
        class: "model-bar",
        tabindex: 0,
        role: "button",
        "aria-label": `${id}: ${(100 * weight).toFixed(3)} percent at epoch ${record.epoch}`,
      });
      bar.append(node("title", {}, `${id}: ${(100 * weight).toFixed(3)}%`));
      const select = () =>
        text(
          "model-detail",
          `${id} · epoch ${record.epoch} · ${(100 * weight).toFixed(3)}% of allocation · ${(weight * 81).toFixed(2)}× uniform. Allocation is a cost decision, not a discovery probability.`,
        );
      bar.addEventListener("click", select);
      bar.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          select();
        }
      });
      svg.append(bar);
      if (i % (width < 500 ? 20 : 10) === 0)
        svg.append(node("text", { x: X(i), y: 225, class: "chart-label" }, id));
    });
    svg.append(
      node("line", {
        x1: 52,
        x2: width - 14,
        y1: Y(1 / 81),
        y2: Y(1 / 81),
        class: "uniform-reference",
      }),
    );
    root.replaceChildren(svg);
    text(
      "model-selected",
      record.epoch
        ? `Epoch ${record.epoch} · ${record.through_verified_tasks} batches`
        : "Uniform prior · 0 batches",
    );
  }
  slider.oninput = draw;
  draw();
}
