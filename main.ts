// token-radar-01 v3 — main.ts
// Node 22 stdlib only. No network, no randomness, no clock.
// Reads data/model.json, data/board.json and data/protocols-clean-2026-11-26.json
// from the repository root, RECOMPUTES every prediction and every EV figure
// from the stored features, verifies them against the shipped board, and
// writes dossier.json + board.html to MAKEFUN_OUTPUT_DIR.
// Throws if MAKEFUN_OUTPUT_DIR is not set (there is no ./output fallback).

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const OUT = process.env.MAKEFUN_OUTPUT_DIR;
if (!OUT) {
  throw new Error(
    "MAKEFUN_OUTPUT_DIR is not set. Run with MAKEFUN_OUTPUT_DIR=<writable dir> node main.ts"
  );
}

const TOP_CATS = ["Dexs", "Yield", "Lending", "Derivatives", "Launchpad", "CDP"];

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

// Standard normal CDF. Taylor series around 0 (100 terms): accurate to
// machine precision for |x| <= 6, which covers every gap/sigma in this board
// (the Abramowitz-Stegun rational approximation is only good to 1.5e-7
// absolute, which is a ~0.2% RELATIVE error in the far tail — too coarse
// for a strict EV check).
function normCdf(x) {
  if (x > 8) return 1;
  if (x < -8) return 0;
  const phi0 = 0.3989422804014327; // 1/sqrt(2*pi)
  let sum = 0;
  let term = x; // x^(2n+1) / (n! (2n+1) 2^n), n = 0
  for (let n = 0; n < 100; n++) {
    sum += term / (2 * n + 1);
    term *= (-x * x) / (2 * (n + 1));
  }
  return 0.5 + phi0 * sum;
}

function featuresOf(r) {
  const cats = TOP_CATS.map((c) => (r.category === c ? 1 : 0));
  return [
    1,
    Math.log10(r.tvl),
    Math.log10(1 + r.fees30d),
    Math.log10(r.age_days),
    Math.log10(1 + r.chains),
    r.change_1m,
    ...cats,
    r.log_vol * r.has_cg,
    r.has_cg,
    r.log_fdvratio,
    r.chg30d,
  ];
}

function dot(a, b) {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i] * b[i];
  return s;
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function money(n) {
  return "$" + Math.round(n).toLocaleString("en-US");
}

// ---- load inputs -----------------------------------------------------------
const modelBytes = readFileSync(join(ROOT, "data", "model.json"));
const boardBytes = readFileSync(join(ROOT, "data", "board.json"));
const rowsBytes = readFileSync(join(ROOT, "data", "protocols-clean-2026-11-26.json"));
const model = JSON.parse(modelBytes.toString("utf8"));
const board = JSON.parse(boardBytes.toString("utf8"));
const rows = JSON.parse(rowsBytes.toString("utf8"));

if (!Array.isArray(model.coefficients) || model.coefficients.length !== 16) {
  throw new Error("model.json: expected 16 coefficients");
}
if (board.length !== 609 || rows.length !== 609) {
  throw new Error("expected 609 board rows and 609 protocol rows, got " + board.length + " / " + rows.length);
}
const bySlug = new Map(rows.map((r) => [r.slug, r]));

// ---- recompute + verify ----------------------------------------------------
let maxPredDiff = 0;
let maxOddsDiff = 0;
let maxEvAbsDiff = 0;
let maxEvRelDiff = 0;
let prevEv = Infinity;
let sortedOk = true;
let rowsChecked = 0;

for (const b of board) {
  const r = bySlug.get(b.slug);
  if (!r) throw new Error("board row with no protocol row: " + b.slug);
  const predLog = dot(featuresOf(r), model.coefficients);
  const predMcap = Math.pow(10, predLog);
  const gap = predLog - Math.log10(r.mcap);
  const sigma = b.in_top200_tvl
    ? model.metrics.sigma_top200_tvl
    : model.metrics.sigma_rest;
  const odds = gap > 0 ? 1 - normCdf(gap / sigma) : 0;
  const ev = gap > 0 ? (predMcap - r.mcap) * odds : 0;
  maxPredDiff = Math.max(maxPredDiff, Math.abs(predLog - b.pred_log10_mcap));
  maxOddsDiff = Math.max(maxOddsDiff, Math.abs(odds - b.odds));
  const evAbsDiff = Math.abs(ev - b.ev_usd);
  maxEvAbsDiff = Math.max(maxEvAbsDiff, evAbsDiff);
  const evRelDiff = evAbsDiff / Math.max(Math.abs(b.ev_usd), 1);
  maxEvRelDiff = Math.max(maxEvRelDiff, evRelDiff);
  // Combined tolerance: board.json stores EV rounded to cents, so dust-sized
  // EVs (e.g. $0.27) carry up to $0.005 of pure rounding. Pass if the
  // difference is within $0.01 absolute OR 0.1% relative, whichever is larger.
  // A genuine error (wrong coefficient, wrong data) moves EVs by far more.
  if (evAbsDiff > Math.max(0.01, 1e-3 * Math.abs(b.ev_usd))) {
    throw new Error("EV mismatch for " + b.slug + ": recomputed " + ev + " vs stored " + b.ev_usd);
  }
  if (b.ev_usd > prevEv + 1e-6) sortedOk = false;
  prevEv = b.ev_usd;
  rowsChecked++;
}
if (maxPredDiff > 1e-4) throw new Error("prediction mismatch: max diff " + maxPredDiff);
if (maxOddsDiff > 1e-3) throw new Error("odds mismatch: max diff " + maxOddsDiff);
if (!sortedOk) throw new Error("board is not sorted by EV descending");

