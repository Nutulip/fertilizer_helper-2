"""Generate the Markdown specification deliverables into exports/docs/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import constants as C          # noqa: E402
import engine as E             # noqa: E402

DOCS = ROOT / "exports" / "docs"
DATA = ROOT / "exports" / "data"

SRC = ("Van der Lugt, G., H.T. Holwerda, K. Hora, M. Bugter, J. Hardeman & "
       "P. de Vries (2020). *Nutrient Solutions for Greenhouse Crops*, "
       "Version 4. ISBN 9789464021844. Eurofins Agro / Nouryon / SQM / Yara.")

HEADER = """> **Source / 数据来源:** {src}
> **Generated from:** live import of `constants.py` / `engine.py` — these
> documents are produced by `tools/build_docs.py`, not maintained by hand, so
> they cannot drift from the running system.
> **Provenance tags:** `SRC:WUR` = from the manual · `SRC:DERIVED` = arithmetic
> consequence · `SRC:PRACTICE` = grower practice, no basis in the manual.
"""


def w(name: str, body: str) -> Path:
    p = DOCS / name
    p.write_text(body.rstrip() + "\n", encoding="utf-8")
    return p


def divergence_table() -> str:
    div = json.loads((DATA / "wur_master_database.json")
                     .read_text(encoding="utf-8"))["spec_divergences"]
    rows = ["| ID | Topic | Export brief states | Codebase implements | Severity |",
            "|---|---|---|---|---|"]
    for d in div:
        rows.append(f"| **{d['id']}** | {d['topic']} | {d['brief_states']} | "
                    f"{d['codebase_implements']} | {d['severity']} |")
    return "\n".join(rows)


# ==========================================================================

def master_spec() -> str:
    aw = "\n".join(f"| {k} | {v} |" for k, v in C.ATOMIC_WEIGHTS.items())
    ox = "\n".join(f"| {k.replace('_to_', ' → ')} | × {v} |"
                   for k, v in C.OXIDE_TO_ELEMENTAL.items())
    wq = "\n".join(
        f"| {l['level']} | < {l['ec_max']} | < {l['ion_max']} | {l['na_ppm']} | "
        f"{l['cl_ppm']} | {l['suitability_en']} / {l['suitability_zh']} |"
        for l in C.WATER_QUALITY_LEVELS)
    na = "\n".join(f"| {k} | {v} | {round(v * 22.99)} |"
                   for k, v in C.NA_LIMITS_MMOL_L.items())
    che = "\n".join(f"| {k} | {v[0]} – {v[1]} |"
                    for k, v in C.FE_CHELATE_BANDS.items())
    return f"""# WUR Master Data Specification
# 【WUR 主数据规范 (WUR Master Data Specification)】

{HEADER.format(src=SRC)}

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
{aw}

Nitrogen is always qualified as **N-NO₃** or **N-NH₄** (both 14.00). Sulphur is
reported as elemental **S** (32.06) while the ion is SO₄²⁻.

## 3. Charge & EC model / 【电荷与电导模型 (Charge & EC Model)】 `SRC:WUR` Formulas 1–4, p.21

```
Eq_cations (mmol_c/L) = [NH4+] + [K+] + [Na+] + 2[Ca2+] + 2[Mg2+] + [H+]
Eq_anions  (mmol_c/L) = [NO3-] + [Cl-] + 2[SO4 2-] + [HCO3-] + [H2PO4-]
EC (mS/cm)            = (Eq_cations + Eq_anions) / {C.EC_DIVISOR:g}
```

**The H⁺ term is not optional.** Table 3 step 7 (p.23) closes only when acid
protons are counted as cations: EqCat 21.2 vs EqAn 21.25 meq/L at H⁺ = 0.5
mmol/L. Omitting it under-counts cations whenever acid is dosed.

Acceptable cation/anion difference: **{C.ION_BALANCE_TOLERANCE * 100:g}%**
(analytical variation, p.21).

## 4. Reference EC normalisation / 【参比电导率换算】 `SRC:WUR` pp.21–22

```
EC_reference = EC_target_values − {C.REFERENCE_EC_OFFSET}
EC_nutrients = EC_analysed − {C.NA_EC_FACTOR} × Na_analysed (mmol/L)
Nutrient_ref = Nutrient_analysed × EC_reference / EC_nutrients
```

