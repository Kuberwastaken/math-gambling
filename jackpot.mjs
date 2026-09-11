import { verifyTriple } from "./engine.mjs?v=027258560b2e";

// This display never validates task coverage or changes a receipt. The default
// target is fixed in the app; other targets are for known-positive test fixtures.
export function createJackpot({ root = document, target = 114, onSave = () => {} } = {}) {
  const get = (id) => root.getElementById(id), panel = get("jackpot-panel");
  if (!panel) return null;
  let evidence = null, effect = null, timer = null, local = false;
  const celebrated = new Set();
  function quiet() {
    if (timer != null) clearTimeout(timer);
    timer = null;
    effect?.remove();
    effect = null;
    get("jackpot-quiet").hidden = true;
  }
  function sparkle() {
    quiet();
    if (root.hidden || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    effect = root.createElement("div");
    effect.className = "jackpot-confetti";
    effect.setAttribute("aria-hidden", "true");
    // Decorative randomness is separate from the numerical search's seeded PRNG.
    for (let i = 0; i < 144; i++) {
      const piece = root.createElement("i"), star = i % 4 === 0;
      piece.className = star ? "jackpot-sparkle" : "jackpot-chip";
      if (star) piece.textContent = "✦";
      for (const [name, value] of Object.entries({
        "--x": `${Math.random() * 100}%`, "--drift": `${(Math.random() - .5) * 30}vw`,
        "--delay": `${Math.random() * 1.5}s`, "--duration": `${3.5 + Math.random() * 2}s`,
        "--turn": `${(Math.random() - .5) * 1440}deg`,
        "--chip-color": ["#b5202a", "#111111", "#c49a36", "#ffffff"][i % 4],
      })) piece.style.setProperty(name, value);
      effect.append(piece);
    }
    root.body.append(effect);
    get("jackpot-quiet").hidden = false;
    timer = setTimeout(quiet, 7500);
  }
  get("jackpot-quiet").addEventListener("click", quiet);
  get("jackpot-save").addEventListener("click", () => { if (evidence) onSave(evidence); });
  root.addEventListener("visibilitychange", () => { if (root.hidden) quiet(); });
  return {
    show({ xyz, receipt, source = "local", animate = true }) {
      if (!verifyTriple(xyz, target)) return false;
      // A cluster refresh must not replace the evidence found on this computer.
      if (local && source !== "local") return true;
      local = source === "local";
      evidence = receipt || { schema: "math-gambling-independent-browser-identity-v1", hits: [{ xyz: [...xyz] }] };
      const key = [...xyz].sort((a, b) => BigInt(a) < BigInt(b) ? -1 : BigInt(a) > BigInt(b) ? 1 : 0).join(",");
      panel.hidden = false;
      get("jackpot-equation").textContent = `${xyz.map((x) => `(${x})³`).join(" + ")} = ${target}`;
      get("jackpot-status").textContent = local
        ? "Your computer found an exact identity. Save the evidence and submit it for independent verification and discovery credit."
        : "The cluster found an exact identity. GitHub’s verifier and this page both checked the integer equation. See the published evidence for attribution.";
      const bank = get("jackpot-bank");
      bank.textContent = local ? "Bank the discovery on GitHub ↗" : "View published discovery evidence ↗";
      // An identity-only bank lets the server preserve a positive even if the
      // original task envelope or browser storage failed. No coverage is claimed.
      bank.href = local
        ? `https://github.com/Kuberwastaken/math-gambling/issues/new?title=${encodeURIComponent("[bank] Exact identity for " + target)}&body=${encodeURIComponent(JSON.stringify({schema: "math-gambling-identity-v1", contributor: evidence.contributor || {name: "Anonymous", github: ""}, hits: [{xyz: [...xyz]}]}))}`
        : "https://github.com/Kuberwastaken/math-gambling/tree/cluster-data/data/receipts/hits";
      if (animate && !celebrated.has(key)) {
        celebrated.add(key);
        panel.focus({ preventScroll: true });
        panel.scrollIntoView({ behavior: "instant", block: "center" });
        // An effects failure must never interfere with the persistent result UI.
        try { sparkle(); } catch { quiet(); }
      }
      return true;
    },
    quiet,
  };
}
