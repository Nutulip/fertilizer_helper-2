# Role: Senior AgTech Software Architect, Data Engineer & Computational Agronomist

Context:
Our codebase (`fertilizer_helper-2`) implements the Wageningen University & Research (WUR) greenhouse fertigation standard across 5 core modules (covering Section B Chapters 13–17 full crop library). We need to extract all embedded WUR agronomic database assets, chemistry formulas, diagnostic safety gates, and solvers into standalone, production-ready deliverables for cross-departmental demonstration (Software, Data Science, AI, and Agronomy).

Task:
Perform a comprehensive scan of the codebase (`constants.py`, `engine.py`, `main.py`, `index.html`, etc.) and automatically generate three parallel export formats for every module:
1. Pure Data & Standalone Code Assets (JSON / CSV / Standalone Python Modules)
2. Technical Specification & Logic Manuals (Markdown Specification Docs)
3. Interactive Analytical Dashboards & Excel Workbooks (Polished .xlsx spreadsheets with openpyxl formatting, conditional formatting, and embedded charts)

---

## 📁 STEP 0: Directory Topology Initialization

Execute the following bash command to create the export directory topology:
`mkdir -p exports/data exports/docs exports/modules exports/excel`

---

## 🛠️ STEP 1: Global Master Database Export

Extract all baseline WUR constants, atomic weight vectors, crop targets (Streefcijfers), and chemistry limits into a unified master dataset.

### Deliverables:
1. `exports/data/wur_master_database.json`:
   - Comprehensive JSON database containing all crop target matrices, atomic weight vectors (WUR Table 7), acid neutralization equivalents, and A/B tank compatibility matrices.
2. `exports/docs/WUR_Master_Data_Spec.md`:
   - Master technical whitepaper documenting all agronomic parameters, formulas, and units in bilingual format: 【中文 (英文/英文缩写)】.

---

## 🧪 STEP 2: Module 1 - Base Water Quality & Acid Neutralization (原水水质与加酸中和)

Extract base water parameters, bicarbonate (HCO3-) neutralization formulas, acid density/molar conversions (65% HNO3, 85% H3PO4), and net nutrient deduction rules.

### Deliverables:
1. `exports/data/module1_acid_neutralization.json`:
   - Raw water quality parameter bounds (pH, EC, HCO3-, Na+, Cl-, Ca2+, Mg2+, SO42-).
   - Molar equivalence conversion factors for Nitric Acid (HNO3) and Phosphoric Acid (H3PO4) (mmol H+/mL acid, N/P yield).
   - Target residual HCO3- safety buffer threshold (0.5–0.75 mmol/L).

2. `exports/docs/Module1_Acid_Algorithm.md`:
   - Step-by-step mathematical derivation of acid volume required per m³ water.
   - Deduction rules for acid-derived N-NO3 and P-H2PO4 from total crop fertigation budget.

3. `exports/excel/Module1_Acid_Dosing_Dashboard.xlsx`:
   - **Workbook Structure**:
     - *Sheet 1: Acid Titration Lookup*: Interactive acid volume lookup across raw HCO3- concentrations (1.0 to 8.0 mmol/L).
     - *Sheet 2: Nutrient Yield Breakdown*: Table showing N and P added per m³ by HNO3 vs H3PO4.
   - **Styling & Charts**: Dark navy header (`#1B365D`) with white bold text, light grey cell borders, conditional formatting highlighting HCO3- > 4.0 mmol/L in amber, and an embedded `LineChart` (via openpyxl) mapping Raw Water HCO3- Concentration vs. Acid Required (mL/m³).

---

## 🌾 STEP 3: Module 2 - WUR Crop Stage Target Value Database (作物物候期目标数据库)

Extract the complete WUR crop target database (Streefcijfers) covering Section B Chapters 13 to 17 (Fruiting Vegetables, Soft Fruits/Berries, Leafy Vegetables, Cut Flowers, Potted Plants).

### Deliverables:
1. `exports/data/wur_crop_targets.json`:
   - Two-tier structured hierarchy: `category` -> `crop_id` -> `substrate_type` (Inert, Organic, Soil) -> `growth_stage`.
   - Complete ion target vectors in mmol/L [NH4, NO3, P, K, Ca, Mg, SO4, Na, Cl] and μmol/L [Fe, Mn, Zn, B, Cu, Mo].
2. `exports/data/wur_crop_targets.csv`:
   - Flattened tabular dataset for rapid Pandas and Excel integration.
3. `exports/docs/Module2_Crop_Database_Spec.md`:
   - Documentation of target EC, pH, and ion ratio benchmarks across crop phenology.
4. `exports/excel/Module2_WUR_Crop_Target_Matrix.xlsx`:
   - **Workbook Structure**: Separate worksheets for each WUR Crop Category (*Fruiting Vegetables*, *Soft Fruits*, *Leafy Vegetables*, *Cut Flowers*, *Potted Plants*).
   - **Styling & Charts**: Forest green header (`#1E4D2B`), freeze panes on top rows, zebra striping. Embed a `BarChart` on each tab comparing Target EC and Key Cations (K+, Ca2+, Mg2+) across different growth stages.

---

## ⚖️ STEP 4: Module 3 - Root Zone Diagnostics, Charge Balance & Safety Gates (理化诊断与刚性熔断)

Extract ion charge balance equations (mmol_c/L), EC normalization algorithms, and If-Else safety circuit-breakers.

