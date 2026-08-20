# Hermes model cost + capability comparison — snapshot 2026-08-20

> ⚠️ **This is a dated price snapshot.** LLM prices move weekly and a family-wide DeepSeek
> rise landed 2026-08-16. Re-verify against openrouter.ai before acting on it more than a few
> weeks after the date above. Readable version published as a Claude artifact.
>
> Method: 5 independent per-family research passes, each re-checked by a separate adversarial
> price verifier, then a completeness critic, then synthesis. 12 agents, 45 models surveyed.

# Hermes Agent model decision — Grok 4.3 vs the 2026-08 field

All prices sampled **2026-08-20** from OpenRouter (your billing path). Prices are **USD per 1M tokens, input / output**.

## 1. Bottom line

- **Yes, xAI shipped two newer Groks — but the newest one is the wrong upgrade.** Grok 4.6 (2026-08-12) costs **1.6x input / 2.4x output** vs your 4.3, **halves the context window** (1M → 500K) and has a **2.5x dearer cache read** ($0.50 vs $0.20).[^1][^3]
- **Switch to `deepseek/deepseek-v4-flash-0731`.** At **$0.065 / $0.14** it is ~**19x cheaper input, 18x cheaper output** than grok-4.3 — and it is *also far more capable*: AA coding **69.1 vs 42.2**, AA agentic **48.4 vs 24.2**.[^4][^2] Open weights, **MIT**, and it exposes `tools` + `tool_choice` + `structured_outputs`, so it is a drop-in for Hermes' tool calling.[^1] This is not a compromise; it strictly dominates the incumbent on both axes you named.
- **Your incumbent is weaker than you think.** grok-4.3's real Artificial Analysis scores are **37.9 intelligence / 42.2 coding / 24.2 agentic** — the lowest of any Grok that publishes them, and below the *cheaper, newer* `grok-build-0.1` ($1.00/$2.00, 40.7/51.5/28.9).[^2][^7] Earlier notes citing "AA Intelligence 53" for 4.3 were wrong by 15 points.
- **"Prior version is now cheap" mostly fails.** Grok 4.5 and 4.6 are **identically $2.00/$6.00**. DeepSeek Pro-0423 is the **same price as** Pro-0813 and measurably worse. DeepSeek Flash actually **inverts** — the newer 0731 is cheaper than 0423. Only **Qwen** rewards staying a generation back (details in §4).
- **The tempting "one generation back" Grok is `grok-4.20` — $1.25/$2.50, same price as your 4.3, with 2M context instead of 1M. I still don't recommend it:** it is the only current Grok with **no Artificial Analysis block at all** (capability literally unmeasured) and it does **not** support `reasoning_effort`, so you cannot tune thinking spend.[^7]
- **If you want to stay on Grok, move to `x-ai/grok-build-0.1`**, not 4.6: it is **newer** than 4.3 (2026-05-20 vs 2026-04-30), **cheaper** ($1.00/$2.00), and beats it on all three AA indices. Cost: context drops 1M → 256K.[^7]

## 2. Master table — sorted by output price ascending

Prices are each model page's headline = the **lowest-input endpoint's (input, output) pair**. Benchmark column is the **Artificial Analysis coding index** (the one number comparable across all four families, all read from the same OpenRouter field[^2]).