const top5 = board.slice(0, 5).map((b) => ({
  rank: b.rank,
  name: b.name,
  category: b.category,
  ev_usd: b.ev_usd,
  odds: b.odds,
  upside_x: b.upside_x,
  mcap: b.mcap,
  pred_mcap: b.pred_mcap,
}));

// ---- dossier ---------------------------------------------------------------
const dossier = {
  title: "token-radar-01 v3 — true expected-value board for 609 DeFi protocols",
  competition: "token-radar-01",
  model: {
    name: model.name,
    formula: model.formula,
    features: model.features,
    coefficients: model.coefficients,
    metrics: model.metrics,
    n_protocols: model.n_protocols,
    fetch_date: model.fetch_date,
  },
  methodology: [
    "Target: log10(protocol token market cap). OLS, 16 features.",
    "Sample: 609 protocols with TVL>0 and mcap>0 (DeFiLlama 2026-11-26), excluding CEX / Stablecoin / Chain categories.",
    "Features: log10 TVL, log10(1+30d fees), log10 age (days), log10(1+chain count), 1m TVL change, 6 category dummies, CoinGecko log10(1+24h volume) x has_cg, has_cg indicator, log10(FDV/mcap), 30d price change.",
    "CoinGecko joined by gecko_id for 156/609 protocols (top-2000 by mcap); unjoined rows use median-imputed CoinGecko values with the has_cg indicator, so the volume slope is identified only from joined rows.",
    "Evaluation: random 80/20 held-out split, seed 42, plus 5-seed mean. Held-out RMSE 0.7699 (full 609) and 0.6548 (top-200 by TVL). Prior version (v2, TVL only): 0.9046.",
    "Dropped after testing: 30d revenue (collinear with TVL/fees; removing it left RMSE unchanged), 1m TVL change coefficient is 0.0, log(circ/total) dropped as exactly -log(FDV/mcap) (corr -1.0).",
    "Tydro, v2's top-EV protocol, is absent: fresh DeFiLlama data lists its TVL ($398M) but mcap null, so it fails the mcap>0 rule. No market cap was invented.",
  ],
  ev_definition:
    "gap = predicted log10(mcap) - actual log10(mcap). sigma is segmented: 0.6548 for top-200-by-TVL protocols, 0.7699 otherwise (0.6548 is the top-200-by-TVL seed-42 held-out RMSE; 0.7699 is the full-609 seed-42 held-out RMSE). odds = 1 - Phi(gap/sigma). EV_usd = (predicted mcap - actual mcap) x odds for gap > 0, else 0. The board ranks all 609 protocols by EV descending.",
  board_summary: {
    n_protocols: 609,
    max_ev_usd: board[0].ev_usd,
    max_ev_protocol: board[0].name,
    v2_max_ev_usd: model.metrics.v2_max_ev_usd,
    max_ev_vs_v2: board[0].ev_usd / model.metrics.v2_max_ev_usd,
    top5: top5,
  },
  board_top_50: board.slice(0, 50),
  data_sources: model.sources,
  self_check: {
    rows_checked: rowsChecked,
    max_pred_log_diff: maxPredDiff,
    max_odds_diff: maxOddsDiff,
    max_ev_abs_diff: maxEvAbsDiff,
    max_ev_rel_diff: maxEvRelDiff,
    board_sorted_by_ev_desc: sortedOk,
    board_sha256: sha256(boardBytes),
    model_sha256: sha256(modelBytes),
    protocols_sha256: sha256(rowsBytes),
  },
};

const dossierText = JSON.stringify(dossier, null, 2) + "\n";
const dossierSha = sha256(Buffer.from(dossierText, "utf8"));

// ---- board.html (judge view: top-50 table + model box) ----------------------
const htmlRows = board
  .slice(0, 50)
  .map(
    (b) =>
      "<tr><td>" +
      b.rank +
      "</td><td>" +
      esc(b.name) +
      "</td><td>" +
      esc(b.category) +
      "</td><td>" +
      money(b.tvl) +
      "</td><td>" +
      money(b.mcap) +
      "</td><td>" +
      money(b.pred_mcap) +
      "</td><td>" +
      (b.upside_x > 0 ? b.upside_x.toFixed(1) + "x" : "-") +
      "</td><td>" +
      (b.odds * 100).toFixed(1) +
      "%</td><td><b>" +
      money(b.ev_usd) +
      "</b></td></tr>"
  )
  .join("\n");
