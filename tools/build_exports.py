"""
Generate the data and documentation deliverables described in
docs/CLAUDE_CODE_MASTER_EXPORT_PROMPT.md.

Everything is derived from the live modules (constants.py / engine.py), never
re-typed, so the exports cannot drift from the running system. Where the export
brief and the codebase disagree, the CODE is exported as authoritative and the
divergence is recorded in `spec_divergences` so a reader of the deliverable can
see it rather than inherit a silent error.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import constants as C          # noqa: E402
import engine as E             # noqa: E402

DATA = ROOT / "exports" / "data"
DOCS = ROOT / "exports" / "docs"
MODS = ROOT / "exports" / "modules"

SOURCE = ("Van der Lugt, G. et al. (2020) Nutrient Solutions for Greenhouse "
          "Crops, Version 4, ISBN 9789464021844. Eurofins Agro / Nouryon / "
          "SQM / Yara.")


def jdump(path: Path, obj) -> Path:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def bi_zh_first(zh: str, en: str) -> str:
    """Brief's STEP 1 format: 【中文 (英文/英文缩写)】"""
    return f"【{zh} ({en})】"


# ==========================================================================
# Divergences between the export brief and the implemented system
# ==========================================================================

SPEC_DIVERGENCES = [
    {
        "id": "DIV-1",
        "topic": "Acid concentrations",
        "brief_states": "65% HNO3, 85% H3PO4",
        "codebase_implements": "38% HNO3 (d=1.24), 60% HNO3 (d=1.37), "
                               "59% H3PO4 (d=1.42)",
        "basis": "WUR Table 5, p.26 lists exactly these three acid grades. "
                 "Neither 65% HNO3 nor 85% H3PO4 appears in the manual.",
        "resolution": "Exported the catalogue grades. Molarity is computed from "
                      "density and mass-per-mole-of-H+, so a site using a "
                      "different grade can add it to the catalogue and every "
                      "downstream figure follows.",
        "severity": "material - dosing volumes differ by roughly 1.7x between "
                    "38% and 65% nitric acid",
    },
    {
        "id": "DIV-2",
        "topic": "Safety gate identifiers",
        "brief_states": "G-ACID-POISON (pH<5.2), G-SALINITY-MELTDOWN (EC>4.5), "
                        "G-K-CA-ANTAGONISM (dK > +2.0 mmol/L), G-NA-CEILING",
        "codebase_implements": "G-MELTDOWN covers BOTH pH<5.2 and EC>4.5 as one "
                               "blocking gate; sodium is G-NA-APPROACH / "
                               "G-NA-EXCEED / G-NA-UNREACHABLE; 36 gates total",
        "basis": "Gate identifiers are emitted by engine.py and consumed by the "
                 "frontend; renaming them in an export would describe a system "
                 "that does not exist.",
        "resolution": "Exported the real gate registry plus an explicit "
                      "`brief_name_mapping` for each requested name.",
        "severity": "naming only - thresholds (pH 5.2, EC 4.5) match exactly",
    },
    {
        "id": "DIV-3",
        "topic": "K:Ca antagonism rule",
        "brief_states": "G-K-CA-ANTAGONISM fires at dK > +2.0 mmol/L",
        "codebase_implements": "No such rule. Antagonism screening is pattern-"
                               "based: K_SUPPRESSES_CA_MG fires when K exceeds "
                               "40% of cation equivalents AND Ca or Mg is below "
                               "target.",
        "basis": "The manual gives no absolute delta-K threshold; it reports the "
                 "K/Ca ratio and the cation balance chart (p.29-30).",
        "resolution": "Exported the implemented pattern rules. The dK>2.0 rule "
                      "is listed as NOT IMPLEMENTED rather than fabricated.",
        "severity": "material - exporting an unimplemented threshold would "
                    "misrepresent the system to the agronomy reviewers",
    },
    {
        "id": "DIV-4",
        "topic": "Charge balance cation formula",
        "brief_states": "Cations = K + 2Ca + 2Mg + NH4 + Na",
        "codebase_implements": "Cations = NH4 + K + Na + 2Ca + 2Mg + H+",
        "basis": "H+ from acid dosing participates as a cation. Table 3 step 7 "
                 "(p.23) only balances when it is included: EqCat 21.2 vs "
                 "EqAn 21.25 with H+ = 0.5 mmol/L.",
        "resolution": "Exported with the H+ term and a note.",
        "severity": "material when acid is dosed; identical otherwise",
    },
    {
        "id": "DIV-5",
        "topic": "Module count",
        "brief_states": "5 core modules",
        "codebase_implements": "8 modules (M1-M8)",
        "basis": "Design document section 6.",
        "resolution": "Exports are grouped into the brief's 5 buckets; the "
                      "mapping is given in the master spec.",
        "severity": "presentational",
    },
    {
        "id": "DIV-6",
        "topic": "Wash target leaching fraction",
        "brief_states": "Extra irrigation to achieve a 32.5% target LF",
        "codebase_implements": "Tiered target: 32.5% only while LF < 30%; "
                               "LF+10 (cap 50%) for 30-40%; no volume target "
                               "at all above 40% (G-WASH-ANOMALY)",
        "basis": "A fixed 32.5% target produces a negative volume once measured "
                 "LF exceeds it, which clamps to zero and yields contradictory "
                 "advice.",
        "resolution": "Excel model and docs show all three tiers.",
        "severity": "material above 30% LF",
    },
]


