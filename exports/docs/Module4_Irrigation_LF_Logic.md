# Module 4 — Irrigation & Leaching Fraction Logic
# 【排液比与洗盐对冲逻辑 (Irrigation & Leaching Fraction)】

> **Source / 数据来源:** Van der Lugt, G., H.T. Holwerda, K. Hora, M. Bugter, J. Hardeman & P. de Vries (2020). *Nutrient Solutions for Greenhouse Crops*, Version 4. ISBN 9789464021844. Eurofins Agro / Nouryon / SQM / Yara.
> **Generated from:** live import of `constants.py` / `engine.py` — these
> documents are produced by `tools/build_docs.py`, not maintained by hand, so
> they cannot drift from the running system.
> **Provenance tags:** `SRC:WUR` = from the manual · `SRC:DERIVED` = arithmetic
> consequence · `SRC:PRACTICE` = grower practice, no basis in the manual.


> ⚠ **Provenance: `SRC:PRACTICE` throughout.** The WUR manual contains no
> leaching-fraction, wash-cycle or dry-back material. Its only related figures
> are the drain EC-contribution mixing rule (p.24) and the crop-page note that
> high water supply means above 5 L/m²/day (e.g. p.41). Every threshold below
> is grower practice and must be validated locally.

## 1. Leaching fraction / 【排液比 (Leaching Fraction)】

$$\text{LF} = \frac{V_{\text{drain}}}{V_{\text{irrigation}}} \times 100\%$$

| Band | LF | Interpretation |
|---|---|---|
| Deficit | < 10% | Under-irrigation; salt accumulation risk |
| Normal generative | 10–20% | Standard generative operation |
| Normal vegetative | 20–30% | Standard vegetative operation |
| Wash / flush | 30–35% | Elevated leaching to strip salts |
| Excess | > 40% | Water and nutrient waste |

## 2. Wash trigger / 【冲洗触发 (Wash Trigger)】

$$\Delta\text{EC} = \text{EC}_{\text{drain}} - \text{EC}_{\text{dripper}}$$

A gap of **≥ 2.0 mS/cm** triggers a wash cycle.

## 3. Extra irrigation volume / 【需增加灌溉量 (Extra Irrigation)】 `SRC:DERIVED`

Plant uptake is the conserved quantity over the short term, **not drain**:

$$V_{\text{uptake}} = V_{\text{irrigation}} \times (1 - \text{LF}_{\text{current}})$$

$$V_{\text{target\_irr}} = \frac{V_{\text{uptake}}}{1 - \text{LF}_{\text{target}}}$$

$$\Delta V_{\text{extra}} = V_{\text{target\_irr}} - V_{\text{irrigation}} = V_{\text{irrigation}} \times \left( \frac{1 - \text{LF}_{\text{current}}}{1 - \text{LF}_{\text{target}}} - 1 \right)$$

> **Do not pin drain volume.** Solving `V_needed = V_drain / LF_target` holds
> drain constant and inverts the agronomy. At V_irr 4.0, V_drain 1.04 (LF 26%)
> it returns 3.47 L/m² — i.e. that salts are flushed by irrigating *less* — so
> the increment clamps to **0.00** and the wash instruction silently does
> nothing. Uptake is what the crop fixes; drain is the residual.

## 4. Tiered wash target / 【分级冲洗目标 (Tiered Wash Target)】

A fixed 32.5% target is only a *raise* while the crop is under-leaching. Past
that it asks for a reduction, clamps to zero, and produces the contradictory
advice "raise LF … add 0.00 L/m²/day".

| Case | Condition | LF_target | ΔV |
|---|---|---|---|
| **STANDARD** | LF < 30% | 32.5% | > 0 |
| **MODERATE** | 30% ≤ LF < 40% | min(50%, LF + 10) | > 0 |
| **ANOMALY** | LF ≥ 40% | none | **0, by diagnosis** |

The ANOMALY case is an agronomic finding, not a clamp. An EC gap persisting
while over 40% of applied water already drains is not a leaching deficit:
water is bypassing the root zone (substrate channeling / preferential flow),
the dripper or stock EC is over-calibrated, or salt has accumulated beyond what
volume can shift. It raises `G-WASH-ANOMALY` **instead of** `G-WASH-TRIGGER`,
and directs the grower to shorter, more frequent pulses rather than more water.

### Worked examples

| Case | V_irr | V_drain | LF | Target | ΔV | V_target |
|---|---|---|---|---|---|---|
| STANDARD | 4.00 | 1.04 | 26.0% | 32.5% | **+0.39** | 4.39 |
| MODERATE | 5.00 | 1.75 | 35.0% | 45.0% | **+0.91** | 5.91 |
| ANOMALY | 5.00 | 2.20 | 44.0% | — | **0.00** | 5.00 |

## 5. Reference irrigation fallback / 【参考灌溉量 (Reference Fallback)】

When no measured volume is supplied, a crop- and stage-keyed reference stands
in and the result is flagged `is_estimated_volume`. Stages stack; the **highest
demand wins**. Every `high_water` entry stays above 5 L/m²/day because that is
the manual's own definition of the stage.

## 6. Standalone module / 【独立模块 (Standalone Module)】

`exports/modules/irrigation_lf_engine.py` — pure standard library, no web
framework, full type hints and docstrings. Public API:

| Function | Purpose |
|---|---|
| `calculate_leaching_fraction()` | LF from irrigation and drain volumes |
| `calculate_extra_wash_volume()` | Full `WashPlan` including tier and ΔV |
| `get_crop_default_irrigation()` | Reference volume fallback |
| `wash_target_lf()` | Tier selection |
| `format_extra_irrigation()` | Bilingual display, never a bare "+0.00" |

Verified to reproduce the live engine bit-for-bit across the tier boundaries.