| model id | in $/1M | out $/1M | context | open weights + licence | reasoning | AA coding |
|---|---|---|---|---|---|---|
| `qwen/qwen3.7-flash` | $0.03 → 0.10 → 0.20 | **$0.13** → 0.40 → 0.80 ⚠️tiered | 1,000,000 | ❌ closed | yes | **unmeasured** |
| `deepseek/deepseek-v4-flash-0731` ⭐ | **$0.065** | **$0.14** | 262K–1.31M by provider | ✅ **MIT** | yes, `reasoning_effort` | **69.1** |
| `deepseek/deepseek-v4-flash` (0423) | $0.0679 | $0.168 | 1,048,576 | ✅ **MIT** | yes | 56.2 |
| `qwen/qwen3-coder-next` | $0.12 | $0.80 | 262,144 | ✅ **Apache-2.0** | no (never thinks) | 36.2 |
| `qwen/qwen3.6-35b-a3b` | $0.098 | $0.95 | 262,144 | ✅ **Apache-2.0** | yes | 41.9 |
| `qwen/qwen3.6-flash` | $0.1875 → 0.75 | $1.125 → 3.00 ⚠️tiered | 1,000,000 | ❌ closed | yes | none published |
| `qwen/qwen3.7-plus` | $0.32 → 0.96 | $1.28 → 3.84 ⚠️tiered | 1,000,000 | ❌ closed | yes | 55.9 |
| `qwen/qwen3.6-plus` | $0.325 → 1.30 | $1.95 → 3.90 ⚠️tiered | 1,000,000 | ❌ closed | yes | 54.5 |
| `deepseek/deepseek-v4-pro-0813` | $0.66 / peak 1.32 | $1.98 / peak 3.96 ⚠️clock | 1,048,576 | ✅ **MIT** | yes, `reasoning_effort` | 68.8 |
| `deepseek/deepseek-v4-pro` (0423) | $0.66 / peak 1.32 | $1.98 / peak 3.96 ⚠️clock | 1,048,576 | ✅ **MIT** | yes | 59.4 |
| `qwen/qwen3.6-27b` | $0.30 | $2.00 | 262,144 | ✅ **Apache-2.0** | yes | 53.7 |
| `x-ai/grok-build-0.1` | $1.00 | $2.00 | 256,000 | ❌ closed | yes (`reasoning` only) | 51.5 |
| `moonshotai/kimi-k2.5` | $0.375 | $2.025 | 262,144 | ✅ modified-MIT | yes | 46.8 |
| **`x-ai/grok-4.3` ← YOUR INCUMBENT** | **$1.25** | **$2.50** | **1,000,000** | ❌ closed | yes, `reasoning_effort` | **42.2** |
| `x-ai/grok-4.20` | $1.25 | $2.50 | 2,000,000 | ❌ closed | yes | none published |
| `qwen/qwen3.8-27b` | $0.40 | $3.00 | 262,144 | ✅ **Apache-2.0** | yes, disableable | 68.1 |
| `moonshotai/kimi-k2.6` | $0.58 | $3.40 | 262,144 | ✅ modified-MIT | yes | 61.8 |
| `moonshotai/kimi-k2.7-code` | $0.67 | $3.40 | 262,144 | ✅ modified-MIT | yes | 60.8 |
| `qwen/qwen3.7-max` | $1.475 | $4.425 | 1,000,000 | ❌ closed | yes | 66.0 |
| `x-ai/grok-4.5` | $2.00 | $6.00 | 500,000 | ❌ closed | yes | 72.4 |
| `x-ai/grok-4.6` (newest Grok) | $2.00 | $6.00 | 500,000 | ❌ closed | yes | 76.8 |
| `qwen/qwen3.8-max` | $2.00 | $6.00 | 1,000,000 | ❌ closed | yes | 71.8 |
| `qwen/qwen3.8-2.4t-a95b` | $2.00 | $6.00 | 262K–1.05M | ✅ **custom-restricted** | **cannot disable** | 71.9 |
| `qwen/qwen3.6-max-preview` | $1.027 → 1.58 | $6.162 → 9.48 ⚠️tiered | 262,144 | ❌ closed | yes | none published |
| `moonshotai/kimi-k3` (newest Kimi) | $2.60 | $13.00 | 974K–1.05M | ✅ **custom-restricted** | yes, `reasoning_effort` | **76.2** |

**Read the sort as the argument: 13 of the models below are cheaper on output than your incumbent, and 9 of those also score higher on AA coding.** Every model named as a candidate in §1 and §5 was checked for `tools` + `tool_choice` support — all pass.[^1]

Sources: Grok[^1][^3][^7] · DeepSeek[^4][^5][^6] · Qwen[^8][^9][^10][^11] · Kimi[^12][^13][^14][^15] · all AA scores[^2] · licences[^16]

⚠️ **tiered** = price steps up with prompt length (the headline is the narrowest tier). ⚠️ **clock** = price changes by time of day. Both detailed in §6.

## 3. Grok generations — where 4.3 sits

Newest is **`x-ai/grok-4.6`**, released **2026-08-12**, canonical slug `x-ai/grok-4.6-20260810`. Confirmed two ways: highest-numbered served model, and the `~x-ai/grok-latest` alias resolves to it. Probes for grok-4.7 / 4.8 / 5 / 4.6-fast / 4.6-mini all return **HTTP 404** — nothing newer exists.[^1]

| generation | model | in / out | context | AA int / cod / agentic | vs your 4.3 |
|---|---|---|---|---|---|
| latest | `grok-4.6` | $2.00 / $6.00 | 500,000 | 60.9 / 76.8 / 58.7 | **+60% in, +140% out, −50% context** |
| prior | `grok-4.5` | $2.00 / $6.00 | 500,000 | 55.8 / 72.4 / 48.9 | same as 4.6 — no saving for going back |
| **yours** | **`grok-4.3`** | **$1.25 / $2.50** | **1,000,000** | **37.9 / 42.2 / 24.2** | — |
| newer + cheaper | `grok-build-0.1` | $1.00 / $2.00 | 256,000 | 40.7 / 51.5 / 28.9 | −20% in, −20% out, **better on all 3** |
| older, big ctx | `grok-4.20` | $1.25 / $2.50 | 2,000,000 | none published | same price, 2x context |

You are **two generations behind**, and 4.3 is *not* deprecated — 4 live endpoints, 99.996–100% uptime.[^3] The trade for 4.6 is **+82% AA coding / +143% AA agentic** for **1.6x/2.4x cost, half the context, 2.5x cache-read cost**. There is no cheap Grok tier any more: `grok-3-mini`, `grok-4-fast`, `grok-4.1-fast`, `grok-code-fast-1` and `grok-4` are all **retired with zero live endpoints** — no price exists for them.[^1] "Fast" is now a **service tier** (`xai/priority` endpoint tag) at exactly **2x** price, not a model.