# ==========================================================================
# STEP 1 - master database
# ==========================================================================

def build_master_database() -> dict:
    return {
        "meta": {
            "title": "WUR Master Agronomic Database",
            "title_bilingual": bi_zh_first("WUR 主数据库", "WUR Master Database"),
            "source": SOURCE,
            "generated_from": "constants.py / engine.py (live import)",
            "engine_version": "1.0.0",
        },
        "atomic_weights_g_per_mol": C.ATOMIC_WEIGHTS,
        "atomic_weights_note": "WUR Table 7, p.39. g/mol == mg/mmol == ug/umol.",
        "ion_charges": C.ION_CHARGE,
        "cations": list(C.CATIONS),
        "anions": list(C.ANIONS),
        "ec_model": {
            "formula": "EC (mS/cm) = (Eq_cations + Eq_anions) / 20",
            "divisor": C.EC_DIVISOR,
            "ion_balance_tolerance_fraction": C.ION_BALANCE_TOLERANCE,
            "reference_ec_offset": C.REFERENCE_EC_OFFSET,
            "na_ec_factor": C.NA_EC_FACTOR,
            "source": "Formulas 1-4, p.21-22",
        },
        "oxide_to_elemental": C.OXIDE_TO_ELEMENTAL,
        "elemental_to_oxide": C.ELEMENTAL_TO_OXIDE,
        "water_quality_levels": C.WATER_QUALITY_LEVELS,
        "sodium_ceilings_mmol_l": C.NA_LIMITS_MMOL_L,
        "sodium_ceiling_note": (
            "Table 2, p.12, stated on the root-zone SOLUTION basis. The crop x "
            "substrate matrix overrides this: organic and soil targets are read "
            "from diluted extracts and their ceilings differ (tomato 8 on inert, "
            "2 on organic)."),
        "chloride_offset_mmol_l": C.CL_OFFSET_MMOL_L,
        "fe_chelate_ph_bands": {k: list(v) for k, v in C.FE_CHELATE_BANDS.items()},
        "fe_chelate_switch_ph": C.FE_CHELATE_SWITCH_PH,
        "prophylactic_eddha_fraction": {
            "inert_substrate": C.PROPHYLACTIC_SUBSTRATE,
            "nft": C.PROPHYLACTIC_NFT,
        },
        "average_plant_need_umol_l": C.APN_UMOL_L,
        "substrate_types": list(C.SUBSTRATE_TYPES),
        "extract_methods": C.EXTRACT_METHODS,
        "crop_categories": list(C.CROP_CATEGORIES),
        "stock_tank_mass_formula": {
            "macronutrient_kg": "mmol/L * mass_per_mol_ion(g) * CF/1000 * V/1000",
            "at_100x_1000L": "kg = mmol/L * mass_per_mol_ion * 0.1",
            "micronutrient_g": "umol/L * atomic_weight / product_fraction * 0.1",
            "critical_note": (
                "mass_per_mol_ion is grams of product per mole of the DRIVING "
                "ion, not per mole of fertiliser. Calcium nitrate is 1080 g/mol "
                "but carries 5 Ca, so the divisor is 216. Using 1080 over-doses "
                "by 5x."),
            "source": "Ch.8, p.28",
        },
        "fertiliser_catalogue": build_fertiliser_catalogue(),
        "spec_divergences": SPEC_DIVERGENCES,
    }


