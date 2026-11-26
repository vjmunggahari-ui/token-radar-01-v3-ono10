#!/usr/bin/env python3
"""token-radar-01 v3 — final fit + EV board (V2-norev, the shipped model).

H2H winner was V5-lean (4/4 vs C3), BUT a final collinearity audit found
log(FDV/mcap) == -log(circ/total) EXACTLY (corr -1.0, max|a+b| = 0.0) — the
two features are the same number with a sign flip, and lstsq split the
coefficient as +-2,003,195. Dropped log_circratio -> V2-norev, statistically
tied with V5-lean (5-seed mean full 0.7669 vs 0.7664; top-200 0.7222 vs 0.7229)
with sane coefficients. V2-norev also drops 30d revenue (Xkiro suggestion,
tested harmless) and keeps change_1m (coefficient ~0, harmless).

Final model V2-norev [measured]: OLS, 16 features
  [1, logTVL, logFees30, logAge, logChains, change_1m,
   Dexs, Yield, Lending, Derivatives, Launchpad, CDP (dummies),
   logVol*has_cg, has_cg, logFDVratio, chg30d]
Held-out (seed 42): RMSE 0.7699 (full 609) / 0.6548 (top-200 TVL).
5-seed mean: 0.7669 / 0.7222. v2: 0.9046. Beats v2 on every seed.

NOTE: v2's top-EV protocol Tydro is NOT in this board — fresh DeFiLlama data
(2026-11-26) lists Tydro TVL $398M but mcap null, so it fails the mcap>0
cleaning rule. No mcap was invented for it.

EV [inferred, documented]: gap = pred_log - act_log; upside = 10**gap - 1.
sigma is SEGMENTED (Groq heteroskedasticity critique): 0.6548 for top-200-by-TVL
protocols, 0.7699 otherwise (0.6548 is the top-200-by-TVL seed-42 held-out RMSE; 0.7699 is the full-609 seed-42 held-out RMSE).
odds = 1 - Phi(gap / sigma); EV_usd = (10**pred_log - 10**act_log) * odds
for gap > 0, else 0. Board ranks by EV desc.
"""
import json, math
import numpy as np
from scipy.stats import norm
from analyze2 import build, TOP_CATS

WORK = "/home/hatch/workspace/makefun/u-token-radar-01-v3-work"
SIGMA_TOP200 = 0.6548   # seed-42 held-out RMSE, top-200 by TVL
SIGMA_FULL = 0.7699     # seed-42 held-out RMSE, full 609
V2_RMSE = 0.9046
V2_MAX_EV = 3142414.0

FEATURES = ["intercept", "log_tvl", "log_fees30", "log_age", "log_chains", "change_1m",
            "cat_Dexs", "cat_Yield", "cat_Lending", "cat_Derivatives",
            "cat_Launchpad", "cat_CDP",
            "log_vol_x_has_cg", "has_cg", "log_fdvratio", "chg30d"]

def design_row(r):
    cats = [1.0 if r["category"] == c else 0.0 for c in TOP_CATS]
    return [1.0, r["log_tvl"], r["log_fees30"], r["log_age"], r["log_chains"],
            r["change_1m"]] + cats + \
           [r["log_vol"] * r["has_cg"], r["has_cg"], r["log_fdvratio"], r["chg30d"]]

def heldout(X, y, seed=42):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    n_test = int(round(0.2 * len(y)))
    te, tr = idx[:n_test], idx[n_test:]
    beta, *_ = np.linalg.lstsq(X[tr], y[tr], rcond=None)
    pred = X[te] @ beta
    return float(np.sqrt(np.mean((pred - y[te]) ** 2))), float(np.mean(np.abs(pred - y[te])))

