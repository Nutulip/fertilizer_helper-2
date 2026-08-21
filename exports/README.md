# Export Deliverables Index
# 【导出交付物索引 (Export Deliverables Index)】

Generated from `docs/CLAUDE_CODE_MASTER_EXPORT_PROMPT.md`.

**Source:** Van der Lugt, G. et al. (2020). *Nutrient Solutions for Greenhouse
Crops*, Version 4. ISBN 9789464021844. Eurofins Agro / Nouryon / SQM / Yara.

Every file here is generated from a live import of `constants.py` / `engine.py`,
so the exports cannot drift from the running system. Regenerate with:

```bash
python tools/build_exports.py        # data assets
python tools/build_docs.py           # specification documents
python exports/generate_excel_reports.py   # formatted workbooks
```

## Data assets 【数据资产】

| File | Content |
|---|---|
| `data/wur_master_database.json` | Atomic weights, ion charges, EC model, oxide conversions, water quality levels, Na ceilings, chelate bands, APN, full fertiliser catalogue, divergence register |
| `data/module1_acid_neutralization.json` | Water parameter bounds, acid molarities, HCO₃ buffer, neutralisation rules, dosing bases |
| `data/wur_crop_targets.json` | Three-tier hierarchy: category → crop → substrate → stage |
| `data/wur_crop_targets.csv` | Flattened, 98 rows × 26 columns, UTF-8 BOM for Excel |
| `data/module3_safety_gates_and_rules.json` | 35-gate registry, charge balance, correction ladder, antagonism patterns, brief-name mapping |
| `data/module5_ab_tank_rules.json` | A/B separation, Ksp limits, allocation order, mass solver, Fe-chelate selection |

## Specification documents 【技术规范文档】

| File | Content |
|---|---|
| `docs/WUR_Master_Data_Spec.md` | Master whitepaper, bilingual 【中文 (English)】 |
| `docs/Module1_Acid_Algorithm.md` | Acid volume derivation, both dosing bases, anion headroom |
| `docs/Module2_Crop_Database_Spec.md` | Crop coverage, three-tier key, transcription validation |
| `docs/Module3_Ion_Charge_Balance_Spec.md` | Charge balance, reference EC, correction ladder, gate registry |
| `docs/Module4_Irrigation_LF_Logic.md` | LF, tiered wash target, ΔV derivation |
| `docs/Module5_AB_Tank_Matrix_Solver.md` | Separation chemistry, allocation order, mass solver |

## Standalone modules 【独立模块】

| File | Content |
|---|---|
| `modules/irrigation_lf_engine.py` | Zero-dependency LF engine, full type hints, doctests. Verified to reproduce the live engine exactly. |

## Excel workbooks 【交互式分析表】

| File | Sheets | Charts |
|---|---|---|
| `excel/Module1_Acid_Dosing_Dashboard.xlsx` | Acid Titration Lookup · Nutrient Yield Breakdown | LineChart |
| `excel/Module2_WUR_Crop_Target_Matrix.xlsx` | One per crop category (5) | BarChart × 5 |
| `excel/Module3_Diagnostic_Safety_Simulator.xlsx` | Diagnostic Evaluator · Safety Gate Thresholds | BarChart |
| `excel/Module4_Leaching_Fraction_Model.xlsx` | LF Simulation · LF × EC Gap Matrix | LineChart |
| `excel/Module5_AB_Stock_Tank_Calculator.xlsx` | Tank Allocation · Fe-Chelate pH Selector | DoughnutChart · BarChart |

10 embedded charts, 14 conditional-formatting rules.

## ⚠ Divergences from the export brief 【与说明书的差异】

Where the brief and the codebase disagree, **the code was exported as
authoritative** and the difference recorded. Full reasoning in the
`spec_divergences` array of `data/wur_master_database.json`.

| ID | Topic | Brief | Code | Severity |
|---|---|---|---|---|
| DIV-1 | Acid grades | 65% HNO₃, 85% H₃PO₄ | 38%/60% HNO₃, 59% H₃PO₄ (WUR Table 5) | **material** — ~1.7× dose difference |
| DIV-2 | Gate names | 4 named gates | `G-MELTDOWN` merges two; 35 gates total | naming only, thresholds match |
| DIV-3 | K:Ca antagonism | ΔK > +2.0 mmol/L | **not implemented**; pattern-based screening instead | **material** — not fabricated |
| DIV-4 | Charge balance | cations omit H⁺ | H⁺ included (required by Table 3 p.23) | material when acid is dosed |
| DIV-5 | Module count | 5 | 8 (grouped into 5 for export) | presentational |
| DIV-6 | Wash target LF | fixed 32.5% | tiered: 32.5 / LF+10 / anomaly | material above 30% LF |

## Provenance tags 【溯源标记】

- `SRC:WUR` — from the manual, with page citation
- `SRC:DERIVED` — arithmetic consequence, validated against the manual's examples
- `SRC:PRACTICE` — grower practice, **no basis in the manual**; validate locally

Module 4 (leaching fraction, wash cycles, dry-back) is `SRC:PRACTICE`
throughout — the manual contains no such material.

## Disclaimer 【免责声明】

Decision support only; not a substitute for professional agronomic advice. The
source manual disclaims warranty as to the accuracy of any data contained
therein.
