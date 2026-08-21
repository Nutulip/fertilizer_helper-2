# Module 1 — Acid Neutralisation Algorithm
# 【原水水质与加酸中和算法 (Base Water & Acid Neutralisation)】

> **Source / 数据来源:** Van der Lugt, G., H.T. Holwerda, K. Hora, M. Bugter, J. Hardeman & P. de Vries (2020). *Nutrient Solutions for Greenhouse Crops*, Version 4. ISBN 9789464021844. Eurofins Agro / Nouryon / SQM / Yara.
> **Generated from:** live import of `constants.py` / `engine.py` — these
> documents are produced by `tools/build_docs.py`, not maintained by hand, so
> they cannot drift from the running system.
> **Provenance tags:** `SRC:WUR` = from the manual · `SRC:DERIVED` = arithmetic
> consequence · `SRC:PRACTICE` = grower practice, no basis in the manual.


## 1. Reaction / 【中和反应 (Neutralisation Reaction)】 `SRC:WUR` p.13

```
Ca²⁺ + 2HCO₃⁻ + 2HNO₃  ⇌  Ca²⁺ + 2CO₂ + 2H₂O + 2NO₃⁻
```

CO₂ must be able to escape. In a closed system the pH will not fall and will
fluctuate — the reaction must occur in an **open** mixing tank.

## 2. Proton demand / 【质子需求 (Proton Demand)】

```
H⁺_required (mmol/L) = max(0, HCO₃⁻_base_water − HCO₃⁻_buffer)
```

The buffer is retained deliberately: **0.50–0.75 mmol/L** HCO₃⁻ holds the
irrigation pH at 5.5–6.0. Neutralising all of it drops pH below 5 (p.24).
Default = 0.5 mmol/L.

## 3. Acid properties / 【酸的物性 (Acid Properties)】 `SRC:WUR` Table 5, p.26

Molarity is derived, not tabulated:

```
mol H⁺/L = (density g/L) / (grams of product per mole of H⁺)
```

| Acid | Density (kg/L) | g product / mol H⁺ | mol H⁺/L | L per (mmol/L · m³) |
|---|---|---|---|---|
| Nitric acid 38% | 1.24 | 167.0 | 7.4251 | 0.134677 |
| Nitric acid 60% | 1.37 | 105.0 | 13.0476 | 0.076642 |
| Phosphoric acid 59% | 1.42 | 167.0 | 8.503 | 0.117606 |

> **DIV-1.** The export brief specifies 65% HNO₃ and 85% H₃PO₄. Neither appears
> in WUR Table 5, which lists 38% and 60% nitric and 59% phosphoric. The
> catalogue grades are exported. Because molarity is computed from density and
> mass-per-mole-of-H⁺, a site using a different grade can add it to the
> catalogue and every downstream volume follows automatically. The difference
> is material: 38% and 65% nitric differ by roughly 1.7× in dose volume.

Cross-check: 1240 g/L ÷ 167 = 7.425 mol/L. Deriving instead from mass fraction,
1.23 g/mL × 1000 × 0.38 / 63.01 = 7.418 mol/L — agreement to 0.1%, the gap being
only the density constant. The computed 8.38% N w/w reproduces the manual's
declared "8.4 N".

## 4. Volume derivation / 【体积推导 (Volume Derivation)】 `SRC:DERIVED`

Two different questions, two different answers, differing by the concentration
factor. Reporting only one invites a 100× dosing error.

| Basis | Question | Formula |
|---|---|---|
| **Stock tank** | acid into one 1000 L A/B tank at 100× | `mmol/L × MW × 0.1 ÷ density` |
| **Working solution** | acid into 1000 L of irrigation water at 1× | `(mmol/L ÷ 1000 × V) ÷ molarity` |

```
stock_tank_litres == working_solution_litres × concentration_factor
```

Worked example, H⁺ = 2.0 mmol/L with 38% nitric: stock tank **26.94 L**,
working solution **0.269 L**.

## 5. Anion headroom constraint / 【阴离子余量约束】 `SRC:WUR` p.13

Every mole of H⁺ drags in a mole of acid anion which counts against the recipe:

```
headroom_NO3 = NO3_recipe_target − NO3_base_water     (nitric, 1 H⁺ : 1 NO3⁻)
headroom_P   = P_recipe_target   − P_base_water       (phosphoric, 1 H⁺ : 1 H2PO4⁻)
```

When demand exceeds headroom the plan is **infeasible** and gate
`G-ACID-INFEASIBLE` fires. Remedies, in order: dilute or replace the base
water; accept residual HCO₃⁻ and shift pH control to ammonium; switch to a
high-pH-stable Fe chelate; or raise the NO₃ target with explicit confirmation.

## 6. Ammonium route / 【铵态氮调控 (Ammonium pH Control)】 `SRC:WUR` p.15

NH₄⁺ uptake releases H⁺ into the root zone. Constraints: 0 ≤ NH₄ ≤ 1.5 mmol/L
and 5–15% of total N in hydroponics. pH too high → raise toward 1.5; pH too low
→ reduce to 0–0.5.

## 7. Base-water nutrient deduction / 【原水养分扣抵】

Credited: Ca, Mg, S, K, NO3, NH4, P, Cl.

**Never credited: Fe.** Iron in irrigation water oxidises and precipitates on
contact with air at the emitter; none of it reaches the roots (p.13). Chelated
iron is dosed independently of the iron already present.

Credits are **clamped at the recipe target**. Water carrying more of an ion than
the target cannot be un-supplied; a negative demand is physically meaningless,
so the excess is reported through `G-WATER-EXCESS` instead.