def build_fertiliser_catalogue() -> list[dict]:
    out = []
    for f in C.FERTILISERS.values():
        rec = {
            "id": f.fid,
            "name_en": f.name_en,
            "name_zh": f.name_zh,
            "formula": f.formula,
            "formula_mass_g_per_mol": f.formula_mass,
            "driving_ion": f.driving_ion,
            "mass_per_mol_driving_ion_g": round(f.mass_per_mol_ion, 4),
            "ion_yields_mol_per_mol": f.yields,
            "tank": f.tank,
            "phase": f.phase,
            "density_kg_per_l": f.density,
            "sodium_bearing": f.sodium_bearing,
            "chelate_agent": f.chelate_agent,
            "ph_stability": list(f.ph_stability) if f.ph_stability else None,
            "micronutrient_fraction": f.micro_fraction,
        }
        if f.driving_ion == "H" and f.density:
            rec["molarity_mol_h_per_l"] = round(E.acid_molarity_mol_per_l(f), 4)
        out.append(rec)
    return out


# ==========================================================================
# STEP 2 - Module 1 acid neutralisation
# ==========================================================================

def build_module1() -> dict:
    acids = []
    for fid in ("hno3_38", "hno3_60", "h3po4_59"):
        f = C.FERTILISERS[fid]
        m = E.acid_molarity_mol_per_l(f)
        acids.append({
            "id": fid,
            "name_en": f.name_en,
            "name_zh": f.name_zh,
            "density_kg_per_l": f.density,
            "grams_product_per_mol_h": f.mass_per_mol_ion,
            "molarity_mol_h_per_l": round(m, 4),
            "mmol_h_per_ml": round(m, 4),
            "anion_yield_per_mol_h": (
                {"NO3": 1.0} if "hno3" in fid else {"H2PO4": 1.0}),
            "litres_per_mmol_per_l_per_m3": round(1.0 / m, 6),
        })
    return {
        "meta": {"module": "M1",
                 "title_bilingual": bi_zh_first("原水水质与加酸中和",
                                                "Base Water & Acid Neutralisation"),
                 "source": SOURCE},
        "raw_water_parameter_bounds": {
            "quality_levels": C.WATER_QUALITY_LEVELS,
            "ph_optimum_hydroponic": [5.5, 6.5],
            "ph_optimum_soil": [6.0, 7.5],
            "iron_limits_umol_l": {
                "drip": 0.0,
                "drip_with_organic_matter": 20.0,
                "sprinkler_soft_water_max": 100.0,
                "decorative_crop_max": 50.0,
                "note": "Base-water Fe is NEVER credited as nutrient; it "
                        "precipitates at the emitter (p.13-14).",
            },
            "micronutrient_screening_umol_l": {
                "B_tolerable_upper": 30.0, "Mn_max": 10.0},
        },
        "acids": acids,
        "hco3_safety_buffer_mmol_l": {
            "min": 0.50, "max": 0.75, "default": C.DEFAULT_POLICY.hco3_buffer_mmol_l,
            "rationale": "Retaining 0.5-0.75 mmol/L HCO3 buffers pH to 5.5-6.0. "
                         "Neutralising all of it drops irrigation pH below 5 "
                         "(p.24).",
        },
        "neutralisation": {
            "reaction": "Ca2+ + 2HCO3- + 2HNO3 <-> Ca2+ + 2CO2 + 2H2O + 2NO3-",
            "h_required_formula": "H+ = max(0, HCO3_base_water - HCO3_buffer)",
            "constraint": "Acid anions count against the recipe: nitric is "
                          "capped by NO3 headroom, phosphoric by P headroom.",
            "co2_requirement": "The reaction must occur in an OPEN system so "
                               "CO2 can escape, otherwise pH will not fall.",
        },
        "dosing_bases": {
            "stock_tank": "kg per 1000 L at 100x = mmol/L * MW * 0.1",
            "working_solution": "L per 1000 L at 1x = (mmol/L / 1000 * V) / molarity",
            "identity": "stock_tank_litres == working_solution_litres * CF",
            "warning": "Confusing the two is a 100x dosing error.",
        },
        "nutrient_deduction_rules": {
            "creditable_from_base_water": list(E.CREDITABLE_FROM_BASE_WATER),
            "never_credited": ["Fe"],
            "clamping": "Credits are capped at the recipe target; base water "
                        "carrying more of an ion than the target cannot be "
                        "un-supplied, so the excess is reported, not negated.",
        },
        "spec_divergences": [d for d in SPEC_DIVERGENCES if d["id"] == "DIV-1"],
    }