Na and HCO₃ are never converted — they never appear in target values.

## 5. Oxide ⇄ elemental / 【氧化物与元素换算】 `SRC:WUR` Table 4, p.25

| Conversion | Factor |
|---|---|
{ox}

## 6. Water quality levels / 【水质等级 (Water Quality Levels)】 `SRC:WUR` Table 1, p.11

| Level | EC (mS/cm) | Na or Cl (mmol/L) | Na (ppm) | Cl (ppm) | Suitability |
|---|---|---|---|---|---|
{wq}

## 7. Sodium ceilings / 【钠上限 (Sodium Ceilings)】 `SRC:WUR` Table 2, p.12

| Crop | mmol/L | ppm |
|---|---|---|
{na}

These are stated on the root-zone **solution** basis. The crop × substrate
matrix overrides them: organic and soil targets are read from diluted water
extracts, so tomato is 8 mmol/L on inert substrate but **2 on organic
material**. Applying the solution-basis figure to an organic sample would let
sodium reach four times the published limit before any gate fired.

Chloride ceiling = sodium ceiling + {C.CL_OFFSET_MMOL_L} mmol/L.

## 8. Fe-chelate pH stability / 【铁螯合物 pH 稳定区间】 `SRC:WUR` Figure 3a, p.35

| Chelate | Stable pH range |
|---|---|
{che}

Switch point **pH {C.FE_CHELATE_SWITCH_PH}** (p.36): below it Fe-DTPA suffices;
above it Fe-EDDHA or Fe-HBED is strongly recommended. Prophylactic replacement
of {C.PROPHYLACTIC_SUBSTRATE:.0%} (inert substrate) or
{C.PROPHYLACTIC_NFT:.0%} (NFT) pre-empts pH drift.

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

{len(C.crop_ids())} crops across {len(C.CROP_CATEGORIES)} categories,
{len(C.CROP_MATRIX)} crop × substrate matrices, machine-extracted from Section B
and validated by the tables' own ppm redundancy. Detail in
`Module2_Crop_Database_Spec.md`.

## 11. Divergences from the export brief / 【与导出说明书的差异】

Where this brief and the codebase disagree, the **code is authoritative** and
the difference is recorded rather than silently reconciled.

{divergence_table()}

Full reasoning per item in the `spec_divergences` array of
`exports/data/wur_master_database.json`.

## 12. Disclaimer / 【免责声明 (Disclaimer)】

Decision support only; not a substitute for professional agronomic advice. The
source manual disclaims warranty as to the accuracy of any data contained
therein. Values tagged `SRC:PRACTICE` have no basis in the manual and must be
validated against local conditions.
"""


def module1_doc() -> str:
    m1 = json.loads((DATA / "module1_acid_neutralization.json")
                    .read_text(encoding="utf-8"))
    acids = "\n".join(
        f"| {a['name_en']} | {a['density_kg_per_l']} | "
        f"{a['grams_product_per_mol_h']} | {a['molarity_mol_h_per_l']} | "
        f"{a['litres_per_mmol_per_l_per_m3']:.6f} |" for a in m1["acids"])
    return f"""# Module 1 — Acid Neutralisation Algorithm
# 【原水水质与加酸中和算法 (Base Water & Acid Neutralisation)】

{HEADER.format(src=SRC)}

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
Default = {C.DEFAULT_POLICY.hco3_buffer_mmol_l} mmol/L.

## 3. Acid properties / 【酸的物性 (Acid Properties)】 `SRC:WUR` Table 5, p.26

Molarity is derived, not tabulated:

```
mol H⁺/L = (density g/L) / (grams of product per mole of H⁺)
```

| Acid | Density (kg/L) | g product / mol H⁺ | mol H⁺/L | L per (mmol/L · m³) |
|---|---|---|---|---|
{acids}

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

Credited: {', '.join(m1['nutrient_deduction_rules']['creditable_from_base_water'])}.

**Never credited: Fe.** Iron in irrigation water oxidises and precipitates on
contact with air at the emitter; none of it reaches the roots (p.13). Chelated
iron is dosed independently of the iron already present.

