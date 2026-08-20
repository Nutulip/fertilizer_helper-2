"""
Deterministic calculation engine — the hard layer.

Pure functions only: no I/O, no network, no LLM. Every public function is
f(inputs, reference_data) -> results. This is what makes the engine testable
against the manual's own worked examples (see tests in main.py).

Module map (matches the implementation brief):
    M1  ppm -> mmol/L conversion & HCO3 acid dosing (0.5 mmol/L buffer)
    M2  Crop Na+ threshold check & discharge alert
    M3  Leaching Fraction & delta-EC washing logic
    M4  3-level feedback correction (25% / 50% steps) + micro ladder
    M5  Stage steering adjustments (Fruit Set K:N shifts)
    M6  A/B stock tank mass splitting & Fe chelate selection
    M7  Base water nutrient auto-deduction (+ recipe pipeline)
    M8  Emergency meltdown gate (pH < 5.2 or EC > 4.5)
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from constants import (
    ANIONS, ATOMIC_WEIGHTS, CATIONS, DEFAULT_POLICY, DEFAULT_SUBSTRATE,
    EC_DIVISOR, get_crop,
    FERTILISERS, FE_CHELATE_SWITCH_PH, ION_BALANCE_TOLERANCE, ION_CHARGE,
    NA_EC_FACTOR, NA_LIMITS_MMOL_L, PROPHYLACTIC_NFT, PROPHYLACTIC_SUBSTRATE,
    reference_irrigation,
    REFERENCE_EC_OFFSET, WATER_QUALITY_LEVELS, CropRecipe, Fertiliser,
    SitePolicy, bi,
)

EPS = 1e-9
MACRO_IONS = ("NH4", "K", "Ca", "Mg", "NO3", "Cl", "S", "P")
MICRO_IONS = ("Fe", "Mn", "Zn", "B", "Cu", "Mo")


# ==========================================================================
# Gates
# ==========================================================================

@dataclass
class Gate:
    gid: str
    severity: str                 # BLOCKING | CRITICAL | WARNING | INFO
    title_en: str
    title_zh: str
    message_en: str
    message_zh: str
    triggered_by: dict[str, float]
    remedy_en: str = ""
    remedy_zh: str = ""
    provenance: str = "SRC:WUR"

    def to_dict(self) -> dict:
        return {
            "gate_id": self.gid,
            "severity": self.severity,
            "severity_text": _SEVERITY_TEXT[self.severity],
            "title": self.title_en,
            "title_text": bi(self.title_en, self.title_zh),
            "message": self.message_en,
            "message_text": bi(self.message_en, self.message_zh),
            "remedy": self.remedy_en,
            "remedy_text": bi(self.remedy_en, self.remedy_zh) if self.remedy_en else "",
            "triggered_by": self.triggered_by,
            "provenance": self.provenance,
        }


_SEVERITY_TEXT = {
    "BLOCKING": bi("Blocking", "阻断"),
    "CRITICAL": bi("Critical", "严重"),
    "WARNING": bi("Warning", "警告"),
    "INFO": bi("Information", "提示"),
}

SEVERITY_ORDER = {"BLOCKING": 0, "CRITICAL": 1, "WARNING": 2, "INFO": 3}


# ==========================================================================
# M1a — Unit conversion (Ch. 12, p. 39)
# ==========================================================================

def ppm_to_mmol(ppm: float, ion: str) -> float:
    """ppm (mg/L) / atomic weight = mmol/L. Macronutrients."""
    aw = ATOMIC_WEIGHTS.get(ion)
    if aw is None:
        raise ValueError(f"Unknown ion for conversion: {ion}")
    return ppm / aw


def mmol_to_ppm(mmol: float, ion: str) -> float:
    """mmol/L * atomic weight (mg/mmol) = ppm (mg/L)."""
    aw = ATOMIC_WEIGHTS.get(ion)
    if aw is None:
        raise ValueError(f"Unknown ion for conversion: {ion}")
    return mmol * aw


def ppb_to_umol(ppb: float, ion: str) -> float:
    """ppb (ug/L) / atomic weight = umol/L. Micronutrients."""
    return ppb / ATOMIC_WEIGHTS[ion]


def umol_to_ppb(umol: float, ion: str) -> float:
    """umol/L * atomic weight (ug/umol) = ppb (ug/L)."""
    return umol * ATOMIC_WEIGHTS[ion]


def convert_analysis_to_mmol(ppm_values: dict[str, float]) -> dict[str, float]:
    """Convert a whole ppm analysis to mmol/L, macro ions only."""
    return {ion: ppm_to_mmol(v, ion) for ion, v in ppm_values.items()}


# ==========================================================================
# Ion balance and EC — Formulas 1-4, p. 21
# ==========================================================================

def eq_cations(m: dict[str, float]) -> float:
    """Eq Cations = NH4 + K + Na + Ca*2 + Mg*2 (+ H from acid)."""
    return sum(ION_CHARGE[i] * m.get(i, 0.0) for i in CATIONS)


def eq_anions(m: dict[str, float]) -> float:
    """Eq Anions = NO3 + Cl + SO4*2 + HCO3 + H2PO4."""
    return sum(ION_CHARGE[i] * m.get(i, 0.0) for i in ANIONS)


def ec_from_ions(m: dict[str, float]) -> float:
    """EC = (Eq cations + Eq anions) / 20."""
    return (eq_cations(m) + eq_anions(m)) / EC_DIVISOR


def balance_report(m: dict[str, float]) -> dict:
    cat, an = eq_cations(m), eq_anions(m)
    base = max(cat, an, EPS)
    diff = abs(cat - an) / base
    balanced = diff <= ION_BALANCE_TOLERANCE
    return {
        "eq_cations_meq_l": round(cat, 3),
        "eq_anions_meq_l": round(an, 3),
        "difference_pct": round(diff * 100, 2),
        "balanced": balanced,
        "balanced_text": (bi("Balanced", "平衡") if balanced
                          else bi("Not balanced", "不平衡")),
        "calculated_ec_ms_cm": round(ec_from_ions(m), 3),
        "tolerance_pct": ION_BALANCE_TOLERANCE * 100,
        "provenance": "SRC:WUR Formulas 1-4, p.21",
    }


# ==========================================================================
# M1b — Water classification & HCO3 acid dosing (Ch. 1-2, pp. 11-15, 24)
# ==========================================================================

@dataclass
class AcidPlan:
    hco3_base_water: float
    hco3_buffer_target: float
    h_required: float
    h_from_nitric: float
    h_from_phosphoric: float
    shortfall: float
    hco3_residual: float
    no3_added: float
    p_added: float
    # Concentrated stock tank: product to add to ONE 1000 L A/B tank, which is
    # then injected at 1:100 into the irrigation line.
    nitric_kg: float
    nitric_l: float
    phosphoric_kg: float
    phosphoric_l: float
    # Direct injection: product to add to 1000 L of irrigation water at working
    # strength (1x). Exactly 1/concentration_factor of the stock-tank figure.
    nitric_l_direct: float
    phosphoric_l_direct: float
    direct_basis_volume_l: float
    feasible: bool


def acid_molarity_mol_per_l(fert: Fertiliser) -> float:
    """
    Moles of titratable H+ per litre of the liquid acid product.

        mol/L = (density g/L) / (grams of product per mole of H+)

    For nitric acid 38% from Table 5 (p. 26): 1240 / 167 = 7.425 mol/L.

    Deriving it the other way round from mass fraction and formula weight,
    1.23 g/mL x 1000 x 0.38 / 63.01 = 7.418 mol/L, agrees to 0.1%. The
    difference is only the density constant — real 38% HNO3 is 1.229-1.234
    g/mL at 20 C. The catalogue value is used so that this path and the
    stock-tank mass path cannot drift apart; override `density` on the
    Fertiliser record if your supplier's data sheet says otherwise.
    """
    if not fert.density:
        raise ValueError(f"{fert.fid} has no density; molarity is undefined")
    return (fert.density * 1000.0) / fert.mass_per_mol_ion


def acid_volume_direct_l(h_required_mmol_per_l: float,
                         fert: Fertiliser,
                         water_volume_l: float = 1000.0) -> float:
    """
    Litres of liquid acid to dose DIRECTLY into `water_volume_l` of irrigation
    water at working strength.

        H+ needed (mol) = h_required (mmol/L) / 1000 x water volume (L)
        volume (L)      = H+ needed / molarity of the product

    This is NOT the stock-tank figure. A 100x A/B tank needs 100 times this
    volume, because one tank of stock treats 100 tank-volumes of water. Use
    this when acid goes straight into a mixing tank or through a dosing pump
    on the irrigation line; use `AcidPlan.nitric_l` when filling A/B tanks.
    """
    if h_required_mmol_per_l <= 0 or water_volume_l <= 0:
        return 0.0
    total_h_mol = (h_required_mmol_per_l / 1000.0) * water_volume_l
    return total_h_mol / acid_molarity_mol_per_l(fert)


def classify_water(ec: float, na: float, cl: float) -> int:
    """Table 1, p. 11. Worst case of the EC-derived and ion-derived level."""
    ion = max(na, cl)
    by_ec = 1 if ec < 0.5 else 2 if ec <= 1.0 else 3 if ec <= 1.5 else 4
    by_ion = 1 if ion < 1.5 else 2 if ion <= 2.5 else 3 if ion <= 4.0 else 4
    return max(by_ec, by_ion)


def water_quality_gates(level: int, recirculating: bool,
                        crop: CropRecipe | None) -> list[Gate]:
    gates: list[Gate] = []
    if level >= 4:
        gates.append(Gate(
            "G-WATER-UNCLASSIFIED", "CRITICAL",
            "Water beyond quality level 3", "原水水质超出三级标准",
            "Na or Cl exceeds 4.0 mmol/L, or EC exceeds 1.5 mS/cm. This water "
            "falls outside Table 1 and is not usable for hydroponics as supplied.",
            "Na 或 Cl 超过 4.0 mmol/L，或 EC 超过 1.5 mS/cm。该水质超出表 1 范围，"
            "不能直接用于无土栽培。",
            {"level": level},
            "Install reverse osmosis, or switch to rainwater.",
            "安装反渗透装置，或改用雨水。"))
    if level >= 2 and recirculating:
        gates.append(Gate(
            "G-WATER-RECIRC", "CRITICAL",
            "Water not suitable for recirculation", "该水质不适合循环回用",
            "Level 2 water is not suitable when recirculation is necessary. "
            "Irrigation water above 1.5 mmol/L Na is unsuitable for recirculating "
            "systems, since recirculation raises Na over time.",
            "二级水质在需要循环回用时不适用。Na 高于 1.5 mmol/L 的灌溉水不适合循环系统，"
            "因为循环会随时间推高钠浓度。",
            {"level": level},
            "Use rainwater or RO for the recirculating loop, or plan routine discharge.",
            "循环回路改用雨水或反渗透水，或制定常规排液计划。"))
    if level >= 3 and crop is not None and crop.na_max_root_zone <= 4.0:
        gates.append(Gate(
            "G-WATER-SALT-SENSITIVE", "CRITICAL",
            "Water not suitable for salt-sensitive crop", "该水质不适合盐敏感作物",
            f"Level 3 water must not be used for salt-sensitive crops. "
            f"{crop.name_en} has a root-zone Na ceiling of "
            f"{crop.na_max_root_zone} mmol/L.",
            f"三级水质不得用于盐敏感作物。{crop.name_zh} 的根际钠上限为 "
            f"{crop.na_max_root_zone} mmol/L。",
            {"level": level, "na_max": crop.na_max_root_zone},
            "Use a lower-salinity water source for this crop.",
            "该作物请改用低盐分水源。"))
    return gates


def iron_screening_gates(fe_umol: float, irrigation_type: str,
                         organic_matter: bool = False) -> list[Gate]:
    """
    Ch. 1, pp. 13-14. Base-water Fe is NEVER credited toward the Fe dose:
    it oxidises and precipitates at the emitter before reaching the plant.
    """
    gates: list[Gate] = []
    if irrigation_type == "DRIP":
        limit = 20.0 if organic_matter else 0.0
        if fe_umol > limit + EPS:
            gates.append(Gate(
                "G-FE-DRIP", "CRITICAL",
                "Iron in base water blocks drip emitters", "原水铁将堵塞滴头",
                f"Measured Fe {fe_umol:g} umol/L. The only acceptable level for "
                f"drip irrigation is 0 umol/L "
                f"({'10-20 umol/L where organic matter is present' if organic_matter else 'no exception applies'}).",
                f"实测铁 {fe_umol:g} umol/L。滴灌系统可接受的铁含量为 0 umol/L"
                f"（{'含有机质时可放宽至 10-20 umol/L' if organic_matter else '本例不适用例外条款'}）。",
                {"fe_umol_l": fe_umol, "limit_umol_l": limit},
                "Aerate the water through a gravel bed or filter to precipitate "
                "the iron before it enters the fertigation unit.",
                "进入施肥机前，先经砾石床或过滤器曝气，使铁预先沉淀。"))
    elif irrigation_type == "SPRINKLER" and fe_umol > 100.0:
        gates.append(Gate(
            "G-FE-SPRINKLER", "WARNING",
            "Iron may cause leaf damage and staining", "铁可能造成叶片伤害与锈斑",
            f"Measured Fe {fe_umol:g} umol/L. Soft water should not exceed "
            f"100 umol/L; where decorative quality matters, keep below 25-50 umol/L.",
            f"实测铁 {fe_umol:g} umol/L。软水不应超过 100 umol/L；"
            f"对观赏品质有要求时应低于 25-50 umol/L。",
            {"fe_umol_l": fe_umol}))
    if fe_umol > 0:
        gates.append(Gate(
            "G-FE-NOT-CREDITED", "INFO",
            "Base-water iron is not counted as nutrient", "原水中的铁不计入养分供给",
            "Iron in irrigation water precipitates on contact with air at the "
            "emitter and never reaches the roots. Chelated iron is dosed "
            "independently of the iron already present in the water.",
            "灌溉水中的铁在滴头处接触空气即沉淀，无法到达根系。螯合铁的投加量"
            "独立计算，与原水含铁量无关。",
            {"fe_umol_l": fe_umol}))
    return gates


def micronutrient_screening_gates(water_micro: dict[str, float]) -> list[Gate]:
    gates: list[Gate] = []
    b = water_micro.get("B", 0.0)
    mn = water_micro.get("Mn", 0.0)
    zn = water_micro.get("Zn", 0.0)
    cu = water_micro.get("Cu", 0.0)
    if b > 30.0:
        gates.append(Gate(
            "G-B-HIGH", "WARNING", "Boron above tolerable upper limit", "硼超过可耐受上限",
            f"Boron {b:g} umol/L exceeds the tolerable upper limit of about "
            f"30 umol/L; tolerance varies by species.",
            f"硼 {b:g} umol/L 超过约 30 umol/L 的可耐受上限；不同作物耐受度不同。",
            {"b_umol_l": b}))
    if mn >= 10.0:
        gates.append(Gate(
            "G-MN-HIGH", "WARNING", "Manganese above advised level", "锰超过建议水平",
            f"Manganese {mn:g} umol/L. Irrigation water should stay below 10 umol/L.",
            f"锰 {mn:g} umol/L。灌溉水应低于 10 umol/L。", {"mn_umol_l": mn}))
    if zn > 0:
        gates.append(Gate(
            "G-ZN-SOURCE", "INFO", "Check zinc source", "请核查锌来源",
            "Elevated zinc commonly comes from galvanised steel gutters "
            "collecting roof rainwater. Check after rainy periods.",
            "锌偏高常来自收集屋面雨水的镀锌钢排水槽。雨季后应复检。",
            {"zn_umol_l": zn}))
    if cu > 0:
        gates.append(Gate(
            "G-CU-SOURCE", "INFO", "Check copper source", "请核查铜来源",
            "Copper in irrigation water usually comes from copper-containing "
            "taps, pipes and pumps in the irrigation equipment.",
            "灌溉水中的铜通常来自灌溉设备中含铜的水龙头、管道与水泵。",
            {"cu_umol_l": cu}))
    return gates


def plan_acid_dosing(hco3_base_water: float,
                     no3_headroom: float,
                     p_headroom: float,
                     policy: SitePolicy = DEFAULT_POLICY) -> AcidPlan:
    """
    Neutralise excess HCO3 while retaining the pH buffer (p. 24).

        H_required = max(0, HCO3_base_water - HCO3_buffer)

    Reaction: Ca2+ + 2HCO3- + 2HNO3 <-> Ca2+ + 2CO2 + 2H2O + 2NO3-

    Each mole of H+ drags in a mole of acid anion, which counts against the
    recipe. Acid is therefore capped by the anion headroom (p. 13).
    """
    buffer_target = policy.hco3_buffer_mmol_l
    h_required = max(0.0, hco3_base_water - buffer_target)

    no3_headroom = max(0.0, no3_headroom)
    p_headroom = max(0.0, p_headroom)

    if policy.acid_policy == "PHOSPHORIC_FIRST":
        h_phos = min(h_required, p_headroom)
        h_nitric = min(h_required - h_phos, no3_headroom)
    elif policy.acid_policy == "PROPORTIONAL":
        total = no3_headroom + p_headroom
        share = (no3_headroom / total) if total > EPS else 0.0
        h_nitric = min(h_required * share, no3_headroom)
        h_phos = min(h_required - h_nitric, p_headroom)
    else:  # NITRIC_FIRST (default)
        h_nitric = min(h_required, no3_headroom)
        h_phos = min(h_required - h_nitric, p_headroom)

    delivered = h_nitric + h_phos
    shortfall = max(0.0, h_required - delivered)
    hco3_residual = hco3_base_water - delivered

    hno3 = FERTILISERS["hno3_38"]
    h3po4 = FERTILISERS["h3po4_59"]
    nitric_kg = stock_mass_kg(h_nitric, hno3.mass_per_mol_ion, policy)
    phos_kg = stock_mass_kg(h_phos, h3po4.mass_per_mol_ion, policy)

    # Working-strength dose, for growers injecting acid straight into a mixing
    # tank rather than filling a concentrated A/B tank.
    direct_basis = policy.tank_volume_l
    return AcidPlan(
        hco3_base_water=hco3_base_water,
        hco3_buffer_target=buffer_target,
        h_required=h_required,
        h_from_nitric=h_nitric,
        h_from_phosphoric=h_phos,
        shortfall=shortfall,
        hco3_residual=hco3_residual,
        no3_added=h_nitric,
        p_added=h_phos,
        nitric_kg=nitric_kg,
        nitric_l=nitric_kg / hno3.density if hno3.density else 0.0,
        phosphoric_kg=phos_kg,
        phosphoric_l=phos_kg / h3po4.density if h3po4.density else 0.0,
        nitric_l_direct=acid_volume_direct_l(h_nitric, hno3, direct_basis),
        phosphoric_l_direct=acid_volume_direct_l(h_phos, h3po4, direct_basis),
        direct_basis_volume_l=direct_basis,
        feasible=shortfall <= EPS,
    )


def acid_gates(plan: AcidPlan) -> list[Gate]:
    gates: list[Gate] = []
    if not plan.feasible:
        gates.append(Gate(
            "G-ACID-INFEASIBLE", "CRITICAL",
            "Acid demand exceeds anion headroom", "加酸需求超出阴离子余量",
            f"Neutralising to the {plan.hco3_buffer_target:g} mmol/L buffer needs "
            f"{plan.h_required:.2f} mmol/L H+, but only "
            f"{plan.h_from_nitric + plan.h_from_phosphoric:.2f} mmol/L can be added "
            f"without pushing NO3 or P above their recipe targets. "
            f"{plan.hco3_residual:.2f} mmol/L HCO3 will remain.",
            f"中和至 {plan.hco3_buffer_target:g} mmol/L 缓冲量需要 "
            f"{plan.h_required:.2f} mmol/L H+，但在不使 NO3 或 P 超过配方目标的前提下，"
            f"仅可加入 {plan.h_from_nitric + plan.h_from_phosphoric:.2f} mmol/L。"
            f"将残留 {plan.hco3_residual:.2f} mmol/L HCO3。",
            {"h_required": round(plan.h_required, 3),
             "h_delivered": round(plan.h_from_nitric + plan.h_from_phosphoric, 3),
             "hco3_residual": round(plan.hco3_residual, 3)},
            "Dilute or replace the base water; or shift pH control to ammonium "
            "and switch to a high-pH-stable Fe chelate (EDDHA / HBED).",
            "稀释或更换原水；或改用铵态氮调控 pH，并改选高 pH 稳定的铁螯合物"
            "（EDDHA / HBED）。"))
    if plan.h_required > EPS:
        gates.append(Gate(
            "G-CO2-ESCAPE", "INFO",
            "Acid reaction requires an open mixing tank", "加酸反应须在开放式混合罐中进行",
            "Treating bicarbonate with acid releases CO2. The CO2 must be allowed "
            "to escape; if it cannot, the pH will not drop and will fluctuate. "
            "The reaction must take place in an open system.",
            "酸与碳酸氢盐反应会释放 CO2。CO2 必须能够逸出；否则 pH 不会下降且会波动。"
            "该反应必须在开放系统中进行。",
            {}))
    return gates


# ==========================================================================
# M2 — Sodium accumulation & discharge gate (Ch. 1, pp. 11-12, 24)
# ==========================================================================

@dataclass
class SodiumResult:
    na_current: float
    na_limit: float
    na_target: float
    na_base_water: float
    headroom: float
    ratio: float
    status: str                       # SAFE | APPROACHING | EXCEEDED | UNREACHABLE
    discharge_volume_l_m2: float
    system_volume_l_m2: float
    limit_source: str
    nutrient_loss: dict[str, float]


def na_limit_for(crop_id: str,
                 substrate_type: str = DEFAULT_SUBSTRATE,
                 policy: SitePolicy = DEFAULT_POLICY) -> tuple[float, str]:
    """
    The sodium ceiling is substrate-dependent, and dramatically so. Tomato is
    8 mmol/L on inert substrate but 2 mmol/L on organic material, because the
    organic figure is read from a 1:1.5 water extract rather than from the
    root-zone solution itself. Applying the inert ceiling to an organic sample
    would let sodium run to four times the published limit before any gate
    fired, so the crop x substrate matrix is the authority here and Table 2
    (p. 12, stated on the solution basis) is used only as a fallback.
    """
    crop = get_crop(crop_id, substrate_type)
    if crop is not None:
        canon = crop.na_max_root_zone
        source = f"SRC:WUR crop page p.{crop.source_page} ({substrate_type})"
    else:
        canon = NA_LIMITS_MMOL_L.get(crop_id)
        source = "SRC:WUR Table 2, p.12"
    if canon is None:
        raise ValueError(
            f"No sodium limit known for crop '{crop_id}' on '{substrate_type}'")
    override = policy.na_overrides.get(crop_id)
    if override is None:
        return canon, source
    return override, "SRC:PRACTICE site override"


def evaluate_sodium(crop_id: str,
                    na_root_zone: float,
                    na_base_water: float = 0.0,
                    system_volume_l_m2: float = 0.0,
                    drain_composition: dict[str, float] | None = None,
                    policy: SitePolicy = DEFAULT_POLICY,
                    substrate_type: str = DEFAULT_SUBSTRATE) -> SodiumResult:
    """
    Mass balance for the forced-discharge volume (SRC:DERIVED — the manual
    states the requirement, not the formula):

        Na_after = (Na_cur * (V_sys - V_d) + Na_base * V_d) / V_sys
        =>  V_d  = V_sys * (Na_cur - Na_target) / (Na_cur - Na_base)
    """
    limit, source = na_limit_for(crop_id, substrate_type, policy)
    target = limit * policy.na_safety_factor
    headroom = limit - na_root_zone
    ratio = na_root_zone / limit if limit > EPS else float("inf")

    discharge = 0.0
    if na_root_zone > limit + EPS:
        if na_base_water >= target - EPS:
            status = "UNREACHABLE"
        else:
            status = "EXCEEDED"
            if system_volume_l_m2 > EPS:
                discharge = (system_volume_l_m2
                             * (na_root_zone - target)
                             / (na_root_zone - na_base_water))
    elif ratio >= policy.na_approach_ratio:
        status = "APPROACHING"
    else:
        status = "SAFE"

    loss: dict[str, float] = {}
    if discharge > EPS and drain_composition:
        for ion, mmol in drain_composition.items():
            aw = ATOMIC_WEIGHTS.get(ion)
            if aw:
                # mmol/L * L/m2 * mg/mmol = mg/m2 -> g/m2
                loss[ion] = round(mmol * discharge * aw / 1000.0, 3)

    return SodiumResult(
        na_current=na_root_zone, na_limit=limit, na_target=target,
        na_base_water=na_base_water, headroom=headroom, ratio=ratio,
        status=status, discharge_volume_l_m2=discharge,
        system_volume_l_m2=system_volume_l_m2,
        limit_source=source, nutrient_loss=loss,
    )


def sodium_gates(r: SodiumResult, crop_id: str) -> list[Gate]:
    gates: list[Gate] = []
    if r.status == "EXCEEDED":
        gates.append(Gate(
            "G-NA-EXCEED", "CRITICAL",
            "Sodium above crop ceiling - forced discharge required",
            "钠超过作物上限 - 需要强行排液",
            f"Root-zone Na is {r.na_current:g} mmol/L against a ceiling of "
            f"{r.na_limit:g} mmol/L for {crop_id}. Discharge a fraction of the "
            f"recirculated solution to prevent yield reduction or a decline in "
            f"produce quality.",
            f"根际钠为 {r.na_current:g} mmol/L，而 {crop_id} 的上限为 "
            f"{r.na_limit:g} mmol/L。需排放部分循环液，以避免减产或品质下降。",
            {"na_current": r.na_current, "na_limit": r.na_limit,
             "discharge_l_m2": round(r.discharge_volume_l_m2, 2)},
            f"Discharge {r.discharge_volume_l_m2:.1f} L/m2 and replace with fresh "
            f"base water to reach {r.na_target:g} mmol/L.",
            f"排放 {r.discharge_volume_l_m2:.1f} L/m2 并补充新鲜原水，"
            f"使钠降至 {r.na_target:g} mmol/L。"))
    elif r.status == "UNREACHABLE":
        gates.append(Gate(
            "G-NA-UNREACHABLE", "CRITICAL",
            "Sodium target unreachable with this water", "以该水源无法达成钠目标",
            f"Base water Na is {r.na_base_water:g} mmol/L, at or above the target "
            f"{r.na_target:g} mmol/L. Flushing cannot reduce Na below the "
            f"concentration of the water used to flush.",
            f"原水钠为 {r.na_base_water:g} mmol/L，已达到或超过目标值 "
            f"{r.na_target:g} mmol/L。冲洗无法使钠低于所用冲洗水本身的浓度。",
            {"na_base_water": r.na_base_water, "na_target": r.na_target},
            "An alternative water source (rainwater / RO) or a sodium-removal "
            "unit is required.",
            "需要替代水源（雨水 / 反渗透）或除钠装置。"))
    elif r.status == "APPROACHING":
        gates.append(Gate(
            "G-NA-APPROACH", "WARNING",
            "Sodium approaching crop ceiling", "钠接近作物上限",
            f"Root-zone Na is {r.na_current:g} mmol/L, "
            f"{r.ratio * 100:.0f}% of the {r.na_limit:g} mmol/L ceiling.",
            f"根际钠为 {r.na_current:g} mmol/L，已达上限 "
            f"{r.na_limit:g} mmol/L 的 {r.ratio * 100:.0f}%。",
            {"na_current": r.na_current, "na_limit": r.na_limit},
            "Increase monitoring frequency and plan a discharge window.",
            "提高监测频次，并规划排液时段。"))
    return gates


# ==========================================================================
# M3 — Leaching fraction & delta-EC washing (SRC:PRACTICE)
# ==========================================================================

@dataclass
class LeachingResult:
    lf_pct: float
    delta_ec: float
    band: str
    wash_required: bool
    target_lf_min: float
    target_lf_max: float
    target_lf_pct: float
    extra_irrigation_l_m2: float
    target_irrigation_l_m2: float
    used_irrigation_l_m2: float
    drain_l_m2: float
    uptake_l_m2: float
    is_estimated_volume: bool


LF_BANDS = [
    (0.0, 10.0, "DEFICIT", "Deficit", "亏缺"),
    (10.0, 20.0, "NORMAL_GENERATIVE", "Normal generative", "生殖生长正常区"),
    (20.0, 30.0, "NORMAL_VEGETATIVE", "Normal vegetative", "营养生长正常区"),
    (30.0, 40.0, "WASH", "Wash / flush", "冲洗区"),
    (40.0, 1e9, "EXCESS", "Excess", "过量"),
]


def extra_irrigation_for_target_lf(v_irrigation_l_m2: float,
                                   lf_current_frac: float,
                                   lf_target_frac: float) -> float:
    """
    Additional daily irrigation needed to lift the leaching fraction from
    `lf_current_frac` to `lf_target_frac`, in L/m2.

    Plant uptake is the conserved quantity over the short term, not drain:

        V_uptake     = V_irrigation x (1 - LF_current)
        V_target_irr = V_uptake / (1 - LF_target)
        dV_extra     = V_irrigation x ((1 - LF_current)/(1 - LF_target) - 1)

    Pinning DRAIN instead of uptake — the previous behaviour — inverts the
    agronomy. With V_irr 4.0 and drain 1.04 (LF 26%), holding drain fixed says
    3.47 L/m2 reaches LF 30%, i.e. that salts are flushed by irrigating LESS.
    Uptake is what the crop actually fixes; drain is the residual.

    Returns 0.0 when the current LF already meets or exceeds the target.
    """
    if v_irrigation_l_m2 <= EPS:
        return 0.0
    if lf_current_frac >= lf_target_frac:
        return 0.0
    if lf_target_frac >= 1.0 - EPS:
        # LF = 100% means zero uptake; the ratio is undefined.
        raise ValueError("Target leaching fraction must be below 100%")
    ratio = (1.0 - lf_current_frac) / (1.0 - lf_target_frac)
    return max(0.0, v_irrigation_l_m2 * (ratio - 1.0))


def evaluate_leaching(v_irrigation_l_m2: float | None,
                      v_drain_l_m2: float,
                      ec_drip: float,
                      ec_drain: float,
                      policy: SitePolicy = DEFAULT_POLICY,
                      crop_id: str | None = None,
                      stages: list[str] | tuple[str, ...] | None = None
                      ) -> LeachingResult:
    """
    LF = (V_drain / V_irrigation) * 100%.

    When the irrigation volume is missing or zero, a crop- and stage-based
    reference volume stands in so the wash increment can still be estimated;
    the result is flagged `is_estimated_volume`.
    """
    is_estimated = v_irrigation_l_m2 is None or v_irrigation_l_m2 <= EPS
    if is_estimated:
        v_irrigation_l_m2 = reference_irrigation(
            crop_id or "", stages, policy.reference_irrigation_overrides)
        if v_irrigation_l_m2 <= EPS:
            raise ValueError("No irrigation volume supplied and no reference "
                             "volume available")

    v_drain_l_m2 = max(0.0, v_drain_l_m2)
    if v_drain_l_m2 > v_irrigation_l_m2:
        raise ValueError("Drain volume cannot exceed irrigation volume")

    lf = 100.0 * v_drain_l_m2 / v_irrigation_l_m2
    delta_ec = ec_drain - ec_drip
    uptake = v_irrigation_l_m2 - v_drain_l_m2

    band = next(code for lo, hi, code, _, _ in LF_BANDS if lo <= lf < hi)
    # Tolerance so that an exact-threshold reading such as 4.6 - 2.6 (which is
    # 1.9999999999999996 in binary floating point) still trips the trigger.
    wash = delta_ec >= policy.wash_trigger_delta_ec - 1e-9

    target_lf_pct = policy.wash_lf_target
    extra = 0.0
    target_irrigation = v_irrigation_l_m2
    if wash:
        extra = extra_irrigation_for_target_lf(
            v_irrigation_l_m2, lf / 100.0, target_lf_pct / 100.0)
        target_irrigation = v_irrigation_l_m2 + extra

    return LeachingResult(
        lf_pct=lf, delta_ec=delta_ec, band=band, wash_required=wash,
        target_lf_min=policy.wash_lf_min, target_lf_max=policy.wash_lf_max,
        target_lf_pct=target_lf_pct,
        extra_irrigation_l_m2=extra,
        target_irrigation_l_m2=target_irrigation,
        used_irrigation_l_m2=v_irrigation_l_m2,
        drain_l_m2=v_drain_l_m2,
        uptake_l_m2=uptake,
        is_estimated_volume=is_estimated,
    )


def leaching_gates(r: LeachingResult, policy: SitePolicy = DEFAULT_POLICY) -> list[Gate]:
    gates: list[Gate] = []
    if r.wash_required:
        gates.append(Gate(
            "G-WASH-TRIGGER", "CRITICAL",
            "Dynamic wash cycle triggered", "触发动态冲洗循环",
            f"Drain-dripper EC gap is {r.delta_ec:.2f} mS/cm, at or above the "
            f"{policy.wash_trigger_delta_ec:g} mS/cm trigger. Salts are "
            f"accumulating in the root zone.",
            f"排液与滴灌电导差为 {r.delta_ec:.2f} mS/cm，达到或超过 "
            f"{policy.wash_trigger_delta_ec:g} mS/cm 触发阈值。根际正在积盐。",
            {"delta_ec": round(r.delta_ec, 2), "lf_pct": round(r.lf_pct, 1),
             "extra_irrigation_l_m2": round(r.extra_irrigation_l_m2, 2),
             "target_irrigation_l_m2": round(r.target_irrigation_l_m2, 2)},
            f"Raise the leaching fraction to {r.target_lf_min:g}-{r.target_lf_max:g}% "
            f"(target {r.target_lf_pct:g}%): add "
            f"{r.extra_irrigation_l_m2:.2f} L/m2/day, taking irrigation from "
            f"{r.used_irrigation_l_m2:.2f} to {r.target_irrigation_l_m2:.2f} "
            f"L/m2/day, until the EC gap closes."
            + (" Irrigation volume was not supplied, so a crop-stage reference "
               "volume was used — verify against your own metering."
               if r.is_estimated_volume else ""),
            f"将排液比提高至 {r.target_lf_min:g}-{r.target_lf_max:g}%"
            f"（目标 {r.target_lf_pct:g}%）：每日增加 "
            f"{r.extra_irrigation_l_m2:.2f} L/m2，灌溉量由 "
            f"{r.used_irrigation_l_m2:.2f} 提高至 {r.target_irrigation_l_m2:.2f} "
            f"L/m2/天，直至电导差回落。"
            + ("（未提供灌溉量，已采用作物阶段参考值估算，请与实际计量核对。）"
               if r.is_estimated_volume else ""),
            "SRC:PRACTICE"))
    if r.band == "DEFICIT":
        gates.append(Gate(
            "G-LF-DEFICIT", "WARNING",
            "Leaching fraction below operating band", "排液比低于运行区间",
            f"LF is {r.lf_pct:.1f}%, below 10%. Under-irrigation risks salt "
            f"accumulation and uneven root-zone moisture.",
            f"排液比为 {r.lf_pct:.1f}%，低于 10%。灌溉不足会导致积盐与根际水分不均。",
            {"lf_pct": round(r.lf_pct, 1)}, "", "", "SRC:PRACTICE"))
    elif r.band == "EXCESS":
        gates.append(Gate(
            "G-LF-EXCESS", "WARNING",
            "Leaching fraction above operating band", "排液比高于运行区间",
            f"LF is {r.lf_pct:.1f}%, above 40%. Check emitter uniformity; "
            f"nutrients and water are being wasted.",
            f"排液比为 {r.lf_pct:.1f}%，高于 40%。请检查滴头均匀性；养分与水正在浪费。",
            {"lf_pct": round(r.lf_pct, 1)}, "", "", "SRC:PRACTICE"))
    return gates


# ==========================================================================
# M4 — 3-level feedback correction (Ch. 5, p. 22)
# ==========================================================================

@dataclass
class Finding:
    ion: str
    analysed: float
    at_reference_ec: float
    target: float
    deviation_pct: float
    level: int
    band: str                         # LOW | NORMAL | HIGH
    adjustment_pct: float
    adjustment_range: tuple[float, float]
    is_micro: bool


def to_reference_ec(analysis_mmol: dict[str, float],
                    ec_analysed: float,
                    ec_target_values: float,
                    crop: CropRecipe) -> tuple[dict[str, float], dict]:
    """
    Reference-EC normalisation, pp. 21-22.

        EC_reference = EC_target_values - 0.30
        EC_nutrients = EC_analysed - 0.10 * Na_analysed
        Nutrient_ref = Nutrient_analysed * EC_reference / EC_nutrients

    Na and HCO3 are never converted (they never appear in target values).
    Cl is converted only when the crop's target table lists a Cl target.
    """
    ec_ref = ec_target_values - REFERENCE_EC_OFFSET
    na = analysis_mmol.get("Na", 0.0)
    ec_nut = ec_analysed - NA_EC_FACTOR * na
    if ec_nut <= EPS:
        raise ValueError("G-EC-NONPOSITIVE: sodium accounts for the entire EC")
    factor = ec_ref / ec_nut

    never = {"Na", "HCO3"}
    has_cl_target = crop.cl_max_root_zone is not None and "Cl" in crop.root_zone_targets

    out: dict[str, float] = {}
    for ion, val in analysis_mmol.items():
        if ion in never:
            out[ion] = val
        elif ion == "Cl" and not has_cl_target:
            out[ion] = val
        else:
            out[ion] = val * factor

    meta = {
        "ec_reference_ms_cm": round(ec_ref, 3),
        "ec_nutrients_ms_cm": round(ec_nut, 3),
        "conversion_factor": round(factor, 4),
        "provenance": "SRC:WUR Ch.5, pp.21-22",
    }
    return out, meta


def correction_factor(deviation: float,
                      policy: SitePolicy = DEFAULT_POLICY) -> tuple[float, int, tuple[float, float]]:
    """
    Corrections are made at 25% deviation (level 1: 10-15%) and at 50%
    deviation (level 2: a further 15-25%). Direction is inverse: root zone
    above target => reduce supply.
    """
    a = abs(deviation)
    sign = 1.0 if deviation > 0 else -1.0
    if a < 0.25:
        return 0.0, 0, (0.0, 0.0)
    if a < 0.50:
        return -sign * policy.band1_default, 1, (0.10, 0.15)
    return (-sign * (policy.band1_default + policy.band2_default), 2,
            (0.25, 0.40))


MICRO_LADDER = [
    (-0.50, 0.50),    # <= -50% deviation -> +50% supply
    (-0.25, 0.25),    # -50% .. -25%      -> +25%
    (0.25, 0.0),      # -25% .. +25%      ->   0%
    (0.50, -0.25),    # +25% .. +50%      -> -25%
]


def micro_step(deviation: float) -> float:
    """Micronutrient stepping ladder: +50%, +25%, 0%, -25%, -50%."""
    if deviation <= -0.50:
        return 0.50
    if deviation < -0.25:
        return 0.25
    if deviation < 0.25:
        return 0.0
    if deviation < 0.50:
        return -0.25
    return -0.50


def evaluate_corrections(root_zone_mmol: dict[str, float],
                         root_zone_umol: dict[str, float],
                         ec_analysed: float,
                         crop: CropRecipe,
                         policy: SitePolicy = DEFAULT_POLICY) -> tuple[list[Finding], dict]:
    ref, meta = to_reference_ec(root_zone_mmol, ec_analysed,
                                crop.ec_root_zone, crop)
    findings: list[Finding] = []

    for ion in MACRO_IONS:
        target = crop.root_zone_targets.get(ion)
        if target is None or target <= EPS:
            continue
        value = ref.get(ion)
        if value is None:
            continue
        dev = (value - target) / target
        adj, level, rng = correction_factor(dev, policy)
        findings.append(Finding(
            ion=ion, analysed=root_zone_mmol.get(ion, 0.0),
            at_reference_ec=value, target=target,
            deviation_pct=dev * 100.0, level=level,
            band="HIGH" if dev >= 0.25 else "LOW" if dev <= -0.25 else "NORMAL",
            adjustment_pct=adj * 100.0, adjustment_range=rng, is_micro=False))

    for ion in MICRO_IONS:
        target = crop.root_zone_targets.get(ion)
        if target is None or target <= EPS:
            continue
        value = root_zone_umol.get(ion)
        if value is None:
            continue
        dev = (value - target) / target
        step = micro_step(dev)
        findings.append(Finding(
            ion=ion, analysed=value, at_reference_ec=value, target=target,
            deviation_pct=dev * 100.0,
            level=2 if abs(dev) >= 0.50 else 1 if abs(dev) >= 0.25 else 0,
            band="HIGH" if dev >= 0.25 else "LOW" if dev <= -0.25 else "NORMAL",
            adjustment_pct=step * 100.0,
            adjustment_range=(abs(step), abs(step)), is_micro=True))

    return findings, meta


def apply_corrections(fertigation: dict[str, float],
                      micro: dict[str, float],
                      findings: list[Finding]) -> tuple[dict[str, float], dict[str, float]]:
    macro_out = dict(fertigation)
    micro_out = dict(micro)
    for f in findings:
        if f.adjustment_pct == 0.0:
            continue
        factor = 1.0 + f.adjustment_pct / 100.0
        if f.is_micro:
            if f.ion in micro_out:
                micro_out[f.ion] = micro_out[f.ion] * factor
        elif f.ion in macro_out:
            macro_out[f.ion] = macro_out[f.ion] * factor
    return macro_out, micro_out


# ==========================================================================
# M5 — Crop steering / stage adjustments (Section B)
# ==========================================================================

DRY_BACK_TARGETS = {
    "STRONGLY_VEGETATIVE": (6.0, 8.0, "Strongly vegetative", "强营养生长"),
    "BALANCED": (8.0, 12.0, "Balanced", "平衡"),
    "GENERATIVE": (12.0, 15.0, "Generative", "生殖生长"),
    "STRONGLY_GENERATIVE": (15.0, 20.0, "Strongly generative", "强生殖生长"),
}


@dataclass
class SteeringResult:
    stages: list[str]
    deltas: dict[str, float]
    macro_before: dict[str, float]
    macro_after: dict[str, float]
    micro_before: dict[str, float]
    micro_after: dict[str, float]
    k_ca_ratio: float
    k_n_ratio: float
    dry_back_intent: str
    dry_back_min: float
    dry_back_max: float
    notes: list[tuple[str, str]]


def apply_stage_adjustments(crop: CropRecipe,
                            stages: list[str],
                            dry_back_intent: str = "BALANCED") -> SteeringResult:
    """
    Fruit Set K:N shift for cucumber and sweet pepper is +1 mmol/L K and
    +1 mmol/L N-NO3 — exactly 1.0 mmol/L of KNO3. Tomato's Fruit Set column
    is different (+1.5 K, -0.5 Ca, -0.25 Mg): adjustments are data-driven per
    crop, never hardcoded.
    """
    macro = dict(crop.fertigation)
    micro = dict(crop.micro_fertigation)
    macro_before, micro_before = dict(macro), dict(micro)

    combined: dict[str, float] = {}
    notes: list[tuple[str, str]] = []

    for stage in stages:
        adj = next((a for a in crop.adjustments if a.stage == stage), None)
        if adj is None:
            continue
        for ion, delta in adj.deltas.items():
            combined[ion] = combined.get(ion, 0.0) + delta
        if adj.note_en:
            notes.append((adj.note_en, adj.note_zh))

    for ion, delta in combined.items():
        if ion in MICRO_IONS:
            micro[ion] = max(0.0, micro.get(ion, 0.0) + delta)
        else:
            macro[ion] = max(0.0, macro.get(ion, 0.0) + delta)

    ca = macro.get("Ca", 0.0)
    total_n = macro.get("NO3", 0.0) + macro.get("NH4", 0.0)
    k_ca = macro.get("K", 0.0) / ca if ca > EPS else 0.0
    k_n = macro.get("K", 0.0) / total_n if total_n > EPS else 0.0

    lo, hi, _, _ = DRY_BACK_TARGETS.get(dry_back_intent,
                                        DRY_BACK_TARGETS["BALANCED"])

    return SteeringResult(
        stages=stages, deltas=combined,
        macro_before=macro_before, macro_after=macro,
        micro_before=micro_before, micro_after=micro,
        k_ca_ratio=k_ca, k_n_ratio=k_n,
        dry_back_intent=dry_back_intent, dry_back_min=lo, dry_back_max=hi,
        notes=notes,
    )


def ammonium_gates(recipe: dict[str, float]) -> list[Gate]:
    """
    Ch. 2, p. 15. Must be evaluated against the recipe that will actually be
    dosed — the M4 feedback correction can push NH4 past the ceiling after
    stage adjustment, so checking the stage-adjusted vector alone misses it.
    """
    gates: list[Gate] = []
    nh4 = recipe.get("NH4", 0.0)
    total_n = recipe.get("NO3", 0.0) + nh4
    if nh4 > 1.5 + EPS:
        gates.append(Gate(
            "G-NH4-CEILING", "CRITICAL",
            "Ammonium above the hydroponic ceiling", "铵态氮超过无土栽培上限",
            f"NH4 is {nh4:.2f} mmol/L. A maximum of 1.0-1.5 mmol/L "
            f"(14-21 ppm N) is acceptable; above this the pH will drop too much.",
            f"铵态氮为 {nh4:.2f} mmol/L。可接受上限为 1.0-1.5 mmol/L"
            f"（14-21 ppm N）；超过后 pH 会下降过多。",
            {"nh4_mmol_l": round(nh4, 2)},
            "Reduce ammonium input.", "降低铵态氮投入。"))
    if total_n > EPS:
        share = nh4 / total_n
        if share > 0.15 + EPS:
            gates.append(Gate(
                "G-NH4-SHARE", "WARNING",
                "Ammonium share of total N above 15%", "铵态氮占总氮比例超过 15%",
                f"NH4 is {share * 100:.0f}% of total N. In hydroponic systems the "
                f"proportion of ammonium should be limited to 5-15%.",
                f"铵态氮占总氮 {share * 100:.0f}%。无土栽培系统中铵态氮比例应控制在 5-15%。",
                {"nh4_share_pct": round(share * 100, 1)}))
    return gates


def steering_gates(r: SteeringResult, crop: CropRecipe,
                   na_ratio: float | None = None,
                   wash_active: bool = False,
                   check_ammonium: bool = True) -> list[Gate]:
    """
    `check_ammonium=False` when the caller evaluates ammonium separately
    against the final corrected recipe, so the gate is not reported twice.
    """
    gates: list[Gate] = ammonium_gates(r.macro_after) if check_ammonium else []
    if (r.dry_back_intent in ("GENERATIVE", "STRONGLY_GENERATIVE")
            and na_ratio is not None and na_ratio >= 0.80):
        gates.append(Gate(
            "G-DRYBACK-NA", "WARNING",
            "Generative dry-back suppressed by sodium load", "钠负荷限制生殖型回干",
            f"Root-zone Na is at {na_ratio * 100:.0f}% of the crop ceiling. Drying "
            f"back concentrates the root-zone solution, including sodium. "
            f"Dry-back intent downgraded to Balanced.",
            f"根际钠已达作物上限的 {na_ratio * 100:.0f}%。回干会浓缩根际溶液，钠亦随之升高。"
            f"回干策略已降级为平衡型。",
            {"na_ratio": round(na_ratio, 2)}, "", "", "SRC:PRACTICE"))
    if wash_active:
        gates.append(Gate(
            "G-DRYBACK-SUPPRESSED", "INFO",
            "Dry-back guidance suppressed during wash", "冲洗期间暂停回干建议",
            "A wash cycle or forced discharge is active. Dry-back and leaching "
            "are contradictory instructions; the wash takes precedence.",
            "当前处于冲洗或强行排液状态。回干与淋洗指令相互矛盾；以冲洗为准。",
            {}, "", "", "SRC:PRACTICE"))
    if crop.medium == "SOIL":
        gates.append(Gate(
            "G-DRYBACK-NA-SOIL", "INFO",
            "Dry-back does not apply to soil", "土壤栽培不适用回干策略",
            "Substrate dry-back targets do not transfer to soil-grown crops.",
            "基质回干目标不适用于土壤栽培作物。", {}, "", "", "SRC:PRACTICE"))
    return gates


# ==========================================================================
# Stock-tank mass — Ch. 8, p. 28
# ==========================================================================

def stock_mass_kg(mmol_per_l: float, mass_per_mol_ion_g: float,
                  policy: SitePolicy = DEFAULT_POLICY) -> float:
    """
    kg per tank = mmol/L * (g per mol of driving ion) * CF/1000 * V/1000

    At the standard CF = 100 and V = 1000 L this reduces to the familiar
    `Mass (kg) = mmol/L * MW * 0.1`.
    """
    return (mmol_per_l * mass_per_mol_ion_g
            * (policy.concentration_factor / 1000.0)
            * (policy.tank_volume_l / 1000.0))


def stock_mass_micro_g(umol_per_l: float, ion: str, fraction: float,
                       policy: SitePolicy = DEFAULT_POLICY) -> float:
    """
    g per tank = umol/L * atomic weight / product fraction * CF/1000 * V/1000

    e.g. Fe 15 umol/L as Fe-DTPA 6%: 15 * 55.85 / 0.06 * 0.1 = 1396 g.
    """
    return (umol_per_l * ATOMIC_WEIGHTS[ion] / fraction
            * (policy.concentration_factor / 1000.0)
            * (policy.tank_volume_l / 1000.0))


@dataclass
class Dose:
    fert: Fertiliser
    amount_mmol_l: float              # mmol/L (macro) or umol/L (micro)
    mass_kg: float
    volume_l: float | None
    is_micro: bool

    @property
    def mass_g(self) -> float:
        return self.mass_kg * 1000.0

    def scaled(self, frac: float) -> "Dose":
        return replace(self,
                       amount_mmol_l=self.amount_mmol_l * frac,
                       mass_kg=self.mass_kg * frac,
                       volume_l=(self.volume_l * frac
                                 if self.volume_l is not None else None))

    def to_dict(self) -> dict:
        d = {
            "fertiliser_id": self.fert.fid,
            "fertiliser": self.fert.name_en,
            "fertiliser_text": self.fert.name,
            "formula": self.fert.formula,
            "is_micronutrient": self.is_micro,
            "provenance": "SRC:WUR Table 5, p.26",
        }
        if self.is_micro:
            d["amount_umol_l"] = round(self.amount_mmol_l, 3)
            d["mass_g"] = round(self.mass_g, 1)
            d["mass_display"] = f"{self.mass_g:.0f} g"
        else:
            d["amount_mmol_l"] = round(self.amount_mmol_l, 4)
            d["mass_kg"] = round(self.mass_kg, 2)
            d["mass_display"] = f"{self.mass_kg:.1f} kg"
        if self.volume_l is not None:
            d["volume_l"] = round(self.volume_l, 2)
            d["mass_display"] = f"{self.volume_l:.1f} L"
        return d


def _make_dose(f: Fertiliser, mol_fertiliser: float, policy: SitePolicy) -> Dose:
    """
    `mol_fertiliser` is mmol/L of the FERTILISER, so the per-mole mass is the
    formula mass. The two conventions are equivalent:

        mmol_ion * mass_per_mol_ion == mmol_fertiliser * formula_mass

    because mass_per_mol_ion = formula_mass / n_driving and
    mmol_ion = mmol_fertiliser * n_driving. Mixing them silently under-doses
    every multi-ion fertiliser (calcium nitrate by 5x, calcium chloride by 2x).
    """
    kg = stock_mass_kg(mol_fertiliser, f.formula_mass, policy)
    vol = kg / f.density if (f.phase == "liquid" and f.density) else None
    return Dose(f, mol_fertiliser, kg, vol, is_micro=False)


def _make_micro_dose(f: Fertiliser, umol: float, policy: SitePolicy) -> Dose:
    g = stock_mass_micro_g(umol, f.micro_ion, f.micro_fraction, policy)
    kg = g / 1000.0
    vol = kg / f.density if (f.phase == "liquid" and f.density) else None
    return Dose(f, umol, kg, vol, is_micro=True)


# ==========================================================================
# M7 — Base water deduction, EC scaling, allocation
# ==========================================================================

# Base-water Fe is deliberately absent: it precipitates at the emitter.
CREDITABLE_FROM_BASE_WATER = ("Ca", "Mg", "S", "K", "NO3", "NH4", "P", "Cl")


def deduct_base_water(recipe: dict[str, float],
                      base_water: dict[str, float]) -> tuple[dict[str, float], dict[str, float]]:
    """
    Automatically deduct base-water nutrients from the target recipe (step 5
    of the manual's pipeline, p. 23). Ca, Mg and SO4 are the usual credits.

    Returns (adjusted_recipe, credit_vector).
    """
    out = dict(recipe)
    credit: dict[str, float] = {}
    for ion in CREDITABLE_FROM_BASE_WATER:
        present = base_water.get(ion, 0.0)
        if present <= EPS or ion not in out:
            continue
        # Credit only up to the target. Water that already carries more of an
        # ion than the recipe wants cannot be un-supplied: a negative demand is
        # physically meaningless and would corrupt the ion balance downstream.
        credited = min(present, out[ion])
        credit[ion] = credited
        out[ion] = out[ion] - credited
    return out, credit


def base_water_excess(recipe: dict[str, float],
                      base_water: dict[str, float]) -> dict[str, float]:
    """
    Ions the base water supplies in excess of the recipe target. These cannot
    be removed by fertiliser choice — only by dilution, blending or RO.
    """
    out: dict[str, float] = {}
    for ion in CREDITABLE_FROM_BASE_WATER:
        present = base_water.get(ion, 0.0)
        target = recipe.get(ion)
        if target is None:
            continue
        if present > target + EPS:
            out[ion] = present - target
    return out


def base_water_excess_gates(excess: dict[str, float]) -> list[Gate]:
    if not excess:
        return []
    detail_en = ", ".join(f"{ion} +{v:.2f} mmol/L" for ion, v in excess.items())
    detail_zh = "、".join(f"{ion} 超出 {v:.2f} mmol/L" for ion, v in excess.items())
    return [Gate(
        "G-WATER-EXCESS", "WARNING",
        "Base water exceeds recipe target for some ions",
        "原水中部分离子已超过配方目标",
        f"The base water already supplies more than the recipe targets: "
        f"{detail_en}. Fertiliser dosing for these ions is zero; the excess "
        f"cannot be removed by changing the recipe.",
        f"原水供应量已超过配方目标：{detail_zh}。这些离子的施肥量为零；"
        f"超出部分无法通过调整配方消除。",
        {ion: round(v, 3) for ion, v in excess.items()},
        "Dilute with rainwater or RO water, or accept the higher concentration "
        "and re-check the ion balance and EC headroom.",
        "使用雨水或反渗透水稀释，或接受较高浓度并复核离子平衡与电导率余量。")]


def deduct_drain(recipe: dict[str, float],
                 drain: dict[str, float],
                 drain_fraction: float) -> tuple[dict[str, float], dict[str, float]]:
    """
    Step 6, p. 24: subtract drain nutrients in proportion to the drain share
    of the irrigation water. The manual's illustration: drain at EC 4.0 reused
    at 20% contributes 4.0 * 0.20 = 0.8 mS/cm.
    """
    out = dict(recipe)
    credit: dict[str, float] = {}
    for ion, value in drain.items():
        if ion not in out:
            continue
        contribution = value * drain_fraction
        if abs(contribution) <= EPS:
            continue
        credited = min(contribution, out[ion]) if out[ion] > 0 else 0.0
        credit[ion] = credited
        out[ion] = out[ion] - credited
    return out, credit


SCALABLE_IONS = ("K", "Ca", "Mg", "NO3", "Cl", "S")
FIXED_IONS = ("NH4", "P")


SCALABLE_CATIONS = ("K", "Ca", "Mg")
SCALABLE_ANIONS = ("NO3", "Cl", "S")


def scale_to_ec(recipe: dict[str, float],
                ec_target: float) -> tuple[dict[str, float], dict[str, float]]:
    """
    Step 4, p. 23. All main nutrients EXCEPT NH4 and P are calculated to the
    higher drip irrigation water level; micronutrients are not scaled at all.

    This is NOT a ratio scale, and it is not a single factor either. Because
    a balanced solution carries equal cation and anion equivalents, and
    Formula 4 gives EC = (EqCat + EqAn)/20, hitting the target EC means

        EqCat = EqAn = 10 * EC_target

    Cations and anions therefore scale by SEPARATE factors, each solved with
    its own fixed ion held back (NH4 on the cation side, P on the anion side):

        f_cat = (10*EC_target - eq(NH4)) / eq(K + Ca + Mg)
        f_an  = (10*EC_target - eq(P))   / eq(NO3 + Cl + SO4)

    This lands on the target EC and restores the cation/anion balance in one
    operation. Verified against Table 3 (EC 2.6 -> 3.0): f_cat = 1.1707 and
    f_an = 1.1593, reproducing the published step-4 row (K 12.9, Mg 2.2,
    NO3 17.4, Cl 1.2, SO4 5.1) and, after steps 5-6, the published step-7 row
    to two decimals. A single shared factor is off by ~0.1 on K and Ca.
    """
    half = 10.0 * ec_target

    q_fixed_cat = sum(ION_CHARGE[i] * recipe.get(i, 0.0)
                      for i in FIXED_IONS if i in CATIONS)
    q_scal_cat = sum(ION_CHARGE[i] * recipe.get(i, 0.0) for i in SCALABLE_CATIONS)
    q_fixed_an = sum(ION_CHARGE[i] * recipe.get(i, 0.0)
                     for i in FIXED_IONS if i in ANIONS)
    q_scal_an = sum(ION_CHARGE[i] * recipe.get(i, 0.0) for i in SCALABLE_ANIONS)

    if q_scal_cat <= EPS or q_scal_an <= EPS:
        raise ValueError("G-NO-SCALABLE-LOAD: nothing left to scale")

    f_cat = (half - q_fixed_cat) / q_scal_cat
    f_an = (half - q_fixed_an) / q_scal_an
    if f_cat <= 0 or f_an <= 0:
        raise ValueError("G-EC-TARGET-BELOW-FIXED-LOAD")

    out: dict[str, float] = {}
    for ion, v in recipe.items():
        if ion in SCALABLE_CATIONS:
            out[ion] = v * f_cat
        elif ion in SCALABLE_ANIONS:
            out[ion] = v * f_an
        else:
            out[ion] = v
    return out, {"f_cations": f_cat, "f_anions": f_an}


def allocate_fertilisers(recipe: dict[str, float],
                         micro: dict[str, float],
                         acid_plan: AcidPlan | None = None,
                         fe_plan: "FeChelatePlan | None" = None,
                         boron_source: str = "borax",
                         policy: SitePolicy = DEFAULT_POLICY) -> tuple[list[Dose], dict[str, float]]:
    """
    Fixed greedy order from Ch. 8, p. 28:  H+ -> Cl -> Ca -> NH4 -> P ->
    Mg -> S -> K, with NO3 closing last through potassium nitrate.

    Every step decrements the ions the chosen fertiliser co-delivers.
    Calcium nitrate carries 5 Ca, 1 NH4 and 11 NO3 per mole; failing to
    decrement those is the classic way to silently over-dose nitrogen.
    """
    rem = {ion: float(recipe.get(ion, 0.0)) for ion in MACRO_IONS}
    doses: list[Dose] = []

    def consume(fid: str, mol: float) -> None:
        if mol <= EPS:
            return
        f = FERTILISERS[fid]
        for ion, n in f.yields.items():
            if ion == "H":
                continue
            rem[ion] = rem.get(ion, 0.0) - n * mol
        doses.append(_make_dose(f, mol, policy))

    # a. H+ from nitric and/or phosphoric acid
    if acid_plan is not None:
        consume("hno3_38", acid_plan.h_from_nitric)
        consume("h3po4_59", acid_plan.h_from_phosphoric)

    # b. Cl from calcium chloride (2 Cl per mole)
    if rem["Cl"] > EPS:
        consume("cacl2_s", rem["Cl"] / 2.0)

    # c. Ca from calcium nitrate solid (5 Ca per mole)
    if rem["Ca"] > EPS:
        consume("can_solid", rem["Ca"] / 5.0)

    # d. NH4 remainder from MAP
    if rem["NH4"] > EPS:
        consume("map", rem["NH4"])

    # e. P from monopotassium phosphate
    if rem["P"] > EPS:
        consume("mkp", rem["P"])

    # f/g. Mg from magnesium sulphate, remainder from magnesium nitrate
    if rem["Mg"] > EPS:
        from_sulphate = min(rem["Mg"], max(rem["S"], 0.0))
        consume("mgso4", from_sulphate)
        if rem["Mg"] > EPS:
            consume("mgno3_s", rem["Mg"])

    # h. S from potassium sulphate
    if rem["S"] > EPS:
        consume("k2so4", rem["S"])

    # i. K (and closing NO3) from potassium nitrate
    if rem["K"] > EPS:
        consume("kno3", rem["K"])

    # j. micronutrients
    micro_map = {"Mn": "mn_edta", "Zn": "zn_edta", "Cu": "cu_edta",
                 "Mo": "na_moly", "B": boron_source}
    for ion, umol in micro.items():
        if umol <= EPS:
            continue
        if ion == "Fe":
            plan = fe_plan or select_fe_chelate(5.5, "INERT_SUBSTRATE", "DRIP")
            for fid, share in plan.allocation():
                if share > EPS:
                    doses.append(_make_micro_dose(FERTILISERS[fid],
                                                  umol * share, policy))
        else:
            fid = micro_map.get(ion)
            if fid:
                doses.append(_make_micro_dose(FERTILISERS[fid], umol, policy))

    residual = {ion: round(v, 4) for ion, v in rem.items() if abs(v) > 1e-6}
    return doses, residual


# ==========================================================================
# M6 — A/B tank splitting & Fe chelate selection (Ch. 9 & 11)
# ==========================================================================

@dataclass
class FeChelatePlan:
    primary_fid: str
    primary_share: float
    secondary_fid: str | None
    secondary_share: float
    reason_en: str
    reason_zh: str
    require_ortho_ortho: bool

    def allocation(self) -> list[tuple[str, float]]:
        out = [(self.primary_fid, self.primary_share)]
        if self.secondary_fid and self.secondary_share > EPS:
            out.append((self.secondary_fid, self.secondary_share))
        return out


def select_fe_chelate(ph_root_zone: float,
                      medium: str = "INERT_SUBSTRATE",
                      irrigation_type: str = "DRIP",
                      calcareous_soil: bool = False) -> FeChelatePlan:
    """
    Ch. 11, p. 36. Below pH 6.5 a DTPA chelate provides sufficient stability;
    above 6.5 Fe-EDDHA or Fe-HBED is strongly recommended.

    Note the switch point is 6.5, not 7.0 (design.md discrepancy D-2), and
    Fe-EDTA's envelope ends at 6.5 while Fe-DTPA reaches 7.5, so the two are
    not interchangeable at the top of the band.
    """
    if calcareous_soil:
        return FeChelatePlan(
            "fe_eddha", 1.0, None, 0.0,
            "In calcareous soils iron is always needed as Fe-EDDHA or Fe-HBED. "
            "Only the ortho-ortho fraction is active; non-ortho-ortho iron drops "
            "off the chelate immediately after application.",
            "石灰质土壤中铁必须以 Fe-EDDHA 或 Fe-HBED 形式供应。仅邻-邻位组分有效；"
            "非邻-邻位的铁施用后立即从螯合物上脱落。",
            require_ortho_ortho=True)

    if ph_root_zone > FE_CHELATE_SWITCH_PH:
        return FeChelatePlan(
            "fe_eddha", 1.0, None, 0.0,
            f"Root-zone pH {ph_root_zone:g} is above {FE_CHELATE_SWITCH_PH:g}. "
            f"Fe-EDDHA or Fe-HBED is strongly recommended; Fe-DTPA loses "
            f"stability above pH 7.5 and Fe-EDTA above pH 6.5.",
            f"根际 pH {ph_root_zone:g} 高于 {FE_CHELATE_SWITCH_PH:g}。"
            f"强烈建议使用 Fe-EDDHA 或 Fe-HBED；Fe-DTPA 在 pH 7.5 以上、"
            f"Fe-EDTA 在 pH 6.5 以上即失去稳定性。",
            require_ortho_ortho=True)

    if irrigation_type == "NFT":
        prophylactic = PROPHYLACTIC_NFT
        why_en = ("NFT systems carry a high risk of pH elevation, so 10% of the "
                  "iron is supplied as Fe-EDDHA or Fe-HBED as a precaution.")
        why_zh = ("NFT 系统 pH 升高风险较高，因此将 10% 的铁以 Fe-EDDHA 或 "
                  "Fe-HBED 形式供应作为预防。")
    elif medium == "INERT_SUBSTRATE":
        prophylactic = PROPHYLACTIC_SUBSTRATE
        why_en = ("Inert substrates carry a high risk of pH elevation, so 25% of "
                  "the iron is supplied as Fe-EDDHA or Fe-HBED as a precaution.")
        why_zh = ("惰性基质 pH 升高风险较高，因此将 25% 的铁以 Fe-EDDHA 或 "
                  "Fe-HBED 形式供应作为预防。")
    else:
        prophylactic = 0.0
        why_en = "Fe-DTPA provides sufficient stability at this pH."
        why_zh = "在该 pH 条件下 Fe-DTPA 具有足够稳定性。"

    return FeChelatePlan(
        "fe_dtpa", 1.0 - prophylactic,
        "fe_eddha" if prophylactic > EPS else None, prophylactic,
        f"Root-zone pH {ph_root_zone:g} is at or below "
        f"{FE_CHELATE_SWITCH_PH:g}. {why_en}",
        f"根际 pH {ph_root_zone:g} 不高于 {FE_CHELATE_SWITCH_PH:g}。{why_zh}",
        require_ortho_ortho=prophylactic > EPS)


def chelate_gates(plan: FeChelatePlan, disinfection: str = "NONE",
                  recirculating: bool = False,
                  metal_sulphates_used: bool = False) -> list[Gate]:
    gates: list[Gate] = []
    if plan.require_ortho_ortho:
        gates.append(Gate(
            "G-OO-DECLARE", "INFO",
            "Check ortho-ortho content on the product label", "请核对产品标签上的邻-邻位含量",
            "For EDDHA and HBED products, only the ortho-ortho fraction is the "
            "active ingredient in soil. In Europe this is an obligatory part of "
            "the guaranteed analysis.",
            "对于 EDDHA 与 HBED 产品，在土壤中仅邻-邻位组分为有效成分。"
            "在欧盟，该项是保证成分表的强制内容。", {}))
    if disinfection in ("UV", "OZONE", "H2O2"):
        gates.append(Gate(
            "G-CHELATE-DISINFECT", "WARNING",
            "Re-dose chelates after disinfection", "消毒后需补加螯合物",
            f"Disinfecting drain water with {disinfection} breaks down chelate "
            f"structures to some extent. Replacing the chelates should be done "
            f"AFTER disinfection, not before.",
            f"使用 {disinfection} 对排液消毒会在一定程度上破坏螯合物结构。"
            f"补加螯合物应在消毒之后进行，而非之前。",
            {"disinfection": 0.0},
            "Also protect nutrient solutions containing chelates from daylight.",
            "含螯合物的营养液还须避光保存。"))
    if recirculating:
        gates.append(Gate(
            "G-CHELATE-SODIUM", "WARNING",
            "Use sodium-free chelates in recirculating systems", "循环系统请使用无钠螯合物",
            "When drain is recycled, sodium input must be minimised. Switching "
            "from sodium-based chelates to potassium-based ones, and from borax "
            "to boric acid, keeps recirculated sodium low.",
            "排液回用时须尽量降低钠输入。将钠基螯合物改为钾基、将硼砂改为硼酸，"
            "可保持循环液中钠含量较低。", {}))
    if metal_sulphates_used:
        gates.append(Gate(
            "G-FE-EXCHANGE-LOSS", "WARNING",
            "Metal sulphates cause iron loss", "金属硫酸盐会造成铁损失",
            "Using Mn, Zn or Cu sulphates leads to losses of iron through "
            "exchange of Fe in the chelate. Depending on pH, losses can be "
            "20-50%. EDTA chelates of Mn, Zn and Cu avoid this.",
            "使用锰、锌、铜的硫酸盐会因螯合物中铁被置换而损失铁。视 pH 而定，"
            "损失可达 20-50%。改用 Mn、Zn、Cu 的 EDTA 螯合物可避免此问题。", {}))
    return gates


@dataclass
class TankSplit:
    tank_a: list[Dose]
    tank_b: list[Dose]
    mass_a_kg: float
    mass_b_kg: float
    gates: list[Gate]


def split_ab_tanks(doses: list[Dose],
                   policy: SitePolicy = DEFAULT_POLICY) -> TankSplit:
    """
    Ch. 9, p. 31.

    All calcium fertilisers must be separated from phosphate and sulphate
    fertilisers: calcium into tank A, sulphate and phosphate into tank B.
    Potassium nitrate, magnesium nitrate, ammonium nitrate and nitric acid can
    go into either tank; spreading them balances the load. Chelates prefer
    tank A, but tank-A acid must stay low enough to keep pH above 3.5.
    """
    fixed_a: list[Dose] = []
    fixed_b: list[Dose] = []
    either: list[Dose] = []

    for d in doses:
        if d.fert.tank == "A":
            fixed_a.append(d)
        elif d.fert.tank == "B":
            fixed_b.append(d)
        else:
            either.append(d)

    out_a, out_b = list(fixed_a), list(fixed_b)
    rest: list[Dose] = []

    # Acid: cap the volume placed in tank A so chelates there stay above pH 3.5
    for d in either:
        if d.fert.driving_ion == "H" and d.volume_l:
            in_a = min(d.volume_l, policy.tank_a_acid_cap_l)
            frac_a = in_a / d.volume_l
            if frac_a > EPS:
                out_a.append(d.scaled(frac_a))
            if 1.0 - frac_a > EPS:
                out_b.append(d.scaled(1.0 - frac_a))
        else:
            rest.append(d)

    # Balance the remaining either-class fertilisers by dissolved mass
    mass_a = sum(x.mass_kg for x in out_a)
    mass_b = sum(x.mass_kg for x in out_b)
    total_rest = sum(x.mass_kg for x in rest)
    target_a = (mass_a + mass_b + total_rest) / 2.0
    budget_a = max(0.0, min(total_rest, target_a - mass_a))

    for d in sorted(rest, key=lambda x: -x.mass_kg):
        if budget_a <= EPS:
            out_b.append(d)
        elif d.mass_kg <= budget_a:
            out_a.append(d)
            budget_a -= d.mass_kg
        else:
            frac = budget_a / d.mass_kg if d.mass_kg > EPS else 0.0
            if frac > EPS:
                out_a.append(d.scaled(frac))
            out_b.append(d.scaled(1.0 - frac))
            budget_a = 0.0

    gates = validate_tank_separation(out_a, out_b)
    return TankSplit(out_a, out_b,
                     sum(x.mass_kg for x in out_a),
                     sum(x.mass_kg for x in out_b),
                     gates)


def validate_tank_separation(tank_a: list[Dose], tank_b: list[Dose]) -> list[Gate]:
    """
    Ksp safety. At 100x concentration both CaSO4 (Ksp ~3.14e-5) and
    Ca3(PO4)2 (Ksp ~2.07e-33) are far past saturation, which is why the
    separation is absolute rather than a computed margin. This gate is
    BLOCKING and cannot be overridden.
    """
    gates: list[Gate] = []
    for tank, name, name_zh in ((tank_a, "A", "A 罐"), (tank_b, "B", "B 罐")):
        ions: set[str] = set()
        for d in tank:
            ions |= set(d.fert.yields.keys())
        if "Ca" not in ions:
            continue
        clashes = [i for i in ("S", "P") if i in ions]
        if clashes:
            product = ("CaSO4 (gypsum)" if "S" in clashes else "Ca3(PO4)2")
            gates.append(Gate(
                "G-PRECIP-RISK", "BLOCKING",
                f"Precipitation risk in tank {name}", f"{name_zh}存在沉淀风险",
                f"Tank {name} contains calcium together with "
                f"{' and '.join(clashes)}. At 100x concentration this "
                f"precipitates as {product} and will block the irrigation system. "
                f"All calcium fertilisers must be separated from phosphate and "
                f"sulphate fertilisers.",
                f"{name_zh}同时含有钙与 {' 和 '.join(clashes)}。在 100 倍浓缩条件下"
                f"将析出 {product} 沉淀并堵塞灌溉系统。所有钙肥必须与磷肥、硫酸盐肥分开存放。",
                {"tank": 0.0},
                "Move the calcium fertilisers to tank A and the sulphate and "
                "phosphate fertilisers to tank B.",
                "将钙肥移至 A 罐，硫酸盐与磷酸盐肥移至 B 罐。"))
    return gates


def tank_ph_gates(split: TankSplit, policy: SitePolicy = DEFAULT_POLICY) -> list[Gate]:
    gates: list[Gate] = []
    acid_a = sum(d.volume_l or 0.0 for d in split.tank_a
                 if d.fert.driving_ion == "H")
    has_chelate_a = any(d.fert.chelate_agent for d in split.tank_a)
    if has_chelate_a and acid_a > policy.tank_a_acid_cap_l + EPS:
        gates.append(Gate(
            "G-TANK-A-ACID", "CRITICAL",
            "Too much acid in tank A for the chelates", "A 罐酸量过高，将破坏螯合物",
            f"Tank A holds {acid_a:.1f} L of acid alongside chelates. At pH 3.5 "
            f"or lower the chelate structure breaks down, especially for EDDHA "
            f"and HBED. Limit tank-A acid to a few litres per m3 and put the "
            f"remainder in tank B.",
            f"A 罐中酸量为 {acid_a:.1f} L 且同时存放螯合物。pH 3.5 及以下时螯合物结构会分解，"
            f"EDDHA 与 HBED 尤为敏感。A 罐酸量应限制在每立方米数升，其余放入 B 罐。",
            {"acid_l": round(acid_a, 2), "cap_l": policy.tank_a_acid_cap_l}))
    gates.append(Gate(
        "G-TANK-PH-CHECK", "INFO",
        "Verify stock tank pH after filling", "配罐后请核查母液 pH",
        "The pH of tank B should be below 5 and the pH of tank A between 3.5 "
        "and 5, so that all fertilisers dissolve completely without breaking "
        "down the chelates.",
        "B 罐 pH 应低于 5，A 罐 pH 应在 3.5 至 5 之间，以保证肥料完全溶解且不破坏螯合物。",
        {}))
    return gates


# ==========================================================================
# M8 — Emergency meltdown gate
# ==========================================================================

def emergency_check(ph: float, ec: float, crop: CropRecipe | None = None,
                    policy: SitePolicy = DEFAULT_POLICY) -> dict | None:
    """
    Hardcoded emergency payload. Evaluated FIRST, before every other module.
    When it fires the recipe output is suppressed and the cognitive layer is
    never invoked — the instruction set below is returned verbatim.
    """
    ph_bad = ph < policy.meltdown_ph_min
    ec_bad = ec > policy.meltdown_ec_max
    if not (ph_bad or ec_bad):
        return None

    reasons_en, reasons_zh = [], []
    if ph_bad:
        reasons_en.append(f"pH {ph:g} is below the {policy.meltdown_ph_min:g} floor")
        reasons_zh.append(f"pH {ph:g} 低于 {policy.meltdown_ph_min:g} 下限")
    if ec_bad:
        reasons_en.append(f"EC {ec:g} mS/cm is above the "
                          f"{policy.meltdown_ec_max:g} mS/cm ceiling")
        reasons_zh.append(f"EC {ec:g} mS/cm 高于 "
                          f"{policy.meltdown_ec_max:g} mS/cm 上限")

    target_ec = crop.ec_root_zone if crop else policy.meltdown_ec_max

    steps = [
        ("Stop nutrient dosing immediately.",
         "立即停止养分投加。"),
        (f"Flush with clean base water (EC < 0.5 mS/cm, pH 5.5-6.0) at a "
         f"leaching fraction of at least 50% until drain EC falls below "
         f"{target_ec:g} mS/cm.",
         f"使用洁净原水（EC < 0.5 mS/cm，pH 5.5-6.0）冲洗，排液比不低于 50%，"
         f"直至排液电导率降至 {target_ec:g} mS/cm 以下。"),
        ("Re-measure drain pH and EC every 2 hours.",
         "每 2 小时复测排液 pH 与 EC。"),
        ("Verify the fertigation unit: injector calibration, acid pump setting, "
         "A/B tank identification, EC and pH probe calibration.",
         "检查施肥机：注肥泵标定、加酸泵设定、A/B 罐标识、EC 与 pH 电极校准。"),
        ("Send a root-zone sample to the laboratory before resuming dosing.",
         "恢复投加前，先送根际样品至实验室分析。"),
        ("Do not resume the previous recipe until the cause is identified.",
         "在查明原因前，不得恢复原配方。"),
    ]

    return {
        "emergency": True,
        "gate_id": "G-MELTDOWN",
        "severity": "BLOCKING",
        "severity_text": _SEVERITY_TEXT["BLOCKING"],
        "title": "EMERGENCY FLUSH REQUIRED",
        "title_text": bi("EMERGENCY FLUSH REQUIRED", "紧急冲洗指令"),
        "status_text": bi("Emergency - Recipe Output Suspended",
                          "紧急状态 - 配方输出已暂停"),
        "reason": "; ".join(reasons_en),
        "reason_text": bi("; ".join(reasons_en), "；".join(reasons_zh)),
        "measured_ph": ph,
        "measured_ec_ms_cm": ec,
        "limit_ph_min": policy.meltdown_ph_min,
        "limit_ec_max": policy.meltdown_ec_max,
        "recipe_suppressed": True,
        "llm_invoked": False,
        "instructions": [
            {"step": i + 1, "action": en, "action_text": bi(en, zh)}
            for i, (en, zh) in enumerate(steps)
        ],
        "provenance": "SRC:PRACTICE thresholds; SRC:WUR agronomic basis (p.15, p.53)",
    }


# ==========================================================================
# Diagnostics helpers (M8 routine path)
# ==========================================================================

def cation_balance_pct(m: dict[str, float]) -> dict[str, float]:
    """Na / K / Ca / Mg as % of cation equivalents (report chart, p. 30)."""
    parts = {i: ION_CHARGE[i] * m.get(i, 0.0) for i in ("Na", "K", "Ca", "Mg")}
    total = sum(parts.values())
    if total <= EPS:
        return {k: 0.0 for k in parts}
    return {k: round(100.0 * v / total, 1) for k, v in parts.items()}


ANTAGONISM_RULES = [
    ("K_SUPPRESSES_CA_MG", "K blocks Ca and Mg uptake", "钾抑制钙镁吸收"),
    ("NA_DISPLACES_CATIONS", "Na displaces nutrient cations", "钠置换养分阳离子"),
    ("CA_SUPPRESSES_MG", "Ca blocks Mg uptake", "钙抑制镁吸收"),
    ("NH4_SUPPRESSES_CA_K", "Ammonium blocks Ca and K uptake", "铵抑制钙钾吸收"),
    ("METALS_DISPLACE_FE", "Mn, Zn and Cu displace Fe from the chelate",
     "锰锌铜从螯合物上置换铁"),
    ("HIGH_PH_LIMITS_P_MICRO", "High pH limits P and micronutrient uptake",
     "高 pH 限制磷与微量元素吸收"),
]


def screen_antagonism(m: dict[str, float], ph: float,
                      targets: dict[str, float],
                      metal_sulphates_used: bool = False) -> list[dict]:
    """
    Deterministic pattern matching only. The engine emits the match; the
    cognitive layer writes the explanation. The pattern is never invented
    by the model.
    """
    shares = cation_balance_pct(m)
    out: list[dict] = []

    def add(code: str, evidence: dict[str, float]) -> None:
        rule = next(r for r in ANTAGONISM_RULES if r[0] == code)
        out.append({
            "code": code,
            "pattern": rule[1],
            "pattern_text": bi(rule[1], rule[2]),
            "evidence": evidence,
        })

    ca_low = m.get("Ca", 0.0) < targets.get("Ca", 0.0) * 0.9
    mg_low = m.get("Mg", 0.0) < targets.get("Mg", 0.0) * 0.9
    if shares["K"] > 40.0 and (ca_low or mg_low):
        add("K_SUPPRESSES_CA_MG", {"k_share_pct": shares["K"]})
    if shares["Na"] > 15.0:
        add("NA_DISPLACES_CATIONS", {"na_share_pct": shares["Na"]})
    mg = m.get("Mg", 0.0)
    if mg > EPS and (m.get("Ca", 0.0) / mg) > 4.0:
        add("CA_SUPPRESSES_MG", {"ca_mg_ratio": round(m.get("Ca", 0.0) / mg, 2)})
    nh4 = m.get("NH4", 0.0)
    total_n = nh4 + m.get("NO3", 0.0)
    if nh4 > 1.5 or (total_n > EPS and nh4 / total_n > 0.15):
        add("NH4_SUPPRESSES_CA_K", {"nh4_mmol_l": round(nh4, 2)})
    if metal_sulphates_used:
        add("METALS_DISPLACE_FE", {"expected_fe_loss_pct_min": 20.0,
                                   "expected_fe_loss_pct_max": 50.0})
    if ph > 6.5:
        add("HIGH_PH_LIMITS_P_MICRO", {"ph": ph})
    return out


def ion_balance_gates(recipe: dict[str, float]) -> list[Gate]:
    """
    Step 7 of the manual restores the cation/anion balance. This engine
    REPORTS the imbalance but does not yet auto-restore it (see design.md
    section 6.7.2, step 7 - counter-ion adjustment is not implemented).
    A recipe flagged here needs manual counter-ion adjustment before use.
    """
    rep = balance_report(recipe)
    if rep["balanced"]:
        return []
    return [Gate(
        "G-ION-IMBALANCE", "WARNING",
        "Cation/anion balance not restored", "阴阳离子平衡尚未恢复",
        f"Cations total {rep['eq_cations_meq_l']} meq/L against anions "
        f"{rep['eq_anions_meq_l']} meq/L, a difference of "
        f"{rep['difference_pct']}%. A difference below 10% is acceptable "
        f"analytical variation; above that the solution is genuinely unbalanced. "
        f"Automatic counter-ion restoration is not implemented.",
        f"阳离子合计 {rep['eq_cations_meq_l']} meq/L，阴离子合计 "
        f"{rep['eq_anions_meq_l']} meq/L，相差 {rep['difference_pct']}%。"
        f"低于 10% 属可接受的分析误差；高于该值则确实失衡。"
        f"本引擎尚未实现自动配衡。",
        {"difference_pct": rep["difference_pct"],
         "eq_cations": rep["eq_cations_meq_l"],
         "eq_anions": rep["eq_anions_meq_l"]},
        "Adjust the least-constrained counter-ion within its crop band "
        "(SO4 or NO3 on the anion side, K or Ca on the cation side) before "
        "filling the tanks.",
        "配罐前，请在作物允许区间内调整约束最少的配衡离子"
        "（阴离子侧为 SO4 或 NO3，阳离子侧为 K 或 Ca）。")]


def sort_gates(gates: list[Gate]) -> list[Gate]:
    return sorted(gates, key=lambda g: SEVERITY_ORDER.get(g.severity, 9))