### Deliverables:
1. `exports/data/module3_safety_gates_and_rules.json`:
   - JSON array of all safety gates:
     - `G-ACID-POISON`: pH < 5.2 (Critical Acid Poisoning)
     - `G-SALINITY-MELTDOWN`: EC > 4.5 mS/cm (High Osmotic Stress)
     - `G-K-CA-ANTAGONISM`: ΔK > +2.0 mmol/L (Cation Antagonism / Blossom End Rot Risk)
     - `G-NA-CEILING`: Na+ > Crop Ceiling (Osmotic Pressure Alert)
2. `exports/docs/Module3_Ion_Charge_Balance_Spec.md`:
   - Single-Side Charge Balance Formula:
     $$\text{Cations } (\text{mmol}_c/\text{L}) = [\text{K}^+] + 2[\text{Ca}^{2+}] + 2[\text{Mg}^{2+}] + [\text{NH}_4^+] + [\text{Na}^+]$$
     $$\text{Anions } (\text{mmol}_c/\text{L}) = [\text{NO}_3^-] + [\text{H}_2\text{PO}_4^-] + 2[\text{SO}_4^{2-}] + [\text{Cl}^-] + [\text{HCO}_3^-]$$
3. `exports/excel/Module3_Diagnostic_Safety_Simulator.xlsx`:
   - **Workbook Structure**:
     - *Sheet 1: Diagnostic Evaluator*: Sample root zone analysis with calculated charge balance error %.
     - *Sheet 2: Safety Gate Thresholds*: Complete matrix of pH, EC, and ion red-lines.
   - **Styling & Charts**: Dark slate headers (`#2C3E50`), Conditional Formatting (Red fill for pH < 5.2 or EC > 4.5, Amber for Charge Error > 5%), and an embedded `BarChart` or `RadarChart` comparing measured vs. target ion concentrations.

---

## 💧 STEP 5: Module 4 - Irrigation, Leaching Fraction (LF) & Wash Cycle Engine (排液比与洗盐对冲)

Extract hydro-dynamics calculations, Leaching Fraction (LF) algorithms, wash cycle triggers, and fallback mechanisms.

### Deliverables:
1. `exports/modules/irrigation_lf_engine.py`:
   - Pure, standalone Python module (zero web framework dependencies).
   - Functions: `calculate_leaching_fraction()`, `calculate_extra_wash_volume()`, `get_crop_default_irrigation()`.
   - Complete type hinting and comprehensive docstrings.
2. `exports/docs/Module4_Irrigation_LF_Logic.md`:
   - Mathematical derivation for extra wash irrigation volume:
     $$\Delta V_{\text{extra}} = V_{\text{irrigation}} \times \left( \frac{1 - \text{LF}_{\text{current}}}{1 - \text{LF}_{\text{target}}} - 1 \right)$$
3. `exports/excel/Module4_Leaching_Fraction_Model.xlsx`:
   - **Workbook Structure**: Simulation matrix showing required extra irrigation volume (L/m²/day) across various current LF % and EC Gap (ΔEC) values.
   - **Styling & Charts**: Ocean blue headers (`#005A9C`), Data Bars for extra volume, and an embedded `LineChart` demonstrating Extra Irrigation Volume needed to achieve 32.5% Target LF as current LF drops.

---

## 🧪 STEP 6: Module 5 - 100x A/B Stock Tank Dosing Matrix (100倍 A/B 母液罐配方精算)

Extract chemical compatibility rules, A/B tank isolation limits, Fe-chelate stability curves, and mass solver linear algebra rules.

### Deliverables:
1. `exports/data/module5_ab_tank_rules.json`:
   - Chemical compatibility rules (Tank A: Calcium Nitrate, Ammonium Nitrate, Fe-chelates; Tank B: MKP, MgSO4, K2SO4, Micronutrients).
   - Fertilizer purity percentages, molecular weights (g/mol), and Ksp solubility limits.
2. `exports/docs/Module5_AB_Tank_Matrix_Solver.md`:
   - Mathematical formulation for solving fertilizer mass $u_j$ (kg per 1 m³ 100x stock solution).
3. `exports/excel/Module5_AB_Stock_Tank_Calculator.xlsx`:
   - **Workbook Structure**:
     - *Sheet 1: Tank Allocation Breakdown*: Mass allocation (kg) between Tank A and Tank B for a 1000L 100x batch.
     - *Sheet 2: Fe-Chelate pH Selector*: Stability matrix for Fe-EDTA, Fe-DTPA, Fe-EDDHA, Fe-HBED across pH 4.0–8.5.
   - **Styling & Charts**: Deep plum headers (`#4A2E35`), muted zebra striping, and an embedded `DoughnutChart` or `BarChart` displaying the mass ratio of fertilizers in Tank A vs. Tank B.

---

## ⚡ AUTOMATED EXCEL GENERATION SCRIPT REQUIREMENT

To fulfill the Excel export requirements across Steps 2 to 6:
1. Create a Python automation script at `exports/generate_excel_reports.py` using `pandas` and `openpyxl`.
2. Programmatically generate, format, and embed `openpyxl.chart` objects for all 5 Excel files into `exports/excel/`.
3. Execute `python exports/generate_excel_reports.py` during execution to ensure all `.xlsx` files are successfully written to disk.
4. Report back with a summary of generated files upon completion.