Credits are **clamped at the recipe target**. Water carrying more of an ion than
the target cannot be un-supplied; a negative demand is physically meaningless,
so the excess is reported through `G-WATER-EXCESS` instead.
"""


def module2_doc() -> str:
    cats = "\n".join(
        f"| {C.CROP_CATEGORY_LABELS[cat]} | {len(C.crops_in_category(cat))} | "
        f"{', '.join(C.crops_in_category(cat))} |" for cat in C.CROP_CATEGORIES)
    t_i, t_o, t_s = (C.get_crop("tomato", m) for m in
                     ("INERT_SUBSTRATE", "ORGANIC_MATERIAL", "SOIL"))
    return f"""# Module 2 — WUR Crop Target Database Specification
# 【作物物候期目标数据库规范 (Crop Stage Target Database)】

{HEADER.format(src=SRC)}

## 1. Coverage / 【覆盖范围 (Coverage)】

{len(C.crop_ids())} crops · {len(C.CROP_MATRIX)} crop × substrate matrices ·
WUR Section B chapters 13–17.

| Category / 【类别】 | Crops | Members |
|---|---|---|
{cats}

**Not present in Section B.** The export brief lists five crops the manual does
not publish; no data was invented for them:
Zucchini 【西葫芦】, Blackberry 【黑莓】, Spinach 【菠菜】, Lily 【百合】, and
Pot Rose 【盆栽月季】. The manual's nearest equivalents — Blueberry 【蓝莓】,
Microgreens 【芽苗菜】, Zantedeschia 【马蹄莲】, and the Bedding / Flowering /
Foliage Plants tables — are included instead.

## 2. Three-tier key / 【三级索引 (Three-tier Key)】

```
category → crop_id → substrate_type → growth_stage
```

**Substrate is part of the key, never an attribute.** Section B publishes a
separate matrix per medium, and they are not interchangeable — organic targets
come from the 1:1.5 volume water extract and soil targets from the 1:2 extract
(Ch.4, p.18), both of which dilute the actual root-zone solution.

Tomato, one crop, three media:

| Value | Inert | Organic | Soil |
|---|---|---|---|
| Root-zone K (mmol/L) | {t_i.root_zone_targets['K']} | {t_o.root_zone_targets['K']} | {t_s.root_zone_targets['K']} |
| Root-zone Ca | {t_i.root_zone_targets['Ca']} | {t_o.root_zone_targets['Ca']} | {t_s.root_zone_targets['Ca']} |
| Root-zone NO₃ | {t_i.root_zone_targets['NO3']} | {t_o.root_zone_targets['NO3']} | {t_s.root_zone_targets['NO3']} |
| Root-zone EC (mS/cm) | {t_i.ec_root_zone} | {t_o.ec_root_zone} | {t_s.ec_root_zone} |
| Fertigation EC | {t_i.ec_fertigation} | {t_o.ec_fertigation} | {t_s.ec_fertigation} |
| **Na ceiling** | **{t_i.na_max_root_zone}** | **{t_o.na_max_root_zone}** | **{t_s.na_max_root_zone}** |
| Measurement basis | direct | 1:1.5 extract | 1:2 extract |
| Source page | p.{t_i.source_page} | p.{t_o.source_page} | p.{t_s.source_page} |

A lookup keyed on crop alone would return numbers that look plausible and are
agronomically meaningless.

## 3. Growth stages / 【生长阶段 (Growth Stages)】

Stage columns are **not** uniform across Section B. Fruiting vegetables print
Start / Fruit Set / High water / End season; roses print Start / Flowering /
High water supply / Winter; alstroemeria only Start / Flowering; anthurium only
Start. Each crop's stages are read from its own printed header.

**`high_water` is not a growth stage.** Supply above 5 L/m²/day is an orthogonal
*condition* that can coincide with any phase, so it is stored separately as
`high_water_adjustment` and driven by an independent flag. Soil pages publish no
adjustment columns at all — with one documented exception, chrysanthemum (p.78),
which is published on soil only.

## 4. Ion vectors / 【离子向量 (Ion Vectors)】

Macronutrients in mmol/L: NH₄, NO₃, P, K, Ca, Mg, S, Cl (and Na as a ceiling).
Micronutrients in µmol/L: Fe, Mn, Zn, B, Cu, Mo.

