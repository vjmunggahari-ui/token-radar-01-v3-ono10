#!/usr/bin/env python3
"""token-radar-01 v3 — experiment contract + model fit (research-to-integration).

EXPERIMENT CONTRACT (written before fitting; evidence labels per skill):
- Goal [measured]: predict log10(protocol token market cap) from public fundamentals,
  beat v2 held-out RMSE 0.9046 (log10 units) on a clean held-out split.
- Baseline [source-reported]: v2 log10(mcap) = 3.0247 + 0.5223 x log10(TVL), RMSE 0.9046.
- Candidates (all OLS, numpy lstsq, no regularisation — n >> p):
    C1: y ~ 1 + logTVL                                  (v2 form, refit on fresh data)
    C2: y ~ 1 + logTVL + logRev30 + logAge + logChains  (fundamentals)
    C3: y ~ 1 + logTVL + logRev30 + logFees30 + logAge + logChains + chg1m
            + category dummies (top-6 categories, rest = other)
- Data split [measured]: random 80/20, seed 42, stratified-free. Metric: held-out RMSE
  of log10(mcap). Also 5-fold CV RMSE on train for stability.
- Acceptance: winner held-out RMSE < 0.9046 AND top-EV board max EV > v2 $3,142,414.
- EV definition [inferred, documented in README]: for gap = pred_log - act_log > 0,
    odds = 1 - Phi(gap / sigma), sigma = winner held-out RMSE (normal residuals);
    upside = 10**gap - 1; EV_usd = (10**pred_log - 10**act_log) * odds
  (expected dollar value of the mispricing gap closing). Board ranks by EV desc.

SOURCES (fetch date 2026-11-26, all public, no key):
- https://api.llama.fi/protocols            (TVL, mcap, chains, category, listedAt, changes)
- https://api.llama.fi/overview/fees?dataType=dailyRevenue  (30d revenue per protocol)
- https://api.llama.fi/overview/fees?dataType=dailyFees     (30d fees per protocol)

CLEANING (documented, no silent drops):
- keep tvl>0 and mcap>0, finite; drop category CEX / Stablecoin / Chain
  (CEX reserves are not DeFi TVL; stablecoin mcap is pegged supply, not a
  valuation; L1/L2 native tokens are valued on chain economics, not protocol TVL).
- revenue/fees: 30d totals; missing -> 0, then log10(1+x).
- age: days since listedAt (2026-11-26); missing listedAt -> median age.
- change_1m: null -> 0.
"""
import json, math, hashlib
import numpy as np
from scipy.stats import norm

WORK = "/home/hatch/workspace/makefun/u-token-radar-01-v3-work"
FETCH_DATE = "2026-11-26"

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def load():
    protos = json.load(open(f"{WORK}/data/raw/protocols-2026-11-26.json"))
    rev = json.load(open(f"{WORK}/data/raw/fees-revenue-2026-11-26.json"))
    fee = json.load(open(f"{WORK}/data/raw/fees-fees-2026-11-26.json"))
    # per-protocol rows live under the "protocols" list (total30d, name, slug)
    rev30, fee30 = {}, {}
    for p in rev.get("protocols", []) or []:
        v = float(p.get("total30d") or 0)
        rev30[p.get("name")] = v
        if p.get("slug"):
            rev30[p["slug"]] = v
    for p in fee.get("protocols", []) or []:
        v = float(p.get("total30d") or 0)
        fee30[p.get("name")] = v
        if p.get("slug"):
            fee30[p["slug"]] = v
    return protos, rev30, fee30

