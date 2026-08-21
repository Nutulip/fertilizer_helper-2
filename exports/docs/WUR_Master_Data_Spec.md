# WUR Master Data Specification
# 【WUR 主数据规范 (WUR Master Data Specification)】

> **Source / 数据来源:** Van der Lugt, G., H.T. Holwerda, K. Hora, M. Bugter, J. Hardeman & P. de Vries (2020). *Nutrient Solutions for Greenhouse Crops*, Version 4. ISBN 9789464021844. Eurofins Agro / Nouryon / SQM / Yara.
> **Generated from:** live import of `constants.py` / `engine.py` — these
> documents are produced by `tools/build_docs.py`, not maintained by hand, so
> they cannot drift from the running system.
> **Provenance tags:** `SRC:WUR` = from the manual · `SRC:DERIVED` = arithmetic
> consequence · `SRC:PRACTICE` = grower practice, no basis in the manual.


## 1. Scope / 【范围 (Scope)】

This whitepaper documents every agronomic constant, formula and unit embedded in
the Fertilizer Helper codebase. Machine-readable counterpart:
`exports/data/wur_master_database.json`.

**Module mapping.** The export brief describes 5 modules; the system implements
8. The grouping used across these deliverables:

| Brief module | Implemented modules |
|---|---|
| 1 — Base Water & Acid Neutralisation 【原水水质与加酸中和】 | M1 (water, acid) + M7 (base-water deduction) |
| 2 — Crop Stage Target Database 【作物物候期目标数据库】 | M5 (steering) + crop library |
| 3 — Diagnostics, Charge Balance & Safety Gates 【理化诊断与刚性熔断】 | M4 (feedback) + M8 (diagnostics, emergency) |
| 4 — Irrigation & Leaching Fraction 【排液比与洗盐对冲】 | M3 |
| 5 — A/B Stock Tank Dosing 【100倍 A/B 母液罐配方精算】 | M6 (tanks, chelates) + M7 (recipe engine) |

## 2. Atomic weights / 【原子量矩阵 (Atomic Weight Matrix)】 `SRC:WUR` Table 7, p.39

Units are g/mol, numerically identical to mg/mmol and µg/µmol.

| Ion / 【离子 (Ion)】 | g/mol |
|---|---|
| K | 39.1 |
| Ca | 40.08 |
| Mg | 24.31 |
| N | 14.0 |
| P | 30.97 |
| S | 32.06 |
| N_NO3 | 14.0 |
| N_NH4 | 14.0 |
| NO3 | 14.0 |
| NH4 | 14.0 |
| Na | 22.99 |
| Cl | 35.45 |
| HCO3 | 61.02 |
| Fe | 55.85 |
| Mn | 54.94 |
| Zn | 65.38 |
| B | 10.81 |
| Cu | 63.55 |
| Mo | 95.94 |

Nitrogen is always qualified as **N-NO₃** or **N-NH₄** (both 14.00). Sulphur is
reported as elemental **S** (32.06) while the ion is SO₄²⁻.

## 3. Charge & EC model / 【电荷与电导模型 (Charge & EC Model)】 `SRC:WUR` Formulas 1–4, p.21

```
Eq_cations (mmol_c/L) = [NH4+] + [K+] + [Na+] + 2[Ca2+] + 2[Mg2+] + [H+]
Eq_anions  (mmol_c/L) = [NO3-] + [Cl-] + 2[SO4 2-] + [HCO3-] + [H2PO4-]
EC (mS/cm)            = (Eq_cations + Eq_anions) / 20
```

**The H⁺ term is not optional.** Table 3 step 7 (p.23) closes only when acid
protons are counted as cations: EqCat 21.2 vs EqAn 21.25 meq/L at H⁺ = 0.5
mmol/L. Omitting it under-counts cations whenever acid is dosed.

Acceptable cation/anion difference: **10%**
(analytical variation, p.21).

## 4. Reference EC normalisation / 【参比电导率换算】 `SRC:WUR` pp.21–22

```
EC_reference = EC_target_values − 0.3
EC_nutrients = EC_analysed − 0.1 × Na_analysed (mmol/L)
Nutrient_ref = Nutrient_analysed × EC_reference / EC_nutrients
```

Na and HCO₃ are never converted — they never appear in target values.

## 5. Oxide ⇄ elemental / 【氧化物与元素换算】 `SRC:WUR` Table 4, p.25

| Conversion | Factor |
|---|---|
| NO3 → N | × 0.226 |
| NH4 → N | × 0.776 |
| P2O5 → P | × 0.436 |
| K2O → K | × 0.83 |
| CaO → Ca | × 0.715 |
| MgO → Mg | × 0.603 |
| SO4 → S | × 0.334 |
| SO3 → S | × 0.4 |

## 6. Water quality levels / 【水质等级 (Water Quality Levels)】 `SRC:WUR` Table 1, p.11

| Level | EC (mS/cm) | Na or Cl (mmol/L) | Na (ppm) | Cl (ppm) | Suitability |
|---|---|---|---|---|---|
| 1 | < 0.5 | < 1.5 | < 34 | < 53 | Suitable for all crops / 适用于所有作物 |
| 2 | < 1.0 | < 2.5 | 34 - 57 | 53 - 87 | Not suitable when recirculation is necessary / 需要循环回用时不适用 |
| 3 | < 1.5 | < 4.0 | 57 - 92 | 87 - 142 | Not to be used for salt-sensitive crops / 不可用于盐敏感作物 |