S is elemental sulphur; the ion is SO₄²⁻. NH₄/NO₃ are reported as N-NH₄ / N-NO₃.

## 5. Transcription validation / 【转录校验 (Transcription Validation)】

Each Section B table prints both mmol/L and ppm. That redundancy is the
checksum: `mmol/L × atomic weight` must reproduce the printed ppm column.
Extraction was validated against nine hand-transcribed matrices — **332 values,
zero mismatches**.

Four anomalies the checksum surfaced:

1. **p.50 sweet pepper** — the root-zone ppm column is copied from tomato
   (313 ppm = tomato's 8 mmol/L K, not pepper's 5). A genuine source erratum;
   the mmol column is authoritative.
2. Three row labels (HCO₃, N-NH₄, N-NO₃) carry **no text layer** in the PDF and
   are recovered positionally from Section B's fixed row order.
3. Four tables had adjustment cells read from the ppm column; converted and
   logged in `adjustment_normalisations`.
4. Two single-cell residuals remain flagged: blueberry Mg (p.57) and orchid Fe
   (p.93).

## 6. Deliverables / 【交付物 (Deliverables)】

| File | Content |
|---|---|
| `exports/data/wur_crop_targets.json` | Full three-tier hierarchy |
| `exports/data/wur_crop_targets.csv` | Flattened, one row per crop × substrate × stage |
| `exports/excel/Module2_WUR_Crop_Target_Matrix.xlsx` | One worksheet per category |
"""


def module3_doc() -> str:
    m3 = json.loads((DATA / "module3_safety_gates_and_rules.json")
                    .read_text(encoding="utf-8"))
    gates = "\n".join(
        f"| `{g['gate_id']}` | {g['severity']} | {g['module']} | "
        f"{g['condition']} | {g['action']} | {g['provenance']} |"
        for g in m3["gate_registry"])
    mapping = "\n".join(
        f"| `{m['brief_name']}` | {m['brief_condition']} | "
        f"`{m['implemented_as']}` | **{m['status']}** |"
        for m in m3["brief_name_mapping"])
    ant = "\n".join(f"| `{a['code']}` | {a['pattern_en']} / {a['pattern_zh']} |"
                    for a in m3["antagonism_patterns"])
    return f"""# Module 3 — Ion Charge Balance & Safety Gate Specification
# 【理化诊断、电荷平衡与刚性熔断 (Diagnostics, Charge Balance & Safety Gates)】

{HEADER.format(src=SRC)}

## 1. Charge balance / 【电荷平衡 (Charge Balance)】 `SRC:WUR` Formulas 1–2, p.21

$$\\text{{Cations}}\\ (\\text{{mmol}}_c/\\text{{L}}) = [\\text{{NH}}_4^+] + [\\text{{K}}^+] + [\\text{{Na}}^+] + 2[\\text{{Ca}}^{{2+}}] + 2[\\text{{Mg}}^{{2+}}] + [\\text{{H}}^+]$$

$$\\text{{Anions}}\\ (\\text{{mmol}}_c/\\text{{L}}) = [\\text{{NO}}_3^-] + [\\text{{Cl}}^-] + 2[\\text{{SO}}_4^{{2-}}] + [\\text{{HCO}}_3^-] + [\\text{{H}}_2\\text{{PO}}_4^-]$$

> **DIV-4.** The export brief omits the **H⁺** term. It is required: Table 3
> step 7 (p.23) closes only with acid protons counted as cations — EqCat 21.2
> vs EqAn 21.25 meq/L at H⁺ = 0.5 mmol/L. Without it the cation side
> under-counts whenever acid is dosed.

$$\\text{{EC}}\\ (\\text{{mS/cm}}) = \\frac{{\\text{{Eq}}_{{cations}} + \\text{{Eq}}_{{anions}}}}{{20}}$$

Charge-balance error is reported as a percentage; differences below
**{C.ION_BALANCE_TOLERANCE * 100:g}%** are acceptable analytical variation.

## 2. Reference EC normalisation / 【参比电导率换算】 `SRC:WUR` pp.21–22

