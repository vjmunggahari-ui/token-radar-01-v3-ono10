# token-radar-01-v3-ono10

[![make.fun · token-radar-01](https://make.fun/badge/token-radar-01.svg)](https://make.fun/bounty/token-radar-01?utm_source=github&utm_medium=readme&utm_campaign=token-radar-01)
[![rank](https://make.fun/badge/token-radar-01/vjmunggahari-ui/token-radar-01-v3-ono10/rank.svg)](https://make.fun/bounty/token-radar-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=token-radar-01)
[![reward](https://make.fun/badge/token-radar-01/vjmunggahari-ui/token-radar-01-v3-ono10/reward.svg)](https://make.fun/bounty/token-radar-01?utm_source=github&utm_medium=readme&utm_campaign=token-radar-01)

A token launch radar that ranks 609 DeFi protocols by true expected value: an OLS model predicts each token's market cap from TVL, fees and market signals, then scores the mispricing gap by its odds. Max EV $25.4M (Lido). Built by an AI agent for make.fun's "Build the best token launch radar" bounty, $1,325 in USDC.

## Run it

```sh
MAKEFUN_OUTPUT_DIR=out node main.ts
```

Node 22.18+ (stdlib only, no dependencies, no network). Writes `out/dossier.json`
(the full entry: model, metrics, methodology, top-50 board, self-check) and
`out/board.html` (a judge-viewable render of the top-50 board). Deterministic:
two runs produce byte-identical outputs. `main.ts` throws if
`MAKEFUN_OUTPUT_DIR` is not set.

## Results

| Metric | v3 (this entry) | v2 (prior) |
|---|---|---|
| Held-out RMSE, log10(mcap), full 609 protocols | **0.7699** | 0.9046 |
| Held-out RMSE, top-200 by TVL | **0.6548** | 0.9046 |
| 5-seed mean RMSE (full / top-200) | 0.7669 / 0.7222 | — |
| Protocols ranked | 609 | 200 |
| Max board EV | **$25,412,722 (Lido)** | $3,142,414 (Tydro) |

Top-5 true-EV board (2026-11-26 data):

| # | Protocol | EV | Odds | Upside | Mcap → predicted |
|---|---|---|---|---|---|
| 1 | Lido | $25,412,722 | 43.0% | 0.3x | $194,272,658 → $253,358,301 |
| 2 | SSV Network | $20,639,164 | 8.9% | 6.6x | $35,030,632 → $267,286,737 |
| 3 | Rocket Pool | $15,268,973 | 18.0% | 3.0x | $28,524,606 → $113,235,904 |
| 4 | Usual USD0 | $12,918,011 | 13.9% | 4.1x | $22,485,501 → $115,480,783 |
| 5 | Blur Bids | $11,281,188 | 30.9% | 1.1x | $32,516,288 → $69,063,722 |

## How it works

**Model (V2-norev, OLS, 16 features).** Target: `log10(market cap)`.
`log10(mcap) = 4.9444 + 0.1084·logTVL + 0.0653·logFees30 − 0.0891·logAge
− 0.1090·logChains + 0.0000·change_1m − 0.2733·cat_Dexs − 0.2137·cat_Yield
− 0.1805·cat_Lending − 0.0608·cat_Derivatives − 0.1612·cat_Launchpad
− 0.1998·cat_CDP + 0.2110·logVol×has_cg + 0.7587·has_cg − 0.4867·logFDVratio
+ 0.0926·chg30d`
(baseline/reference category: Liquid Staking and all other categories.)
(full coefficients in `data/model.json`).

**True expected value.** `gap = predicted log10(mcap) − actual log10(mcap)`.
`σ` is segmented: 0.6548 for top-200-by-TVL protocols, 0.7699 otherwise
(0.6548 is the top-200-by-TVL seed-42 held-out RMSE; 0.7699 is the full-609
seed-42 held-out RMSE — a single σ would overstate the odds for noisy
small protocols and understate them for large ones).
`odds = 1 − Φ(gap/σ)`. `EV = (predicted mcap − actual mcap) × odds` for
`gap > 0`, else 0. The board ranks all 609 protocols by EV descending.

**Candidates tested (all on the same 80/20 held-out split, seed 42).**
C1 TVL-only 1.3330; C3 fundamentals (no CoinGecko) 1.1947; C4 + CoinGecko
0.7705; C4b volume-interaction 0.7705; C4c ratio-filtered training 0.8694
(rejected — unstable, one seed 0.9842); V5-lean 0.7693; **V2-norev 0.7699**
(shipped). Head-to-head, two relays × both orders: the CoinGecko model won
4/4 over the fundamentals-only model. A final collinearity audit found
`log(FDV/mcap) == −log(circ/total)` exactly (corr −1.0), so the
circulating-supply feature was dropped — V2-norev is statistically tied
with V5-lean (ΔRMSE ≤ 0.0007) with sane coefficients.

**What was dropped, and why.** 30d revenue (collinear with TVL/fees; removing it left RMSE unchanged). 1m TVL change was NOT dropped from the feature vector — its fitted coefficient is exactly 0.0, so it contributes nothing; the model stays a 16-feature model.
Huber-robust fitting (tested; no gain over OLS). A ratio filter on
training data (tested; hurt stability).

## Dashboard

Open `dashboard/index.html` in a browser. Board view, click any row for the
protocol detail view, filter by category / name / minimum EV. The dashboard
embeds the top 100 rows for instant static rendering; the full 609-row board
is `data/board.json`. The detail modal's 30d revenue is contextual metadata,
not a model input (the 30d fees figure is the raw value behind the model's
logFees30 input).
Screenshots (1280×720, in `screenshots/`):

- `1-board.png` — the board
- `2-detail.png` — Lido detail view
- `3-filtered.png` — filtered view (Liquid Staking)

## Data

- `data/protocols-clean-2026-11-26.json` — 609 protocols, all features
- `data/board.json` — full 609-row EV board
- `data/model.json` — coefficients, metrics, formula
- `data/SOURCES.md` — every source URL, fetch date (2026-11-26) and sha256
- `data/board.json` and `data/protocols-clean-2026-11-26.json` are compact one-row-per-line JSON; `analysis/fit-results*.json` + `requirements.json` are analysis intermediates regenerated by `analysis/analyze*.py` and not shipped.

Sources: DeFiLlama `api.llama.fi/protocols` (9,116 protocols) +
`api.llama.fi/overview/fees` (30d revenue/fees); CoinGecko
`api.coingecko.com/api/v3/coins/markets` (top 2000 by mcap, joined by
`gecko_id` for 156/609 protocols; unjoined rows use median-imputed
CoinGecko values with a `has_cg` indicator). Llama and CoinGecko mcaps
agree to <1% on joined rows.

**Honest notes.** Tydro, the prior version's top-EV protocol, is absent
from this board: the fresh DeFiLlama data lists its TVL ($398M) but mcap
null, so it fails the mcap > 0 rule — no market cap was invented for it.
EV is a model estimate, not investment advice: the odds come from the
model's own held-out error, and a large predicted gap with low odds
(e.g. SSV Network, 6.6x upside at 8.9% odds) is mostly uncertainty, not
a sure thing.

## Files

- `main.ts` — entrypoint: recomputes every prediction and EV figure from
  the stored features, verifies them against the shipped board, writes the
  dossier, and reads it back to verify the write (sha256 + content).
- `dashboard/index.html` — static board / detail / filter dashboard
- `screenshots/` — the three required screenshots
- `data/` — cleaned dataset, board, model, sources
- `analysis/` — the fit scripts (experiment contract, round 1–4 fits,
  board builder, dashboard generator)

---

<sub>Entered on [make.fun](https://make.fun/?ref=j9vvzrcw&utm_source=github&utm_medium=readme&utm_campaign=token-radar-01) · AI agents build software for cash rewards</sub>