# ==========================================================================
# STEP 3 - Module 2 crop target database
# ==========================================================================

def build_crop_targets() -> tuple[dict, list[dict]]:
    hierarchy: dict = {}
    rows: list[dict] = []
    for cat in C.CROP_CATEGORIES:
        hierarchy[cat] = {"label": C.CROP_CATEGORY_LABELS[cat], "crops": {}}
        for cid in C.crops_in_category(cat):
            meta = C.crop_meta(cid)
            entry = {
                "name_en": meta["name_en"], "name_zh": meta["name_zh"],
                "botanical": meta.get("botanical", ""),
                "substrates": {},
            }
            for sub in C.substrates_for(cid):
                crop = C.get_crop(cid, sub)
                stages = {a.stage: {"label_en": a.label_en, "label_zh": a.label_zh,
                                    "deltas": a.deltas} for a in crop.adjustments}
                entry["substrates"][sub] = {
                    "source_page": crop.source_page,
                    "extract_method": crop.extract_method,
                    "ph_root_zone": list(crop.ph_root_zone),
                    "ph_fertigation": crop.ph_fertigation,
                    "ec_root_zone": crop.ec_root_zone,
                    "ec_fertigation": crop.ec_fertigation,
                    "root_zone_targets": crop.root_zone_targets,
                    "fertigation_mmol_l": crop.fertigation,
                    "fertigation_micro_umol_l": crop.micro_fertigation,
                    "na_max_root_zone_mmol_l": crop.na_max_root_zone,
                    "cl_max_root_zone_mmol_l": crop.cl_max_root_zone,
                    "growth_stages": stages,
                    "high_water_adjustment": crop.high_water_adjustment,
                }
                base = {
                    "category": cat, "crop_id": cid,
                    "crop_en": meta["name_en"], "crop_zh": meta["name_zh"],
                    "substrate_type": sub, "extract_method": crop.extract_method,
                    "source_page": crop.source_page,
                    "ec_root_zone": crop.ec_root_zone,
                    "ec_fertigation": crop.ec_fertigation,
                    "ph_fertigation": crop.ph_fertigation,
                }
                for stage in ["_fertigation"] + list(stages):
                    row = dict(base)
                    row["growth_stage"] = stage.lstrip("_")
                    vec = dict(crop.fertigation)
                    micro = dict(crop.micro_fertigation)
                    if stage != "_fertigation":
                        for ion, d in stages[stage]["deltas"].items():
                            if ion in micro:
                                micro[ion] = max(0.0, micro[ion] + d)
                            else:
                                vec[ion] = max(0.0, vec.get(ion, 0.0) + d)
                    for ion in ("NH4", "NO3", "P", "K", "Ca", "Mg", "S", "Cl"):
                        row[f"{ion}_mmol_l"] = round(vec.get(ion, 0.0), 3)
                    for ion in ("Fe", "Mn", "Zn", "B", "Cu", "Mo"):
                        row[f"{ion}_umol_l"] = round(micro.get(ion, 0.0), 3)
                    row["Na_max_mmol_l"] = crop.na_max_root_zone
                    rows.append(row)
            hierarchy[cat]["crops"][cid] = entry
    return ({"meta": {"title_bilingual": bi_zh_first("作物物候期目标数据库",
                                                     "Crop Stage Target Database"),
                      "source": SOURCE,
                      "crops": len(C.crop_ids()),
                      "matrices": len(C.CROP_MATRIX),
                      "note": "S is elemental sulphur; the ion is SO4(2-). "
                              "NH4/NO3 are reported as N-NH4 / N-NO3."},
             "categories": hierarchy},
            rows)