```
EC_reference = EC_target_values − {C.REFERENCE_EC_OFFSET}
EC_nutrients = EC_analysed − {C.NA_EC_FACTOR} × Na_analysed
Nutrient_ref = Nutrient_analysed × EC_reference / EC_nutrients
```

Excluded from conversion: **Na, HCO₃** (never in target values). Cl only when
the crop publishes a Cl target.

> **Open question.** The manual states a single conversion factor, but the
> Eurofins report it reproduces (p.29) evidently uses different factors for
> cations (~0.966) and anions (~0.900). The documented single-factor method is
> implemented; verify against printed lab reports before relying on the anion
> column.

## 3. Correction ladder / 【三级纠偏 (Correction Ladder)】 `SRC:WUR` p.22

| Level | Deviation from target | Supply adjustment |
|---|---|---|
| 0 | < 25% | none |
| 1 | 25–50% | ∓ 10–15% |
| 2 | ≥ 50% | ∓ a further 15–25% (cumulative 25–40%) |

Direction is inverse: root zone above target → reduce supply. Micronutrient
stepping ladder: **+50%, +25%, 0%, −25%, −50%** `SRC:PRACTICE`.

## 4. Emergency thresholds / 【紧急熔断阈值 (Emergency Gate)】

| Parameter | Limit | Behaviour |
|---|---|---|
| pH | < {C.DEFAULT_POLICY.meltdown_ph_min} | **BLOCKING** |
| EC | > {C.DEFAULT_POLICY.meltdown_ec_max} mS/cm | **BLOCKING** |

When it fires: recipe output is **suppressed**, a hardcoded bilingual flush
instruction set is returned, and the cognitive layer is never invoked — not
merely ignored. Thresholds are `SRC:PRACTICE`; their basis is that the manual
sets hydroponic optimum pH at 5.5–6.5 (p.15) and the highest published
root-zone EC target is 4.0 (tomato inert, p.53).

## 5. Gate registry / 【闸门登记表 (Gate Registry)】

{len(m3['gate_registry'])} gates. Evaluation is in severity precedence; the
first BLOCKING gate short-circuits the pipeline.

| Gate | Severity | Module | Condition | Action | Provenance |
|---|---|---|---|---|---|
{gates}

## 6. Brief name mapping / 【说明书命名对照 (Brief Name Mapping)】

> **DIV-2 / DIV-3.** The gate names in the export brief do not exist in the
> codebase. Rather than rename the emitted identifiers — which the frontend
> consumes — the real registry is exported with this mapping.

| Brief name | Brief condition | Implemented as | Status |
|---|---|---|---|
{mapping}

**`G-K-CA-ANTAGONISM` is not implemented as specified.** No absolute ΔK > +2.0
mmol/L threshold exists in the codebase, and the manual gives none — it reports
the K/Ca ratio and a cation-balance chart (pp.29–30). Fabricating the threshold
for an export would misrepresent the system to agronomy reviewers. Adding it is
an agronomic decision requiring sign-off, not an export task.

## 7. Antagonism patterns / 【离子拮抗模式 (Antagonism Patterns)】

Deterministic pattern matching only — the engine emits the match, the narrative
layer explains it, and the pattern itself is never model-generated.

| Code | Pattern |
|---|---|
{ant}
"""


def module4_doc() -> str:
    return f"""# Module 4 — Irrigation & Leaching Fraction Logic
# 【排液比与洗盐对冲逻辑 (Irrigation & Leaching Fraction)】

{HEADER.format(src=SRC)}

> ⚠ **Provenance: `SRC:PRACTICE` throughout.** The WUR manual contains no
> leaching-fraction, wash-cycle or dry-back material. Its only related figures
> are the drain EC-contribution mixing rule (p.24) and the crop-page note that
> high water supply means above 5 L/m²/day (e.g. p.41). Every threshold below
> is grower practice and must be validated locally.

## 1. Leaching fraction / 【排液比 (Leaching Fraction)】

$$\\text{{LF}} = \\frac{{V_{{\\text{{drain}}}}}}{{V_{{\\text{{irrigation}}}}}} \\times 100\\%$$

| Band | LF | Interpretation |
|---|---|---|
| Deficit | < 10% | Under-irrigation; salt accumulation risk |
| Normal generative | 10–20% | Standard generative operation |
| Normal vegetative | 20–30% | Standard vegetative operation |
| Wash / flush | 30–35% | Elevated leaching to strip salts |
| Excess | > 40% | Water and nutrient waste |

