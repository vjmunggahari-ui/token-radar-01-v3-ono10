#!/usr/bin/env python3
"""token-radar-01 v3 — round 2: CoinGecko features + robust fit.

Round-1 finding [measured]: no candidate beat v2's 0.9046 on the full 609-row
sample (best C3 1.1947 held-out). Diagnostics showed heavy residual tails
(31 rows |resid|>2) and that the relation is far tighter for large protocols
(top-200-by-TVL C1 in-sample RMSE 0.964; top-200-by-mcap 0.6314 — the latter
is target-selected, so it is reported only as a diagnostic, never as the claim).

Round-2 hypotheses [inferred]:
- H1: trading volume + unlock overhang (FDV/mcap) + 30d momentum carry real
  valuation signal beyond TVL/revenue (CoinGecko, public, 2026-11-26).
- H2: Huber-robust fitting downweights the 31 extreme-residual protocols and
  lowers held-out RMSE on a heavy-tailed target.
- H3: the v2-comparable board is the top-200 protocols by TVL (v2 ranked 200);
  RMSE is reported on that board AND on the full 609 for transparency.

Samples (both from the same cleaned rows, exogenous selection only):
- S-full: all 609 rows.  S-top200: top-200 by TVL.
Split: random 80/20, seed 42, identical indices across candidates within a sample.
"""
import json, math
import numpy as np

WORK = "/home/hatch/workspace/makefun/u-token-radar-01-v3-work"

def load_cg():
    cg = {}
    for pg in range(1, 9):
        d = json.load(open(f"{WORK}/data/raw/coingecko-markets-p{pg}-2026-11-26.json"))
        if isinstance(d, list):
            for c in d:
                cg[c["id"]] = c
    return cg

def build():
    protos = {p["slug"]: p for p in json.load(open(f"{WORK}/data/raw/protocols-2026-11-26.json"))}
    rows = json.load(open(f"{WORK}/data/protocols-clean-2026-11-26.json"))
    cg = load_cg()
    # medians for imputation, from joined rows only
    vols, fdvrs, chg30s = [], [], []
    for r in rows:
        g = protos.get(r["slug"], {}).get("gecko_id")
        c = cg.get(g) if g else None
        if c and c.get("total_volume"):
            vols.append(math.log10(1 + c["total_volume"]))
        if c and c.get("fully_diluted_valuation") and c.get("market_cap"):
            fdvrs.append(math.log10(c["fully_diluted_valuation"] / c["market_cap"]))
        if c and c.get("price_change_percentage_30d_in_currency") is not None:
            chg30s.append(c["price_change_percentage_30d_in_currency"] / 100.0)
    med_vol = float(np.median(vols)) if vols else 0.0
    med_fdvr = float(np.median(fdvrs)) if fdvrs else 0.0
    med_chg30 = float(np.median(chg30s)) if chg30s else 0.0
    for r in rows:
        g = protos.get(r["slug"], {}).get("gecko_id")
        c = cg.get(g) if g else None
        has = 1.0 if (c and c.get("total_volume")) else 0.0
        r["has_cg"] = has
        r["log_vol"] = math.log10(1 + c["total_volume"]) if (c and c.get("total_volume")) else med_vol
        if c and c.get("fully_diluted_valuation") and c.get("market_cap"):
            r["log_fdvratio"] = math.log10(c["fully_diluted_valuation"] / c["market_cap"])
        else:
            r["log_fdvratio"] = med_fdvr
        chg = c.get("price_change_percentage_30d_in_currency") if c else None
        r["chg30d"] = (chg / 100.0) if chg is not None else med_chg30
        r["audits"] = len(protos.get(r["slug"], {}).get("audits") or [])
    return rows, {"med_vol": med_vol, "med_fdvr": med_fdvr, "med_chg30": med_chg30,
                  "n_cg_joined": len(vols)}

TOP_CATS = ["Dexs", "Yield", "Lending", "Derivatives", "Launchpad", "CDP"]

def design(rows, kind):
    X = []
    for r in rows:
        base = [1.0, r["log_tvl"], r["log_rev30"], r["log_fees30"], r["log_age"],
                r["log_chains"], r["change_1m"]]
        cats = [1.0 if r["category"] == c else 0.0 for c in TOP_CATS]
        if kind == "C1":
            v = [1.0, r["log_tvl"]]
        elif kind == "C3":
            v = base + cats
        elif kind == "C4":
            v = base + cats + [r["log_vol"], r["has_cg"], r["log_fdvratio"], r["chg30d"]]
        elif kind == "C6":
            v = base + cats
        else:
            raise ValueError(kind)
        X.append(v)
    return np.array(X, dtype=float)

def huber_fit(X, y, iters=25, k=1.345):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    for _ in range(iters):
        res = y - X @ beta
        s = 1.4826 * np.median(np.abs(res - np.median(res))) or 1.0
        u = res / (k * s)
        w = np.where(np.abs(u) <= 1, 1.0, 1.0 / np.maximum(np.abs(u), 1e-9))
        Xw = X * np.sqrt(w)[:, None]
        yw = y * np.sqrt(w)
        beta_new, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
        if np.max(np.abs(beta_new - beta)) < 1e-8:
            beta = beta_new
            break
        beta = beta_new
    return beta

def evaluate(X, y, robust=False, seed=42):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    n_test = int(round(0.2 * len(y)))
    te, tr = idx[:n_test], idx[n_test:]
    if robust:
        beta = huber_fit(X[tr], y[tr])
    else:
        beta, *_ = np.linalg.lstsq(X[tr], y[tr], rcond=None)
    pred = X[te] @ beta
    rmse = float(np.sqrt(np.mean((pred - y[te]) ** 2)))
    mae = float(np.mean(np.abs(pred - y[te])))
    return beta, rmse, mae

def main():
    rows, meta = build()
    print("CG imputation medians:", {k: round(v, 4) for k, v in meta.items()})
    samples = {
        "S-full(609)": rows,
        "S-top200-TVL": sorted(rows, key=lambda r: -r["tvl"])[:200],
    }
    out = {}
    for sname, srows in samples.items():
        y = np.array([r["log_mcap"] for r in srows])
        print(f"\n== {sname} n={len(srows)} ==")
        for kind, robust in [("C1", False), ("C3", False), ("C4", False),
                             ("C6", True), ("C4", True)]:
            label = kind + ("-huber" if robust else "")
            X = design(srows, kind)
            beta, rmse, mae = evaluate(X, y, robust=robust)
            print(f"  {label}: held-out RMSE={rmse:.4f} MAE={mae:.4f} feats={X.shape[1]}")
            out[f"{sname}|{label}"] = {"rmse": rmse, "mae": mae,
                                       "beta": [round(float(b), 4) for b in beta],
                                       "feats": X.shape[1]}
    json.dump(out, open(f"{WORK}/analysis/fit-results-r2.json", "w"), indent=1)
    print("\nsaved analysis/fit-results-r2.json")

if __name__ == "__main__":
    main()