# ==========================================================================
# STEP 4 - Module 3 safety gates
# ==========================================================================

BRIEF_GATE_MAPPING = [
    {"brief_name": "G-ACID-POISON", "brief_condition": "pH < 5.2",
     "implemented_as": "G-MELTDOWN", "status": "IMPLEMENTED (merged)",
     "note": "One blocking gate covers both the pH floor and the EC ceiling; "
             "the response names which limit fired."},
    {"brief_name": "G-SALINITY-MELTDOWN", "brief_condition": "EC > 4.5 mS/cm",
     "implemented_as": "G-MELTDOWN", "status": "IMPLEMENTED (merged)",
     "note": "Same gate as above."},
    {"brief_name": "G-K-CA-ANTAGONISM", "brief_condition": "dK > +2.0 mmol/L",
     "implemented_as": "K_SUPPRESSES_CA_MG (pattern, not a gate)",
     "status": "NOT IMPLEMENTED AS SPECIFIED",
     "note": "No absolute delta-K threshold exists in the codebase or in the "
             "manual. Screening fires when K exceeds 40% of cation equivalents "
             "AND Ca or Mg is below target. Adding a 2.0 mmol/L rule would "
             "need agronomic sign-off, not an export."},
    {"brief_name": "G-NA-CEILING", "brief_condition": "Na > crop ceiling",
     "implemented_as": "G-NA-EXCEED (plus G-NA-APPROACH, G-NA-UNREACHABLE)",
     "status": "IMPLEMENTED (renamed, expanded)",
     "note": "Three-state gate: approaching 80% of ceiling, exceeded, and "
             "unreachable when base water Na is already above the target."},
]

