# Module 5 — A/B Stock Tank Matrix Solver
# 【100倍 A/B 母液罐配方精算 (100× A/B Stock Tank Solver)】

> **Source / 数据来源:** Van der Lugt, G., H.T. Holwerda, K. Hora, M. Bugter, J. Hardeman & P. de Vries (2020). *Nutrient Solutions for Greenhouse Crops*, Version 4. ISBN 9789464021844. Eurofins Agro / Nouryon / SQM / Yara.
> **Generated from:** live import of `constants.py` / `engine.py` — these
> documents are produced by `tools/build_docs.py`, not maintained by hand, so
> they cannot drift from the running system.
> **Provenance tags:** `SRC:WUR` = from the manual · `SRC:DERIVED` = arithmetic
> consequence · `SRC:PRACTICE` = grower practice, no basis in the manual.


## 1. Separation rule / 【分罐规则 (Separation Rule)】 `SRC:WUR` Ch.9, p.31

> "All calcium fertilisers must be separated from phosphate and sulphate
> fertilisers. This means putting calcium fertilisers into the A tank and
> sulphate and phosphate fertilisers into the B tank."

| Tank | Contents | Members |
|---|---|---|
| **A** 【A 母液罐】 | Calcium fertilisers, chelates | can_solid, cacl2_s, fe_edta, fe_dtpa, fe_eddha, fe_hbed, mn_edta, zn_edta, cu_edta |
| **B** 【B 母液罐】 | Sulphate and phosphate fertilisers | h3po4_59, map, mkp, mgso4, k2so4, borax, h3bo3, na_moly, mnso4, znso4, cuso4 |
| Either | Load-balancing | hno3_38, hno3_60, nh4no3_liq, mgno3_s, kno3, kcl |

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
4 L/m³ with the remainder placed in tank B.

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
tank volume $V$ (L) and concentration factor $\text{CF}$:

$$u_j\ (\text{kg}) = c_i \times \text{MW}_{i,j} \times \frac{\text{CF}}{1000} \times \frac{V}{1000}$$

At the standard CF = 100 and V = 1000 L this reduces to
$u_j = c_i \times \text{MW}_{i,j} \times 0.1$.

Micronutrients, where $w_j$ is the product's mass fraction:

$$u_j\ (\text{g}) = c_i\ (\mu\text{mol/L}) \times \frac{A_i}{w_j} \times 0.1$$

Liquids: $V_j = u_j / \rho_j$.

⚠ $\text{MW}_{i,j}$ is grams of product per mole of the **driving ion**.
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
| > 6.5 | **Fe-EDDHA or Fe-HBED** | strongly recommended (p.36) |
| Calcareous soil, any pH | **Fe-EDDHA / Fe-HBED, high ortho-ortho** | mandatory |

Prophylactic replacement: 25% of total Fe in inert
substrate, 10% in NFT. If deficiency symptoms are already
visible, that fraction is **added on top of** the normal Fe rather than
replacing it.

Metal sulphates of Mn, Zn and Cu cost 20–50% of the iron through chelate
exchange (p.36); EDTA chelates avoid this. Chelates degrade under UV, ozone and
H₂O₂ — re-dose **after** disinfection, never before.