def build_rows():
    protos, rev30, fee30 = load()
    fetch_ts = 1795651200  # 2026-11-26 00:00 UTC approx (used only for age in days)
    ages = []
    for p in protos:
        if p.get("listedAt"):
            ages.append((fetch_ts - p["listedAt"]) / 86400.0)
    median_age = float(np.median(ages)) if ages else 365.0
    rows, dropped = [], {"no_tvl_or_mcap": 0, "excluded_cat": 0}
    for p in protos:
        tvl, mcap = p.get("tvl"), p.get("mcap")
        if not tvl or not mcap or tvl <= 0 or mcap <= 0 or not math.isfinite(tvl) or not math.isfinite(mcap):
            dropped["no_tvl_or_mcap"] += 1
            continue
        cat = p.get("category") or "Unknown"
        if cat in ("CEX", "Stablecoin", "Chain"):
            dropped["excluded_cat"] += 1
            continue
        name = p.get("name") or p.get("slug")
        rev = max(0.0, float(rev30.get(name, rev30.get(p.get("slug"), 0)) or 0))
        fe = max(0.0, float(fee30.get(name, fee30.get(p.get("slug"), 0)) or 0))
        age = (fetch_ts - p["listedAt"]) / 86400.0 if p.get("listedAt") else median_age
        age = max(age, 1.0)
        chg1m = p.get("change_1m")
        chg1m = float(chg1m) if chg1m is not None else 0.0
        rows.append({
            "name": name, "slug": p.get("slug"), "category": cat,
            "tvl": float(tvl), "mcap": float(mcap),
            "chains": len(p.get("chains") or []),
            "revenue30d": rev, "fees30d": fe,
            "age_days": age, "change_1m": chg1m,
            "log_tvl": math.log10(tvl), "log_mcap": math.log10(mcap),
            "log_rev30": math.log10(1.0 + rev), "log_fees30": math.log10(1.0 + fe),
            "log_age": math.log10(age), "log_chains": math.log10(1 + len(p.get("chains") or [])),
        })
    return rows, dropped, median_age

def design(rows, kind, top_cats):
    X, names = [], []
    for r in rows:
        if kind == "C1":
            v = [1.0, r["log_tvl"]]
        elif kind == "C2":
            v = [1.0, r["log_tvl"], r["log_rev30"], r["log_age"], r["log_chains"]]
        else:  # C3
            v = [1.0, r["log_tvl"], r["log_rev30"], r["log_fees30"], r["log_age"],
                 r["log_chains"], r["change_1m"]]
            for c in top_cats:
                v.append(1.0 if r["category"] == c else 0.0)
        X.append(v)
    return np.array(X, dtype=float)

def fit_eval(X, y, seed=42):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    n_test = int(round(0.2 * len(y)))
    te, tr = idx[:n_test], idx[n_test:]
    beta, *_ = np.linalg.lstsq(X[tr], y[tr], rcond=None)
    pred_te = X[te] @ beta
    rmse_te = float(np.sqrt(np.mean((pred_te - y[te]) ** 2)))
    # 5-fold CV on train
    fold = np.array_split(rng.permutation(len(tr)), 5)
    cvs = []
    for f in fold:
        m = np.ones(len(tr), bool); m[f] = False
        b, *_ = np.linalg.lstsq(X[tr][m], y[tr][m], rcond=None)
        cvs.append(float(np.sqrt(np.mean((X[tr][f] @ b - y[tr][f]) ** 2))))
    return beta, rmse_te, float(np.mean(cvs)), float(np.std(cvs)), te, tr

def main():
    rows, dropped, median_age = build_rows()
    print(f"rows kept: {len(rows)}  dropped: {dropped}  median_age_days: {median_age:.0f}")
    cats = {}
    for r in rows:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    top_cats = [c for c, _ in sorted(cats.items(), key=lambda kv: -kv[1])[:6]]
    print("top categories:", [(c, cats[c]) for c in top_cats])
    y = np.array([r["log_mcap"] for r in rows])
    results = {}
    for kind in ("C1", "C2", "C3"):
        X = design(rows, kind, top_cats)
        beta, rmse_te, cv_mean, cv_sd, te, tr = fit_eval(X, y)
        results[kind] = {"beta": beta.tolist(), "rmse_heldout": rmse_te,
                         "cv_mean": cv_mean, "cv_sd": cv_sd, "n_feat": X.shape[1]}
        print(f"{kind}: held-out RMSE={rmse_te:.4f}  5-fold CV={cv_mean:.4f} +- {cv_sd:.4f}  feats={X.shape[1]}")
        print(f"   beta={np.round(beta, 4).tolist()}")
    # winner = lowest held-out RMSE
    winner = min(results, key=lambda k: results[k]["rmse_heldout"])
    print(f"WINNER: {winner} RMSE {results[winner]['rmse_heldout']:.4f} vs v2 0.9046 "
          f"-> beats v2 by {0.9046 - results[winner]['rmse_heldout']:.4f}")
    json.dump({"rows": len(rows), "dropped": dropped, "median_age_days": median_age,
               "top_categories": top_cats, "results": results, "winner": winner,
               "v2_rmse": 0.9046},
              open(f"{WORK}/analysis/fit-results.json", "w"), indent=1)
    # save cleaned rows for the board builder
    json.dump(rows, open(f"{WORK}/data/protocols-clean-2026-11-26.json", "w"))
    print("saved analysis/fit-results.json + data/protocols-clean-2026-11-26.json")

if __name__ == "__main__":
    main()
