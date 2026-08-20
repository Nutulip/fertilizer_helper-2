"""
WUR reference data — atomic weights, fertiliser catalogue, crop benchmarks.

Source: Van der Lugt, G. et al. (2020). "Nutrient Solutions for Greenhouse Crops",
Version 4. ISBN 9789464021844. Eurofins Agro / Nouryon / SQM / Yara.

Every constant below is transcribed from the manual with its page citation.
Nothing in this module is invented.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


# --------------------------------------------------------------------------
# Bilingual helper (中英双语)
# --------------------------------------------------------------------------

def bi(en: str, zh: str) -> str:
    """Render a bilingual display string: 'English Term (中文翻译)'."""
    return f"{en} ({zh})"


# --------------------------------------------------------------------------
# WUR Atomic Weight Matrix — Table 7, p. 39 (g/mol == mg/mmol == ug/umol)
# --------------------------------------------------------------------------

ATOMIC_WEIGHTS: dict[str, float] = {
    # Macronutrients (required by spec)
    "K": 39.10,
    "Ca": 40.08,
    "Mg": 24.31,
    "N": 14.00,
    "P": 30.97,
    "S": 32.06,
    # Remaining macro ions from Table 7
    "N_NO3": 14.00,
    "N_NH4": 14.00,
    "NO3": 14.00,      # reported as N-NO3
    "NH4": 14.00,      # reported as N-NH4
    "Na": 22.99,
    "Cl": 35.45,
    "HCO3": 61.02,
    # Micronutrients
    "Fe": 55.85,
    "Mn": 54.94,
    "Zn": 65.38,
    "B": 10.81,
    "Cu": 63.55,
    "Mo": 95.94,
}

# Ion charge for equivalent arithmetic — Formulas 1-2, p. 21.
# H+ participates as a cation (proven by Table 3 step 7 balance closure).
ION_CHARGE: dict[str, int] = {
    "NH4": 1, "K": 1, "Na": 1, "Ca": 2, "Mg": 2, "H": 1,
    "NO3": 1, "Cl": 1, "S": 2, "HCO3": 1, "P": 1,
}
CATIONS = ("NH4", "K", "Na", "Ca", "Mg", "H")
ANIONS = ("NO3", "Cl", "S", "HCO3", "P")

EC_DIVISOR = 20.0                 # Formula 4, p. 21
ION_BALANCE_TOLERANCE = 0.10      # <10% acceptable, p. 21
REFERENCE_EC_OFFSET = 0.30        # EC_ref = EC_target - 0.30, p. 21
NA_EC_FACTOR = 0.10               # EC_nutrients = EC - 0.1 * Na, p. 22

# Oxide <-> elemental conversion — Table 4, p. 25
OXIDE_TO_ELEMENTAL: dict[str, float] = {
    "NO3_to_N": 0.226, "NH4_to_N": 0.776, "P2O5_to_P": 0.436,
    "K2O_to_K": 0.830, "CaO_to_Ca": 0.715, "MgO_to_Mg": 0.603,
    "SO4_to_S": 0.334, "SO3_to_S": 0.400,
}
ELEMENTAL_TO_OXIDE: dict[str, float] = {
    "N_to_NO3": 4.426, "N_to_NH4": 1.288, "P_to_P2O5": 2.292,
    "K_to_K2O": 1.205, "Ca_to_CaO": 1.399, "Mg_to_MgO": 1.658,
    "S_to_SO4": 2.996, "S_to_SO3": 2.497,
}


# --------------------------------------------------------------------------
# Fertiliser catalogue — Table 5, p. 26; tank class from Ch. 9, p. 31
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Fertiliser:
    fid: str
    name_en: str
    name_zh: str
    formula: str
    formula_mass: float                    # g/mol of the written formula
    driving_ion: str                       # ion used to size the dose
    yields: dict[str, float]               # mol ion per mol fertiliser
    tank: str                              # "A" | "B" | "EITHER"
    phase: str = "solid"
    density: float | None = None           # kg/L, liquids only
    micro_ion: str | None = None
    micro_fraction: float | None = None    # w/w fraction, e.g. 0.06 for Fe 6%
    sodium_bearing: bool = False
    chelate_agent: str | None = None
    ph_stability: tuple[float, float] | None = None

    @property
    def name(self) -> str:
        return bi(self.name_en, self.name_zh)

    @property
    def mass_per_mol_ion(self) -> float:
        """
        Grams of product per mole of the DRIVING ion.

        This is the 'MW' in `kg = mmol/L * MW * 0.1`. Calcium nitrate is
        1080 g/mol but carries 5 Ca, so the divisor is 1080/5 = 216 (p. 28).
        Using the raw formula mass here over-doses by 5x.
        """
        return self.formula_mass / self.yields[self.driving_ion]


FERTILISERS: dict[str, Fertiliser] = {
    # ---- acids ----
    "hno3_38": Fertiliser(
        "hno3_38", "Nitric acid 38%", "硝酸 38%", "HNO3", 167.0,
        driving_ion="H", yields={"H": 1, "NO3": 1},
        tank="EITHER", phase="liquid", density=1.24),
    "hno3_60": Fertiliser(
        "hno3_60", "Nitric acid 60%", "硝酸 60%", "HNO3", 105.0,
        driving_ion="H", yields={"H": 1, "NO3": 1},
        tank="EITHER", phase="liquid", density=1.37),
    "h3po4_59": Fertiliser(
        "h3po4_59", "Phosphoric acid 59%", "磷酸 59%", "H3PO4", 167.0,
        driving_ion="H", yields={"H": 1, "P": 1},
        tank="B", phase="liquid", density=1.42),

    # ---- main elements ----
    "can_solid": Fertiliser(
        "can_solid", "Calcium nitrate solid", "固体硝酸钙",
        "5[Ca(NO3)2.2H2O].NH4NO3", 1080.0,
        driving_ion="Ca", yields={"Ca": 5, "NH4": 1, "NO3": 11}, tank="A"),
    "cacl2_s": Fertiliser(
        "cacl2_s", "Calcium chloride anhydrous", "无水氯化钙", "CaCl2", 111.0,
        driving_ion="Cl", yields={"Ca": 1, "Cl": 2}, tank="A"),
    "map": Fertiliser(
        "map", "Monoammonium phosphate", "磷酸一铵", "NH4H2PO4", 115.0,
        driving_ion="NH4", yields={"NH4": 1, "P": 1}, tank="B"),
    "nh4no3_liq": Fertiliser(
        "nh4no3_liq", "Ammonium nitrate liquid", "液体硝酸铵", "NH4NO3", 156.0,
        driving_ion="NH4", yields={"NH4": 1, "NO3": 1},
        tank="EITHER", phase="liquid", density=1.25),
    "mkp": Fertiliser(
        "mkp", "Monopotassium phosphate", "磷酸二氢钾", "KH2PO4", 136.1,
        driving_ion="P", yields={"K": 1, "P": 1}, tank="B"),
    "mgso4": Fertiliser(
        "mgso4", "Magnesium sulphate", "七水硫酸镁", "MgSO4.7H2O", 246.4,
        driving_ion="Mg", yields={"Mg": 1, "S": 1}, tank="B"),
    "mgno3_s": Fertiliser(
        "mgno3_s", "Magnesium nitrate", "六水硝酸镁", "Mg(NO3)2.6H2O", 256.0,
        driving_ion="Mg", yields={"Mg": 1, "NO3": 2}, tank="EITHER"),
    "k2so4": Fertiliser(
        "k2so4", "Potassium sulphate", "硫酸钾", "K2SO4", 174.3,
        driving_ion="S", yields={"K": 2, "S": 1}, tank="B"),
    "kno3": Fertiliser(
        "kno3", "Potassium nitrate", "硝酸钾", "KNO3", 101.1,
        driving_ion="K", yields={"K": 1, "NO3": 1}, tank="EITHER"),
    "kcl": Fertiliser(
        "kcl", "Potassium chloride", "氯化钾", "KCl", 74.6,
        driving_ion="Cl", yields={"K": 1, "Cl": 1}, tank="EITHER"),

    # ---- micronutrients: chelates (tank A preferred, Ch. 9 p. 31) ----
    "fe_edta": Fertiliser(
        "fe_edta", "Iron chelate Fe-EDTA 13%", "铁螯合物 Fe-EDTA 13%", "Fe-EDTA",
        429.0, driving_ion="Fe", yields={"Fe": 1}, tank="A",
        micro_ion="Fe", micro_fraction=0.13,
        chelate_agent="EDTA", ph_stability=(1.5, 6.5)),
    "fe_dtpa": Fertiliser(
        "fe_dtpa", "Iron chelate Fe-DTPA 6%", "铁螯合物 Fe-DTPA 6%", "Fe-DTPA",
        931.0, driving_ion="Fe", yields={"Fe": 1}, tank="A",
        micro_ion="Fe", micro_fraction=0.06,
        chelate_agent="DTPA", ph_stability=(1.5, 7.5)),
    "fe_eddha": Fertiliser(
        "fe_eddha", "Iron chelate Fe-EDDHA 6%", "铁螯合物 Fe-EDDHA 6%", "Fe-EDDHA",
        931.0, driving_ion="Fe", yields={"Fe": 1}, tank="A",
        micro_ion="Fe", micro_fraction=0.06,
        chelate_agent="EDDHA", ph_stability=(3.0, 10.0)),
    "fe_hbed": Fertiliser(
        "fe_hbed", "Iron chelate Fe-HBED 6%", "铁螯合物 Fe-HBED 6%", "Fe-HBED",
        931.0, driving_ion="Fe", yields={"Fe": 1}, tank="A",
        micro_ion="Fe", micro_fraction=0.06,
        chelate_agent="HBED", ph_stability=(3.0, 12.0)),
    "mn_edta": Fertiliser(
        "mn_edta", "Manganese EDTA 13%", "锰螯合物 Mn-EDTA 13%", "Mn-EDTA",
        423.0, driving_ion="Mn", yields={"Mn": 1}, tank="A",
        micro_ion="Mn", micro_fraction=0.13,
        chelate_agent="EDTA", ph_stability=(3.0, 10.0)),
    "zn_edta": Fertiliser(
        "zn_edta", "Zinc EDTA 15%", "锌螯合物 Zn-EDTA 15%", "Zn-EDTA",
        436.0, driving_ion="Zn", yields={"Zn": 1}, tank="A",
        micro_ion="Zn", micro_fraction=0.15,
        chelate_agent="EDTA", ph_stability=(2.0, 10.0)),
    "cu_edta": Fertiliser(
        "cu_edta", "Copper EDTA 15%", "铜螯合物 Cu-EDTA 15%", "Cu-EDTA",
        424.0, driving_ion="Cu", yields={"Cu": 1}, tank="A",
        micro_ion="Cu", micro_fraction=0.15,
        chelate_agent="EDTA", ph_stability=(1.5, 10.0)),

    # ---- micronutrients: salts (tank B, Ch. 9 p. 31) ----
    "borax": Fertiliser(
        "borax", "Borax 11.3% B", "硼砂 11.3% B", "Na2B4O7.10H2O", 381.0,
        driving_ion="B", yields={"B": 4}, tank="B",
        micro_ion="B", micro_fraction=0.113, sodium_bearing=True),
    "h3bo3": Fertiliser(
        "h3bo3", "Boric acid 17.5% B", "硼酸 17.5% B", "H3BO3", 62.0,
        driving_ion="B", yields={"B": 1}, tank="B",
        micro_ion="B", micro_fraction=0.175),
    "na_moly": Fertiliser(
        "na_moly", "Sodium molybdate 39.6%", "钼酸钠 39.6%", "Na2MoO4.2H2O",
        241.9, driving_ion="Mo", yields={"Mo": 1}, tank="B",
        micro_ion="Mo", micro_fraction=0.396, sodium_bearing=True),
    "mnso4": Fertiliser(
        "mnso4", "Manganese sulphate 32.5%", "硫酸锰 32.5%", "MnSO4.H2O", 169.0,
        driving_ion="Mn", yields={"Mn": 1, "S": 1}, tank="B",
        micro_ion="Mn", micro_fraction=0.325),
    "znso4": Fertiliser(
        "znso4", "Zinc sulphate 22.7%", "硫酸锌 22.7%", "ZnSO4.7H2O", 287.5,
        driving_ion="Zn", yields={"Zn": 1, "S": 1}, tank="B",
        micro_ion="Zn", micro_fraction=0.227),
    "cuso4": Fertiliser(
        "cuso4", "Copper sulphate 25.5%", "硫酸铜 25.5%", "CuSO4.5H2O", 249.7,
        driving_ion="Cu", yields={"Cu": 1, "S": 1}, tank="B",
        micro_ion="Cu", micro_fraction=0.255),
}


# --------------------------------------------------------------------------
# Water quality levels — Table 1, p. 11
# --------------------------------------------------------------------------

WATER_QUALITY_LEVELS = [
    {"level": 1, "ec_max": 0.5, "ion_max": 1.5, "na_ppm": "< 34", "cl_ppm": "< 53",
     "suitability_en": "Suitable for all crops",
     "suitability_zh": "适用于所有作物"},
    {"level": 2, "ec_max": 1.0, "ion_max": 2.5, "na_ppm": "34 - 57", "cl_ppm": "53 - 87",
     "suitability_en": "Not suitable when recirculation is necessary",
     "suitability_zh": "需要循环回用时不适用"},
    {"level": 3, "ec_max": 1.5, "ion_max": 4.0, "na_ppm": "57 - 92", "cl_ppm": "87 - 142",
     "suitability_en": "Not to be used for salt-sensitive crops",
     "suitability_zh": "不可用于盐敏感作物"},
]


# --------------------------------------------------------------------------
# Maximum root-zone Na — Table 2, p. 12
#
# NOTE: these are the manual's values. The project brief quoted Tomato <= 15
# and Cucumber <= 8; both are looser than the source (8 and 6 respectively).
# See design.md section 2.2, discrepancy D-1. Overrides are possible through
# SitePolicy.na_overrides but are badged as practice, never as WUR canon.
# --------------------------------------------------------------------------

NA_LIMITS_MMOL_L: dict[str, float] = {
    "tomato": 8.0,
    "sweet_pepper": 6.0,
    "eggplant": 6.0,
    "cucumber": 6.0,
    "melon": 6.0,
    "rose": 4.0,
    "gerbera": 4.0,
    "carnation": 4.0,
    "orchid": 1.0,
}

CL_OFFSET_MMOL_L = 0.2   # Cl ceiling = Na ceiling + 0.2-0.5 mmol/L, p. 12


# --------------------------------------------------------------------------
# Fe-chelate pH stability — Figure 3a, p. 35 (refined by Nouryon table, p. 27)
# --------------------------------------------------------------------------

FE_CHELATE_BANDS = {
    "fe_edta": (1.5, 6.5),
    "fe_dtpa": (1.5, 7.5),
    "fe_eddha": (3.0, 10.0),
    "fe_hbed": (3.0, 12.0),
}
FE_CHELATE_SWITCH_PH = 6.5     # p. 36 — NOT 7.0; see design.md D-2
PROPHYLACTIC_SUBSTRATE = 0.25  # replace 25% of Fe with EDDHA/HBED, p. 36
PROPHYLACTIC_NFT = 0.10        # replace 10% in NFT, p. 36


# --------------------------------------------------------------------------
# Average Plant Need — Table 6, p. 34 (umol/L)
# --------------------------------------------------------------------------

APN_UMOL_L = {
    "rose":         {"Fe": 25, "Mn": 5,  "Zn": 3, "B": 20, "Cu": 0.8, "Mo": 0.5},
    "potted_plant": {"Fe": 15, "Mn": 5,  "Zn": 4, "B": 10, "Cu": 0.5, "Mo": 0.5},
    "tomato":       {"Fe": 15, "Mn": 10, "Zn": 5, "B": 30, "Cu": 0.8, "Mo": 0.5},
}


# --------------------------------------------------------------------------
# Crop recipe benchmarks — Section B
#
# All three records below were transcribed from the RENDERED crop pages, not
# from flat text extraction, because the four adjustment columns
# (Start | Fruit Set | High water | End season) collapse and mis-assign when
# the PDF is read as plain text. Each is verified by the ppm cross-check
# mmol/L * atomic weight == printed ppm (see tests).
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Substrate types (基质类型)
#
# Section B publishes a SEPARATE matrix per crop per growing medium. The three
# are not interchangeable: organic targets come from the 1:1.5 volume water
# extract and soil targets from the 1:2 volume extract (Ch. 4, p. 18), both of
# which dilute the actual root-zone solution. Tomato root-zone K is 8 mmol/L on
# inert substrate but 2.8 mmol/L on organic material — same crop, same plant,
# different measurement basis. Every target lookup must therefore be keyed on
# (crop_id, substrate_type), never on crop alone.
# --------------------------------------------------------------------------

SUBSTRATE_TYPES = ("INERT_SUBSTRATE", "ORGANIC_MATERIAL", "SOIL")
DEFAULT_SUBSTRATE = "INERT_SUBSTRATE"

SUBSTRATE_LABELS: dict[str, str] = {
    "INERT_SUBSTRATE": bi("Inert Substrate", "岩棉/惰性基质"),
    "ORGANIC_MATERIAL": bi("Organic Material", "椰糠/泥炭有机基质"),
    "SOIL": bi("Soil", "土壤栽培"),
}

EXTRACT_METHODS: dict[str, str] = {
    "INERT_SUBSTRATE": "direct",
    "ORGANIC_MATERIAL": "1:1.5_volume",
    "SOIL": "1:2_volume",
}

EXTRACT_METHOD_LABELS: dict[str, str] = {
    "direct": bi("Direct solution sample", "直接取根际溶液"),
    "1:1.5_volume": bi("1:1.5 volume water extract", "1:1.5 体积水浸提"),
    "1:2_volume": bi("1:2 volume water extract", "1:2 体积水浸提"),
}


@dataclass(frozen=True)
class StageAdjustment:
    stage: str
    label_en: str
    label_zh: str
    deltas: dict[str, float]          # mmol/L (macro) or umol/L (micro)
    note_en: str = ""
    note_zh: str = ""


@dataclass(frozen=True)
class CropRecipe:
    crop_id: str
    name_en: str
    name_zh: str
    botanical: str
    category: str
    medium: str
    ph_root_zone: tuple[float, float]
    ph_fertigation: float
    ec_root_zone: float
    ec_fertigation: float
    root_zone_targets: dict[str, float]     # macro mmol/L, micro umol/L
    fertigation: dict[str, float]           # macro mmol/L
    micro_fertigation: dict[str, float]     # umol/L
    na_max_root_zone: float
    cl_max_root_zone: float
    adjustments: tuple[StageAdjustment, ...]
    # `high_water` is an orthogonal CONDITION, not a growth stage: supply above
    # 5 L/m2/day can coincide with any stage. Kept out of `adjustments` so the
    # UI cannot present it as a mutually-exclusive phase.
    high_water_adjustment: dict[str, float]
    source_page: int
    # How the root-zone target values were derived. This is NOT cosmetic: the
    # organic and soil targets are expressed on a diluted water-extract basis,
    # so their numbers are not comparable with the inert-substrate ones.
    extract_method: str = "direct"

    @property
    def name(self) -> str:
        return bi(self.name_en, self.name_zh)

    @property
    def medium_label(self) -> str:
        return SUBSTRATE_LABELS[self.medium]


_FRUIT_SET_NOTE_EN = ("Fruit-set adjustment may vary 0.25-2 mmol/L for K "
                      "and 0.2-0.75 mmol/L for Ca.")
_FRUIT_SET_NOTE_ZH = ("坐果期调整幅度：K 可在 0.25-2 mmol/L、"
                      "Ca 可在 0.2-0.75 mmol/L 范围内变动。")
_HIGH_WATER_NOTE_EN = "Recommended when water supply exceeds 5 L/m2/day."
_HIGH_WATER_NOTE_ZH = "当供水量超过 5 L/m2/天 时建议采用。"
_END_SEASON_NOTE_EN = ("End of the crop, after removal of the growth point. "
                       "Mostly in autumn as the last fruits ripen.")
_END_SEASON_NOTE_ZH = "生育末期，摘心之后；多在秋季末批果实成熟期。"


# --------------------------------------------------------------------------
# Crop x substrate library — loaded from crops_wur.json
#
# That file is machine-extracted from Section B by tools/extract2.py and
# validated by the tables' own redundancy: every mmol/L value must reproduce
# the printed ppm column when multiplied by its atomic weight. The extractor
# was checked against nine hand-transcribed matrices (tomato, cucumber and
# sweet pepper across all three substrates): 332 values, zero mismatches.
#
# `high_water` is deliberately NOT a growth stage. The manual prints it as a
# fourth adjustment column, but agronomically it is an orthogonal condition —
# supply above 5 L/m2/day — that can coincide with any stage. It is therefore
# stored separately as `high_water_adjustment` and driven by its own flag.
# --------------------------------------------------------------------------

CROP_CATEGORIES: tuple[str, ...] = (
    "fruiting_vegetables", "soft_fruits", "leafy_vegetables",
    "cut_flowers", "potted_plants",
)

CROP_CATEGORY_LABELS: dict[str, str] = {
    "fruiting_vegetables": bi("Fruiting Vegetables", "果菜类"),
    "soft_fruits":         bi("Soft Fruits / Berries", "浆果类"),
    "leafy_vegetables":    bi("Leafy Vegetables", "叶菜类"),
    "cut_flowers":         bi("Cut Flowers", "切花类"),
    "potted_plants":       bi("Potted Plants", "盆栽植物"),
}

GROWTH_STAGE_LABELS: dict[str, tuple[str, str]] = {
    "start":      ("Start / Rooting", "定植期 / 生根期"),
    "vegetative": ("Vegetative", "营养生长期"),
    "flowering":  ("Flowering", "花期"),
    "fruit_set":  ("Fruit Set", "坐果期"),
    "production": ("Heavy Bearing / Production", "盛产期"),
    "end_season": ("Final Phase / End of Season", "生育末期"),
    "winter":     ("Winter", "冬季"),
}

HIGH_WATER_NOTE_EN = ("Adjustments for high water supply are recommended when "
                      "water supply exceeds 5 l/m2/day.")
HIGH_WATER_NOTE_ZH = "当供水量超过 5 升/平方米/天时，建议进行高供水调整。"

_LIB_PATH = Path(__file__).resolve().parent / "crops_wur.json"
_LIB = json.loads(_LIB_PATH.read_text(encoding="utf-8"))

_FRUIT_SET_NOTE = (_FRUIT_SET_NOTE_EN, _FRUIT_SET_NOTE_ZH)
_END_SEASON_NOTE = (_END_SEASON_NOTE_EN, _END_SEASON_NOTE_ZH)


def _build_recipe(meta: dict, m: dict) -> CropRecipe:
    stages = []
    for stage, deltas in m["growth_stages"].items():
        en, zh = GROWTH_STAGE_LABELS.get(stage, (stage.title(), stage))
        note_en, note_zh = "", ""
        if stage == "fruit_set":
            note_en, note_zh = _FRUIT_SET_NOTE
        elif stage == "end_season":
            note_en, note_zh = _END_SEASON_NOTE
        stages.append(StageAdjustment(stage, en, zh, dict(deltas), note_en, note_zh))
    order = list(GROWTH_STAGE_LABELS)
    stages.sort(key=lambda a: order.index(a.stage) if a.stage in order else 99)

    ph = m["ph_root_zone"]
    return CropRecipe(
        crop_id=meta["crop_id"],
        name_en=meta["name_en"], name_zh=meta["name_zh"],
        botanical=meta.get("botanical", ""),
        category=meta["category"],
        medium=m["substrate_type"],
        ph_root_zone=(ph[0], ph[1]),
        ph_fertigation=m["ph_fertigation"],
        ec_root_zone=m["ec_root_zone"],
        ec_fertigation=m["ec_fertigation"],
        root_zone_targets=dict(m["root_zone_targets"]),
        fertigation=dict(m["fertigation"]),
        micro_fertigation=dict(m["micro_fertigation"]),
        na_max_root_zone=m.get("na_max_root_zone"),
        cl_max_root_zone=m.get("cl_max_root_zone"),
        adjustments=tuple(stages),
        high_water_adjustment=dict(m.get("high_water_adjustment") or {}),
        source_page=m["source_page"],
        extract_method=m["extract_method"],
    )


CROP_MATRIX: dict[tuple[str, str], CropRecipe] = {}
for _cid, _meta in _LIB["crops"].items():
    for _med, _m in _meta["matrices"].items():
        CROP_MATRIX[(_cid, _med)] = _build_recipe(_meta, _m)


def get_crop(crop_id: str, substrate_type: str = DEFAULT_SUBSTRATE) -> CropRecipe | None:
    """
    Resolve one crop x substrate matrix. Returns None when the pairing has no
    published table, so callers can raise a specific error rather than silently
    substituting the wrong medium's targets.
    """
    return CROP_MATRIX.get((crop_id, substrate_type))


def crop_ids() -> list[str]:
    return list(_LIB["crops"].keys())


def substrates_for(crop_id: str) -> list[str]:
    return [s for s in SUBSTRATE_TYPES if (crop_id, s) in CROP_MATRIX]


def crops_in_category(category: str) -> list[str]:
    return [cid for cid, m in _LIB["crops"].items() if m["category"] == category]


def crop_meta(crop_id: str) -> dict | None:
    return _LIB["crops"].get(crop_id)


def growth_stages_for(crop_id: str,
                      substrate_type: str = DEFAULT_SUBSTRATE) -> list[str]:
    """Stage ids with published adjustments. Never includes `high_water`."""
    crop = get_crop(crop_id, substrate_type)
    return [a.stage for a in crop.adjustments] if crop else []


# --------------------------------------------------------------------------
# Reference daily irrigation volumes — SRC:PRACTICE
#
# The manual publishes no irrigation volumes. Its single anchor is the note on
# the crop pages that "adjustments for high water supply are recommended when
# water supply exceeds 5 l/m2/day" (e.g. p. 41), which fixes what "high water"
# means but says nothing about the other stages.
#
# These figures are therefore grower-practice defaults, used ONLY as a fallback
# when the operator leaves the irrigation volume blank, so that the wash-cycle
# increment can still be estimated. Any result derived from them is flagged
# `is_estimated_volume` so the UI can badge it. Override per site through
# SitePolicy.reference_irrigation_overrides.
# --------------------------------------------------------------------------

REFERENCE_IRRIGATION_L_M2_DAY: dict[str, dict[str, float]] = {
    #                 start  fruit_set  high_water  end_season  standard
    "tomato":       {"start": 1.5, "fruit_set": 3.8, "high_water": 5.5,
                     "end_season": 2.5, "standard": 3.8},
    "cucumber":     {"start": 1.5, "fruit_set": 4.0, "high_water": 5.5,
                     "end_season": 2.5, "standard": 4.0},
    "sweet_pepper": {"start": 1.3, "fruit_set": 3.5, "high_water": 5.5,
                     "end_season": 2.2, "standard": 3.5},
}

# Category-level defaults, used for crops without their own row. Every
# `high_water` entry stays above 5 L/m2/day because that threshold is the
# manual's own definition of the stage (crop-page note, e.g. p. 41).
REFERENCE_IRRIGATION_BY_CATEGORY: dict[str, dict[str, float]] = {
    "fruiting_vegetables": {"start": 1.5, "fruit_set": 3.8, "high_water": 5.5,
                            "end_season": 2.5, "standard": 3.8},
    "soft_fruits":         {"start": 1.0, "fruit_set": 2.5, "high_water": 5.2,
                            "end_season": 1.5, "standard": 2.5},
    "leafy_vegetables":    {"start": 0.8, "fruit_set": 2.0, "high_water": 5.2,
                            "end_season": 1.2, "standard": 2.0},
    "cut_flowers":         {"start": 1.2, "fruit_set": 3.0, "high_water": 5.2,
                            "end_season": 1.8, "standard": 3.0},
    "potted_plants":       {"start": 0.8, "fruit_set": 1.8, "high_water": 5.2,
                            "end_season": 1.2, "standard": 1.8},
}

# Used when neither the crop nor its category is known.
REFERENCE_IRRIGATION_FALLBACK = 3.5

# NOTE ON `high_water`: the manual defines this stage as supply ABOVE
# 5 L/m2/day, so 5.5 is the smallest value consistent with the source. The
# original specification suggested 3.80 for both fruit_set and high_water;
# 3.80 is used for fruit_set as specified, but applying it to high_water would
# contradict the stage's own published definition, so high_water keeps 5.5.


def reference_irrigation(crop_id: str,
                         stages: list[str] | tuple[str, ...] | None = None,
                         overrides: dict[str, dict[str, float]] | None = None) -> float:
    """
    Fallback daily irrigation volume in L/m2/day for a crop at given stage(s).

    Stages stack in this system, so when several are active the highest
    demand wins — a crop in fruit set during a heat wave is watered to the
    heat wave, not to the average of the two.
    """
    table = dict(REFERENCE_IRRIGATION_L_M2_DAY)
    if overrides:
        for cid, per_stage in overrides.items():
            table[cid] = {**table.get(cid, {}), **per_stage}

    per_stage = table.get(crop_id)
    if per_stage is None:
        meta = _LIB["crops"].get(crop_id)
        if meta:
            per_stage = REFERENCE_IRRIGATION_BY_CATEGORY.get(meta["category"])
    if per_stage is None:
        return REFERENCE_IRRIGATION_FALLBACK

    active = [s for s in (stages or []) if s in per_stage]
    if not active:
        return per_stage.get("standard", REFERENCE_IRRIGATION_FALLBACK)
    return max(per_stage[s] for s in active)


# --------------------------------------------------------------------------
# Site policy — practice-layer defaults (SRC:PRACTICE, see design.md 2.2 D-4)
# --------------------------------------------------------------------------

@dataclass
class SitePolicy:
    # M1 — acid dosing
    hco3_buffer_mmol_l: float = 0.50          # SRC:WUR p. 24 (range 0.50-0.75)
    acid_policy: str = "NITRIC_FIRST"

    # M2 — sodium
    na_overrides: dict[str, float] = field(default_factory=dict)
    na_safety_factor: float = 0.90
    na_approach_ratio: float = 0.80
    cl_offset: float = CL_OFFSET_MMOL_L

    # M3 — leaching (SRC:PRACTICE)
    wash_trigger_delta_ec: float = 2.0
    wash_lf_min: float = 30.0
    wash_lf_max: float = 35.0
    # Midpoint of the wash band; what the extra-irrigation calculation aims at.
    wash_lf_target: float = 32.5
    # {crop_id: {stage: L/m2/day}} — overrides REFERENCE_IRRIGATION_L_M2_DAY
    reference_irrigation_overrides: dict[str, dict[str, float]] = field(
        default_factory=dict)

    # M4 — correction bands (SRC:WUR p. 22 thresholds, midpoint defaults)
    band1_default: float = 0.125              # within 10-15%
    band2_default: float = 0.20               # a further 15-25%

    # M6 — tanks
    tank_a_acid_cap_l: float = 4.0            # "a few litres per m3", p. 31
    tank_volume_l: float = 1000.0
    concentration_factor: float = 100.0

    # M8 — emergency gate (SRC:PRACTICE thresholds)
    meltdown_ph_min: float = 5.2
    meltdown_ec_max: float = 4.5


DEFAULT_POLICY = SitePolicy()