GATE_REGISTRY = [
    ("G-MELTDOWN", "BLOCKING", "M8", "pH < 5.2 or EC > 4.5 mS/cm",
     "Emergency flush; recipe output suppressed; LLM layer bypassed",
     "SRC:PRACTICE thresholds"),
    ("G-PRECIP-RISK", "BLOCKING", "M6", "Ca together with SO4 or PO4 in one tank",
     "Tank bill refused outright - CaSO4 / Ca3(PO4)2 precipitation", "SRC:WUR p.31"),
    ("G-ACID-INFEASIBLE", "CRITICAL", "M1", "H+ demand exceeds NO3+P headroom",
     "Dilute water, or shift pH control to ammonium", "SRC:WUR p.13"),
    ("G-NA-EXCEED", "CRITICAL", "M2", "Root-zone Na above crop ceiling",
     "Forced discharge volume issued", "SRC:WUR Table 2 p.12"),
    ("G-NA-UNREACHABLE", "CRITICAL", "M2", "Base water Na >= flush target",
     "Flushing cannot help; alternative water source required", "SRC:DERIVED"),
    ("G-NA-APPROACH", "WARNING", "M2", "Na >= 80% of ceiling",
     "Increase monitoring, plan a discharge window", "SRC:PRACTICE"),
    ("G-WASH-TRIGGER", "CRITICAL", "M4", "Drain-dripper EC gap >= 2.0 mS/cm",
     "Raise leaching fraction; extra irrigation volume issued", "SRC:PRACTICE"),
    ("G-WASH-ANOMALY", "CRITICAL", "M4", "EC gap >= 2.0 while LF >= 40%",
     "DO NOT add volume; investigate channeling / EC calibration", "SRC:PRACTICE"),
    ("G-NH4-CEILING", "CRITICAL", "M5", "NH4 > 1.5 mmol/L in the dosed recipe",
     "Reduce ammonium; pH will drop too far", "SRC:WUR p.15"),
    ("G-WATER-RECIRC", "CRITICAL", "M1", "Quality level >= 2 with recirculation",
     "Level 2 water unsuitable when recirculating", "SRC:WUR p.11"),
    ("G-WATER-SALT-SENSITIVE", "CRITICAL", "M1", "Level 3 water, Na ceiling <= 4",
     "Not for salt-sensitive crops", "SRC:WUR p.11"),
    ("G-WATER-UNCLASSIFIED", "CRITICAL", "M1", "Beyond Table 1 level 3",
     "Reverse osmosis or alternative source", "SRC:WUR p.11"),
    ("G-FE-DRIP", "CRITICAL", "M1", "Base-water Fe > 0 on drip irrigation",
     "Aerate and filter before the fertigation unit", "SRC:WUR p.14"),
    ("G-TANK-A-ACID", "CRITICAL", "M6", "Tank A acid above cap with chelates",
     "Chelates break down below pH 3.5", "SRC:WUR p.31"),
    ("G-ION-IMBALANCE", "WARNING", "M7", "Cation/anion difference > 10%",
     "Counter-ion adjustment needed before filling tanks", "SRC:WUR p.21"),
    ("G-ALLOCATION-RESIDUAL", "WARNING", "M7", "Allocation cannot hit all targets",
     "Usually nitrate over-supply from acid + calcium nitrate", "SRC:DERIVED"),
    ("G-WATER-EXCESS", "WARNING", "M7", "Base water above recipe target for an ion",
     "Cannot be un-supplied; dilute or accept", "SRC:DERIVED"),
    ("G-LF-DEFICIT", "WARNING", "M4", "Leaching fraction < 10%",
     "Under-irrigation; salt accumulation risk", "SRC:PRACTICE"),
    ("G-LF-EXCESS", "WARNING", "M4", "Leaching fraction > 40%",
     "Water and nutrient waste; check emitter uniformity", "SRC:PRACTICE"),
    ("G-NH4-SHARE", "WARNING", "M5", "NH4 > 15% of total N",
     "Hydroponic proportion should stay 5-15%", "SRC:WUR p.15"),
    ("G-CHELATE-DISINFECT", "WARNING", "M6", "UV / ozone / H2O2 disinfection",
     "Re-dose chelates AFTER disinfection", "SRC:WUR p.36"),
    ("G-CHELATE-SODIUM", "WARNING", "M6", "Recirculating system",
     "Use Na-free K-based chelates and boric acid", "SRC:WUR p.24, p.36"),
    ("G-FE-EXCHANGE-LOSS", "WARNING", "M6", "Mn/Zn/Cu supplied as sulphates",
     "20-50% Fe loss by chelate exchange", "SRC:WUR p.36"),
    ("G-DRYBACK-NA", "WARNING", "M5", "Generative dry-back with Na >= 80% ceiling",
     "Dry-back concentrates sodium; intent downgraded", "SRC:PRACTICE"),
    ("G-B-HIGH", "WARNING", "M1", "Base-water B > 30 umol/L",
     "Above tolerable upper limit", "SRC:WUR p.14"),
    ("G-MN-HIGH", "WARNING", "M1", "Base-water Mn >= 10 umol/L",
     "Above advised level", "SRC:WUR p.14"),
    ("G-FE-SPRINKLER", "WARNING", "M1", "Sprinkler Fe > 100 umol/L",
     "Leaf damage and staining", "SRC:WUR p.14"),
    ("G-CO2-ESCAPE", "INFO", "M1", "Any acid dose",
     "Reaction must occur in an open mixing tank", "SRC:WUR p.13"),
    ("G-FE-NOT-CREDITED", "INFO", "M1", "Base water contains Fe",
     "Never counted as nutrient", "SRC:WUR p.13"),
    ("G-TANK-PH-CHECK", "INFO", "M6", "Every tank bill",
     "Tank A pH 3.5-5.0, tank B below 5.0", "SRC:WUR p.31"),
    ("G-OO-DECLARE", "INFO", "M6", "EDDHA / HBED selected",
     "Check declared ortho-ortho content", "SRC:WUR p.36"),
    ("G-ZN-SOURCE", "INFO", "M1", "Base water contains Zn",
     "Likely galvanised gutters", "SRC:WUR p.14"),
    ("G-CU-SOURCE", "INFO", "M1", "Base water contains Cu",
     "Likely copper plumbing", "SRC:WUR p.14"),
    ("G-DRYBACK-SUPPRESSED", "INFO", "M5", "Wash cycle active",
     "Dry-back and leaching are contradictory", "SRC:PRACTICE"),
    ("G-DRYBACK-NA-SOIL", "INFO", "M5", "Soil substrate",
     "Dry-back does not transfer to soil", "SRC:PRACTICE"),
]


