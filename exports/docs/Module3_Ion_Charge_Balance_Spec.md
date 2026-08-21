# Module 3 — Ion Charge Balance & Safety Gate Specification
# 【理化诊断、电荷平衡与刚性熔断 (Diagnostics, Charge Balance & Safety Gates)】

> **Source / 数据来源:** Van der Lugt, G., H.T. Holwerda, K. Hora, M. Bugter, J. Hardeman & P. de Vries (2020). *Nutrient Solutions for Greenhouse Crops*, Version 4. ISBN 9789464021844. Eurofins Agro / Nouryon / SQM / Yara.
> **Generated from:** live import of `constants.py` / `engine.py` — these
> documents are produced by `tools/build_docs.py`, not maintained by hand, so
> they cannot drift from the running system.
> **Provenance tags:** `SRC:WUR` = from the manual · `SRC:DERIVED` = arithmetic
> consequence · `SRC:PRACTICE` = grower practice, no basis in the manual.


## 1. Charge balance / 【电荷平衡 (Charge Balance)】 `SRC:WUR` Formulas 1–2, p.21

$$\text{Cations}\ (\text{mmol}_c/\text{L}) = [\text{NH}_4^+] + [\text{K}^+] + [\text{Na}^+] + 2[\text{Ca}^{2+}] + 2[\text{Mg}^{2+}] + [\text{H}^+]$$

$$\text{Anions}\ (\text{mmol}_c/\text{L}) = [\text{NO}_3^-] + [\text{Cl}^-] + 2[\text{SO}_4^{2-}] + [\text{HCO}_3^-] + [\text{H}_2\text{PO}_4^-]$$

> **DIV-4.** The export brief omits the **H⁺** term. It is required: Table 3
> step 7 (p.23) closes only with acid protons counted as cations — EqCat 21.2
> vs EqAn 21.25 meq/L at H⁺ = 0.5 mmol/L. Without it the cation side
> under-counts whenever acid is dosed.

$$\text{EC}\ (\text{mS/cm}) = \frac{\text{Eq}_{cations} + \text{Eq}_{anions}}{20}$$

Charge-balance error is reported as a percentage; differences below
**10%** are acceptable analytical variation.

## 2. Reference EC normalisation / 【参比电导率换算】 `SRC:WUR` pp.21–22

