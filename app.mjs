import {
  CONTEXTS,
  makeTask,
  taskId,
  canonicalJSON,
  verifyTriple,
  validateTask,
} from "./engine.mjs?v=91edbf56d67b";
import { createLiveVisuals } from "./live-viz.mjs?v=91edbf56d67b";
import { createJackpot } from "./jackpot.mjs?v=91edbf56d67b";
import { loadChallenger } from "./challenger-viz.mjs?v=91edbf56d67b";
import { renderModelEvolution } from "./model-viz.mjs?v=91edbf56d67b";
import { setupRunnerDownload } from "./runner-setup.mjs?v=91edbf56d67b";
setupRunnerDownload();
import { createCoverageClient, newSeed, seededRandom, SEED_ALGORITHM } from "./search-session.mjs?v=91edbf56d67b";
const BASE = new URL("./", import.meta.url),
  REPO = "https://github.com/Kuberwastaken/math-gambling";
const $ = (id) => document.getElementById(id),
  text = (id, v) => {
    if ($(id)) $(id).textContent = v;
  };
const nf = new Intl.NumberFormat("en-US"),
  compact = new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  });
const fmt = (v) => {
  try {
    return nf.format(BigInt(v ?? 0));
  } catch {
    return "—";
  }
};
const small = (v) => {
  try {
    return compact.format(BigInt(v ?? 0));
  } catch {
    return "—";
  }
};
const date = (v) => {
  const d = new Date(v);
  return Number.isFinite(d.getTime())
    ? d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : "No timestamp";
};
const reportRequests = new Map();
const REPORT_TIMEOUT_MS = 12000, REPORT_BYTE_LIMIT = 16 * 1024 * 1024;
function fetchJSON(file) {
  if (reportRequests.has(file)) return reportRequests.get(file);
  const controller = new AbortController();
  let timer;
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(Error("Report request timed out"));
    }, REPORT_TIMEOUT_MS);
  });
  const reading = (async () => {
    const response = await fetch(new URL(file, BASE), {
      cache: "no-cache", signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Report unavailable (${response.status})`);
    if (Number(response.headers.get("content-length")) > REPORT_BYTE_LIMIT) {
      controller.abort();
      throw Error("Report exceeds its size limit");
    }
    const reader = response.body.getReader(), chunks = [];
    let length = 0;
    try {
      for (;;) {
        const {done, value} = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > REPORT_BYTE_LIMIT) throw Error("Report exceeds its size limit");
        chunks.push(value);
      }
    } catch (error) {
      controller.abort();
      try { await reader.cancel(); } catch {}
      throw error;
    }
    const bytes = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    return JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(bytes));
  })();
  const request = Promise.race([reading, deadline]).finally(() => {
    clearTimeout(timer);
    reportRequests.delete(file);
  });
  reportRequests.set(file, request);
  return request;
}
const sharedCoverage = createCoverageClient(BASE);
let jackpot;
try {
  jackpot = createJackpot({ onSave: (evidence) => download("math-gambling-identity-evidence.json", JSON.stringify(evidence, null, 2)) });
} catch { /* The display cannot interrupt evidence preservation. */ }
function showJackpot(xyz, receipt, source = "local", animate = true) {
  try {
    if (jackpot?.show({ xyz, receipt, source, animate })) showRun("jackpot", xyz);
  } catch { /* Saving and banking run independently of the celebration. */ }
}
let liveVisuals;
try {
  liveVisuals = createLiveVisuals(CONTEXTS);
} catch {
  /* Visuals never decide coverage. */
}
function showRun(method, value) {
  try {
    liveVisuals?.[method](value);
  } catch {
    liveVisuals = null;
    text(
      "viz-state",
      "Charts paused. Exact computation and saving remain active.",
    );
  }
}
const DUTIES = [25, 50, 90],
  DUTY_NAMES = ["Gentle", "Balanced", "All in"];
function processorDuty() {
  return (DUTIES[Number($("run-duty")?.value)] ?? 25) / 100;
}
function updateProcessor() {
  const index = DUTIES.indexOf(Math.round(processorDuty() * 100)),
    percent = DUTIES[index];
  text("duty-readout", `${percent}% · ${DUTY_NAMES[index]}`);
  $("run-duty")?.setAttribute(
    "aria-valuetext",
    `${DUTY_NAMES[index]}, ${percent} percent of one worker`,
  );
}
$("run-duty")?.addEventListener("input", updateProcessor);
updateProcessor();
function safeProfileURL(value) {
  if (typeof value !== "string" || value.length > 2048 ||
      /[\s\u0000-\u001f\u007f\\]/u.test(value) || !/^https?:\/\//i.test(value)) return "";
  try {
    const url = new URL(value);
    return url.hostname && !url.username && !url.password ? value : "";
  } catch { return ""; }
}
let profile = { name: "", github: "", url: "" };
try {
  profile = JSON.parse(localStorage.getItem("mg-profile") || "null") || profile;
} catch {}
profile = {
  name: typeof profile?.name === "string" ? profile.name.slice(0, 60) : "",
  github:
    typeof profile?.github === "string" ? profile.github.slice(0, 39) : "",
  url: safeProfileURL(profile?.url),
};
function profilePreview() {
  const name =
    typeof profile.name === "string" ? profile.name.slice(0, 60) : "";
  text("teaser-name", name || "________________________");
  text(
    "paper-contributor",
    name
      ? `${name}${profile.github ? ` (@${profile.github})` : ""}`
      : "________________________",
  );
  if (name)
    text(
      "paper-preview-note",
      `This copy previews a contribution credit for ${name}. The finder and result remain blank. This is not a claim of authorship or discovery.`,
    );
}
profilePreview();
$("clear-profile")?.addEventListener("click", () => {
  localStorage.removeItem("mg-profile");
  profile = { name: "", github: "" };
  text(
    "clear-profile-status",
    "Profile removed. Computation receipts are retained.",
  );
  profilePreview();
});
$("print-paper")?.addEventListener("click", () => window.print());
function download(name, body, type = "application/json") {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
$("download-tex")?.addEventListener("click", async (e) => {
  if (!profile.name) return;
  e.preventDefault();
  try {
    let t = await (
      await fetch(new URL("downloads/math-gambling-draft.tex", BASE))
    ).text();
    const esc = (s) =>
      s.replace(
        /[\\{}$&#_%~^]/g,
        (c) =>
          ({
            "\\": "\\textbackslash{}",
            "{": "\\{",
            "}": "\\}",
            $: "\\$",
            "&": "\\&",
            "#": "\\#",
            _: "\\_",
            "%": "\\%",
            "~": "\\textasciitilde{}",
            "^": "\\textasciicircum{}",
          })[c],
      );
    t = t.replace(
      "\\underline{\\hspace{45mm}}",
      esc(profile.name + (profile.github ? ` (@${profile.github})` : "")),
    );
    download("math-gambling-personal-preview.tex", t, "application/x-tex");
  } catch {
    text(
      "paper-preview-note",
      "Download failed. The source remains available in the repository.",
    );
  }
});
const filterText = [
  "First, check the exact norm and whether it belongs to the task’s allowed shell.",
  "Require an invertible root extractor and independently check r³ ≡ 114 (mod D). Noninvertible inputs are unresolved, not globally impossible.",
  "Apply necessary congruence, parity and quadratic-residue conditions. A failed condition rules out that candidate. No model is involved.",
  "Use exact integer division and an integer square root. A floating-point near miss does not count.",
  "Reconstruct integer x and y, then add x³ + y³ + z³ exactly. A discovery must equal 114. GitHub’s verifier checks again independently.",
];
$("filter-stage")?.addEventListener("input", (e) =>
  text("filter-explanation", filterText[Number(e.target.value)]),
);

function lineChart(el, points, { label, format = small, height = 170 } = {}) {
  if (!el) return;
  const clean = points.filter(
    (p) => Number.isFinite(p.x) && Number.isFinite(p.y),
  );
  if (clean.length < 2) {
    el.replaceChildren(
      Object.assign(document.createElement("p"), {
        textContent: "Not enough recorded observations to draw a trend.",
      }),
    );
    return;
  }
  const W = Math.max(340, Math.min(1000, el.clientWidth || 1000)),
    H = height,
    pl = 75,
    pr = 12,
    pt = 15,
    pb = 30,
    minx = Math.min(...clean.map((p) => p.x)),
    maxx = Math.max(...clean.map((p) => p.x));
  let miny = Math.min(...clean.map((p) => p.y)),
    maxy = Math.max(...clean.map((p) => p.y));
  if (maxy === miny) {
    miny = Math.max(0, miny - 1);
    maxy += 1;
  }
  const X = (x) => pl + ((x - minx) / (maxx - minx || 1)) * (W - pl - pr),
    Y = (y) => pt + (1 - (y - miny) / (maxy - miny)) * (H - pt - pb);
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", label || "Recorded measurements");
  function node(tag, attrs, content) {
    const n = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (content != null) n.textContent = content;
    svg.append(n);
    return n;
  }
  const title = document.createElementNS(ns, "title");
  title.textContent = label || "Recorded measurements";
  svg.append(title);
  for (let i = 0; i < 3; i++) {
    const val = miny + ((maxy - miny) * i) / 2,
      y = Y(val);
    node("line", { x1: pl, y1: y, x2: W - pr, y2: y, class: "chart-grid" });
    node(
      "text",
      { x: pl - 10, y: y + 4, "text-anchor": "end", class: "chart-label" },
      format(Math.round(val)),
    );
  }
  node("path", {
    d: clean
      .map(
        (p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(2)},${Y(p.y).toFixed(2)}`,
      )
      .join(" "),
    class: "chart-line",
  });
  node(
    "text",
    { x: pl, y: H - 5, class: "chart-label" },
    clean[0].label || "Start",
  );
  node(
    "text",
    { x: W - pr, y: H - 5, "text-anchor": "end", class: "chart-label" },
    clean.at(-1).label || "Latest",
  );
  el.replaceChildren(svg);
}
function calibrationScatter(mac) {
  const el = $("mac-calibration");
  if (!el) return;
  const h = mac.learning?.holdout || {},
    rows = (h.rows || []).filter((r) => r.predicted > 0 && r.observed > 0);
  text(
    "mac-calibration-note",
    `Rank correlation: ${Number.isFinite(h.spearman) ? h.spearman.toFixed(3) : "unavailable"}. Top-quarter observed throughput / baseline: ${Number.isFinite(h.top_quarter_over_baseline) ? h.top_quarter_over_baseline.toFixed(2) + "×" : "unavailable"}. ${rows.length} held-out contexts.`,
  );
  if (!rows.length) {
    el.textContent = "No per-context calibration observations are available.";
    return;
  }
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg");
  const width = Math.max(340, Math.min(1000, el.clientWidth || 1000));
  svg.setAttribute("viewBox", `0 0 ${width} 340`);
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    "Frozen Mac model: predicted versus observed conditional throughput, logarithmic axes",
  );
  const values = rows.flatMap((r) => [
      Math.log10(r.predicted),
      Math.log10(r.observed),
    ]),
    lo = Math.floor(Math.min(...values)),
    hi = Math.ceil(Math.max(...values)),
    X = (v) => 80 + ((v - lo) / (hi - lo)) * (width - 115),
    Y = (v) => 290 - ((v - lo) / (hi - lo)) * 260;
  function node(tag, attrs, value) {
    const e = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (value != null) e.textContent = value;
    svg.append(e);
    return e;
  }
  for (let i = lo; i <= hi; i++) {
    node("line", {
      x1: 80,
      y1: Y(i),
      x2: width - 35,
      y2: Y(i),
      class: "chart-grid",
    });
    node(
      "text",
      { x: 70, y: Y(i) + 4, "text-anchor": "end", class: "chart-label" },
      small(10 ** i),
    );
    node(
      "text",
      { x: X(i), y: 315, "text-anchor": "middle", class: "chart-label" },
      small(10 ** i),
    );
  }
  node("line", {
    x1: 80,
    y1: 290,
    x2: width - 35,
    y2: 30,
    stroke: "#b5c5b8",
    "stroke-dasharray": "4 5",
  });
  for (const r of rows) {
    const circle = node("circle", {
      cx: X(Math.log10(r.predicted)),
      cy: Y(Math.log10(r.observed)),
      r: 4,
      fill: "#dfbd72",
      "fill-opacity": ".7",
    });
    const t = document.createElementNS(ns, "title");
    t.textContent = `${r.context}: predicted ${r.predicted.toFixed(2)}, observed ${r.observed.toFixed(2)}`;
    circle.append(t);
  }
  node(
    "text",
    { x: width / 2, y: 338, "text-anchor": "middle", class: "chart-label" },
    "Predicted throughput score",
  );
  node(
    "text",
    { x: 80, y: 15, class: "chart-label" },
    "Observed throughput score",
  );
  el.replaceChildren(svg);
}