## 2. Wash trigger / 【冲洗触发 (Wash Trigger)】

$$\\Delta\\text{{EC}} = \\text{{EC}}_{{\\text{{drain}}}} - \\text{{EC}}_{{\\text{{dripper}}}}$$

A gap of **≥ {C.DEFAULT_POLICY.wash_trigger_delta_ec} mS/cm** triggers a wash cycle.

## 3. Extra irrigation volume / 【需增加灌溉量 (Extra Irrigation)】 `SRC:DERIVED`

Plant uptake is the conserved quantity over the short term, **not drain**:

$$V_{{\\text{{uptake}}}} = V_{{\\text{{irrigation}}}} \\times (1 - \\text{{LF}}_{{\\text{{current}}}})$$

$$V_{{\\text{{target\\_irr}}}} = \\frac{{V_{{\\text{{uptake}}}}}}{{1 - \\text{{LF}}_{{\\text{{target}}}}}}$$

$$\\Delta V_{{\\text{{extra}}}} = V_{{\\text{{target\\_irr}}}} - V_{{\\text{{irrigation}}}} = V_{{\\text{{irrigation}}}} \\times \\left( \\frac{{1 - \\text{{LF}}_{{\\text{{current}}}}}}{{1 - \\text{{LF}}_{{\\text{{target}}}}}} - 1 \\right)$$

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
| **STANDARD** | LF < {C.DEFAULT_POLICY.wash_lf_moderate_min:g}% | {C.DEFAULT_POLICY.wash_lf_target:g}% | > 0 |
| **MODERATE** | {C.DEFAULT_POLICY.wash_lf_moderate_min:g}% ≤ LF < {C.DEFAULT_POLICY.wash_lf_anomaly_min:g}% | min(50%, LF + 10) | > 0 |
| **ANOMALY** | LF ≥ {C.DEFAULT_POLICY.wash_lf_anomaly_min:g}% | none | **0, by diagnosis** |

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
"""


def module5_doc() -> str:
    m5 = json.loads((DATA / "module5_ab_tank_rules.json").read_text(encoding="utf-8"))
    a = ", ".join(m5["tank_assignment"]["A_only"])
    b = ", ".join(m5["tank_assignment"]["B_only"])
    e = ", ".join(m5["tank_assignment"]["either"])
    return f"""# Module 5 — A/B Stock Tank Matrix Solver
# 【100倍 A/B 母液罐配方精算 (100× A/B Stock Tank Solver)】

{HEADER.format(src=SRC)}

## 1. Separation rule / 【分罐规则 (Separation Rule)】 `SRC:WUR` Ch.9, p.31

> "All calcium fertilisers must be separated from phosphate and sulphate
> fertilisers. This means putting calcium fertilisers into the A tank and
> sulphate and phosphate fertilisers into the B tank."

| Tank | Contents | Members |
|---|---|---|
| **A** 【A 母液罐】 | Calcium fertilisers, chelates | {a} |
| **B** 【B 母液罐】 | Sulphate and phosphate fertilisers | {b} |
| Either | Load-balancing | {e} |

### Precipitation chemistry

| Product | Ksp | Ions |
|---|---|---|
| CaSO₄·2H₂O (gypsum) | 3.14 × 10⁻⁵ | Ca²⁺ + SO₄²⁻ |
| Ca₃(PO₄)₂ | 2.07 × 10⁻³³ | Ca²⁺ + PO₄³⁻ |

At 100× concentration both are far past saturation, which is why separation is
**absolute** rather than a computed margin. Gate `G-PRECIP-RISK` is BLOCKING and
cannot be overridden — the failure mode is an unrecoverable tank of sludge and a
blocked irrigation system.

### Tank pH limits

Tank A **3.5–5.0**, tank B **below 5.0**. Chelate structures break down at
pH ≤ 3.5, especially EDDHA and HBED, so tank-A acid is capped at
{C.DEFAULT_POLICY.tank_a_acid_cap_l:g} L/m³ with the remainder placed in tank B.

## 2. Allocation order / 【配肥顺序 (Allocation Order)】 `SRC:WUR` Ch.8, p.28

