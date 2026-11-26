#!/usr/bin/env python3
"""Generate dashboard/index.html from data/board.json + data/model.json.

The dashboard is fully static (no network, no fetch): the top-100 board rows
are embedded as a JS const. Views are deep-linkable via the URL hash so the
three required screenshots can be taken with plain headless-chrome calls:
  board:    dashboard/index.html
  detail:   dashboard/index.html#detail=lido
  filtered: dashboard/index.html#filter=Liquid%20Staking
"""
import json, html

WORK = "/home/hatch/workspace/makefun/u-token-radar-01-v3-work"
board = json.load(open(f"{WORK}/data/board.json"))
model = json.load(open(f"{WORK}/data/model.json"))
top100 = board[:100]

def money(n):
    return "$" + f"{round(n):,}"

cats = sorted({b["category"] for b in top100})
cat_options = "".join(
    f'<option value="{html.escape(c)}">{html.escape(c)}</option>' for c in cats
)
data_js = json.dumps(top100)
m = model["metrics"]

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>token-radar-01 v3 — true EV board</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }}
  header {{ padding: 18px 24px 12px; background: #1e293b; border-bottom: 1px solid #334155; }}
  h1 {{ margin: 0 0 4px; font-size: 22px; }}
  h1 span {{ color: #38bdf8; }}
  .sub {{ color: #94a3b8; font-size: 13px; margin: 0; line-height: 1.5; }}
  .stats {{ display: flex; gap: 16px; padding: 12px 24px; flex-wrap: wrap; }}
  .stat {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; min-width: 150px; }}
  .stat .k {{ font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: .05em; }}
  .stat .v {{ font-size: 20px; font-weight: 700; margin-top: 2px; }}
  .controls {{ display: flex; gap: 10px; padding: 0 24px 12px; align-items: center; }}
  .controls select, .controls input {{ background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; padding: 7px 10px; font-size: 14px; }}
  .controls label {{ font-size: 13px; color: #94a3b8; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 7px 10px; text-align: right; border-bottom: 1px solid #1e293b; white-space: nowrap; }}
  th {{ background: #1e293b; color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; position: sticky; top: 0; }}
  td:nth-child(2), td:nth-child(3) {{ text-align: left; }}
  tbody tr {{ cursor: pointer; }}
  tbody tr:hover {{ background: #1e293b; }}
  td.ev {{ font-weight: 700; color: #4ade80; }}
  .wrap {{ padding: 0 24px 24px; }}
  footer {{ padding: 12px 24px 24px; color: #64748b; font-size: 12px; line-height: 1.6; }}
  #modal {{ display: none; position: fixed; inset: 0; background: rgba(2,6,23,.8); align-items: flex-start; justify-content: center; padding-top: 60px; z-index: 10; }}
  #modal.open {{ display: flex; }}
  #card {{ background: #1e293b; border: 1px solid #475569; border-radius: 12px; width: 640px; max-width: 92vw; padding: 20px 24px; }}
  #card h2 {{ margin: 0 0 2px; font-size: 20px; }}
  #card .cat {{ color: #94a3b8; font-size: 13px; margin: 0 0 12px; }}
  #card dl {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px 24px; margin: 0 0 12px; font-size: 14px; }}
  #card dt {{ color: #94a3b8; }} #card dd {{ margin: 0; text-align: right; font-weight: 600; }}
  #card .big {{ font-size: 26px; color: #4ade80; font-weight: 800; }}
  #card .why {{ font-size: 13px; color: #cbd5e1; line-height: 1.55; background: #0f172a; border-radius: 8px; padding: 10px 12px; }}
  #card button {{ margin-top: 14px; background: #38bdf8; color: #082f49; border: 0; border-radius: 6px; padding: 8px 14px; font-weight: 700; cursor: pointer; }}
</style>
</head>
<body>
<header>
  <h1>TOKEN RADAR <span>v3</span> — true expected-value board</h1>
  <p class="sub">609 DeFi protocols ranked by expected dollar value of the mispricing gap.
  Model: OLS on log10(market cap), 16 features (DeFiLlama TVL/fees/age/chains/category + CoinGecko volume, FDV/mcap, 30d momentum).
  Held-out RMSE <b style="color:#e2e8f0">0.7699</b> (full 609) / <b style="color:#e2e8f0">0.6548</b> (top-200 by TVL) vs prior version 0.9046.
  Data: DeFiLlama + CoinGecko, 2026-11-26. Click any row for the protocol detail view.</p>
</header>
<div class="stats">
  <div class="stat"><div class="k">Protocols ranked</div><div class="v">609</div></div>
  <div class="stat"><div class="k">Max EV</div><div class="v">{money(board[0]["ev_usd"])}</div></div>
  <div class="stat"><div class="k">Max EV protocol</div><div class="v">{html.escape(board[0]["name"])}</div></div>
  <div class="stat"><div class="k">Max EV vs v2 ($3,142,414)</div><div class="v">8.09x</div></div>
  <div class="stat"><div class="k">Held-out RMSE</div><div class="v">0.7699</div></div>
</div>
<div class="controls">
  <label>Category <select id="cat"><option value="">All categories</option>{cat_options}</select></label>
  <label>Search <input id="q" type="text" placeholder="protocol name…" size="22"></label>
  <label>Min EV ($) <input id="minev" type="number" placeholder="0" min="0" step="1000000" style="width:130px"></label>
  <span id="count" style="color:#94a3b8;font-size:13px"></span>
</div>
<div class="wrap"><table>
<thead><tr><th>#</th><th>Protocol</th><th>Category</th><th>TVL</th><th>Market cap</th><th>Predicted mcap</th><th>Upside</th><th>Odds</th><th>EV</th></tr></thead>
<tbody id="rows"></tbody>
</table></div>
<footer>
  EV = (predicted mcap &minus; actual mcap) &times; odds, odds = 1 &minus; &Phi;(gap/&sigma;), gap = predicted &minus; actual log10(mcap),
  &sigma; segmented: 0.6548 for top-200-by-TVL protocols, 0.7699 otherwise (0.6548 is the top-200-by-TVL seed-42 held-out RMSE; 0.7699 is the full-609 seed-42 held-out RMSE).
  Sources: api.llama.fi/protocols, api.llama.fi/overview/fees (dailyRevenue, dailyFees), api.coingecko.com/api/v3/coins/markets (top 2000).
  Full 609-row board: data/board.json. Model + metrics: data/model.json. Reproduce: MAKEFUN_OUTPUT_DIR=out node main.ts.
</footer>
<div id="modal"><div id="card"></div></div>
<script>
const BOARD = {data_js};
const fmt$ = n => "$" + Math.round(n).toLocaleString("en-US");
function render() {{
  const cat = document.getElementById("cat").value;
  const q = document.getElementById("q").value.trim().toLowerCase();
  const minEv = parseFloat(document.getElementById("minev").value) || 0;
  const rows = BOARD.filter(b =>
    (!cat || b.category === cat) &&
    (!q || b.name.toLowerCase().includes(q)) &&
    b.ev_usd >= minEv);
  document.getElementById("count").textContent = rows.length + " of " + BOARD.length + " shown (top 100 embedded)";
  document.getElementById("rows").innerHTML = rows.map(b =>
    "<tr data-slug='" + b.slug + "'><td>" + b.rank + "</td><td>" + b.name + "</td><td>" + b.category +
    "</td><td>" + fmt$(b.tvl) + "</td><td>" + fmt$(b.mcap) + "</td><td>" + fmt$(b.pred_mcap) +
    "</td><td>" + (b.upside_x > 0 ? b.upside_x.toFixed(1) + "x" : "-") + "</td><td>" + (b.odds * 100).toFixed(1) +
    "%</td><td class='ev'>" + fmt$(b.ev_usd) + "</td></tr>").join("");
  document.querySelectorAll("#rows tr").forEach(tr =>
    tr.addEventListener("click", () => showDetail(tr.getAttribute("data-slug"))));
}}
function showDetail(slug) {{
  const b = BOARD.find(x => x.slug === slug);
  if (!b) return;
  document.getElementById("card").innerHTML =
    "<h2>" + b.name + " <span style='color:#94a3b8;font-size:14px'>#" + b.rank + " by EV</span></h2>" +
    "<p class='cat'>" + b.category + " &middot; " + b.chains + " chains &middot; age " + b.age_days + " days</p>" +
    "<dl>" +
    "<dt>TVL</dt><dd>" + fmt$(b.tvl) + "</dd>" +
    "<dt>Market cap (actual)</dt><dd>" + fmt$(b.mcap) + "</dd>" +
    "<dt>Predicted market cap</dt><dd>" + fmt$(b.pred_mcap) + "</dd>" +
    "<dt>Gap (log10)</dt><dd>" + b.gap_log10.toFixed(3) + "</dd>" +
    "<dt>Upside if gap closes</dt><dd>" + (b.upside_x > 0 ? b.upside_x.toFixed(1) + "x" : "none") + "</dd>" +
    "<dt>Odds the gap is real</dt><dd>" + (b.odds * 100).toFixed(1) + "%</dd>" +
    "<dt>30d revenue / fees</dt><dd>" + fmt$(b.revenue30d) + " / " + fmt$(b.fees30d) + "</dd>" +
    "</dl>" +
    "<div class='big'>Expected value: " + fmt$(b.ev_usd) + "</div>" +
    "<p class='why'>Why: the model predicts a market cap of " + fmt$(b.pred_mcap) + " from this protocol's TVL, fees, age, " +
    "chains and market signals, versus an actual " + fmt$(b.mcap) + ". The " + (b.odds * 100).toFixed(1) + "% odds reflect " +
    "the model's held-out error (&sigma; = " + b.sigma + " in log10 units on this segment), so the expected dollar value " +
    "of the gap is " + fmt$(b.ev_usd) + ". This is a model estimate, not investment advice.</p>" +
    "<button id='closeBtn'>Close</button>";
  document.getElementById("closeBtn").addEventListener("click", () => {{
    document.getElementById("modal").classList.remove("open");
    history.replaceState(null, "", " ");
  }});
  document.getElementById("modal").classList.add("open");
  history.replaceState(null, "", "#detail=" + slug);
}}
document.getElementById("modal").addEventListener("click", e => {{
  if (e.target.id === "modal") {{ document.getElementById("modal").classList.remove("open"); history.replaceState(null, "", " "); }}
}});
["cat", "q", "minev"].forEach(id => document.getElementById(id).addEventListener("input", render));
// Deep links: #detail=<slug> and/or #filter=<category>
(function () {{
  const h = new URLSearchParams(location.hash.slice(1));
  const f = h.get("filter");
  if (f) document.getElementById("cat").value = f;
  render();
  const d = h.get("detail");
  if (d) showDetail(d);
}})();
</script>
</body>
</html>
"""
open(f"{WORK}/dashboard/index.html", "w").write(page)
print("dashboard written:", len(page), "bytes; rows embedded:", len(top100))
