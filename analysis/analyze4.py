#!/usr/bin/env python3
"""token-radar-01 v3 — round 4: relay-feedback variants.

Relay feedback applied as TESTABLE variants (not adopted on authority):
- Groq: EV sigma ignores heteroskedasticity -> board EV uses sigma from the
  top-200 board sample (0.6567), not the full-sample sigma (handled in board
  builder, not here). Groq also: drop 1m TVL change (noisy) -> V3.
- Xkiro: drop 30d revenue (collinear with TVL/fees) -> V2.
- Groq blind spot: token supply dynamics -> V4 adds log(circulating/total
  supply) from CoinGecko (joined rows only, median-imputed, has_cg indicator
  already present).
- V5: leanest combo (V2+V3+V4).
Winner = lowest 5-seed mean held-out RMSE on BOTH samples.
"""
import json, math
import numpy as np
from analyze2 import build, TOP_CATS

WORK = "/home/hatch/workspace/makefun/u-token-radar-01-v3-work"

def enrich(rows):
    protos = {p["slug"]: p for p in json.load(open(f"{WORK}/data/raw/protocols-2026-11-26.json"))}
    cg = {}
    for pg in range(1, 9):
        d = json.load(open(f"{WORK}/data/raw/coingecko-markets-p{pg}-2026-11-26.json"))
        if isinstance(d, list):
            for c in d:
                cg[c["id"]] = c
    ratios = []
    for r in rows:
        g = protos.get(r["slug"], {}).get("gecko_id")
        c = cg.get(g) if g else None
        if c and c.get("circulating_supply") and c.get("total_supply") and c["total_supply"] > 0:
            ratios.append(math.log10(c["circulating_supply"] / c["total_supply"]))
    med = float(np.median(ratios)) if ratios else 0.0
    for r in rows:
        g = protos.get(r["slug"], {}).get("gecko_id")
        c = cg.get(g) if g else None
        if c and c.get("circulating_supply") and c.get("total_supply") and c["total_supply"] > 0:
            r["log_circratio"] = math.log10(c["circulating_supply"] / c["total_supply"])
        else:
            r["log_circratio"] = med
    return med, len(ratios)

def design(rows, kind):
    X = []
    for r in rows:
        cats = [1.0 if r["category"] == c else 0.0 for c in TOP_CATS]
        cg = [r["log_vol"] * r["has_cg"], r["has_cg"], r["log_fdvratio"], r["chg30d"]]
        if kind == "V1-C4b":
            v = [1.0, r["log_tvl"], r["log_rev30"], r["log_fees30"], r["log_age"],
                 r["log_chains"], r["change_1m"]] + cats + cg
        elif kind == "V2-norev":
            v = [1.0, r["log_tvl"], r["log_fees30"], r["log_age"],
                 r["log_chains"], r["change_1m"]] + cats + cg
        elif kind == "V3-nochg1m":
            v = [1.0, r["log_tvl"], r["log_rev30"], r["log_fees30"], r["log_age"],
                 r["log_chains"]] + cats + cg
        elif kind == "V4-circ":
            v = [1.0, r["log_tvl"], r["log_rev30"], r["log_fees30"], r["log_age"],
                 r["log_chains"], r["change_1m"]] + cats + cg + [r["log_circratio"]]
        elif kind == "V5-lean":
            v = [1.0, r["log_tvl"], r["log_fees30"], r["log_age"],
                 r["log_chains"]] + cats + cg + [r["log_circratio"]]
        else:
            raise ValueError(kind)
        X.append(v)
    return np.array(X, dtype=float)

def eval_seeds(X, y, seeds=(42, 1, 7, 123, 2026)):
    rmses = []
    for s in seeds:
        rng = np.random.default_rng(s)
        idx = rng.permutation(len(y))
        n_test = int(round(0.2 * len(y)))
        te, tr = idx[:n_test], idx[n_test:]
        beta, *_ = np.linalg.lstsq(X[tr], y[tr], rcond=None)
        rmses.append(float(np.sqrt(np.mean((X[te] @ beta - y[te]) ** 2))))
    return float(np.mean(rmses)), float(np.min(rmses)), float(np.max(rmses)), [round(v, 4) for v in rmses]

def main():
    rows, meta = build()
    med, n_circ = enrich(rows)
    print(f"circ-ratio median={med:.4f} from {n_circ} joined rows")
    samples = {"S-full(609)": rows, "S-top200-TVL": sorted(rows, key=lambda r: -r["tvl"])[:200]}
    out = {}
    for sname, srows in samples.items():
        y = np.array([r["log_mcap"] for r in srows])
        print(f"\n== {sname} ==")
        for kind in ("V1-C4b", "V2-norev", "V3-nochg1m", "V4-circ", "V5-lean"):
            X = design(srows, kind)
            mean, mn, mx, per = eval_seeds(X, y)
            print(f"  {kind}: 5-seed mean={mean:.4f} min={mn:.4f} max={mx:.4f} feats={X.shape[1]} per-seed={per}")
            out[f"{sname}|{kind}"] = {"mean": mean, "min": mn, "max": mx, "per_seed": per,
                                      "feats": X.shape[1]}
    json.dump(out, open(f"{WORK}/analysis/fit-results-r4.json", "w"), indent=1)
    print("\nsaved analysis/fit-results-r4.json")

if __name__ == "__main__":
    main()