def main():
    rows, meta = build()
    top200_slugs = {r["slug"] for r in sorted(rows, key=lambda r: -r["tvl"])[:200]}
    X = np.array([design_row(r) for r in rows])
    y = np.array([r["log_mcap"] for r in rows])
    # held-out stats on both samples (seed 42 + 5-seed mean)
    rmse42, mae42 = heldout(X, y, 42)
    means = []
    for s in (42, 1, 7, 123, 2026):
        rm, _ = heldout(X, y, s)
        means.append(rm)
    X200 = np.array([design_row(r) for r in rows if r["slug"] in top200_slugs])
    y200 = np.array([r["log_mcap"] for r in rows if r["slug"] in top200_slugs])
    rmse200, mae200 = heldout(X200, y200, 42)
    means200 = [heldout(X200, y200, s)[0] for s in (42, 1, 7, 123, 2026)]
    print(f"V5 full-609: seed42 RMSE={rmse42:.4f} MAE={mae42:.4f} | 5-seed mean={np.mean(means):.4f} max={np.max(means):.4f}")
    print(f"V5 top200:  seed42 RMSE={rmse200:.4f} MAE={mae200:.4f} | 5-seed mean={np.mean(means200):.4f} max={np.max(means200):.4f}")
    # final fit on ALL rows (shipped coefficients)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    print("beta:", [round(float(b), 4) for b in beta])
    board = []
    for r, xi in zip(rows, X):
        pred_log = float(xi @ beta)
        pred_mcap = 10 ** pred_log
        gap = pred_log - r["log_mcap"]
        sigma = SIGMA_TOP200 if r["slug"] in top200_slugs else SIGMA_FULL
        odds = float(1 - norm.cdf(gap / sigma)) if gap > 0 else 0.0
        ev = (pred_mcap - r["mcap"]) * odds if gap > 0 else 0.0
        board.append({
            "rank": 0, "name": r["name"], "slug": r["slug"], "category": r["category"],
            "tvl": r["tvl"], "mcap": r["mcap"], "pred_mcap": round(pred_mcap, 2),
            "pred_log10_mcap": round(pred_log, 4), "act_log10_mcap": round(r["log_mcap"], 4),
            "gap_log10": round(gap, 4), "upside_x": round(10 ** gap - 1, 4) if gap > 0 else 0.0,
            "odds": round(odds, 4), "ev_usd": round(ev, 2),
            "sigma": sigma, "in_top200_tvl": r["slug"] in top200_slugs,
            "chains": r["chains"], "revenue30d": r["revenue30d"], "fees30d": r["fees30d"],
            "age_days": round(r["age_days"], 1),
        })
    board.sort(key=lambda b: -b["ev_usd"])
    for i, b in enumerate(board):
        b["rank"] = i + 1
    top5 = board[:5]
    print("\nTOP-5 EV board:")
    for b in top5:
        print(f"  #{b['rank']} {b['name']} ({b['category']}): EV ${b['ev_usd']:,.0f} | odds {b['odds']:.1%} | "
              f"upside {b['upside_x']:.1f}x | mcap ${b['mcap']:,.0f} -> pred ${b['pred_mcap']:,.0f}")
    max_ev = board[0]["ev_usd"]
    print(f"\nMAX EV ${max_ev:,.0f} vs v2 ${V2_MAX_EV:,.0f} -> {'BEATS v2' if max_ev > V2_MAX_EV else 'BELOW v2'} "
          f"({max_ev / V2_MAX_EV:.2f}x)")
    tyd = [b for b in board if b["slug"] == "tydro" or b["name"].lower().startswith("tydro")]
    for b in tyd:
        print(f"Tydro: rank {b['rank']} EV ${b['ev_usd']:,.0f} odds {b['odds']:.1%}")
    model = {
        "name": "token-radar-01 v3 — V2-norev OLS",
        "formula": "log10(mcap) = " + " + ".join(
            f"{b:+.4f}*{f}" for b, f in zip(beta, FEATURES)),
        "features": FEATURES,
        "coefficients": [round(float(b), 6) for b in beta],
        "metrics": {
            "heldout_rmse_seed42_full609": round(rmse42, 4),
            "heldout_mae_seed42_full609": round(mae42, 4),
            "heldout_rmse_5seed_mean_full609": round(float(np.mean(means)), 4),
            "heldout_rmse_5seed_max_full609": round(float(np.max(means)), 4),
            "heldout_rmse_seed42_top200tvl": round(rmse200, 4),
            "heldout_mae_seed42_top200tvl": round(mae200, 4),
            "heldout_rmse_5seed_mean_top200tvl": round(float(np.mean(means200)), 4),
            "heldout_rmse_5seed_max_top200tvl": round(float(np.max(means200)), 4),
            "v2_rmse": V2_RMSE, "v2_max_ev_usd": V2_MAX_EV,
            "sigma_top200_tvl": SIGMA_TOP200, "sigma_rest": SIGMA_FULL,
        },
        "n_protocols": len(rows),
        "n_top200_tvl": 200,
        "max_ev_usd": round(max_ev, 2),
        "fetch_date": "2026-11-26",
        "sources": [
            "https://api.llama.fi/protocols",
            "https://api.llama.fi/overview/fees?dataType=dailyRevenue",
            "https://api.llama.fi/overview/fees?dataType=dailyFees",
            "https://api.coingecko.com/api/v3/coins/markets (pages 1-8, top 2000 by mcap)",
        ],
    }
    json.dump(board, open(f"{WORK}/data/board.json", "w"), indent=1)
    json.dump(model, open(f"{WORK}/data/model.json", "w"), indent=1)
    # re-save the ENRICHED cleaned rows (with CoinGecko fields) so main.ts can
    # recompute every feature from stored values, independently of this script
    json.dump(rows, open(f"{WORK}/data/protocols-clean-2026-11-26.json", "w"), indent=1)
    print("\nsaved data/board.json (609 rows) + data/model.json + data/protocols-clean-2026-11-26.json (enriched)")

if __name__ == "__main__":
    main()