```
EC_reference = EC_target_values − 0.3
EC_nutrients = EC_analysed − 0.1 × Na_analysed
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
| pH | < 5.2 | **BLOCKING** |
| EC | > 4.5 mS/cm | **BLOCKING** |

When it fires: recipe output is **suppressed**, a hardcoded bilingual flush
instruction set is returned, and the cognitive layer is never invoked — not
merely ignored. Thresholds are `SRC:PRACTICE`; their basis is that the manual
sets hydroponic optimum pH at 5.5–6.5 (p.15) and the highest published
root-zone EC target is 4.0 (tomato inert, p.53).

## 5. Gate registry / 【闸门登记表 (Gate Registry)】

35 gates. Evaluation is in severity precedence; the
first BLOCKING gate short-circuits the pipeline.

| Gate | Severity | Module | Condition | Action | Provenance |
|---|---|---|---|---|---|
| `G-MELTDOWN` | BLOCKING | M8 | pH < 5.2 or EC > 4.5 mS/cm | Emergency flush; recipe output suppressed; LLM layer bypassed | SRC:PRACTICE thresholds |
| `G-PRECIP-RISK` | BLOCKING | M6 | Ca together with SO4 or PO4 in one tank | Tank bill refused outright - CaSO4 / Ca3(PO4)2 precipitation | SRC:WUR p.31 |
| `G-ACID-INFEASIBLE` | CRITICAL | M1 | H+ demand exceeds NO3+P headroom | Dilute water, or shift pH control to ammonium | SRC:WUR p.13 |
| `G-NA-EXCEED` | CRITICAL | M2 | Root-zone Na above crop ceiling | Forced discharge volume issued | SRC:WUR Table 2 p.12 |
| `G-NA-UNREACHABLE` | CRITICAL | M2 | Base water Na >= flush target | Flushing cannot help; alternative water source required | SRC:DERIVED |
| `G-NA-APPROACH` | WARNING | M2 | Na >= 80% of ceiling | Increase monitoring, plan a discharge window | SRC:PRACTICE |
| `G-WASH-TRIGGER` | CRITICAL | M4 | Drain-dripper EC gap >= 2.0 mS/cm | Raise leaching fraction; extra irrigation volume issued | SRC:PRACTICE |
| `G-WASH-ANOMALY` | CRITICAL | M4 | EC gap >= 2.0 while LF >= 40% | DO NOT add volume; investigate channeling / EC calibration | SRC:PRACTICE |
| `G-NH4-CEILING` | CRITICAL | M5 | NH4 > 1.5 mmol/L in the dosed recipe | Reduce ammonium; pH will drop too far | SRC:WUR p.15 |
| `G-WATER-RECIRC` | CRITICAL | M1 | Quality level >= 2 with recirculation | Level 2 water unsuitable when recirculating | SRC:WUR p.11 |
| `G-WATER-SALT-SENSITIVE` | CRITICAL | M1 | Level 3 water, Na ceiling <= 4 | Not for salt-sensitive crops | SRC:WUR p.11 |
| `G-WATER-UNCLASSIFIED` | CRITICAL | M1 | Beyond Table 1 level 3 | Reverse osmosis or alternative source | SRC:WUR p.11 |
| `G-FE-DRIP` | CRITICAL | M1 | Base-water Fe > 0 on drip irrigation | Aerate and filter before the fertigation unit | SRC:WUR p.14 |
| `G-TANK-A-ACID` | CRITICAL | M6 | Tank A acid above cap with chelates | Chelates break down below pH 3.5 | SRC:WUR p.31 |
| `G-ION-IMBALANCE` | WARNING | M7 | Cation/anion difference > 10% | Counter-ion adjustment needed before filling tanks | SRC:WUR p.21 |
| `G-ALLOCATION-RESIDUAL` | WARNING | M7 | Allocation cannot hit all targets | Usually nitrate over-supply from acid + calcium nitrate | SRC:DERIVED |
| `G-WATER-EXCESS` | WARNING | M7 | Base water above recipe target for an ion | Cannot be un-supplied; dilute or accept | SRC:DERIVED |
| `G-LF-DEFICIT` | WARNING | M4 | Leaching fraction < 10% | Under-irrigation; salt accumulation risk | SRC:PRACTICE |
| `G-LF-EXCESS` | WARNING | M4 | Leaching fraction > 40% | Water and nutrient waste; check emitter uniformity | SRC:PRACTICE |
| `G-NH4-SHARE` | WARNING | M5 | NH4 > 15% of total N | Hydroponic proportion should stay 5-15% | SRC:WUR p.15 |
| `G-CHELATE-DISINFECT` | WARNING | M6 | UV / ozone / H2O2 disinfection | Re-dose chelates AFTER disinfection | SRC:WUR p.36 |
| `G-CHELATE-SODIUM` | WARNING | M6 | Recirculating system | Use Na-free K-based chelates and boric acid | SRC:WUR p.24, p.36 |
| `G-FE-EXCHANGE-LOSS` | WARNING | M6 | Mn/Zn/Cu supplied as sulphates | 20-50% Fe loss by chelate exchange | SRC:WUR p.36 |
| `G-DRYBACK-NA` | WARNING | M5 | Generative dry-back with Na >= 80% ceiling | Dry-back concentrates sodium; intent downgraded | SRC:PRACTICE |
| `G-B-HIGH` | WARNING | M1 | Base-water B > 30 umol/L | Above tolerable upper limit | SRC:WUR p.14 |
| `G-MN-HIGH` | WARNING | M1 | Base-water Mn >= 10 umol/L | Above advised level | SRC:WUR p.14 |
| `G-FE-SPRINKLER` | WARNING | M1 | Sprinkler Fe > 100 umol/L | Leaf damage and staining | SRC:WUR p.14 |
| `G-CO2-ESCAPE` | INFO | M1 | Any acid dose | Reaction must occur in an open mixing tank | SRC:WUR p.13 |
| `G-FE-NOT-CREDITED` | INFO | M1 | Base water contains Fe | Never counted as nutrient | SRC:WUR p.13 |
| `G-TANK-PH-CHECK` | INFO | M6 | Every tank bill | Tank A pH 3.5-5.0, tank B below 5.0 | SRC:WUR p.31 |
| `G-OO-DECLARE` | INFO | M6 | EDDHA / HBED selected | Check declared ortho-ortho content | SRC:WUR p.36 |
| `G-ZN-SOURCE` | INFO | M1 | Base water contains Zn | Likely galvanised gutters | SRC:WUR p.14 |
| `G-CU-SOURCE` | INFO | M1 | Base water contains Cu | Likely copper plumbing | SRC:WUR p.14 |
| `G-DRYBACK-SUPPRESSED` | INFO | M5 | Wash cycle active | Dry-back and leaching are contradictory | SRC:PRACTICE |
| `G-DRYBACK-NA-SOIL` | INFO | M5 | Soil substrate | Dry-back does not transfer to soil | SRC:PRACTICE |

## 6. Brief name mapping / 【说明书命名对照 (Brief Name Mapping)】

> **DIV-2 / DIV-3.** The gate names in the export brief do not exist in the
> codebase. Rather than rename the emitted identifiers — which the frontend
> consumes — the real registry is exported with this mapping.

| Brief name | Brief condition | Implemented as | Status |
|---|---|---|---|
| `G-ACID-POISON` | pH < 5.2 | `G-MELTDOWN` | **IMPLEMENTED (merged)** |
| `G-SALINITY-MELTDOWN` | EC > 4.5 mS/cm | `G-MELTDOWN` | **IMPLEMENTED (merged)** |
| `G-K-CA-ANTAGONISM` | dK > +2.0 mmol/L | `K_SUPPRESSES_CA_MG (pattern, not a gate)` | **NOT IMPLEMENTED AS SPECIFIED** |
| `G-NA-CEILING` | Na > crop ceiling | `G-NA-EXCEED (plus G-NA-APPROACH, G-NA-UNREACHABLE)` | **IMPLEMENTED (renamed, expanded)** |

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
| `K_SUPPRESSES_CA_MG` | K blocks Ca and Mg uptake / 钾抑制钙镁吸收 |
| `NA_DISPLACES_CATIONS` | Na displaces nutrient cations / 钠置换养分阳离子 |
| `CA_SUPPRESSES_MG` | Ca blocks Mg uptake / 钙抑制镁吸收 |
| `NH4_SUPPRESSES_CA_K` | Ammonium blocks Ca and K uptake / 铵抑制钙钾吸收 |
| `METALS_DISPLACE_FE` | Mn, Zn and Cu displace Fe from the chelate / 锰锌铜从螯合物上置换铁 |
| `HIGH_PH_LIMITS_P_MICRO` | High pH limits P and micronutrient uptake / 高 pH 限制磷与微量元素吸收 |