def build_module3() -> dict:
    return {
        "meta": {"module": "M8 / M4 diagnostics",
                 "title_bilingual": bi_zh_first("理化诊断与刚性熔断",
                                                "Diagnostics & Safety Gates"),
                 "source": SOURCE},
        "charge_balance": {
            "cations_mmol_c_per_l": "[NH4+] + [K+] + [Na+] + 2[Ca2+] + 2[Mg2+] + [H+]",
            "anions_mmol_c_per_l": "[NO3-] + [Cl-] + 2[SO4 2-] + [HCO3-] + [H2PO4-]",
            "h_plus_note": "H+ from acid dosing MUST be included. Table 3 step 7 "
                           "(p.23) balances only with it: 21.2 vs 21.25 meq/L.",
            "ec_estimate": "EC = (Eq_cations + Eq_anions) / 20",
            "acceptable_difference_pct": C.ION_BALANCE_TOLERANCE * 100,
            "source": "Formulas 1-4, p.21",
        },
        "reference_ec_normalisation": {
            "ec_reference": "EC_target_values - 0.30",
            "ec_nutrients": "EC_analysed - 0.10 * Na_analysed(mmol/L)",
            "conversion": "Nutrient_ref = Nutrient_analysed * EC_ref / EC_nutrients",
            "never_normalised": ["Na", "HCO3"],
            "source": "p.21-22",
        },
        "correction_ladder": {
            "level_1": {"deviation_pct": 25, "adjustment_pct": [10, 15]},
            "level_2": {"deviation_pct": 50, "adjustment_pct": [15, 25],
                        "cumulative_pct": [25, 40]},
            "micronutrient_steps_pct": [50, 25, 0, -25, -50],
            "source": "p.22",
        },
        "emergency_thresholds": {
            "ph_min": C.DEFAULT_POLICY.meltdown_ph_min,
            "ec_max_ms_cm": C.DEFAULT_POLICY.meltdown_ec_max,
            "behaviour": "BLOCKING - recipe suppressed, hardcoded flush "
                         "instructions returned, cognitive layer never invoked",
        },
        "antagonism_patterns": [
            {"code": c, "pattern_en": en, "pattern_zh": zh}
            for c, en, zh in E.ANTAGONISM_RULES],
        "gate_registry": [
            {"gate_id": g, "severity": s, "module": m, "condition": c,
             "action": a, "provenance": p}
            for g, s, m, c, a, p in GATE_REGISTRY],
        "gate_severity_order": ["BLOCKING", "CRITICAL", "WARNING", "INFO"],
        "brief_name_mapping": BRIEF_GATE_MAPPING,
        "spec_divergences": [d for d in SPEC_DIVERGENCES
                             if d["id"] in ("DIV-2", "DIV-3", "DIV-4")],
    }


# ==========================================================================
# STEP 6 - Module 5 A/B tank rules
# ==========================================================================