let macData = null,
  clusterData = null,
  strategy = null;
async function loadMac() {
  if (!$("mac-curves")) return;
  try {
    const [mac, history] = await Promise.all([
      fetchJSON("data/mac.json"),
      fetchJSON("data/mac-history.json"),
    ]);
    macData = mac;
    calibrationScatter(mac);
    text("mac-curves", small(mac.totals?.curve_checks));
    text("mac-exact", small(mac.totals?.exact_tests));
    text("mac-hits", fmt((mac.solutions || []).length));
    const age = Date.now() - Date.parse(mac.updated_utc),
      stale = age > 2 * 3600000;
    text(
      "mac-state",
      stale
        ? "Snapshot overdue"
        : mac.state === "running"
          ? "Running at report time"
          : mac.state || "Snapshot",
    );
    text(
      "mac-updated",
      `${date(mac.updated_utc)}${stale ? " · more than 2 hours old" : ""}`,
    );
    if (history.snapshot_id === mac.snapshot_id || !history.snapshot_id) {
      const points = (history.samples || [])
        .filter((s) => s.totals?.curve_checks != null)
        .map((s) => ({
          x: Date.parse(s.updated_utc),
          y: Number(s.totals.curve_checks),
          label: new Date(s.updated_utc).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        }));
      lineChart($("mac-history-chart"), points, {
        label:
          "Recorded cumulative curve-interval checks in the native Mac campaign. The vertical axis is cropped to the observed range.",
      });
      const rates = [];
      for (let i = 1; i < points.length; i++) {
        const elapsed = (points[i].x - points[i - 1].x) / 1000,
          delta = points[i].y - points[i - 1].y;
        if (elapsed > 0 && delta >= 0)
          rates.push({ ...points[i], y: delta / elapsed });
      }
      lineChart($("mac-rate-chart"), rates, {
        label:
          "Native Mac curve intervals per second, averaged between real snapshots. Vertical axis cropped to the observed range.",
      });
    } else
      text(
        "mac-history-chart",
        "The history snapshot is updating. Please refresh shortly.",
      );
    const audit = mac.audit || {},
      pass =
        audit.database_integrity === "ok" &&
        audit.source_identity_matches === true &&
        audit.reserved_tiles_disjoint_and_gapless === true;
    text(
      "mac-audit",
      `Audit: ${pass ? "integrity, source identity and reservation checks passed" : "see the source report for available checks"}. Observed ${date(audit.observed_utc)}. The throughput model is not a probability model.`,
    );
  } catch (e) {
    text("mac-state", "Report unavailable");
    text("mac-updated", e.message);
    text(
      "mac-history-chart",
      "No current report available. We do not extrapolate missing data.",
    );
  }
}
function renderAllocation() {
  if (!$("allocation-chart") || !strategy) return;
  const items = strategy.contexts || [],
    max = Math.max(...items.map((c) => Number(c.weight) || 0), 1 / 81),
    grid = $("allocation-chart");
  grid.replaceChildren();
  for (const context of CONTEXTS) {
    const entry = items.find((c) => c.id === context.id) || { weight: 1 / 81 };
    const b = document.createElement("button");
    b.className = "context-cell";
    b.textContent = context.id;
    b.setAttribute("aria-pressed", "false");
    b.setAttribute(
      "aria-label",
      `${context.id}, allocation ${(100 * entry.weight).toFixed(2)} percent`,
    );
    const intensity = Math.max(
      0.12,
      Math.min(0.7, ((Number(entry.weight) || 0) / max) * 0.7),
    );
    b.style.backgroundColor = `rgb(0 0 0 / ${intensity})`;
    b.style.color = intensity > 0.45 ? "white" : "black";
    b.addEventListener("click", () => {
      for (const c of grid.children) c.setAttribute("aria-pressed", "false");
      b.setAttribute("aria-pressed", "true");
      text(
        "context-detail",
        `${context.id}: ℓ=${context.ell}, shape ${context.shape + 1}, shell ${context.shell + 1}, |z|/D ∈ (${context.low}, ${context.high}]. Allocation ${(100 * entry.weight).toFixed(2)}%. ${entry.sample_size || 0} replay observations; ${entry.robust_cpu_ms == null ? "no stable cost estimate" : Number(entry.robust_cpu_ms).toFixed(2) + " ms median replay cost (descriptive)"}.`,
      );
    });
    grid.append(b);
  }
  text("strategy-epoch", `Epoch ${strategy.epoch ?? 0}`);
  text(
    "strategy-reason",
    strategy.reason ||
      "Uniform allocation until enough verified observations exist.",
  );
}
async function loadStrategy() {
  try {
    const s = await fetchJSON("data/strategy.json");
    const entries = s.contexts;
    if (
      !Array.isArray(entries) ||
      entries.length !== 81 ||
      new Set(entries.map((c) => c.id)).size !== 81 ||
      entries.some(
        (c) =>
          !CONTEXTS.some((x) => x.id === c.id) ||
          !Number.isFinite(c.weight) ||
          c.weight < 0.4 / 81 - 1e-10,
      ) ||
      Math.abs(entries.reduce((a, c) => a + c.weight, 0) - 1) > 0.001
    )
      throw Error("Invalid policy");
    strategy = s;
    text("policy-method-note", s.reason + " Allocation is a search preference, not a discovery probability.");
    showRun("policy", strategy);
    renderAllocation();
    if (clusterData)
      try {
        renderModelEvolution(clusterData, strategy);
      } catch {}
  } catch {
    strategy = null;
    showRun("policy", null);
    text(
      "strategy-reason",
      "Strategy unavailable or invalid. Browser work uses uniform exploration.",
    );
  }
}
async function loadCluster() {
  try {
    const [report, config] = await Promise.all([
      fetchJSON("data/cluster.json"),
      fetchJSON("data/site-config.json").catch(() => ({})),
    ]);
    clusterData = report;
    const aliases = config.display_aliases || {};
    const urls = config.display_urls || {};
    const t = clusterData.totals || {};
    text("cluster-reported", fmt(t.reported_tasks));
    text("cluster-inputs", fmt(t.verified_computations));
    text("cluster-verified", fmt(t.verified_unique_tasks));
    text("cluster-duplicates", fmt(t.duplicate_tasks));
    text("cluster-hits", fmt(t.verified_hits));
    text(
      "cluster-updated",
      clusterData.updated_at
        ? `Snapshot generated ${date(clusterData.updated_at)}`
        : "No published verification run yet",
    );
    text(
      "cluster-note",
      Number(t.verified_unique_tasks)
        ? "Ranked by independently verified inputs. Duplicate tasks earn no extra credit."
        : "The volunteer ledger starts at zero. Be the first to bank a verified computation.",
    );
    const body = $("contributors");
    if (body) {
      body.replaceChildren();
      const people = [...(clusterData.contributors || [])].sort((a, b) => {
        const x = BigInt(a.verified_computations || 0),
          y = BigInt(b.verified_computations || 0);
        return y > x ? 1 : y < x ? -1 : 0;
      });
      for (const [rank, p] of people.entries()) {
        const user = String(p.submitter || ""),
          website = safeProfileURL(p.url) ||
            (Object.hasOwn(urls, user.toLowerCase()) ? safeProfileURL(urls[user.toLowerCase()]) : ""),
          row = body.insertRow(),
          alias = row.insertCell(),
          place = document.createElement("span"),
          name = document.createElement(website ? "a" : "span");
        if (website) {
          name.href = website;
          name.rel = "nofollow ugc noopener noreferrer";
        }
        place.className = "rank-number";
        place.textContent = String(rank + 1).padStart(2, "0");
        const display = Object.hasOwn(aliases, user.toLowerCase())
            ? aliases[user.toLowerCase()]
            : null;
        name.textContent =
          (typeof display === "string" && display.trim() ? display : p.name) ||
          user ||
          "Contributor";
        alias.append(place, name);
        const account = row.insertCell();
        if (/^[A-Za-z0-9-]{1,39}$/.test(user)) {
          const a = document.createElement("a");
          a.href = `https://github.com/${user}`;
          a.textContent = `@${user}`;
          account.append(a);
        } else account.textContent = "Unattributed";
        row.insertCell().textContent = fmt(p.verified_computations);
      }
      // Empty ranks invite participation without fabricating people or work.
      for (let rank = people.length; rank < 10; rank++) {
        const row = body.insertRow();
        row.className = "empty-rank";
        const first = row.insertCell();
        const place = document.createElement("span");
        place.className = "rank-number";
        place.textContent = String(rank + 1).padStart(2, "0");
        first.append(place, document.createTextNode("—"));
        row.insertCell().textContent = "—";
        row.insertCell().textContent = "—";
      }
    }
    try {
      renderModelEvolution(clusterData, strategy);
    } catch {
      text(
        "model-detail",
        "Model display unavailable. The published policy is still linked on the cluster page.",
      );
    }
    const hist = clusterData.calibration_history || [];
    if (hist.length > 1)
      lineChart(
        $("calibration-chart"),
        hist.map((h) => ({
          x: Number(h.epoch),
          y: Number(h.through_verified_tasks ?? h.verified_unique_tasks ?? 0),
          label: `Epoch ${h.epoch}`,
        })),
        { label: "Verified unique tasks at recorded policy epochs" },
      );
    if ($("cluster-discoveries")) $("cluster-discoveries").replaceChildren();
    for (const d of clusterData.discoveries || []) {
        const xyz = d.xyz || d.hit?.xyz;
        if (verifyTriple(xyz)) {
          showJackpot(xyz, d, "cluster");
          const p = document.createElement("p");
          p.className = "discovery";
          p.textContent = `Verified identity: ${xyz.map((x) => `(${x})³`).join(" + ")} = 114. See the repository evidence for attribution.`;
          $("cluster-discoveries")?.append(p);
        }
      }
    if ($("join-form")) await reconcileBanks();
  } catch (e) {
    text(
      "cluster-note",
      "Published ledger unavailable. Local computation remains available.",
    );
    text("cluster-updated", "Could not load report");
  }
}