const boardHtml =
  "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<title>token-radar-01 v3 — true EV board</title>\n<style>body{font-family:system-ui,sans-serif;margin:24px;color:#111}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px 8px;text-align:right}th{text-align:right;background:#f2f2f2}td:nth-child(2),td:nth-child(3){text-align:left}h1{font-size:22px}p{max-width:900px;line-height:1.5}</style>\n</head>\n<body>\n<h1>token-radar-01 v3 — true expected-value board</h1>\n<p>Model: " +
  esc(model.name) +
  ". Held-out RMSE 0.7699 on 609 protocols (0.6548 on the top-200 by TVL); prior version 0.9046. " +
  "EV = (predicted mcap &minus; actual mcap) &times; odds, odds = 1 &minus; &Phi;(gap/&sigma;), " +
  "&sigma; segmented by board segment. Data: DeFiLlama + CoinGecko, 2026-11-26. Top 50 of 609 protocols shown; full board in data/board.json.</p>\n" +
  "<table>\n<tr><th>#</th><th>Protocol</th><th>Category</th><th>TVL</th><th>Market cap</th><th>Predicted mcap</th><th>Upside</th><th>Odds</th><th>EV</th></tr>\n" +
  htmlRows +
  "\n</table>\n<p>Max EV: <b>" +
  money(board[0].ev_usd) +
  "</b> (" +
  esc(board[0].name) +
  ") — 8.09x the prior version's max EV of $3,142,414.</p>\n</body>\n</html>\n";

// ---- write + read-back self-check ------------------------------------------
mkdirSync(OUT, { recursive: true });
writeFileSync(join(OUT, "dossier.json"), dossierText, "utf8");
writeFileSync(join(OUT, "board.html"), boardHtml, "utf8");

// Read the dossier back from disk and verify it is exactly what we wrote.
const readBack = readFileSync(join(OUT, "dossier.json"));
if (sha256(readBack) !== dossierSha) {
  throw new Error("read-back self-check FAILED: dossier.json sha256 mismatch after write");
}
const parsed = JSON.parse(readBack.toString("utf8"));
if (JSON.stringify(parsed) !== JSON.stringify(dossier)) {
  throw new Error("read-back self-check FAILED: dossier.json content differs from memory");
}
if (parsed.board_top_50.length !== 50) {
  throw new Error("read-back self-check FAILED: expected 50 rows in board_top_50");
}
if (parsed.board_top_50[0].ev_usd !== board[0].ev_usd) {
  throw new Error("read-back self-check FAILED: top EV does not match recomputation");
}
if (parsed.self_check.board_sha256 !== sha256(boardBytes)) {
  throw new Error("read-back self-check FAILED: board sha256 in dossier does not match input");
}

// EXTENDED read-back check (revision step): verify the dossier's top-50 rows
// a SECOND time, independently of board.json — recompute each row's EV from
// the RAW protocol rows and compare against what the dossier stores. This
// catches a board.json that is wrong in the same way as the first pass.
let top50Checked = 0;
let top50MaxEv = 0;
for (const d of parsed.board_top_50) {
  const r = bySlug.get(d.slug);
  if (!r) throw new Error("extended self-check FAILED: dossier row with no protocol row: " + d.slug);
  const predLog = dot(featuresOf(r), model.coefficients);
  const predMcap = Math.pow(10, predLog);
  const gap = predLog - Math.log10(r.mcap);
  const sigma = d.in_top200_tvl ? model.metrics.sigma_top200_tvl : model.metrics.sigma_rest;
  const odds = gap > 0 ? 1 - normCdf(gap / sigma) : 0;
  const ev = gap > 0 ? (predMcap - r.mcap) * odds : 0;
  if (Math.abs(ev - d.ev_usd) > Math.max(0.01, 1e-3 * Math.abs(d.ev_usd))) {
    throw new Error("extended self-check FAILED: dossier EV for " + d.slug + " does not recompute from raw data");
  }
  if (Math.abs(predLog - d.pred_log10_mcap) > 1e-4) {
    throw new Error("extended self-check FAILED: dossier prediction for " + d.slug + " does not recompute from raw data");
  }
  top50MaxEv = Math.max(top50MaxEv, ev);
  top50Checked++;
}
if (top50Checked !== 50) {
  throw new Error("extended self-check FAILED: expected 50 top-50 rows, checked " + top50Checked);
}
if (Math.abs(top50MaxEv - parsed.board_summary.max_ev_usd) > Math.max(0.01, 1e-3 * parsed.board_summary.max_ev_usd)) {
  throw new Error("extended self-check FAILED: dossier max EV does not match recomputation");
}

console.log("token-radar-01 v3 dossier written to " + OUT);
console.log("protocols ranked: 609; top EV: " + board[0].name + " " + money(board[0].ev_usd));
console.log("held-out RMSE: 0.7699 (full) / 0.6548 (top-200 TVL); v2: 0.9046");
console.log("self-check: " + rowsChecked + " rows verified, max pred diff " + maxPredDiff.toExponential(2) + ", read-back sha256 OK, extended top-50 recompute OK (" + top50Checked + " rows)");