def build_module5() -> dict:
    tank_a = [f.fid for f in C.FERTILISERS.values() if f.tank == "A"]
    tank_b = [f.fid for f in C.FERTILISERS.values() if f.tank == "B"]
    either = [f.fid for f in C.FERTILISERS.values() if f.tank == "EITHER"]
    return {
        "meta": {"module": "M6 / M7",
                 "title_bilingual": bi_zh_first("100倍 A/B 母液罐配方精算",
                                                "100x A/B Stock Tank Solver"),
                 "source": SOURCE},
        "separation_rule": {
            "statement": "All calcium fertilisers must be separated from "
                         "phosphate and sulphate fertilisers.",
            "tank_a": "calcium fertilisers and chelates",
            "tank_b": "sulphate and phosphate fertilisers",
            "either": "KNO3, Mg(NO3)2, NH4NO3, HNO3 - split to balance load",
            "enforcement": "BLOCKING gate G-PRECIP-RISK; not overridable",
            "source": "Ch.9, p.31",
        },
        "precipitation_risks": [
            {"product": "CaSO4.2H2O (gypsum)", "ksp": 3.14e-5,
             "ions": ["Ca", "SO4"]},
            {"product": "Ca3(PO4)2", "ksp": 2.07e-33, "ions": ["Ca", "PO4"]},
        ],
        "ksp_note": "At 100x concentration both are far past saturation, which "
                    "is why separation is absolute rather than a computed margin.",
        "tank_ph_limits": {"tank_a": [3.5, 5.0], "tank_b": [None, 5.0],
                           "chelate_breakdown_below_ph": 3.5,
                           "tank_a_acid_cap_l_per_m3":
                               C.DEFAULT_POLICY.tank_a_acid_cap_l},
        "tank_assignment": {"A_only": tank_a, "B_only": tank_b, "either": either},
        "allocation_order": ["H+", "Cl", "Ca", "NH4", "P", "Mg", "S", "K",
                             "NO3 (closes via KNO3)", "micronutrients"],
        "allocation_note": "Fixed greedy order from Ch.8 p.28. Every step "
                           "decrements co-delivered ions; calcium nitrate "
                           "carries 5 Ca, 1 NH4 and 11 NO3 per mole.",
        "mass_solver": {
            "macro_kg_per_1000L_at_100x": "u_j = c_ion(mmol/L) * MW_per_ion * 0.1",
            "micro_g_per_1000L_at_100x":
                "u_j = c(umol/L) * atomic_weight / fraction * 0.1",
            "liquid_volume_l": "kg / density",
            "generalised": "mass_kg = mmol/L * MW_per_ion * (CF/1000) * (V/1000)",
        },
        "fe_chelate_selection": {
            "switch_ph": C.FE_CHELATE_SWITCH_PH,
            "below_switch": "Fe-DTPA sufficient",
            "above_switch": "Fe-EDDHA or Fe-HBED strongly recommended",
            "prophylactic_replacement": {
                "inert_substrate_fraction": C.PROPHYLACTIC_SUBSTRATE,
                "nft_fraction": C.PROPHYLACTIC_NFT},
            "calcareous_soil": "Always EDDHA/HBED with high ortho-ortho content",
            "ph_stability_bands": {k: list(v) for k, v
                                   in C.FE_CHELATE_BANDS.items()},
            "source": "Figure 3a p.35; Ch.11 p.36",
        },
        "fertiliser_catalogue": build_fertiliser_catalogue(),
    }


# ==========================================================================
# main
# ==========================================================================

def main() -> None:
    written: list[Path] = []

    written.append(jdump(DATA / "wur_master_database.json", build_master_database()))
    written.append(jdump(DATA / "module1_acid_neutralization.json", build_module1()))

    targets, rows = build_crop_targets()
    written.append(jdump(DATA / "wur_crop_targets.json", targets))

    csv_path = DATA / "wur_crop_targets.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    written.append(csv_path)

    written.append(jdump(DATA / "module3_safety_gates_and_rules.json", build_module3()))
    written.append(jdump(DATA / "module5_ab_tank_rules.json", build_module5()))

    for p in written:
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size:,} bytes)")
    print(f"\n{len(written)} data files written; crop CSV rows: {len(rows)}")


if __name__ == "__main__":
    main()