// Finished tasks and prepared banks persist separately. Preparing/copying is not submitting.
let dbPromise;
function db() {
  return (dbPromise ??= new Promise((resolve, reject) => {
    const request = indexedDB.open("math-gambling-v1", 1);
    request.onupgradeneeded = () => {
      const d = request.result;
      d.createObjectStore("tasks", { keyPath: "id" });
      d.createObjectStore("banks", { keyPath: "digest" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  }));
}
async function readAll(store) {
  const d = await db();
  return new Promise((resolve, reject) => {
    const tx = d.transaction(store),
      req = tx.objectStore(store).getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function save(store, record) {
  const d = await db();
  return new Promise((resolve, reject) => {
    const tx = d.transaction(store, "readwrite");
    tx.objectStore(store).put(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || Error("Storage aborted"));
  });
}
async function hash(obj) {
  const b = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(
      canonicalJSON(obj).replace(
        /[\u007f-\uffff]/g,
        (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"),
      ),
    ),
  );
  return Array.from(new Uint8Array(b), (x) =>
    x.toString(16).padStart(2, "0"),
  ).join("");
}
// Keep identities outside the task/bank database: a broken task envelope or
// unavailable receipt store must not prevent an independently checked rescue.
let identityDBPromise, pendingIdentitySaves = 0;
const rescuedIdentities = new Map();
function identityDB() {
  return (identityDBPromise ??= new Promise((resolve, reject) => {
    const request = indexedDB.open("math-gambling-identities-v1", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("identities", {keyPath: "key"});
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(Error("Identity backup database is blocked"));
  }));
}
async function saveIdentity(key, evidence) {
  const d = await identityDB();
  return new Promise((resolve, reject) => {
    const tx = d.transaction("identities", "readwrite");
    tx.objectStore("identities").put({key, evidence});
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || Error("Identity backup aborted"));
  });
}
function preserveIdentity(xyz, owner, provenance) {
  if (!verifyTriple(xyz)) return;
  const key = [...xyz].sort((a, b) => BigInt(a) < BigInt(b) ? -1 : BigInt(a) > BigInt(b) ? 1 : 0).join(",");
  let rescue = rescuedIdentities.get(key);
  if (rescue?.saved || rescue?.saving) return;
  if (!rescue) {
    const copy = [...xyz];
    rescue = {evidence: {
      schema: "math-gambling-independent-browser-identity-v1",
      xyz: [copy], hits: [{xyz: copy}], contributor: {...owner},
      search_session: {...provenance}, observed: new Date().toISOString(),
    }, saved: false, saving: false};
    rescuedIdentities.set(key, rescue);
  }
  const evidence = rescue.evidence;
  try {
    localStorage.setItem("mg-discovery-v1", JSON.stringify(evidence));
    rescue.saved = true;
  } catch {}
  rescue.saving = true;
  pendingIdentitySaves++;
  saveIdentity(key, evidence).then(() => { rescue.saved = true; }).catch(() => {
    if (!rescue.saved) text("session-message", "The identity is displayed, but browser storage failed. Save the discovery evidence before closing this page.");
  }).finally(() => { rescue.saving = false; pendingIdentitySaves--; });
  $("discovery").hidden = false;
  $("discovery").textContent =
    `Exact identity: ${xyz.map((x) => `(${x})³`).join(" + ")} = 114. Save the evidence and bank the discovery.`;
  showJackpot(xyz, evidence);
  // Download and animation failures cannot interrupt either persistent store.
  try {
    download("math-gambling-identity-evidence.json", JSON.stringify(evidence, null, 2));
  } catch {}
}
async function recoverIdentityBackups() {
  try {
    const d = await identityDB();
    const rows = await new Promise((resolve, reject) => {
      const req = d.transaction("identities").objectStore("identities").getAll(null, 64);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    if (rescuedIdentities.size) return;
    for (const {evidence} of rows.sort((a, b) => String(b.evidence?.observed).localeCompare(String(a.evidence?.observed)))) {
      const xyz = evidence?.hits?.find((hit) => verifyTriple(hit?.xyz))?.xyz;
      if (xyz) { showJackpot(xyz, evidence, "local", false); break; }
    }
  } catch { /* Optional rescue recovery cannot block the ordinary outbox. */ }
}
let tasks = [],
  banks = [],
  activeBank = null,
  priorityBankTask = null,
  banking = false;
function validStoredTask(t) {
  try {
    return (
      t &&
      t.id === taskId(t.result.task) &&
      t.result.id === t.id &&
      validProfile(t.contributor) &&
      typeof t.result.digest === "string" &&
      /^[0-9a-f]{64}$/.test(t.result.digest)
    );
  } catch {
    return false;
  }
}
async function refreshSaved() {
  const records = await readAll("tasks");
  tasks = records
    .filter(validStoredTask)
    .sort((a, b) => String(a.created).localeCompare(String(b.created)));
  banks = (await readAll("banks")).filter(
    (b) =>
      b &&
      typeof b.digest === "string" &&
      Array.isArray(b.ids) &&
      b.ids.every((id) => typeof id === "string") &&
      b.payload?.schema === "math-gambling-bank-v1",
  );
  if (tasks.length !== records.length)
    text(
      "session-message",
      "Some stored records have an unsupported format. They are retained in local storage; save your receipts before clearing browser data.",
    );
  updateBankUI();
}
function coveredIds() {
  return new Set(
    banks
      .filter((b) => b.status !== "rejected" && (b.observed || b.posted))
      .flatMap((b) => b.ids),
  );
}
function updateBankUI() {
  if (!$("bank-button")) return;
  const covered = coveredIds(),
    pending = tasks.filter((t) => !covered.has(t.id));
  text(
    "sync-state",
    `${fmt(tasks.length)} saved locally · ${fmt(pending.length)} ready to bank`,
  );
  $("bank-button").disabled = pending.length === 0;
  $("download-receipts").disabled = tasks.length === 0;
  const list = $("bank-history");
  if (list) {
    list.replaceChildren();
    for (const b of [...banks].reverse().slice(0, 8)) {
      const p = document.createElement("p");
      p.className = "form-note";
      p.textContent = b.observed
        ? `Bank ${b.digest.slice(0, 8)}: ${b.status}. ${b.accepted || 0} accepted, ${b.duplicates || 0} duplicates, ${b.rejected || 0} rejected, ${b.unreplayed || 0} unreplayed (no verified credit); ${b.processed || 0}/${b.ids.length} processed.`
        : `Bank ${b.digest.slice(0, 8)}: ${b.posted ? "marked posted locally; not yet in published ledger" : "prepared locally; not submitted"}. ${b.ids.length} tasks.`;
      if (b.issue) {
        const a = document.createElement("a");
        a.href = `${REPO}/issues/${Number(b.issue)}`;
        a.textContent = " View submission ↗";
        p.append(a);
      }
      list.append(p);
    }
  }
}
async function reconcileBanks() {
  if (!clusterData) return;
  try {
    banks = await readAll("banks");
    let changed = false;
    for (const bank of banks) {
      const entry = (clusterData.banks || []).find(
        (b) => b.bank_digest === bank.digest,
      );
      if (entry) {
        bank.observed = true;
        bank.status = entry.status;
        bank.issue = entry.issue;
        bank.accepted = entry.accepted_tasks;
        bank.duplicates = entry.duplicate_tasks;
        bank.rejected = entry.rejected_tasks;
        bank.unreplayed = entry.unreplayed_tasks || 0;
        bank.processed = entry.processed_tasks;
        await save("banks", bank);
        changed = true;
      }
    }
    if (changed) await refreshSaved();
  } catch {}
}
function validProfile(p) {
  return (
    typeof p.name === "string" &&
    p.name.trim().length > 0 &&
    p.name.length <= 60 &&
    typeof p.github === "string" &&
    (!p.github ||
      /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/.test(p.github)) &&
    (!p.url || Boolean(safeProfileURL(p.url)))
  );
}
async function prepareBank(priorityId = null, attribution = null) {
  if (priorityId) priorityBankTask = priorityId;
  if (attribution && !validProfile(attribution))
    throw Error("Enter a valid optional GitHub username.");
  await refreshSaved();
  const observed = coveredIds();
  const pending = priorityId
    ? tasks.filter((t) => t.id === priorityId)
    : tasks.filter((t) => !observed.has(t.id));
  if (!pending.length) return;
  // A pending prepared bank stays stable until it appears in GitHub's published ledger.
  const previous = priorityId
    ? null
    : banks.find(
        (b) =>
          !b.observed &&
          !b.posted &&
          b.ids.every((id) => !observed.has(id)) &&
          (!attribution ||
            (b.payload.contributor.name === attribution.name &&
              b.payload.contributor.github === attribution.github &&
              (b.payload.contributor.url || "") === (attribution.url || ""))),
      );
  let bank = previous;
  if (!bank) {
    const originalOwner = pending[0].contributor;
    const owner = attribution ? { ...attribution } : originalOwner;
    const claims = [];
    for (const r of pending
      .filter(
        (t) =>
          t.contributor.name === originalOwner.name &&
          t.contributor.github === originalOwner.github,
      )
      .slice(0, 256)) {
      const claim = { task: r.result.task, digest: r.result.digest };
      if (r.result.hits?.length) claim.hits = r.result.hits;
      const candidate = {
        schema: "math-gambling-bank-v1",
        contributor: owner,
        tasks: [...claims, claim],
      };
      if (new TextEncoder().encode(JSON.stringify(candidate)).length > 58000)
        break;
      claims.push(claim);
    }
    const payload = {
      schema: "math-gambling-bank-v1",
      contributor: owner,
      tasks: claims,
    };
    const digest = await hash(payload);
    bank = {
      digest,
      payload,
      ids: claims.map((c) => taskId(c.task)),
      observed: false,
      created: new Date().toISOString(),
    };
    await save("banks", bank);
    banks.push(bank);
  }
  activeBank = bank;
  $("bank-panel").hidden = false;
  $("bank-receipt").hidden = false;
  $("bank-body").value = JSON.stringify(bank.payload);
  text(
    "bank-count",
    `${bank.ids.length} completed tasks · ${bank.payload.contributor.name}`,
  );
  $("bank-open").href =
    `${REPO}/issues/new?template=compute.yml&title=${encodeURIComponent("[compute] Bank " + bank.ids.length + " tasks")}`;
  updateBankUI();
  $("bank-panel").scrollIntoView({
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "instant"
      : "smooth",
    block: "nearest",
  });
}
function openBank() {
  $("bank-panel").hidden = false;
  $("bank-receipt").hidden = true;
  $("player-name").value = profile.name === "Anonymous" ? "" : profile.name;
  $("player-github").value = profile.github;
  $("player-url").value = profile.url || "";
  text("bank-identity-status", "");
  $("bank-panel").scrollIntoView({
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "instant"
      : "smooth",
    block: "nearest",
  });
}
async function submitBankProfile(e) {
  e.preventDefault();
  if (banking) return;
  const github = $("player-github").value.trim().replace(/^@/, ""),
    name = $("player-name").value.trim() || github || "Anonymous";
  const url = $("player-url").value.trim();
  if (url && !safeProfileURL(url)) {
    text("bank-identity-status", "Use a full http:// or https:// link without spaces or login details.");
    return;
  }
  const attribution = { name, github, ...(url ? { url } : {}) };
  if (!validProfile(attribution)) {
    text("bank-identity-status", "Enter a valid optional GitHub username.");
    return;
  }
  banking = true;
  $("prepare-bank").disabled = true;
  try {
    await prepareBank(priorityBankTask, attribution);
    profile = attribution;
    // Attribution is attached to the bank. Exact saved task results stay unchanged.
    try {
      localStorage.setItem("mg-profile", JSON.stringify(profile));
    } catch {}
    profilePreview();
    text("bank-identity-status", "");
  } catch (e) {
    text(
      "bank-identity-status",
      `Could not prepare the bank: ${e.message}. Your saved computations are retained.`,
    );
  } finally {
    banking = false;
    $("prepare-bank").disabled = false;
  }
}
$("bank-button")?.addEventListener("click", openBank);
$("close-bank")?.addEventListener("click", () => {
  $("bank-panel").hidden = true;
});
$("bank-profile-form")?.addEventListener("submit", submitBankProfile);
$("copy-bank")?.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("bank-body").value);
    text(
      "copy-status",
      "Copied. Open GitHub, paste into the receipt field, and submit the issue.",
    );
  } catch {
    $("bank-body").focus();
    $("bank-body").select();
    text(
      "copy-status",
      "Clipboard unavailable. The receipt is selected; copy it, then paste on GitHub.",
    );
  }
});
$("posted-bank")?.addEventListener("click", async () => {
  if (!activeBank) return;
  activeBank.posted = true;
  await save("banks", activeBank);
  priorityBankTask = null;
  await refreshSaved();
  $("bank-panel").hidden = true;
  text(
    "session-message",
    "Marked posted on this device. This is not verification; the published ledger will confirm processing.",
  );
});
$("download-bank")?.addEventListener("click", () => {
  if (activeBank)
    download(
      `math-gambling-bank-${activeBank.digest.slice(0, 12)}.json`,
      JSON.stringify(activeBank.payload, null, 2) + "\n",
    );
});
$("download-receipts")?.addEventListener("click", async () => {
  const raw = await readAll("tasks");
  download(
    "math-gambling-local-results.jsonl",
    raw.map((t) => JSON.stringify(t)).join("\n") + "\n",
    "application/x-ndjson",
  );
});

let worker = null,
  running = false,
  starting = false,
  busy = false,
  stopReason = "",
  sessionGeneration = 0,
  startAt = 0,
  nextTimer = null,
  runTimer = null,
  counts = { generators: 0, curves: 0, exact_tests: 0, tasks: 0 },
  seen = new Set(),
  completedSinceRefresh = 0,
  currentSeed = "",
  randomStream = null,
  assigningGeneration = null,
  coverageRefreshDue = false;
const workerAssignments = new WeakMap();
async function nextTask(generation) {
  const weights =
    strategy?.contexts || CONTEXTS.map((c) => ({ id: c.id, weight: 1 / 81 }));
  const policyEpoch = strategy?.epoch ?? 0;
  const rng = randomStream;
  for (let attempt = 0; attempt < 100; attempt++) {
    let draw = Number(await rng.below(1n << 53n)) / 2 ** 53;
    let id = weights.at(-1).id;
    for (const c of weights) {
      draw -= c.weight;
      if (draw <= 0) { id = c.id; break; }
    }
    const c = CONTEXTS.find((c) => c.id === id);
    const task = makeTask(id,
      (await rng.below(c.rowTasks)) * BigInt(c.rowStride),
      Number(await rng.below(c.blocks)));
    if (generation !== sessionGeneration || !running) return null;
    if (seen.has(taskId(task))) continue;
    if (await sharedCoverage.has(task)) continue;
    if (generation !== sessionGeneration || !running) return null;
    return { task, policyEpoch };
  }
  throw Error("No fresh task found in 100 attempts. Saved work is retained; try a new run after the shared index updates.");
}
function showCoverage() {
  text("run-coverage", sharedCoverage.revision == null ? "Coverage not loaded" :
    `${fmt(sharedCoverage.revision)} verified batches excluded · policy ${strategy?.epoch ?? 0}`);
}
function counter(id, value) {
  const el = $(id);
  if (!el) return;
  const exact = fmt(value);
  let display = exact.length > 7 ? small(value) : exact;
  if (display.length > 9) display = new Intl.NumberFormat("en-US", {
    notation: "scientific", maximumFractionDigits: 2,
  }).format(BigInt(value));
  el.textContent = display;
  el.title = exact;
  el.setAttribute("aria-label", exact);
  el.setAttribute("tabindex", "0");
}
function renderCounts() {
  counter("local-inputs", counts.generators);
  counter("local-curves", counts.curves);
  counter("local-exact", counts.exact_tests);
  counter("local-tasks", counts.tasks);
}
function finishStop() {
  if (busy) return;
  worker?.terminate();
  worker = null;
  $("stop-button").disabled = true;
  $("start-button").disabled = false;
  text("session-state", "Stopped");
  showRun("state", "stopped");
  text(
    "session-message",
    stopReason || "Stopped. Finished tasks remain saved.",
  );
  $("join-form")
    ?.querySelectorAll("input,select")
    .forEach((e) => (e.disabled = false));
}
function stop(
  reason = "Stopped. Finished tasks remain saved and ready to bank.",
) {
  running = false;
  clearTimeout(nextTimer);
  clearInterval(runTimer);
  stopReason = reason;
  $("stop-button").disabled = true;
  if (busy) {
    text("session-state", "Finishing current task");
    text(
      "session-message",
      "Stopping after the current bounded task is safely saved.",
    );
  } else finishStop();
}
function failStop(reason) {
  busy = false;
  stop(reason);
}
async function dispatch() {
  if (!running || busy || assigningGeneration === sessionGeneration) return;
  if (document.hidden) {
    text("session-state", "Paused · tab hidden");
    showRun("state", "paused");
    return;
  }
  const covered = coveredIds();
  if (tasks.filter((t) => !covered.has(t.id)).length >= 4096) {
    stop(
      "Local receipt limit reached. Bank and save your work before starting another session.",
    );
    return;
  }
  const generation = sessionGeneration;
  assigningGeneration = generation;
  try {
    text("session-state", "Checking shared coverage");
    if (coverageRefreshDue) {
      await sharedCoverage.refresh(true);
      if (generation !== sessionGeneration || !running) return;
      coverageRefreshDue = false;
    }
    const selection = await nextTask(generation);
    if (!selection || generation !== sessionGeneration || !running || !worker) return;
    if (document.hidden) { text("session-state", "Paused · tab hidden"); return; }
    const { task, policyEpoch } = selection;
    showCoverage();
    const provenance = Object.freeze({
      seed: currentSeed, algorithm: SEED_ALGORITHM,
      policy_epoch: policyEpoch,
      coverage_revision: sharedCoverage.revision,
    });
    workerAssignments.set(worker, Object.freeze({task: Object.freeze({...task}), provenance}));
    busy = true;
    text("session-state", "Computing");
    text(
      "task-detail",
      `${task.context} · rows ${task.row}–${BigInt(task.row) + 127n} · block ${task.block}`,
    );
    showRun("dispatch", task);
    worker.postMessage({ type: "start", task });
    seen.add(taskId(task));
  } catch (e) {
    if (generation === sessionGeneration && running)
      failStop(`Could not confirm fresh shared coverage: ${e.message}. Completed work is saved.`);
  } finally {
    if (assigningGeneration === generation) assigningGeneration = null;
  }
}
async function start(e) {
  e.preventDefault();
  if (running || starting || worker) return;
  starting = true;
  try {
    await refreshSaved();
  } catch (e) {
    text(
      "session-message",
      "Persistent storage is unavailable. Please enable local storage or use the downloadable runner; starting would risk losing your work.",
    );
    starting = false;
    return;
  }
  try {
    text("session-state", "Loading shared coverage");
    await sharedCoverage.refresh(true);
    coverageRefreshDue = false;
    showCoverage();
    currentSeed = newSeed();
    randomStream = seededRandom(currentSeed);
    text("run-seed", currentSeed);
  } catch (e) {
    text("session-state", "Could not start");
    text("session-message", `Shared coverage is unavailable: ${e.message}. Try again when connected; the local runner has an explicit offline mode.`);
    starting = false;
    return;
  }
  starting = false;
  const owner = { name: "Anonymous", github: "" },
    generation = ++sessionGeneration;
  stopReason = "";
  profilePreview();
  seen = new Set(tasks.map((t) => t.id));
  counts = { generators: 0, curves: 0, exact_tests: 0, tasks: 0 };
  renderCounts();
  startAt = Date.now();
  showRun("reset");
  running = true;
  busy = false;
  $("start-button").disabled = true;
  $("stop-button").disabled = false;
  // The processor slider remains adjustable during a run.
  text("session-message", "");
  try {
    worker = new Worker(new URL("search-worker.mjs?v=91edbf56d67b", BASE), { type: "module" });
  } catch (e) {
    failStop(`Could not start a browser worker: ${e.message}`);
    return;
  }
  const sessionWorker = worker;
  worker.onerror = (e) => {
    if (generation === sessionGeneration)
      failStop(`Worker stopped after an error: ${e.message}. Completed receipts are preserved.`);
  };
  worker.onmessage = ({ data }) => {
    (async () => {
      if (generation !== sessionGeneration && !["result", "identity"].includes(data.type)) return;
      if (data.type === "ready") {
        if (running) dispatch();
        else finishStop();
        return;
      }
      if (data.type === "error") {
        failStop(`Worker error: ${data.message}`);
        return;
      }
      if (!["result", "identity"].includes(data.type)) return;
      const r = data.type === "identity" ? {hits: [data.hit]} : data.result;
      const assignment = workerAssignments.get(sessionWorker);
      const issuedTask = assignment?.task, provenance = assignment?.provenance;
      // An exact identity is valuable even if the surrounding task envelope is damaged.
      const exactHits = Array.isArray(r?.hits)
        ? r.hits.slice(0, 64).filter((h) => verifyTriple(h?.xyz))
        : [];
      if (exactHits.length) {
        for (const hit of exactHits) preserveIdentity(hit.xyz, owner, provenance);
        if (data.type === "identity")
          stop("An exact identity was preserved. Finishing the current task before banking its full receipt.");
      }

      // An early positive is evidence of the equation only, never completed
      // task coverage. The ordinary result must still pass every receipt check.
      if (data.type === "identity") return;

      if (generation !== sessionGeneration) {
        if (exactHits.length) stop("An exact identity from an earlier session was preserved. Save the discovery evidence.");
        return;
      }
      if (
        !r ||
        !issuedTask ||
        taskId(validateTask(r.task)) !== taskId(issuedTask) ||
        r.id !== taskId(issuedTask) ||
        !r.counters ||
        Object.values(r.counters).some(
          (v) => !Number.isSafeInteger(v) || v < 0,
        ) ||
        !["generators", "curves", "exact_tests"].every((k) =>
          Number.isSafeInteger(r.counters[k]),
        ) ||
        !Array.isArray(r.hits)
      )
        throw Error(
          "Worker result did not match its assigned task or counter schema",
        );
      const { digest, ...core } = r;
      if (digest !== (await hash(core)))
        throw Error("Worker result digest mismatch");
      for (const hit of r.hits || []) {
        if (!verifyTriple(hit.xyz)) {
          if (generation === sessionGeneration) failStop(
            "A returned candidate failed the independent page identity check. It has not been credited.",
          );
          return;
        }
      }
      const record = {
        id: r.id,
        result: r,
        contributor: owner,
        search_session: provenance,
        created: new Date().toISOString(),
      };
      try {
        await save("tasks", record);
        tasks.push(record);
        seen.add(record.id);
      } catch {
        download(
          "math-gambling-emergency-result.json",
          JSON.stringify(record, null, 2),
        );
        if (generation !== sessionGeneration) return;
        failStop(
          "Could not save to local storage. An emergency receipt download was started; preserve it before closing this page.",
        );
        return;
      }
      if (generation !== sessionGeneration) return;
      counts.generators += Number(r.counters.generators);
      counts.curves += Number(r.counters.curves);
      counts.exact_tests += Number(r.counters.exact_tests);
      counts.tasks++;
      renderCounts();
      updateBankUI();
      showRun("result", { result: r, elapsedMs: data.elapsedMs });
      if (r.hits?.length) {
        const hit = r.hits[0];
        showJackpot(hit.xyz, record);
        $("discovery").hidden = false;
        $("discovery").textContent =
          `Exact identity found: ${hit.xyz.map((x) => `(${x})³`).join(" + ")} = 114. Saved locally. Download this evidence and bank it for independent verification.`;
        download(
          "math-gambling-discovery.json",
          JSON.stringify(record, null, 2),
        );
        busy = false;
        stop(
          "Candidate identity verified locally. Computation stopped to preserve the evidence.",
        );
        await prepareBank(r.id);
        return;
      }
      busy = false;
      if (running && ++completedSinceRefresh >= 64) {
        completedSinceRefresh = 0;
        coverageRefreshDue = true;
        // Optional reports never hold the save/stop barrier. Fresh shared
        // coverage is still required by dispatch before the next task starts.
        void Promise.allSettled([loadStrategy(), loadCluster(), loadChallenger(fetchJSON)]);
      }
      if (running) {
        const duty = processorDuty();
        nextTimer = setTimeout(
          dispatch,
          Math.max(0, (data.elapsedMs * (1 - duty)) / duty),
        );
      } else finishStop();
    })().catch((e) => {
      if (generation === sessionGeneration)
        failStop(`Result handling failed: ${e.message}. Previously completed receipts are preserved.`);
    });
  };
  runTimer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startAt) / 1000);
    text(
      "elapsed",
      `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`,
    );
  }, 500);
}
$("join-form")?.addEventListener("submit", start);
$("stop-button")?.addEventListener("click", () => stop());
window.addEventListener("beforeunload", (e) => {
  if (busy || pendingIdentitySaves) {
    e.preventDefault();
    e.returnValue = "";
  }
});
document.addEventListener("visibilitychange", () => {
  if (running) {
    text(
      "session-state",
      document.hidden ? "Paused · tab hidden" : "Computing",
    );
    showRun("state", document.hidden ? "paused" : "running");
    if (!document.hidden) dispatch();
  }
});
if ($("join-form")) {
  void recoverIdentityBackups();
  try {
    const saved = localStorage.getItem("mg-discovery-v1");
    if (saved && saved.length < 100000) {
      const evidence = JSON.parse(saved);
      const xyz = evidence.hits?.find((hit) => verifyTriple(hit?.xyz))?.xyz || evidence.xyz?.find((xyz) => verifyTriple(xyz));
      if (xyz) showJackpot(xyz, evidence, "local", false);
    }
  } catch { /* A corrupt optional preview must not block saved task recovery. */ }
  if (typeof profile.name === "string") $("player-name").value = profile.name;
  if (typeof profile.github === "string")
    $("player-github").value = profile.github;
  $("player-url").value = profile.url || "";
  refreshSaved()
    .then(() => {
      text("session-message", tasks.length ? "" : "");
    })
    .catch(() => {
      text(
        "session-message",
        "Local storage is unavailable; use the downloadable runner.",
      );
      $("start-button").disabled = true;
    });
}
await Promise.allSettled([loadMac(), loadStrategy(), loadCluster(), loadChallenger(fetchJSON)]);
setInterval(() => {
  if (!document.hidden) {
    loadMac();
    loadCluster();
    loadStrategy();
  }
}, 60000);

if ($("lane-domains")) {
  for (const context of CONTEXTS) {
    const row = $("lane-domains").insertRow();
    for (const value of [context.id, context.ell, context.shape + 1,
      fmt(context.dlo), fmt(context.dhi), `(${context.low}, ${context.high}]`]) {
      row.insertCell().textContent = value;
    }
  }
}
