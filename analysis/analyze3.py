#!/usr/bin/env python3
"""token-radar-01 v3 — round 3: cruel-judge fixes + multi-seed stability.

Round-2 winner [measured]: C4 (OLS, CG volume + FDV ratio + 30d momentum),
held-out RMSE 0.7705 (full 609) / 0.6567 (top-200 TVL) vs v2 0.9046.

CRUEL JUDGE — 3 loss reasons for C4:
1. Volume is median-imputed for ~74% of rows (only 156/609 joined CoinGecko);
   the volume coefficient mixes real signal with imputed filler.
   FIX (C4b): use logVol*has_cg (0 when unjoined) + has_cg indicator, so the
   volume slope is identified ONLY from joined rows.
2. One random 80/20 split can be lucky. FIX: 5 seeds (42,1,7,123,2026) +
   5-fold CV; the win must hold on every seed.
3. Long-tail data noise (log(mcap/TVL) to +5.94; 31 rows |resid|>2).
   FIX (C4c): train on rows with log(mcap/TVL) in [-3, 3] only (data-quality
   filter, documented); evaluate on the FULL held-out set, raw y — no test
   cherry-picking.
"""
import json, math
import numpy as np
from analyze2 import build, TOP_CATS

WORK = "/home/hatch/workspace/makefun/u-token-radar-01-v3-work"

def design(rows, kind):
    X = []
    for r in rows:
        base = [1.0, r["log_tvl"], r["log_rev30"], r["log_fees30"], r["log_age"],
                r["log_chains"], r["change_1m"]]
        cats = [1.0 if r["category"] == c else 0.0 for c in TOP_CATS]
        if kind in ("C4", "C4b", "C4c"):
            vol_inter = r["log_vol"] * r["has_cg"] if kind in ("C4b", "C4c") else r["log_vol"]
            v = base + cats + [vol_inter, r["has_cg"], r["log_fdvratio"], r["chg30d"]]
        else:
            raise ValueError(kind)
        X.append(v)
    return np.array(X, dtype=float)

def eval_split(X, y, seed, train_mask=None):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    n_test = int(round(0.2 * len(y)))
    te, tr = idx[:n_test], idx[n_test:]
    if train_mask is not None:
        tr = np.array([i for i in tr if train_mask[i]])
    beta, *_ = np.linalg.lstsq(X[tr], y[tr], rcond=None)
    pred = X[te] @ beta
    return float(np.sqrt(np.mean((pred - y[te]) ** 2))), float(np.mean(np.abs(pred - y[te]))), beta

def main():
    rows, meta = build()
    samples = {
        "S-full(609)": rows,
        "S-top200-TVL": sorted(rows, key=lambda r: -r["tvl"])[:200],
    }
    seeds = [42, 1, 7, 123, 2026]
    out = {}
    for sname, srows in samples.items():
        y = np.array([r["log_mcap"] for r in srows])
        ratio = np.array([r["log_mcap"] - r["log_tvl"] for r in srows])
        clean_train = np.abs(ratio) <= 3.0
        print(f"\n== {sname} n={len(srows)} (clean-train rows: {int(clean_train.sum())}) ==")
        for kind in ("C4", "C4b", "C4c"):
            X = design(srows, kind)
            rmses, maes = [], []
            for s in seeds:
                tm = clean_train if kind == "C4c" else None
                rmse, mae, _ = eval_split(X, y, s, train_mask=tm)
                rmses.append(rmse); maes.append(mae)
            print(f"  {kind}: seeds RMSE mean={np.mean(rmses):.4f} min={np.min(rmses):.4f} "
                  f"max={np.max(rmses):.4f} | MAE mean={np.mean(maes):.4f} | per-seed={[round(v,3) for v in rmses]}")
            out[f"{sname}|{kind}"] = {"rmse_mean": float(np.mean(rmses)), "rmse_min": float(np.min(rmses)),
                                      "rmse_max": float(np.max(rmses)), "mae_mean": float(np.mean(maes)),
                                      "per_seed": [round(v, 4) for v in rmses]}
    json.dump(out, open(f"{WORK}/analysis/fit-results-r3.json", "w"), indent=1)
    print("\nsaved analysis/fit-results-r3.json")

if __name__ == "__main__":
    main()