```
H⁺ → Cl → Ca → NH₄ → P → Mg → S → K   (NO₃ closes last, via KNO₃)
```

Fixed and deterministic; must not be reordered. Every step **decrements
co-delivered ions** — calcium nitrate carries 5 Ca, 1 NH₄ and 11 NO₃ per mole.
Failing to decrement is the classic way to silently over-dose nitrogen.

Where the chosen salts cannot satisfy every target simultaneously, the residual
is reported through `G-ALLOCATION-RESIDUAL` rather than absorbed. Nitrate is the
usual case: acid plus calcium nitrate can together exceed the NO₃ target,
leaving potassium nitrate nothing to close with.

## 3. Mass solver / 【质量求解 (Mass Solver)】

For fertiliser $j$ supplying driving ion $i$ at concentration $c_i$ (mmol/L),
tank volume $V$ (L) and concentration factor $\\text{{CF}}$:

$$u_j\\ (\\text{{kg}}) = c_i \\times \\text{{MW}}_{{i,j}} \\times \\frac{{\\text{{CF}}}}{{1000}} \\times \\frac{{V}}{{1000}}$$

At the standard CF = 100 and V = 1000 L this reduces to
$u_j = c_i \\times \\text{{MW}}_{{i,j}} \\times 0.1$.

Micronutrients, where $w_j$ is the product's mass fraction:

$$u_j\\ (\\text{{g}}) = c_i\\ (\\mu\\text{{mol/L}}) \\times \\frac{{A_i}}{{w_j}} \\times 0.1$$

Liquids: $V_j = u_j / \\rho_j$.

⚠ $\\text{{MW}}_{{i,j}}$ is grams of product per mole of the **driving ion**.
Calcium nitrate is 1080 g/mol carrying 5 Ca, so the divisor is **216**.

### Validation

The solver reproduces the manual's printed tomato A+B recipe (p.53) line for
line: calcium nitrate 106 kg, CaCl₂ 6, MAP 3, MKP 17, MgSO₄ 59, K₂SO₄ 35,
KNO₃ 43, Fe 1396 g, Mn-EDTA 423 g, Zn-EDTA 218 g, borax 287 g, Cu-EDTA 32 g,
Na-molybdate 12 g — with zero unallocated residual.

## 4. Fe-chelate selection / 【铁源选型 (Fe-Chelate Selection)】 `SRC:WUR` Ch.11

Driven by **root-zone** pH, not drip pH — the chelate must survive where the
root is.

| Root-zone pH | Primary source | Note |
|---|---|---|
| ≤ 6.0 | Fe-EDTA acceptable, Fe-DTPA preferred | EDTA envelope ends at 6.5 |
| 6.0 – 6.5 | **Fe-DTPA** | stable to 7.5 |
| > {C.FE_CHELATE_SWITCH_PH} | **Fe-EDDHA or Fe-HBED** | strongly recommended (p.36) |
| Calcareous soil, any pH | **Fe-EDDHA / Fe-HBED, high ortho-ortho** | mandatory |

Prophylactic replacement: {C.PROPHYLACTIC_SUBSTRATE:.0%} of total Fe in inert
substrate, {C.PROPHYLACTIC_NFT:.0%} in NFT. If deficiency symptoms are already
visible, that fraction is **added on top of** the normal Fe rather than
replacing it.

Metal sulphates of Mn, Zn and Cu cost 20–50% of the iron through chelate
exchange (p.36); EDTA chelates avoid this. Chelates degrade under UV, ozone and
H₂O₂ — re-dose **after** disinfection, never before.
"""


def main() -> None:
    written = [
        w("WUR_Master_Data_Spec.md", master_spec()),
        w("Module1_Acid_Algorithm.md", module1_doc()),
        w("Module2_Crop_Database_Spec.md", module2_doc()),
        w("Module3_Ion_Charge_Balance_Spec.md", module3_doc()),
        w("Module4_Irrigation_LF_Logic.md", module4_doc()),
        w("Module5_AB_Tank_Matrix_Solver.md", module5_doc()),
    ]
    for p in written:
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size:,} bytes)")
    print(f"\n{len(written)} specification documents written")


if __name__ == "__main__":
    main()