## 7. Sodium ceilings / 【钠上限 (Sodium Ceilings)】 `SRC:WUR` Table 2, p.12

| Crop | mmol/L | ppm |
|---|---|---|
| tomato | 8.0 | 184 |
| sweet_pepper | 6.0 | 138 |
| eggplant | 6.0 | 138 |
| cucumber | 6.0 | 138 |
| melon | 6.0 | 138 |
| rose | 4.0 | 92 |
| gerbera | 4.0 | 92 |
| carnation | 4.0 | 92 |
| orchid | 1.0 | 23 |

These are stated on the root-zone **solution** basis. The crop × substrate
matrix overrides them: organic and soil targets are read from diluted water
extracts, so tomato is 8 mmol/L on inert substrate but **2 on organic
material**. Applying the solution-basis figure to an organic sample would let
sodium reach four times the published limit before any gate fired.

Chloride ceiling = sodium ceiling + 0.2 mmol/L.

## 8. Fe-chelate pH stability / 【铁螯合物 pH 稳定区间】 `SRC:WUR` Figure 3a, p.35

| Chelate | Stable pH range |
|---|---|
| fe_edta | 1.5 – 6.5 |
| fe_dtpa | 1.5 – 7.5 |
| fe_eddha | 3.0 – 10.0 |
| fe_hbed | 3.0 – 12.0 |

Switch point **pH 6.5** (p.36): below it Fe-DTPA suffices;
above it Fe-EDDHA or Fe-HBED is strongly recommended. Prophylactic replacement
of 25% (inert substrate) or
10% (NFT) pre-empts pH drift.

## 9. Stock tank mass / 【母液质量计算】 `SRC:WUR` Ch.8, p.28

```
Macronutrient:  kg = mmol/L × MW_per_driving_ion × (CF/1000) × (V/1000)
                at CF=100, V=1000 L  →  kg = mmol/L × MW × 0.1
Micronutrient:   g = µmol/L × atomic_weight / product_fraction × 0.1
Liquid:          L = kg / density
```

⚠ `MW_per_driving_ion` is grams of product per mole of the **driving ion**, not
per mole of fertiliser. Calcium nitrate is 1080 g/mol but carries 5 Ca, so the
divisor is 1080/5 = **216**. Using 1080 over-doses fivefold.

## 10. Crop library / 【作物库 (Crop Library)】

24 crops across 5 categories,
47 crop × substrate matrices, machine-extracted from Section B
and validated by the tables' own ppm redundancy. Detail in
`Module2_Crop_Database_Spec.md`.

## 11. Divergences from the export brief / 【与导出说明书的差异】

Where this brief and the codebase disagree, the **code is authoritative** and
the difference is recorded rather than silently reconciled.

| ID | Topic | Export brief states | Codebase implements | Severity |
|---|---|---|---|---|
| **DIV-1** | Acid concentrations | 65% HNO3, 85% H3PO4 | 38% HNO3 (d=1.24), 60% HNO3 (d=1.37), 59% H3PO4 (d=1.42) | material - dosing volumes differ by roughly 1.7x between 38% and 65% nitric acid |
| **DIV-2** | Safety gate identifiers | G-ACID-POISON (pH<5.2), G-SALINITY-MELTDOWN (EC>4.5), G-K-CA-ANTAGONISM (dK > +2.0 mmol/L), G-NA-CEILING | G-MELTDOWN covers BOTH pH<5.2 and EC>4.5 as one blocking gate; sodium is G-NA-APPROACH / G-NA-EXCEED / G-NA-UNREACHABLE; 36 gates total | naming only - thresholds (pH 5.2, EC 4.5) match exactly |
| **DIV-3** | K:Ca antagonism rule | G-K-CA-ANTAGONISM fires at dK > +2.0 mmol/L | No such rule. Antagonism screening is pattern-based: K_SUPPRESSES_CA_MG fires when K exceeds 40% of cation equivalents AND Ca or Mg is below target. | material - exporting an unimplemented threshold would misrepresent the system to the agronomy reviewers |
| **DIV-4** | Charge balance cation formula | Cations = K + 2Ca + 2Mg + NH4 + Na | Cations = NH4 + K + Na + 2Ca + 2Mg + H+ | material when acid is dosed; identical otherwise |
| **DIV-5** | Module count | 5 core modules | 8 modules (M1-M8) | presentational |
| **DIV-6** | Wash target leaching fraction | Extra irrigation to achieve a 32.5% target LF | Tiered target: 32.5% only while LF < 30%; LF+10 (cap 50%) for 30-40%; no volume target at all above 40% (G-WASH-ANOMALY) | material above 30% LF |

Full reasoning per item in the `spec_divergences` array of
`exports/data/wur_master_database.json`.

## 12. Disclaimer / 【免责声明 (Disclaimer)】

Decision support only; not a substitute for professional agronomic advice. The
source manual disclaims warranty as to the accuracy of any data contained
therein. Values tagged `SRC:PRACTICE` have no basis in the manual and must be
validated against local conditions.
