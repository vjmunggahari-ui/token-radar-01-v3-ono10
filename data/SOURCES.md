# Data sources — token-radar-01 v3

Fetch date: **2026-11-26** (all public APIs, no key, no account).

## Raw downloads (kept in `data/raw/` during the build; NOT shipped — see note)

| Source | URL | Rows | sha256 |
|---|---|---|---|
| DeFiLlama protocols | https://api.llama.fi/protocols | 9,116 protocols | `fc7273f383f9110ecfbc58c574952d3ec67f9195622690a377485716189e44c2` |
| DeFiLlama revenue (30d) | https://api.llama.fi/overview/fees?dataType=dailyRevenue | 2,945 protocols in `protocols[]` | `19d8c4ae9002c2c429d9ac84149e700b7c541d1bba06d80cb1221a887a1502f7` |
| DeFiLlama fees (30d) | https://api.llama.fi/overview/fees?dataType=dailyFees | 2,945 protocols in `protocols[]` | `2946ef59d2e1af772ed04292586026614bef920b5eed668c432ca20b7f2be421` |
| CoinGecko markets p1 | https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1&price_change_percentage=24h%2C7d%2C30d | 250 coins | `70e2c1e03416d65647891c5ca1f90c3759c421bbff1dae2e8b129bc37b2858f9` |
| CoinGecko markets p2 | …page=2… | 250 coins | `30706fb0de28bfa0021d30cc3632c7b3611941637ecb223c962c845cc72b2480` |
| CoinGecko markets p3 | …page=3… | 250 coins | `29279f13637e9c58258c95fffe8239a3dd7506a56d8d06724f5700a26f325dfa` |
| CoinGecko markets p4 | …page=4… | 250 coins | `f962a7f5a20d043a9597f215a8cabd4584a50ab4f65e3bd569f431e592d5b5f8` |
| CoinGecko markets p5 | …page=5… | 250 coins | `7b38b5ea24992af58bf9f31d8ce76af39d038d3617ee1264ac041e15e0cad4ad` |
| CoinGecko markets p6 | …page=6… | 250 coins | `894df70fab50cef53f4f7cb32eec5da02401f0d4112b45aafd7526f7eb83bc9d` |
| CoinGecko markets p7 | …page=7… | 250 coins | `3fe20bd9cbc3c8140d9c29d416e6b8d70cb6d8c36acc0bfc3a3e36bd27b9ef6c` |
| CoinGecko markets p8 | …page=8… | 250 coins | `3d89cbe3afd36bb92079f8ca65ee78254e8ea26c2375d6aeb4e48f613f06c9b6` |

CoinGecko pages were fetched 12 s apart (free-tier rate limit). Llama mcap and
CoinGecko mcap agree to <1% on joined rows (cross-validated 2026-11-26).

## Cleaning (documented, no silent drops)

- Keep TVL > 0 and mcap > 0 and finite: 9,116 → 625 rows.
- Exclude category CEX / Stablecoin / Chain (16 rows): CEX reserves are not
  DeFi TVL; a stablecoin's mcap is pegged supply, not a valuation; L1/L2
  native tokens are valued on chain economics, not protocol TVL.
- Result: **609 protocols** (`data/protocols-clean-2026-11-26.json`).
- Revenue/fees: 30d totals; missing → 0, then log10(1+x); negative 30d
  totals (data errors) clamped at 0.
- Age: days since `listedAt` (2026-11-26); missing → median age (905 days).
- `change_1m`: null → 0.
- CoinGecko join by `gecko_id`: 161/609 joined (top-2000 by mcap). Unjoined
  rows get median-imputed CoinGecko values + a `has_cg` indicator, so the
  volume slope is identified only from joined rows.

## Note on raw files

`data/raw/` (~70 MB) is build scratch and is NOT part of the shipped entry
(the staged repo carries only the cleaned dataset, the board and the model).
Re-fetch any raw file from the URLs above and verify against the sha256 here.

## Tydro

v2's top-EV protocol (Tydro) is NOT in this board: the fresh DeFiLlama data
lists Tydro TVL $398,012,619 but mcap null, so it fails the mcap > 0 rule.
No market cap was invented for it.