## 4. Latest vs prior, per open-weight family

### DeepSeek — prior is NOT cheaper (Pro), and is *dearer* (Flash)

| | latest | prior | delta |
|---|---|---|---|
| Pro | `v4-pro-0813` $0.66/$1.98 | `v4-pro` (0423) $0.66/$1.98 | **$0.00 — identical, override table for override table** |
| Flash | `v4-flash-0731` **$0.065/$0.14** | `v4-flash` (0423) $0.0679/$0.168 | **newer is 4% / 17% CHEAPER** |
| older gen | — | `v3.2` $0.2088/$0.3096, 163K ctx | 3x Flash's input for AA coding 44.2 vs 69.1 |

**Verdict: no. The prior Pro is strictly dominated** — same price, AA 45.3/59.4/37.8 vs 53.2/68.8/49.6. On Flash the premise inverts outright. Both lines are **MIT**.[^4][^5][^6][^16]

### Qwen — the one family where prior IS cheaper

| | latest | prior | delta |
|---|---|---|---|
| closed flagship | `qwen3.8-max` $2.00/$6.00 (AA cod 71.8) | `qwen3.7-max` **$1.475/$4.425** (AA cod 66.0) | **prior 26% cheaper both sides, −5.8 AA coding** |
| open weights | `qwen3.8-27b` $0.40/$3.00 (Apache-2.0) | `qwen3.6-27b` **$0.30/$2.00** (Apache-2.0) | **prior 25% in / 33% out cheaper** |
| open small | — | `qwen3.6-35b-a3b` $0.098/$0.95 (Apache-2.0) | cheapest Apache-2.0 route anywhere here |
| two back | — | `qwen3.6-max-preview` $1.027/**$6.162** | **output DEARER than the latest flagship** |

**Verdict: yes, but it's the wrong prize.** The prior generation genuinely costs less, *and* the capability gap is real (qwen3.6-27b AA 37.7/53.7/27.5 vs qwen3.8-27b 52/68.1/50.9). The actual best-value Qwen is a **latest-gen** model: **`qwen3.8-27b` at $0.40/$3.00 under a clean Apache-2.0 licence**, self-hostable, thinking disableable. Note the entire **Qwen 3.7 generation has zero open weights** (`author=Qwen&search=Qwen3.7` → 0 HF repos), so 3.6 *is* the prior open generation.[^8][^9][^10][^11][^16]

### Kimi — prior is much cheaper, and the newest one has a licence change

| | model | in / out | AA int / cod / agentic | licence |
|---|---|---|---|---|
| latest | `kimi-k3` (2026-07-16) | $2.60 / **$13.00** | **59.7 / 76.2 / 54.3** | **custom "Kimi K3 License"** |
| prior | `kimi-k2.7-code` (2026-06-12) | $0.67 / $3.40 | 43.0 / 60.8 / 30.3 | modified-MIT |
| prior | `kimi-k2.6` (2026-04-20) | **$0.58 / $3.40** | 45.1 / 61.8 / 31.2 | modified-MIT |
| older | `kimi-k2.5` (2026-01-27) | $0.375 / $2.025 | 36.0 / 46.8 / 21.7 | modified-MIT |

**Verdict: yes — dramatically.** K3 is a genuine top-tier model (AA coding 76.2, essentially tied with grok-4.6's 76.8) but at **$13/1M output it has the most expensive output in this entire comparison — 5.2x your incumbent and 93x DeepSeek Flash-0731.** `kimi-k2.6` at $0.58/$3.40 delivers 81% of K3's AA coding for **26% of the output cost**, and note K2.6 is *cheaper than* the newer K2.7-code while scoring slightly higher. Older K2 generations (`kimi-k2`, `kimi-k2-0905`, `kimi-k2-thinking`) are all dominated — `kimi-k2-thinking` scores AA coding **21.0** at $0.60/$2.50. There is no non-code `kimi-k2.7` (HTTP 404) — that generation shipped as a coding model only. `~moonshotai/kimi-latest` is a floating alias → `kimi-k3`; don't pin it.[^12][^13][^14][^15][^16]

## 5. Cost in practice

**Stated assumption** — personal Telegram agent, one user: **90 requests/day**, **~8,000 input tokens** per request (system prompt + memories + tool definitions + short history) and **~600 output tokens** (including billed thinking tokens). That is **≈21.6M input + 1.6M output per month**. Contexts stay far below 200K, so every ≥200K cliff below is a boundary you will not cross at this shape.

| model | monthly cost | vs incumbent |
|---|---|---|
| `deepseek/deepseek-v4-flash-0731` @ $0.065/$0.14 | **$1.63** | **−95%** |
| `deepseek/deepseek-v4-flash` (0423) | $1.74 | −94% |
| `deepseek-v4-flash-0731` @ modal $0.14/$0.28 | $3.47 | −89% |
| `qwen/qwen3.8-27b` | $13.44 | −57% |
| `moonshotai/kimi-k2.6` | $17.97 | −42% |
| `deepseek/deepseek-v4-pro-0813` (off-peak / blended) | $17.42 / ≈$22.50 | −44% / −27% |
| `x-ai/grok-build-0.1` | $24.80 | −20% |
| **`x-ai/grok-4.3` (incumbent)** | **$31.00** | — |
| `qwen/qwen3.7-max` | $38.94 | +26% |
| `x-ai/grok-4.6` | $52.80 | **+70%** |
| `moonshotai/kimi-k3` | $76.96 | **+148%** |

**At this volume the whole decision is worth ~$30/month, so capability should drive it — and the cheapest option is also the more capable one.** Two practical notes: (1) **output includes thinking tokens**, so raising `reasoning_effort` raises spend invisibly; flash-0731 and qwen3.8-27b let you bound it, while `qwen3.8-2.4t-a95b` **cannot disable thinking at all** — you pay $6/1M reasoning on every call. (2) The $0.065/$0.14 headline is OpenInference, whose context ceiling is **262,144** — irrelevant at the ~8K prompts assumed here, so it is the right route for this workload. **If you later need more than 262K**, use **Relace ($0.07/$0.14, 1,048,576 ctx)** or **Sail Research ($0.065/$0.18, 1,048,576 ctx)**; Relace costs $1.74/mo at this volume, still −94%.[^4] Do **not** route Flash to DeepSeek's own endpoint — at $0.22/$0.66 it is the second-dearest of 28.

## 6. Caveats and what remains UNVERIFIED

**Price convention (this changes conclusions, not decimals).** OpenRouter's `pricing` field in `/api/v1/models` reports **one arbitrary non-cheapest provider endpoint**, not the price the model page lists and routes to. The page headline is the **lowest-input endpoint's (input, output) pair** — not a column-wise minimum. Every price in this report was taken from `/endpoints` under that rule and cross-checked against the rendered page. Using the raw field would have you reporting that the older `qwen3.6-27b` ($0.60/$3.60) costs *more* than the newer `qwen3.8-27b` ($0.45/$3.20) — it doesn't ($0.30/$2.00 vs $0.40/$3.00).

**DeepSeek prices change by the clock, and the page does not say so.** DeepSeek's own endpoint carries time-of-day `pricing.overrides` (UTC): Pro is **$0.66/$1.98 from 10:00–01:00 and 04:00–06:00**, but **$1.32/$3.96 from 01:00–04:00 and 06:00–10:00** — peak for **7 of every 24 hours**. Flash first-party is $0.22/$0.66 off-peak, $0.44/$1.32 peak. Alibaba's endpoint on Pro-0813 runs its own clock ($1.32/$3.96 00:00–14:00, $0.726/$2.178 14:00–00:00). The rendered model page shows only the off-peak figure.[^5][^6] Budget Pro against **$0.66–1.32 in / $1.98–3.96 out**. A family-wide DeepSeek price rise took effect **2026-08-16 16:00 UTC**; some third-party endpoints may not have repriced yet.

**Grok's two hidden 2x multipliers.** Every live Grok **doubles input and output at ≥200,000 prompt tokens** (`overrides.min_prompt_tokens=200000`), and the `xai/priority` tag doubles again — worst case **4x** headline. On your 4.3 that is $1.25/$2.50 → $2.50/$5.00 → $5.00/$10.00. Because 4.3 advertises 1M context, an agent that fills it silently pays double.[^3] Zero-data-retention (`xai/zdr`) is free.

**Qwen tiered pricing is a trap on 1M-context models.** `qwen3.7-flash` runs **6.7x** from cheapest to dearest tier ($0.03/$0.13 <32K → $0.10/$0.40 at 32K → $0.20/$0.80 at ≥256K). `qwen3.7-plus` **triples** at ≥256K. `qwen3-coder-plus` hits $1.95/$9.75 at ≥128K.[^10]

**Licences — "open weights" is not uniformly permissive.** Verified via the HF API `cardData.license`:[^16] **MIT** — all DeepSeek V4 Pro/Flash and V3.2. **Apache-2.0** — `qwen3.8-27b`, `qwen3.6-27b`, `qwen3.6-35b-a3b`, `qwen3-coder-next`. **Custom-restricted** — `qwen3.8-2.4t-a95b` (`license_name: qwen3.8-max`) and **`kimi-k3` (`license_name: kimi-k3`, not the modified-MIT used by every earlier Kimi)**. I read both custom licence files: they are MIT-derived, adding (a) name attribution above 100M MAU or $20M monthly revenue and (b) a separate agreement if you run a Model-as-a-Service business above $20M (Kimi) / $50M (Qwen) over 12 months. **Neither binds a homelab agent.** Provider quantisation also varies at identical prices (fp4/fp8/bf16) — cheapest is not equivalent.

**Genuinely UNVERIFIED:**
- **Benchmarks are self-reported.** No primary SWE-bench Verified / GPQA Diamond / AIME / MMLU-Pro exists for **any** current Grok — xAI publishes a different suite (DeepSWE, CursorBench, Terminal-Bench). Widely-circulated "Grok 4.6 SWE-bench Verified 95.6%" and "LiveCodeBench 88.2%" figures come from low-quality aggregators and are **deliberately omitted**. Vendor cards across families use different harnesses and are **not cross-comparable** — hence the single AA column.
- **`knowledge_cutoff` is null** for grok-4.3/4.5/4.6 in the API; the commonly cited "1 Feb 2026" cutoff for 4.6 is not from OpenRouter and I did not verify it.
- **`x-ai/grok-4.20` and `qwen/qwen3.7-flash` have no AA block at all** — capability is unmeasured, not merely unlisted.
- **Release dates for `qwen3.7-plus`, `qwen3.7-flash`, `qwen3-coder-plus`**: only OpenRouter *listing* dates exist, which are demonstrably not release dates (four qwen3.6 models share one bulk listing date).
- **Alibaba's own English Model Studio docs do not list `qwen3.8-max` at all**, even though Alibaba serves it on OpenRouter at $2/$6 — treat that page as stale, not as evidence of unavailability.
- **The adversarial verification pass for Qwen arrived truncated**, so Qwen figures rest on my own live re-verification rather than an audited second opinion. DeepSeek and Grok had full verification.

**Retired — no price exists** (zero live endpoints; not "unverified", unpurchasable): `x-ai/grok-4`, `grok-4-fast`, `grok-4.1-fast`, `grok-code-fast-1`, `grok-3-mini`, `qwen/qwen-max`, `qwen/qwen-turbo`. ⚠️ The `openrouter.ai/x-ai/grok-4` marketing page **still renders** and still cites a stale **128K** surcharge threshold (every live Grok uses 200K) — do not eyeball prices from it.

**Floating aliases — do not pin these in Hermes:** `~x-ai/grok-latest` → grok-4.6, `~moonshotai/kimi-latest` → kimi-k3, `~deepseek/deepseek-v4-flash-latest` → v4-flash-0731. They silently re-point to a different model, price and context window on every vendor release. Also note the **slug collision**: on OpenRouter the bare `deepseek/deepseek-v4-pro` is the **old 0423 snapshot**, whereas on DeepSeek's own API that name serves 0813 — reaching for the obvious name here silently gets you the prior generation.

---

[^1]: https://openrouter.ai/api/v1/models
[^2]: `benchmarks.artificial_analysis` block in https://openrouter.ai/api/v1/models (retrieved 2026-08-20; no publication date given by the field)
[^3]: https://openrouter.ai/api/v1/models/x-ai/grok-4.3/endpoints · https://openrouter.ai/api/v1/models/x-ai/grok-4.6/endpoints · https://openrouter.ai/api/v1/models/x-ai/grok-4.5/endpoints · https://docs.x.ai/docs/models
[^4]: https://openrouter.ai/deepseek/deepseek-v4-flash-0731 · https://openrouter.ai/api/v1/models/deepseek/deepseek-v4-flash-0731/endpoints
[^5]: https://openrouter.ai/deepseek/deepseek-v4-pro-0813 · https://openrouter.ai/api/v1/models/deepseek/deepseek-v4-pro-0813/endpoints
[^6]: https://openrouter.ai/deepseek/deepseek-v4-pro · https://openrouter.ai/api/v1/models/deepseek/deepseek-v4-pro/endpoints · https://api-docs.deepseek.com/quick_start/pricing
[^7]: https://openrouter.ai/api/v1/models/x-ai/grok-build-0.1/endpoints · https://openrouter.ai/api/v1/models/x-ai/grok-4.20/endpoints
[^8]: https://openrouter.ai/qwen/qwen3.8-27b · https://openrouter.ai/api/v1/models/qwen/qwen3.8-27b/endpoints
[^9]: https://openrouter.ai/qwen/qwen3.6-27b · https://openrouter.ai/api/v1/models/qwen/qwen3.6-27b/endpoints · https://openrouter.ai/qwen/qwen3.6-35b-a3b
[^10]: https://openrouter.ai/api/v1/models/qwen/qwen3.7-max/endpoints · .../qwen3.7-plus/endpoints · .../qwen3.7-flash/endpoints · .../qwen3.6-plus/endpoints · .../qwen3.6-flash/endpoints · .../qwen3.6-max-preview/endpoints
[^11]: https://openrouter.ai/api/v1/models/qwen/qwen3.8-max/endpoints · .../qwen3.8-2.4t-a95b/endpoints · .../qwen3-coder-next/endpoints
[^12]: https://openrouter.ai/moonshotai/kimi-k3 · https://openrouter.ai/api/v1/models/moonshotai/kimi-k3/endpoints
[^13]: https://openrouter.ai/moonshotai/kimi-k2.6 · https://openrouter.ai/api/v1/models/moonshotai/kimi-k2.6/endpoints
[^14]: https://openrouter.ai/moonshotai/kimi-k2.7-code · https://openrouter.ai/api/v1/models/moonshotai/kimi-k2.7-code/endpoints
[^15]: https://openrouter.ai/moonshotai/kimi-k2.5 · https://openrouter.ai/api/v1/models/moonshotai/kimi-k2.5/endpoints
[^16]: https://huggingface.co/api/models/moonshotai/Kimi-K3 · https://huggingface.co/moonshotai/Kimi-K3/raw/main/LICENSE · https://huggingface.co/api/models/moonshotai/Kimi-K2.6 · https://huggingface.co/api/models/Qwen/Qwen3.8-27B · https://huggingface.co/api/models/Qwen/Qwen3.6-27B · https://huggingface.co/api/models/Qwen/Qwen3.6-35B-A3B · https://huggingface.co/api/models/deepseek-ai/DeepSeek-V3.2 · https://huggingface.co/api/models/Qwen/Qwen3.8-2.4T-A95B
---

## Appendix — completeness critic output (raw)

## Blocking caveat on the input I was given

The data array is **truncated mid-Qwen** — it ends at `"openrouter_id": "qwen/qwen3.8-max", "pr`. The Qwen verifier's `checks[]`, `missed_models[]` and `summary` were never supplied, so **one of the three families arrived with no verification pass I could critique**. Everything I state about Qwen below is my own live verification, not an audit of theirs. All figures sampled 2026-08-20; working notes at `/tmp/claude-1000/-home-matteo-Claude-HomelabProject/4db44dcc-0c52-4561-9d11-5f09bc2e3850/scratchpad/completeness_critic_notes.txt`.

## 1. The price convention — and its exact scope

The DeepSeek verifier's root-cause finding is correct and I reproduced it independently from `/endpoints` rather than re-reading its pages. The rule: **an OpenRouter model page's headline price is the (input, output) pair of the lowest-*input* endpoint**, while `pricing.prompt`/`pricing.completion` in `https://openrouter.ai/api/v1/models` is one arbitrary non-cheapest endpoint. Not a column-wise minimum — on `deepseek/deepseek-v4-pro`, DigitalOcean's $1.74 output undercuts DeepSeek's $1.98, yet the headline is still $0.66/$1.98 (https://openrouter.ai/api/v1/models/deepseek/deepseek-v4-pro/endpoints).

**The same error contaminated Qwen, and nobody corrected it.** The Qwen researcher documented the symptom themselves ("the page shows qwen3.8-27b at $0.40/$3.00 while the API default is $0.45/$3.20") and then reported the API default anyway. Verified both ways:

- `qwen/qwen3.8-27b` — page headline **$0.40 / $3.00** (Chutes, fp8), API field $0.45/$3.20 (AkashML/Parasail/Reka/Venice). 7 endpoints, $0.40–$0.55 in / $3.00–$3.40 out. https://openrouter.ai/qwen/qwen3.8-27b and https://openrouter.ai/api/v1/models/qwen/qwen3.8-27b/endpoints
- `qwen/qwen3.6-27b` — page headline **$0.30 / $2.00**, API field $0.60/$3.60. https://openrouter.ai/qwen/qwen3.6-27b

**Scope bound so this isn't over-applied:** all Grok models and every closed Alibaba model (`qwen3.8-max`, `qwen3.7-max/plus/flash`, `qwen3.6-plus/flash/max-preview`, `qwen3-coder-plus`) are **single-provider**, so their prices were never at risk and are confirmed exact. Among reported Qwen multi-provider rows only `qwen3.8-27b` was actually wrong — `qwen3.8-2.4t-a95b` ($2.00/$6.00) and `qwen3-coder-next` ($0.12/$0.80, Parasail bf16) are right because cheapest happens to equal modal there.

I also re-derived the verifier's five DeepSeek corrections from endpoint data and **they all hold**: v4-pro-0813 $0.66/$1.98, v4-pro $0.66/$1.98, v4-flash-0731 $0.065/$0.14 (OpenInference), v4-flash $0.0679/$0.168 (DigitalOcean), v3.2 $0.2088/$0.3096 (GMICloud).

## 2. Item 1 — the prior-version gap that actually defeats the request: Qwen open weights

Grok's prior (4.5) was found. DeepSeek's prior was found for **both** the Pro and Flash lines. **Qwen's prior open-weight generation was never priced at all.** The researcher established that the entire 3.7 generation is API-only — I re-confirmed it: `https://huggingface.co/api/models?author=Qwen&search=Qwen3.7` returns **0 repos**, while `search=Qwen3.6` returns 4 (`Qwen3.6-27B`, `Qwen3.6-35B-A3B`, plus both FP8 variants). So the immediately-prior open-weight Qwen generation is **3.6**, and it was named in passing and priced nowhere. Filling it:

| model | licence (verified) | headline (cheapest-input) | full range | ctx | AA int / cod / agentic |
|---|---|---|---|---|---|
| `qwen/qwen3.6-27b` | **Apache-2.0** | **$0.30 / $2.00** (Chutes fp8) | $0.30–0.60 in / $2.00–3.60 out, 7 eps | 262,144 | 37.7 / 53.7 / 27.5 |
| `qwen/qwen3.6-35b-a3b` | **Apache-2.0** | **$0.098 / $0.95** (Venice fp8) | $0.098–0.25 in / $0.95–1.60 out, 9 eps | 262,144 | 32.1 / 41.9 / 21.6 |
| `qwen/qwen3.6-plus` (closed) | proprietary | **$0.325 / $1.95** | Alibaba only; **≥256K → $1.30 / $3.90** | 1,000,000 | 40.5 / 54.5 / 29.0 |
| `qwen/qwen3.6-flash` (closed) | proprietary | **$0.1875 / $1.125** | Alibaba only; **≥256K → $0.75 / $3.00** | 1,000,000 | none published |
| `qwen/qwen3.6-max-preview` (closed) | proprietary | **$1.027 / $6.162** | Alibaba only; **≥128K → $1.58 / $9.48** | 262,144 | none published |

Licences read from `https://huggingface.co/api/models/Qwen/Qwen3.6-27B` and `.../Qwen3.6-35B-A3B` (`cardData.license = apache-2.0`, ungated) — genuinely unrestricted, unlike the latest 2.4T checkpoint whose licence I re-confirmed as `license: other`, `license_name: qwen3.8-max` (custom-restricted, https://huggingface.co/api/models/Qwen/Qwen3.8-2.4T-A95B). Endpoint pricing from `https://openrouter.ai/api/v1/models/qwen/qwen3.6-27b/endpoints` (and the three siblings); headlines cross-checked on https://openrouter.ai/qwen/qwen3.6-35b-a3b.

Nothing newer exists in any family — the 414-model catalogue's newest per author are `deepseek/deepseek-v4-pro-0813` (2026-08-12), `qwen/qwen3.8-27b` (2026-08-14), `x-ai/grok-4.6` (2026-08-12).

## 3. Item 2 — the two fillable UNVERIFIEDs are now closed

**DeepSeek peak/off-peak passthrough — RESOLVED, and it's worse than "unverified".** OpenRouter *does* pass the swing through, as time-of-day `pricing.overrides` carrying `utc_start`/`utc_end` (HHMM):

- DeepSeek's own endpoint on **both** `v4-pro` and `v4-pro-0813`: `10:00–01:00 $0.66/$1.98` · `01:00–04:00 $1.32/$3.96` · `04:00–06:00 $0.66/$1.98` · `06:00–10:00 $1.32/$3.96`; cache read $0.022 off-peak / $0.044 peak.
- DeepSeek's endpoint on `v4-flash` and `v4-flash-0731`: **$0.22/$0.66 off-peak, $0.44/$1.32 peak**, same windows.
- Alibaba's endpoint on `v4-pro-0813` runs its *own* clock: `00:00–14:00 $1.32/$3.96`, `14:00–00:00 $0.726/$2.178`.

Source: https://openrouter.ai/api/v1/models/deepseek/deepseek-v4-pro-0813/endpoints and `.../deepseek-v4-flash-0731/endpoints`.

**This breaks the headline rule I just adopted, and it is the most decision-relevant thing I found.** The $0.66/$1.98 headline is the *off-peak* figure. During peak (7 of every 24 hours) the DeepSeek endpoint is $1.32/$3.96 and is no longer the lowest-input route — on `v4-pro`, DigitalOcean at $0.87/$1.74 becomes cheapest. And the rendered page **does not surface the time variation at all**: I fetched https://openrouter.ai/deepseek/deepseek-v4-pro-0813 and it shows only "$0.66 / $1.98 per 1M", no peak/off-peak note. Anyone budgeting from the page has a number that is wrong for 29% of the day.

**`deepseek/deepseek-v3.2` licence — RESOLVED: MIT.** `https://huggingface.co/api/models/deepseek-ai/DeepSeek-V3.2` → `cardData.license = mit`, ungated. (Also confirmed MIT: `DeepSeek-V4-Pro`, `DeepSeek-V4-Pro-0813`, `DeepSeek-V4-Flash-0731`. `Qwen/Qwen3-Coder-Next` = Apache-2.0.)

Correctly closed-with-reason, not fillable: the five retired Grok slugs (`grok-4`, `grok-4-fast`, `grok-4.1-fast`, `grok-code-fast-1`, `grok-3-mini`) and `qwen/qwen-max`/`qwen-turbo` — all zero endpoints, so "retired, no price exists" is the right statement, not UNVERIFIED. Note also that `knowledge_cutoff` is **null** for grok-4.3/4.5/4.6 in the API (only the 4.20 family publishes `2025-09-01`), so the research's "1 Feb 2026 cutoff" for 4.6 is not from OpenRouter and I did not verify it.

## 4. Item 3 — where "older models are now cheap" DIES

**Grok: premise fails outright at the prior generation.** `grok-4.5` and `grok-4.6` are **both $2.00 / $6.00** (`xai` tag), both 500K context, both with `xai/priority` at exactly 2x ($4/$12) and both doubling at ≥200K prompt tokens. There is *zero* cost saving from staying one generation back. The only reason to prefer 4.5 is that its **cache read is cheaper — $0.30/1M vs 4.6's $0.50/1M** ($0.60 vs $1.00 in the ≥200K tier), which matters only for cache-heavy agent loops. The premise survives only two generations back at `grok-4.3` ($1.25/$2.50). Sources: https://openrouter.ai/api/v1/models/x-ai/grok-4.6/endpoints and `.../grok-4.5/endpoints`.

**DeepSeek: the prior generation is strictly dominated — same price, worse model.** On DeepSeek's own endpoint, `v4-pro` (0423) and `v4-pro-0813` are **identically priced, override table for override table** ($0.66/$1.98 off-peak, $1.32/$3.96 peak, cache $0.022). So the older snapshot buys AA intelligence 45.3 / coding 59.4 / agentic 37.8 versus 53.2 / 68.8 / 49.6 at *exactly* the same cost. On Flash it's worse than a tie: the **newer** 0731 is cheaper — $0.065/$0.14 versus 0423's $0.0679/$0.168. The research's apparent "cheaper prior output" was entirely the `pricing`-field artifact.

**Qwen: the one family where the premise survives — but only under the corrected convention.**
- Closed flagship: `qwen3.7-max` **$1.475/$4.425** vs `qwen3.8-max` **$2.00/$6.00** — prior is ~26% cheaper on both sides. Both Alibaba-only, both flat-rate, so these are exact. Premise holds.
- Open weights: `qwen3.6-27b` **$0.30/$2.00** vs `qwen3.8-27b` **$0.40/$3.00** — 25% cheaper input, 33% cheaper output, with a real capability gap (AA 37.7/53.7/27.5 vs 52/68.1/50.9). Premise holds.
- **And here is the cleanest proof that the convention error changes conclusions, not just decimals: on the API-default field the same comparison inverts.** $0.60/$3.60 (3.6-27b) vs $0.45/$3.20 (3.8-27b) would have you reporting that the *older* open-weight Qwen costs *more* than the newer one. It doesn't.
- Second counterexample inside the same family: `qwen3.6-max-preview` output is **$6.162** — *above* `qwen3.8-max`'s $6.00. Two generations back is more expensive on output.
- Sharper point than "prior is cheaper": the best-value Qwen is a **latest-generation** model, `qwen3.8-27b` at $0.40/$3.00 under Apache-2.0 — not the prior flagship. And the tiered rows are traps: `qwen3.7-plus` triples at ≥256K ($0.32/$1.28 → $0.96/$3.84) and `qwen3.7-flash` runs 6.7x from cheapest to dearest tier ($0.03/$0.13 → $0.10/$0.40 at 32K → $0.20/$0.80 at 256K), both on models advertised with 1M context.

## 5. Item 4 — the incumbent `x-ai/grok-4.3`

Its **price was never the unclear part** and is confirmed exactly: $1.25/$2.50, 1,000,000 context, four live tags (`xai`, `xai/priority`, `xai/zdr`, `xai/zdr/priority`), `uptime_last_30m` 99.996–100%, `overrides.min_prompt_tokens=200000` → $2.50/$5.00, priority tag $2.50/$5.00 → $5.00/$10.00 at ≥200K, cache read $0.20→$0.40, `web_search` $0.005, `internal_reasoning` null (thinking bills at the plain $2.50 output rate), and `reasoning_effort` supported. https://openrouter.ai/api/v1/models/x-ai/grok-4.3/endpoints

**What was genuinely unclear is now resolved, and it inverts the research's conclusion.** The researcher wrote that `benchmarks[]` is "deliberately empty" because xAI published nothing, and cited "the only public scoring is third-party (Artificial Analysis Intelligence Index 53)". Both statements are wrong. The `benchmarks` field in `https://openrouter.ai/api/v1/models` is **populated** for grok-4.3 — with 21 Design Arena rows *and* an `artificial_analysis` block:

| | AA intelligence | AA coding | AA agentic |
|---|---|---|---|
| `x-ai/grok-4.3` (incumbent) | **37.9** | **42.2** | **24.2** |
| `x-ai/grok-4.5` | 55.8 | 72.4 | 48.9 |
| `x-ai/grok-4.6` | 60.9 | 76.8 | 58.7 |
| `x-ai/grok-build-0.1` | 40.7 | 51.5 | 28.9 |

The claimed "AA Intelligence Index 53" for 4.3 is off by 15 points; the real figure is **37.9**. Its Design Arena ranks are 44th–58th in the model arenas and 21st–36th in the agent arenas. So the trade the user actually faces is: **+82% AA coding, +143% AA agentic** for **1.6x input, 2.4x output, and half the context (1M → 500K)** — plus 4.6's cache read is 2.5x dearer ($0.50 vs $0.20). The "defensible incumbent for long-context work" framing rests only on price and window; on every comparable capability measure that exists, 4.3 is two generations and a very large margin behind, and `grok-build-0.1` — which is *newer* than 4.3 (20260520 vs 20260430, so the research's "older"/"variant" labels are chronologically inverted) and cheaper at $1.00/$2.00 — already beats it on all three AA indices. `x-ai/grok-4.20` is the one current Grok with **no** `artificial_analysis` block at all.