# Module 2 — WUR Crop Target Database Specification
# 【作物物候期目标数据库规范 (Crop Stage Target Database)】

> **Source / 数据来源:** Van der Lugt, G., H.T. Holwerda, K. Hora, M. Bugter, J. Hardeman & P. de Vries (2020). *Nutrient Solutions for Greenhouse Crops*, Version 4. ISBN 9789464021844. Eurofins Agro / Nouryon / SQM / Yara.
> **Generated from:** live import of `constants.py` / `engine.py` — these
> documents are produced by `tools/build_docs.py`, not maintained by hand, so
> they cannot drift from the running system.
> **Provenance tags:** `SRC:WUR` = from the manual · `SRC:DERIVED` = arithmetic
> consequence · `SRC:PRACTICE` = grower practice, no basis in the manual.


## 1. Coverage / 【覆盖范围 (Coverage)】

24 crops · 47 crop × substrate matrices ·
WUR Section B chapters 13–17.

| Category / 【类别】 | Crops | Members |
|---|---|---|
| Fruiting Vegetables (果菜类) | 5 | cucumber, eggplant, melon, sweet_pepper, tomato |
| Soft Fruits / Berries (浆果类) | 3 | blueberry, raspberry, strawberry |
| Leafy Vegetables (叶菜类) | 3 | herbs, lettuce, microgreens |
| Cut Flowers (切花类) | 6 | alstroemeria, carnation, chrysanthemum, gerbera, rose, zantedeschia |
| Potted Plants (盆栽植物) | 7 | anthurium, bedding_plants, poinsettia, flowering_plants, foliage_plants, phalaenopsis, orchids_other |

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
| Root-zone K (mmol/L) | 8.0 | 2.8 | 2.2 |
| Root-zone Ca | 10.0 | 3.8 | 2.5 |
| Root-zone NO₃ | 22.0 | 8.25 | 5.0 |
| Root-zone EC (mS/cm) | 4.0 | 1.5 | 1.4 |
| Fertigation EC | 2.6 | 2.6 | 1.3 |
| **Na ceiling** | **8.0** | **2.0** | **8.0** |
| Measurement basis | direct | 1:1.5 extract | 1:2 extract |
| Source page | p.53 | p.54 | p.55 |

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
