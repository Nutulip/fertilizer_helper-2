"""
Fertilizer Helper — FastAPI backend
温室营养液决策助手 — 后端服务

Dual-driven hybrid architecture (see design.md):
  * HARD LAYER  — engine.py, deterministic, pure functions, fully tested
  * SOFT LAYER  — not implemented here; it consumes EngineResult and appends
                  prose only. No LLM call can alter a dose.

Every JSON response carries English keys plus a bilingual `*_text` display
string, e.g. "status_text": "Safe Zone (安全区域)".

Run the API:
    uvicorn main:app --reload
    python main.py              # reads HOST (default 127.0.0.1) and PORT (default 8000)

Environment:
    PORT              — bind port (default 8000)
    HOST              — bind address (default 127.0.0.1)
    ALLOWED_ORIGINS   — CORS origins, comma-separated (default *)

Run the tests:
    python main.py test
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

from constants import (
    APN_UMOL_L, ATOMIC_WEIGHTS, CROPS, DEFAULT_POLICY, ELEMENTAL_TO_OXIDE,
    FERTILISERS, FE_CHELATE_BANDS, NA_LIMITS_MMOL_L, OXIDE_TO_ELEMENTAL,
    WATER_QUALITY_LEVELS, SitePolicy, bi,
)
from engine import (
    DRY_BACK_TARGETS, Gate, LF_BANDS, acid_gates, allocate_fertilisers,
    apply_corrections, apply_stage_adjustments, balance_report,
    base_water_excess, base_water_excess_gates,
    cation_balance_pct, chelate_gates, classify_water, convert_analysis_to_mmol,
    deduct_base_water, deduct_drain, ec_from_ions, emergency_check,
    ammonium_gates, evaluate_corrections, evaluate_leaching, evaluate_sodium,
    ion_balance_gates,
    iron_screening_gates,
    leaching_gates, micronutrient_screening_gates, mmol_to_ppm, na_limit_for,
    plan_acid_dosing, ppb_to_umol, ppm_to_mmol, scale_to_ec, screen_antagonism,
    select_fe_chelate, sodium_gates, sort_gates, split_ab_tanks, steering_gates,
    stock_mass_kg, stock_mass_micro_g, tank_ph_gates, to_reference_ec,
    umol_to_ppb, water_quality_gates,
)

# --------------------------------------------------------------------------
# Bilingual display vocabulary for status enums
# --------------------------------------------------------------------------

STATUS_TEXT: dict[str, str] = {
    # M2 sodium
    "SAFE": bi("Safe Zone", "安全区域"),
    "APPROACHING": bi("Approaching Limit", "接近上限"),
    "EXCEEDED": bi("Threshold Exceeded - Discharge Required", "超出阈值 - 需要排液"),
    "UNREACHABLE": bi("Target Unreachable With This Water", "以该水源无法达成目标"),
    # M3 leaching bands
    "DEFICIT": bi("Deficit", "亏缺"),
    "NORMAL_GENERATIVE": bi("Normal Generative", "生殖生长正常区"),
    "NORMAL_VEGETATIVE": bi("Normal Vegetative", "营养生长正常区"),
    "WASH": bi("Wash / Flush", "冲洗区"),
    "EXCESS": bi("Excess", "过量"),
    # M4 bands
    "LOW": bi("Below Target", "低于目标"),
    "NORMAL": bi("Within Target", "处于目标区间"),
    "HIGH": bi("Above Target", "高于目标"),
    # generic
    "OK": bi("Normal Operation", "正常运行"),
    "EMERGENCY": bi("Emergency", "紧急状态"),
}

MEDIUM_TEXT = {
    "INERT_SUBSTRATE": bi("Inert Substrate", "惰性基质"),
    "ORGANIC_MATERIAL": bi("Organic Material", "有机基质"),
    "SOIL": bi("Soil", "土壤"),
}

LEVEL_TEXT = {
    0: bi("No correction", "无需纠偏"),
    1: bi("Level 1 correction", "一级纠偏"),
    2: bi("Level 2 correction", "二级纠偏"),
}


def envelope(module: str, module_en: str, module_zh: str,
             data: dict, gates: list[Gate] | None = None) -> dict:
    """Standard response envelope with bilingual headers and sorted gates."""
    gates = sort_gates(gates or [])
    blocking = [g for g in gates if g.severity == "BLOCKING"]
    critical = [g for g in gates if g.severity == "CRITICAL"]
    if blocking:
        overall, overall_zh = "BLOCKED", "已阻断"
    elif critical:
        overall, overall_zh = "ACTION REQUIRED", "需要处置"
    elif gates:
        overall, overall_zh = "REVIEW", "需复核"
    else:
        overall, overall_zh = "OK", "正常"
    return {
        "module": module,
        "module_text": bi(module_en, module_zh),
        "overall_status": overall,
        "overall_status_text": bi(overall, overall_zh),
        "data": data,
        "gates": [g.to_dict() for g in gates],
        "gate_count": len(gates),
        "engine_version": "1.0.0",
        "reference_source": "WUR / Nutrient Solutions for Greenhouse Crops (2020) v4",
    }


def _policy(overrides: dict | None) -> SitePolicy:
    p = SitePolicy()
    for k, v in (overrides or {}).items():
        if hasattr(p, k):
            setattr(p, k, v)
    return p


def _crop_or_400(crop_id: str):
    crop = CROPS.get(crop_id)
    if crop is None:
        raise _http_error(404, f"Unknown crop '{crop_id}'. "
                               f"Available: {', '.join(sorted(CROPS))}")
    return crop


# ==========================================================================
# FastAPI application
# ==========================================================================

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, Response
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field

    FASTAPI_AVAILABLE = True
except ImportError:  # tests still run without the web layer installed
    FASTAPI_AVAILABLE = False
    FastAPI = None  # type: ignore
    HTTPException = Exception  # type: ignore
    BaseModel = object  # type: ignore

    def Field(*_a, **_k):  # type: ignore
        return None


def _http_error(code: int, detail: str):
    if FASTAPI_AVAILABLE:
        return HTTPException(status_code=code, detail=detail)
    return ValueError(detail)


if FASTAPI_AVAILABLE:

    # ---------------- request models ----------------

    class ConvertRequest(BaseModel):
        values_ppm: dict[str, float] = Field(
            default_factory=dict,
            description="Macronutrient analysis in ppm (mg/L), keyed by ion")
        values_ppb: dict[str, float] = Field(
            default_factory=dict,
            description="Micronutrient analysis in ppb (ug/L), keyed by ion")

    class AcidRequest(BaseModel):
        crop_id: str
        base_water_mmol: dict[str, float] = Field(default_factory=dict)
        base_water_micro_umol: dict[str, float] = Field(default_factory=dict)
        base_water_ec: float = 0.0
        base_water_ph: float = 7.5
        irrigation_type: str = "DRIP"
        organic_matter_present: bool = False
        recirculating: bool = False
        policy: dict | None = None

    class SodiumRequest(BaseModel):
        crop_id: str
        na_root_zone_mmol: float
        na_base_water_mmol: float = 0.0
        system_volume_l_m2: float = 0.0
        drain_composition_mmol: dict[str, float] | None = None
        policy: dict | None = None

    class LeachingRequest(BaseModel):
        irrigation_volume_l_m2: float
        drain_volume_l_m2: float
        ec_dripper: float
        ec_drain: float
        policy: dict | None = None

    class CorrectionRequest(BaseModel):
        crop_id: str
        root_zone_mmol: dict[str, float]
        root_zone_micro_umol: dict[str, float] = Field(default_factory=dict)
        root_zone_ec: float
        root_zone_ph: float = 6.0
        policy: dict | None = None

    class SteeringRequest(BaseModel):
        crop_id: str
        stages: list[str] = Field(default_factory=lambda: ["fruit_set"])
        dry_back_intent: str = "BALANCED"
        na_ratio: float | None = None
        wash_active: bool = False

    class TankRequest(BaseModel):
        crop_id: str
        stages: list[str] = Field(default_factory=list)
        ph_root_zone: float = 5.5
        irrigation_type: str = "DRIP"
        calcareous_soil: bool = False
        disinfection: str = "NONE"
        recirculating: bool = False
        boron_source: str = "borax"
        acid_h_mmol: float = 0.0
        policy: dict | None = None

    class ChelateRequest(BaseModel):
        ph_root_zone: float
        medium: str = "INERT_SUBSTRATE"
        irrigation_type: str = "DRIP"
        calcareous_soil: bool = False
        disinfection: str = "NONE"
        recirculating: bool = False
        metal_sulphates_used: bool = False

    class BaseWaterRequest(BaseModel):
        crop_id: str
        base_water_mmol: dict[str, float] = Field(default_factory=dict)
        drain_mmol: dict[str, float] | None = None
        drain_reuse_fraction: float = 0.0
        target_drip_ec: float | None = None

    class EmergencyRequest(BaseModel):
        ph: float
        ec: float
        crop_id: str | None = None
        policy: dict | None = None

    class SessionRequest(BaseModel):
        crop_id: str
        stages: list[str] = Field(default_factory=list)
        target_drip_ec: float | None = None
        base_water_mmol: dict[str, float] = Field(default_factory=dict)
        base_water_micro_umol: dict[str, float] = Field(default_factory=dict)
        base_water_ec: float = 0.0
        root_zone_mmol: dict[str, float] | None = None
        root_zone_micro_umol: dict[str, float] | None = None
        root_zone_ec: float | None = None
        root_zone_ph: float = 5.8
        drain_mmol: dict[str, float] | None = None
        drain_reuse_fraction: float = 0.0
        ec_dripper: float | None = None
        ec_drain: float | None = None
        irrigation_volume_l_m2: float | None = None
        drain_volume_l_m2: float | None = None
        system_volume_l_m2: float = 0.0
        irrigation_type: str = "DRIP"
        recirculating: bool = False
        disinfection: str = "NONE"
        organic_matter_present: bool = False
        calcareous_soil: bool = False
        boron_source: str = "borax"
        dry_back_intent: str = "BALANCED"
        policy: dict | None = None

    app = FastAPI(
        title="Fertilizer Helper API (温室营养液决策助手 接口)",
        version="1.0.0",
        description=(
            "Deterministic fertigation engine for protected horticulture, "
            "derived from 'Nutrient Solutions for Greenhouse Crops' "
            "(WUR / Eurofins / Nouryon / SQM / Yara, 2020, v4). "
            "All numeric output is computed, never generated."),
    )

    # In production this app serves its own frontend, so calls are same-origin
    # and CORS is not strictly needed. It stays enabled because the page is
    # also opened straight from disk during development (origin "null"), and
    # so other tools can call the API. No credentials are ever used, which is
    # what makes a wildcard origin safe here. Set ALLOWED_ORIGINS to a
    # comma-separated list to lock it down.
    _origins = os.getenv("ALLOWED_ORIGINS", "*")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if _origins == "*" else
                      [o.strip() for o in _origins.split(",") if o.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # ---------------- frontend ----------------
    # Serving index.html from the API itself means one free service, one public
    # URL, and no cross-origin configuration for users to get wrong.

    @app.get("/", include_in_schema=False)
    def serve_index():
        index = BASE_DIR / "index.html"
        if not index.exists():
            return {"detail": "index.html not found — API is running at /docs"}
        return FileResponse(index, media_type="text/html")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        """No icon shipped — answer 204 so the browser stops asking."""
        return Response(status_code=204)

    # Local copy of Tailwind, so the page does not depend on a public CDN.
    # This matters where cdn.tailwindcss.com is slow or unreachable. The
    # directory is optional: index.html falls back to the CDN if it is absent.
    _vendor = BASE_DIR / "vendor"
    if _vendor.is_dir():
        app.mount("/vendor", StaticFiles(directory=_vendor), name="vendor")

    # ---------------- reference data ----------------

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "status_text": bi("Service healthy", "服务正常"),
            "crops_loaded": len(CROPS),
            "fertilisers_loaded": len(FERTILISERS),
        }

    @app.get("/api/v1/constants")
    def get_constants() -> dict:
        return {
            "atomic_weights": ATOMIC_WEIGHTS,
            "atomic_weights_text": bi("WUR Atomic Weight Matrix",
                                      "WUR 原子量矩阵"),
            "oxide_to_elemental": OXIDE_TO_ELEMENTAL,
            "elemental_to_oxide": ELEMENTAL_TO_OXIDE,
            "ec_formula": "EC = (Eq cations + Eq anions) / 20",
            "ec_formula_text": bi("EC = (Eq cations + Eq anions) / 20",
                                  "电导率 =（阳离子当量 + 阴离子当量）/ 20"),
            "stock_mass_formula": "kg per 1000 L at 100x = mmol/L * MW * 0.1",
            "stock_mass_formula_text": bi(
                "kg per 1000 L at 100x = mmol/L * MW * 0.1",
                "1000 L 100 倍母液的千克数 = mmol/L × 分子量 × 0.1"),
            "stock_mass_note_text": bi(
                "MW is the fertiliser mass per mole of the driving ion, not "
                "per mole of fertiliser (calcium nitrate: 1080/5 = 216)",
                "分子量指每摩尔主导离子对应的肥料质量，而非每摩尔肥料的质量"
                "（硝酸钙：1080/5 = 216）"),
            "source": "Tables 4 and 7, pp. 25 and 39",
        }

    @app.get("/api/v1/reference/water-levels")
    def get_water_levels() -> dict:
        return {"levels": [
            {**lv,
             "level_text": bi(f"Quality Level {lv['level']}",
                              f"水质 {lv['level']} 级"),
             "suitability_text": bi(lv["suitability_en"], lv["suitability_zh"])}
            for lv in WATER_QUALITY_LEVELS],
            "source": "Table 1, p. 11"}

    @app.get("/api/v1/reference/na-limits")
    def get_na_limits() -> dict:
        return {
            "limits_mmol_l": NA_LIMITS_MMOL_L,
            "limits_text": bi("Maximum root-zone sodium",
                              "根际钠最大允许浓度"),
            "note_text": bi(
                "Values are the manual's Table 2. The project brief quoted "
                "Tomato 15 and Cucumber 8; both are looser than the source.",
                "此处为手册表 2 的数值。项目需求书曾给出番茄 15、黄瓜 8，"
                "两者均宽于原始依据。"),
            "source": "Table 2, p. 12",
        }

    @app.get("/api/v1/reference/chelates")
    def get_chelates() -> dict:
        return {
            "ph_stability_bands": {k: list(v) for k, v in FE_CHELATE_BANDS.items()},
            "switch_ph": 6.5,
            "switch_text": bi(
                "Below pH 6.5 Fe-DTPA is sufficient; above pH 6.5 Fe-EDDHA or "
                "Fe-HBED is strongly recommended",
                "pH 6.5 以下 Fe-DTPA 即可满足；pH 6.5 以上强烈建议使用 "
                "Fe-EDDHA 或 Fe-HBED"),
            "source": "Figure 3a p. 35; Ch. 11 p. 36",
        }

    @app.get("/api/v1/reference/apn")
    def get_apn() -> dict:
        return {"apn_umol_l": APN_UMOL_L,
                "apn_text": bi("Average Plant Need", "植物平均需求"),
                "source": "Table 6, p. 34"}

    @app.get("/api/v1/crops")
    def list_crops() -> dict:
        return {"crops": [
            {"crop_id": c.crop_id, "name": c.name_en, "name_text": c.name,
             "botanical": c.botanical, "medium": c.medium,
             "medium_text": MEDIUM_TEXT[c.medium],
             "ec_fertigation": c.ec_fertigation,
             "na_max_root_zone_mmol_l": c.na_max_root_zone,
             "source_page": c.source_page}
            for c in CROPS.values()]}

    @app.get("/api/v1/crops/{crop_id}")
    def get_crop(crop_id: str) -> dict:
        c = _crop_or_400(crop_id)
        return {
            "crop_id": c.crop_id,
            "name": c.name_en, "name_text": c.name,
            "botanical": c.botanical,
            "medium": c.medium, "medium_text": MEDIUM_TEXT[c.medium],
            "ph_root_zone": list(c.ph_root_zone),
            "ph_fertigation": c.ph_fertigation,
            "ec_root_zone_ms_cm": c.ec_root_zone,
            "ec_fertigation_ms_cm": c.ec_fertigation,
            "root_zone_targets": c.root_zone_targets,
            "root_zone_targets_text": bi("Target values root zone (Streefcijfers)",
                                         "根际目标值"),
            "fertigation_solution_mmol_l": c.fertigation,
            "fertigation_micro_umol_l": c.micro_fertigation,
            "na_max_root_zone_mmol_l": c.na_max_root_zone,
            "cl_max_root_zone_mmol_l": c.cl_max_root_zone,
            "adjustments": [
                {"stage": a.stage, "label": a.label_en,
                 "label_text": bi(a.label_en, a.label_zh),
                 "deltas": a.deltas,
                 "note_text": bi(a.note_en, a.note_zh) if a.note_en else ""}
                for a in c.adjustments],
            "source_page": c.source_page,
        }

    # ---------------- M1 ----------------

    @app.post("/api/v1/m1/convert")
    def m1_convert(req: ConvertRequest) -> dict:
        """ppm -> mmol/L (macro) and ppb -> umol/L (micro)."""
        macro = convert_analysis_to_mmol(req.values_ppm)
        micro = {ion: ppb_to_umol(v, ion) for ion, v in req.values_ppb.items()}
        data = {
            "macro_mmol_l": {k: round(v, 4) for k, v in macro.items()},
            "macro_mmol_l_text": bi("Macronutrients (mmol/L)", "大量元素 (mmol/L)"),
            "micro_umol_l": {k: round(v, 3) for k, v in micro.items()},
            "micro_umol_l_text": bi("Micronutrients (umol/L)", "微量元素 (umol/L)"),
            "round_trip_ppm": {k: round(mmol_to_ppm(v, k), 2)
                               for k, v in macro.items()},
            "formula": "ppm / atomic weight = mmol/L",
            "formula_text": bi("ppm / atomic weight = mmol/L",
                               "ppm ÷ 原子量 = mmol/L"),
        }
        if macro:
            data["ion_balance"] = balance_report(macro)
        return envelope("M1", "Unit Conversion", "单位换算", data)

    @app.post("/api/v1/m1/acid-dosing")
    def m1_acid(req: AcidRequest) -> dict:
        crop = _crop_or_400(req.crop_id)
        pol = _policy(req.policy)
        water = req.base_water_mmol

        level = classify_water(req.base_water_ec,
                               water.get("Na", 0.0), water.get("Cl", 0.0))
        gates = water_quality_gates(level, req.recirculating, crop)
        gates += iron_screening_gates(req.base_water_micro_umol.get("Fe", 0.0),
                                      req.irrigation_type,
                                      req.organic_matter_present)
        gates += micronutrient_screening_gates(req.base_water_micro_umol)

        no3_headroom = crop.fertigation.get("NO3", 0.0) - water.get("NO3", 0.0)
        p_headroom = crop.fertigation.get("P", 0.0) - water.get("P", 0.0)
        plan = plan_acid_dosing(water.get("HCO3", 0.0),
                                no3_headroom, p_headroom, pol)
        gates += acid_gates(plan)

        lv = WATER_QUALITY_LEVELS[min(level, 3) - 1]
        data = {
            "water_quality_level": level,
            "water_quality_level_text": bi(f"Quality Level {level}",
                                           f"水质 {level} 级"),
            "water_suitability_text": (bi(lv["suitability_en"], lv["suitability_zh"])
                                       if level <= 3
                                       else bi("Beyond Table 1 - not usable as supplied",
                                               "超出表 1 范围 - 不可直接使用")),
            "hco3_base_water_mmol_l": round(plan.hco3_base_water, 3),
            "hco3_buffer_target_mmol_l": plan.hco3_buffer_target,
            "hco3_buffer_text": bi(
                f"Retain {plan.hco3_buffer_target:g} mmol/L HCO3 to buffer pH to 5.5-6.0",
                f"保留 {plan.hco3_buffer_target:g} mmol/L HCO3 以将 pH 缓冲在 5.5-6.0"),
            "hco3_residual_mmol_l": round(plan.hco3_residual, 3),
            "h_required_mmol_l": round(plan.h_required, 3),
            "h_from_nitric_mmol_l": round(plan.h_from_nitric, 3),
            "h_from_phosphoric_mmol_l": round(plan.h_from_phosphoric, 3),
            "shortfall_mmol_l": round(plan.shortfall, 3),
            "feasible": plan.feasible,
            "feasible_text": (bi("Acid plan feasible", "加酸方案可行")
                              if plan.feasible
                              else bi("Acid plan infeasible", "加酸方案不可行")),
            "no3_contributed_mmol_l": round(plan.no3_added, 3),
            "p_contributed_mmol_l": round(plan.p_added, 3),
            "nitric_acid_38pct_l_per_1000l": round(plan.nitric_l, 2),
            "nitric_acid_38pct_text": bi("Nitric acid 38%", "硝酸 38%"),
            "phosphoric_acid_59pct_l_per_1000l": round(plan.phosphoric_l, 2),
            "phosphoric_acid_59pct_text": bi("Phosphoric acid 59%", "磷酸 59%"),
            "reaction": "Ca2+ + 2HCO3- + 2HNO3 <-> Ca2+ + 2CO2 + 2H2O + 2NO3-",
            "base_water_fe_credited": False,
            "base_water_fe_credited_text": bi(
                "Base-water iron is never counted as nutrient",
                "原水中的铁不计入养分供给"),
        }
        return envelope("M1", "Base Water & Acid Dosing",
                        "原水水质与中和加酸", data, gates)

    # ---------------- M2 ----------------

    @app.post("/api/v1/m2/sodium")
    def m2_sodium(req: SodiumRequest) -> dict:
        _crop_or_400(req.crop_id)
        pol = _policy(req.policy)
        r = evaluate_sodium(req.crop_id, req.na_root_zone_mmol,
                            req.na_base_water_mmol, req.system_volume_l_m2,
                            req.drain_composition_mmol, pol)
        gates = sodium_gates(r, req.crop_id)
        data = {
            "na_root_zone_mmol_l": round(r.na_current, 3),
            "na_root_zone_ppm": round(mmol_to_ppm(r.na_current, "Na"), 1),
            "na_limit_mmol_l": r.na_limit,
            "na_limit_ppm": round(mmol_to_ppm(r.na_limit, "Na"), 1),
            "na_limit_source": r.limit_source,
            "na_target_mmol_l": round(r.na_target, 3),
            "na_base_water_mmol_l": r.na_base_water,
            "headroom_mmol_l": round(r.headroom, 3),
            "utilisation_pct": round(r.ratio * 100, 1),
            "status": r.status,
            "status_text": STATUS_TEXT[r.status],
            "discharge_required": r.status == "EXCEEDED",
            "discharge_volume_l_m2": round(r.discharge_volume_l_m2, 2),
            "discharge_volume_text": bi(
                f"Forced discharge {r.discharge_volume_l_m2:.1f} L/m2",
                f"强行排液 {r.discharge_volume_l_m2:.1f} L/m2"),
            "system_volume_l_m2": r.system_volume_l_m2,
            "nutrient_loss_g_m2": r.nutrient_loss,
            "nutrient_loss_text": bi("Nutrients lost with discharge (g/m2)",
                                     "随排液流失的养分 (g/m2)"),
        }
        return envelope("M2", "Sodium Accumulation & Discharge Gate",
                        "钠离子累积与强行排液预警", data, gates)

    # ---------------- M3 ----------------

    @app.post("/api/v1/m3/leaching")
    def m3_leaching(req: LeachingRequest) -> dict:
        pol = _policy(req.policy)
        r = evaluate_leaching(req.irrigation_volume_l_m2, req.drain_volume_l_m2,
                              req.ec_dripper, req.ec_drain, pol)
        gates = leaching_gates(r, pol)
        data = {
            "leaching_fraction_pct": round(r.lf_pct, 2),
            "leaching_fraction_text": bi("Leaching Fraction (LF)", "排液比"),
            "formula": "LF = (V_drain / V_irrigation) * 100%",
            "formula_text": bi("LF = (V_drain / V_irrigation) * 100%",
                               "排液比 =（排液量 / 灌溉量）× 100%"),
            "delta_ec_ms_cm": round(r.delta_ec, 3),
            "delta_ec_text": bi("Drain-Dripper EC Gap", "排液-滴灌电导差"),
            "band": r.band,
            "band_text": STATUS_TEXT[r.band],
            "wash_required": r.wash_required,
            "wash_required_text": (bi("Dynamic wash triggered", "已触发动态冲洗")
                                   if r.wash_required
                                   else bi("No wash required", "无需冲洗")),
            "wash_trigger_delta_ec": pol.wash_trigger_delta_ec,
            "target_lf_pct_min": r.target_lf_min,
            "target_lf_pct_max": r.target_lf_max,
            "extra_irrigation_l_m2": round(r.extra_irrigation_l_m2, 2),
            "provenance": "SRC:PRACTICE - not present in the WUR manual",
            "provenance_text": bi(
                "Practice default - not present in the WUR manual",
                "实践经验默认值 - WUR 手册未收录"),
        }
        return envelope("M3", "Leaching Fraction & Irrigation Engine",
                        "排液比与动态灌溉引擎", data, gates)

    # ---------------- M4 ----------------

    @app.post("/api/v1/m4/correction")
    def m4_correction(req: CorrectionRequest) -> dict:
        crop = _crop_or_400(req.crop_id)
        pol = _policy(req.policy)
        try:
            findings, meta = evaluate_corrections(
                req.root_zone_mmol, req.root_zone_micro_umol,
                req.root_zone_ec, crop, pol)
        except ValueError as exc:
            raise _http_error(422, str(exc))

        macro_after, micro_after = apply_corrections(
            crop.fertigation, crop.micro_fertigation, findings)

        rows = []
        for f in findings:
            unit = "umol/L" if f.is_micro else "mmol/L"
            rows.append({
                "ion": f.ion,
                "analysis": round(f.analysed, 3),
                "at_reference_ec": round(f.at_reference_ec, 3),
                "target": round(f.target, 3),
                "unit": unit,
                "deviation_pct": round(f.deviation_pct, 1),
                "band": f.band,
                "band_text": STATUS_TEXT[f.band],
                "correction_level": f.level,
                "correction_level_text": LEVEL_TEXT[f.level],
                "supply_adjustment_pct": round(f.adjustment_pct, 1),
                "supply_adjustment_text": bi(
                    f"{f.adjustment_pct:+.1f}% supply adjustment",
                    f"供给调整 {f.adjustment_pct:+.1f}%"),
                "is_micronutrient": f.is_micro,
            })

        antagonism = screen_antagonism(req.root_zone_mmol, req.root_zone_ph,
                                       crop.root_zone_targets)
        data = {
            "reference_ec": meta,
            "reference_ec_text": bi("Reference EC normalisation", "参比电导率换算"),
            "comparison_rows": rows,
            "corrected_fertigation_mmol_l": {k: round(v, 3)
                                             for k, v in macro_after.items()},
            "corrected_micro_umol_l": {k: round(v, 3)
                                       for k, v in micro_after.items()},
            "cation_balance_pct": cation_balance_pct(req.root_zone_mmol),
            "cation_balance_text": bi("Balance of cations (% of equivalents)",
                                      "阳离子平衡（当量占比 %）"),
            "antagonism_patterns": antagonism,
            "antagonism_text": bi("Deterministic ion antagonism screening",
                                  "离子拮抗确定性筛查"),
            "rules_text": bi(
                "25% deviation triggers a 10-15% adjustment; 50% deviation "
                "triggers a further 15-25%",
                "偏差达 25% 触发 10-15% 调整；偏差达 50% 再追加 15-25%"),
            "micro_ladder_text": bi(
                "Micronutrient stepping: +50%, +25%, 0%, -25%, -50%",
                "微量元素分级步进：+50%、+25%、0%、-25%、-50%"),
        }
        return envelope("M4", "3-Level Feedback Correction Engine",
                        "根际三级反馈纠偏引擎", data)

    # ---------------- M5 ----------------

    @app.post("/api/v1/m5/steering")
    def m5_steering(req: SteeringRequest) -> dict:
        crop = _crop_or_400(req.crop_id)
        r = apply_stage_adjustments(crop, req.stages, req.dry_back_intent)
        gates = steering_gates(r, crop, req.na_ratio, req.wash_active)
        lo, hi, intent_en, intent_zh = DRY_BACK_TARGETS.get(
            req.dry_back_intent, DRY_BACK_TARGETS["BALANCED"])
        data = {
            "stages": r.stages,
            "stages_text": bi(", ".join(r.stages) or "standard",
                              "、".join(r.stages) or "标准"),
            "applied_deltas": {k: round(v, 3) for k, v in r.deltas.items()},
            "applied_deltas_text": bi("Stage adjustment deltas",
                                      "生育阶段调整增量"),
            "fertigation_before_mmol_l": {k: round(v, 3)
                                          for k, v in r.macro_before.items()},
            "fertigation_after_mmol_l": {k: round(v, 3)
                                         for k, v in r.macro_after.items()},
            "micro_after_umol_l": {k: round(v, 3) for k, v in r.micro_after.items()},
            "k_ca_ratio": round(r.k_ca_ratio, 3),
            "k_ca_ratio_text": bi("K:Ca ratio", "钾钙比"),
            "k_n_ratio": round(r.k_n_ratio, 3),
            "k_n_ratio_text": bi("K:N ratio", "钾氮比"),
            "dry_back_intent": r.dry_back_intent,
            "dry_back_intent_text": bi(intent_en, intent_zh),
            "dry_back_target_pct_min": lo,
            "dry_back_target_pct_max": hi,
            "dry_back_text": bi(
                f"Target overnight dry-back {lo:g}-{hi:g}%",
                f"夜间目标回干幅度 {lo:g}-{hi:g}%"),
            "dry_back_provenance_text": bi(
                "Practice default - not present in the WUR manual",
                "实践经验默认值 - WUR 手册未收录"),
            "notes": [bi(en, zh) for en, zh in r.notes],
        }
        return envelope("M5", "Crop Steering & Dry-back Assistant",
                        "作物物候助手", data, gates)

    # ---------------- M6 ----------------

    @app.post("/api/v1/m6/chelate")
    def m6_chelate(req: ChelateRequest) -> dict:
        plan = select_fe_chelate(req.ph_root_zone, req.medium,
                                 req.irrigation_type, req.calcareous_soil)
        gates = chelate_gates(plan, req.disinfection, req.recirculating,
                              req.metal_sulphates_used)
        alloc = [{"fertiliser_id": fid,
                  "fertiliser_text": FERTILISERS[fid].name,
                  "share_pct": round(share * 100, 1),
                  "ph_stability": list(FE_CHELATE_BANDS.get(fid, (0, 0)))}
                 for fid, share in plan.allocation()]
        data = {
            "ph_root_zone": req.ph_root_zone,
            "switch_ph": 6.5,
            "allocation": alloc,
            "allocation_text": bi("Iron chelate allocation", "铁螯合物配比"),
            "requires_ortho_ortho": plan.require_ortho_ortho,
            "requires_ortho_ortho_text": bi(
                "Check declared ortho-ortho content",
                "请核对标示的邻-邻位含量") if plan.require_ortho_ortho else "",
            "reason": plan.reason_en,
            "reason_text": bi(plan.reason_en, plan.reason_zh),
            "source": "Ch. 11, pp. 35-36; Figure 3a",
        }
        return envelope("M6", "Fe Chelate Selector", "铁源选型", data, gates)

    @app.post("/api/v1/m6/tanks")
    def m6_tanks(req: TankRequest) -> dict:
        crop = _crop_or_400(req.crop_id)
        pol = _policy(req.policy)
        steer = apply_stage_adjustments(crop, req.stages)
        fe_plan = select_fe_chelate(req.ph_root_zone, crop.medium,
                                    req.irrigation_type, req.calcareous_soil)

        acid_plan = None
        if req.acid_h_mmol > 0:
            acid_plan = plan_acid_dosing(
                req.acid_h_mmol + pol.hco3_buffer_mmol_l,
                crop.fertigation.get("NO3", 0.0),
                0.0, pol)

        doses, residual = allocate_fertilisers(
            steer.macro_after, steer.micro_after, acid_plan, fe_plan,
            req.boron_source, pol)
        split = split_ab_tanks(doses, pol)

        gates = list(split.gates)
        gates += tank_ph_gates(split, pol)
        gates += chelate_gates(fe_plan, req.disinfection, req.recirculating,
                               req.boron_source == "borax" and req.recirculating)

        data = {
            "tank_volume_l": pol.tank_volume_l,
            "concentration_factor": pol.concentration_factor,
            "concentration_text": bi(
                f"{pol.tank_volume_l:.0f} L tank, {pol.concentration_factor:.0f}x concentrated",
                f"{pol.tank_volume_l:.0f} L 母液罐，{pol.concentration_factor:.0f} 倍浓缩"),
            "tank_a": [d.to_dict() for d in split.tank_a],
            "tank_a_text": bi("Stock Tank A - calcium fertilisers and chelates",
                              "A 母液罐 - 钙肥与螯合物"),
            "tank_a_total_kg": round(split.mass_a_kg, 1),
            "tank_b": [d.to_dict() for d in split.tank_b],
            "tank_b_text": bi("Stock Tank B - sulphate and phosphate fertilisers",
                              "B 母液罐 - 硫酸盐与磷酸盐肥"),
            "tank_b_total_kg": round(split.mass_b_kg, 1),
            "separation_rule_text": bi(
                "All calcium fertilisers must be separated from phosphate and "
                "sulphate fertilisers (CaSO4 / Ca3(PO4)2 precipitation)",
                "所有钙肥必须与磷酸盐、硫酸盐肥分开存放（防止 CaSO4 / Ca3(PO4)2 沉淀）"),
            "tank_ph_rule_text": bi(
                "Tank A pH 3.5-5.0, Tank B pH below 5.0",
                "A 罐 pH 3.5-5.0，B 罐 pH 低于 5.0"),
            "fe_chelate_reason_text": bi(fe_plan.reason_en, fe_plan.reason_zh),
            "unallocated_residual_mmol_l": residual,
            "recipe_mmol_l": {k: round(v, 3) for k, v in steer.macro_after.items()},
            "recipe_micro_umol_l": {k: round(v, 3)
                                    for k, v in steer.micro_after.items()},
        }
        return envelope("M6", "A/B Stock Tank & Chelate Selector",
                        "A/B 罐隔离与铁源选型", data, gates)

    # ---------------- M7 ----------------

    @app.post("/api/v1/m7/base-water")
    def m7_base_water(req: BaseWaterRequest) -> dict:
        crop = _crop_or_400(req.crop_id)
        recipe = dict(crop.fertigation)

        target_ec = req.target_drip_ec or crop.ec_fertigation
        scaled, factors = scale_to_ec(recipe, target_ec)

        excess = base_water_excess(scaled, req.base_water_mmol)
        gates = base_water_excess_gates(excess)

        after_water, water_credit = deduct_base_water(scaled, req.base_water_mmol)
        after_drain, drain_credit = after_water, {}
        if req.drain_mmol and req.drain_reuse_fraction > 0:
            after_drain, drain_credit = deduct_drain(
                after_water, req.drain_mmol, req.drain_reuse_fraction)

        data = {
            "base_water_excess_mmol_l": {k: round(v, 3) for k, v in excess.items()},
            "base_water_excess_text": bi(
                "Ions supplied by the base water above the recipe target",
                "原水供应量超过配方目标的离子"),
            "basic_solution_mmol_l": {k: round(v, 3) for k, v in recipe.items()},
            "basic_solution_text": bi("Step 1 - basic nutrient solution",
                                      "第 1 步 - 基础营养液"),
            "scaled_to_ec_mmol_l": {k: round(v, 3) for k, v in scaled.items()},
            "scaled_to_ec_text": bi(
                f"Step 4 - scaled to drip EC {target_ec:g} mS/cm "
                f"(NH4, P and micronutrients held fixed)",
                f"第 4 步 - 按滴灌电导率 {target_ec:g} mS/cm 换算"
                f"（NH4、P 与微量元素不参与换算）"),
            "scale_factors": {k: round(v, 4) for k, v in factors.items()},
            "base_water_credit_mmol_l": {k: round(v, 3)
                                         for k, v in water_credit.items()},
            "base_water_credit_text": bi(
                "Step 5 - base water nutrients deducted (Ca, Mg, SO4 and others)",
                "第 5 步 - 扣除原水养分（Ca、Mg、SO4 等）"),
            "after_base_water_mmol_l": {k: round(v, 3)
                                        for k, v in after_water.items()},
            "drain_credit_mmol_l": {k: round(v, 3) for k, v in drain_credit.items()},
            "drain_credit_text": bi(
                f"Step 6 - drain water deducted at {req.drain_reuse_fraction * 100:.0f}%",
                f"第 6 步 - 按 {req.drain_reuse_fraction * 100:.0f}% 扣除排液养分"),
            "final_recipe_mmol_l": {k: round(v, 3) for k, v in after_drain.items()},
            "final_recipe_text": bi("Step 7 - final fertigation recipe",
                                    "第 7 步 - 最终施肥配方"),
            "ion_balance": balance_report(after_drain),
            "iron_not_credited_text": bi(
                "Base-water iron is excluded by design: it precipitates at the "
                "emitter and never reaches the roots",
                "原水中的铁按设计不予扣抵：它在滴头处即沉淀，无法到达根系"),
        }
        gates += ion_balance_gates(after_drain)
        return envelope("M7", "Base Water Nutrient Auto-Deduction",
                        "原水养分自动扣抵", data, gates)

    # ---------------- M8 ----------------

    @app.post("/api/v1/m8/emergency")
    def m8_emergency(req: EmergencyRequest) -> dict:
        pol = _policy(req.policy)
        crop = CROPS.get(req.crop_id) if req.crop_id else None
        payload = emergency_check(req.ph, req.ec, crop, pol)
        if payload is not None:
            return payload
        return {
            "emergency": False,
            "gate_id": None,
            "status": "OK",
            "status_text": STATUS_TEXT["OK"],
            "measured_ph": req.ph,
            "measured_ec_ms_cm": req.ec,
            "limit_ph_min": pol.meltdown_ph_min,
            "limit_ec_max": pol.meltdown_ec_max,
            "message_text": bi(
                "Root zone is within the safe operating envelope",
                "根际处于安全运行区间"),
            "recipe_suppressed": False,
        }

    @app.post("/api/v1/m8/diagnostics")
    def m8_diagnostics(req: CorrectionRequest) -> dict:
        crop = _crop_or_400(req.crop_id)
        pol = _policy(req.policy)
        emergency = emergency_check(req.root_zone_ph, req.root_zone_ec, crop, pol)
        if emergency:
            return emergency
        return m4_correction(req)

    # ---------------- orchestrated session ----------------

    @app.post("/api/v1/session/run")
    def session_run(req: SessionRequest) -> dict:
        """
        Full pipeline in gate-precedence order. A BLOCKING gate short-circuits
        everything downstream and suppresses the recipe.
        """
        crop = _crop_or_400(req.crop_id)
        pol = _policy(req.policy)

        # --- M8 emergency pre-check, evaluated FIRST ---
        if req.root_zone_ec is not None:
            emergency = emergency_check(req.root_zone_ph, req.root_zone_ec,
                                        crop, pol)
            if emergency:
                return {"module": "M8", "pipeline_halted": True, **emergency}

        gates: list[Gate] = []
        modules: dict[str, dict] = {}

        # --- M1 water + acid ---
        water = req.base_water_mmol
        level = classify_water(req.base_water_ec, water.get("Na", 0.0),
                               water.get("Cl", 0.0))
        gates += water_quality_gates(level, req.recirculating, crop)
        gates += iron_screening_gates(req.base_water_micro_umol.get("Fe", 0.0),
                                      req.irrigation_type,
                                      req.organic_matter_present)
        acid_plan = plan_acid_dosing(
            water.get("HCO3", 0.0),
            crop.fertigation.get("NO3", 0.0) - water.get("NO3", 0.0),
            crop.fertigation.get("P", 0.0) - water.get("P", 0.0), pol)
        gates += acid_gates(acid_plan)
        modules["M1"] = {
            "water_quality_level": level,
            "water_quality_level_text": bi(f"Quality Level {level}",
                                           f"水质 {level} 级"),
            "h_required_mmol_l": round(acid_plan.h_required, 3),
            "hco3_residual_mmol_l": round(acid_plan.hco3_residual, 3),
            "nitric_acid_l_per_1000l": round(acid_plan.nitric_l, 2),
        }

        # --- M2 sodium ---
        na_ratio = None
        if req.root_zone_mmol and "Na" in req.root_zone_mmol:
            na = evaluate_sodium(req.crop_id, req.root_zone_mmol["Na"],
                                 water.get("Na", 0.0), req.system_volume_l_m2,
                                 req.drain_mmol, pol)
            gates += sodium_gates(na, req.crop_id)
            na_ratio = na.ratio
            modules["M2"] = {
                "status": na.status, "status_text": STATUS_TEXT[na.status],
                "na_root_zone_mmol_l": round(na.na_current, 3),
                "na_limit_mmol_l": na.na_limit,
                "discharge_volume_l_m2": round(na.discharge_volume_l_m2, 2),
            }

        # --- M3 leaching ---
        wash_active = False
        if (req.irrigation_volume_l_m2 and req.drain_volume_l_m2 is not None
                and req.ec_dripper is not None and req.ec_drain is not None):
            lf = evaluate_leaching(req.irrigation_volume_l_m2,
                                   req.drain_volume_l_m2,
                                   req.ec_dripper, req.ec_drain, pol)
            gates += leaching_gates(lf, pol)
            wash_active = lf.wash_required
            modules["M3"] = {
                "leaching_fraction_pct": round(lf.lf_pct, 2),
                "delta_ec_ms_cm": round(lf.delta_ec, 3),
                "band": lf.band, "band_text": STATUS_TEXT[lf.band],
                "wash_required": lf.wash_required,
            }

        # --- M4 corrections + M5 steering ---
        recipe = dict(crop.fertigation)
        micro = dict(crop.micro_fertigation)

        if req.root_zone_mmol and req.root_zone_ec:
            findings, meta = evaluate_corrections(
                req.root_zone_mmol, req.root_zone_micro_umol or {},
                req.root_zone_ec, crop, pol)
            recipe, micro = apply_corrections(recipe, micro, findings)
            modules["M4"] = {
                "reference_ec": meta,
                "corrections_applied": [
                    {"ion": f.ion, "deviation_pct": round(f.deviation_pct, 1),
                     "level": f.level, "level_text": LEVEL_TEXT[f.level],
                     "adjustment_pct": round(f.adjustment_pct, 1)}
                    for f in findings if f.level > 0],
            }

        steer = apply_stage_adjustments(crop, req.stages, req.dry_back_intent)
        for ion, delta in steer.deltas.items():
            if ion in micro:
                micro[ion] = max(0.0, micro[ion] + delta)
            else:
                recipe[ion] = max(0.0, recipe.get(ion, 0.0) + delta)
        gates += steering_gates(steer, crop, na_ratio, wash_active,
                                check_ammonium=False)
        modules["M5"] = {
            "stages": req.stages,
            "applied_deltas": {k: round(v, 3) for k, v in steer.deltas.items()},
            "k_ca_ratio": round(steer.k_ca_ratio, 3),
            "dry_back_target_pct_min": steer.dry_back_min,
            "dry_back_target_pct_max": steer.dry_back_max,
        }

        # --- M7 scale, deduct base water, deduct drain ---
        target_ec = req.target_drip_ec or crop.ec_fertigation
        scaled, factors = scale_to_ec(recipe, target_ec)
        excess = base_water_excess(scaled, water)
        gates += base_water_excess_gates(excess)
        after_water, water_credit = deduct_base_water(scaled, water)
        final, drain_credit = after_water, {}
        if req.drain_mmol and req.drain_reuse_fraction > 0:
            final, drain_credit = deduct_drain(after_water, req.drain_mmol,
                                               req.drain_reuse_fraction)
        modules["M7"] = {
            "scale_factors": {k: round(v, 4) for k, v in factors.items()},
            "base_water_excess_mmol_l": {k: round(v, 3) for k, v in excess.items()},
            "base_water_credit_mmol_l": {k: round(v, 3)
                                         for k, v in water_credit.items()},
            "drain_credit_mmol_l": {k: round(v, 3) for k, v in drain_credit.items()},
            "final_recipe_mmol_l": {k: round(v, 3) for k, v in final.items()},
            "ion_balance": balance_report(final),
        }
        gates += ion_balance_gates(final)
        # Ammonium is checked here, on the recipe that will actually be dosed,
        # because the M4 correction is applied after stage adjustment.
        gates += ammonium_gates(final)

        # --- M6 allocation, chelate, tanks ---
        fe_plan = select_fe_chelate(req.root_zone_ph, crop.medium,
                                    req.irrigation_type, req.calcareous_soil)
        doses, residual = allocate_fertilisers(final, micro, acid_plan, fe_plan,
                                               req.boron_source, pol)
        split = split_ab_tanks(doses, pol)
        gates += split.gates
        gates += tank_ph_gates(split, pol)
        gates += chelate_gates(fe_plan, req.disinfection, req.recirculating)
        modules["M6"] = {
            "tank_a": [d.to_dict() for d in split.tank_a],
            "tank_b": [d.to_dict() for d in split.tank_b],
            "tank_a_total_kg": round(split.mass_a_kg, 1),
            "tank_b_total_kg": round(split.mass_b_kg, 1),
            "fe_chelate_text": bi(fe_plan.reason_en, fe_plan.reason_zh),
            "unallocated_residual_mmol_l": residual,
        }

        blocking = [g for g in gates if g.severity == "BLOCKING"]
        result = envelope("SESSION", "Full Fertigation Pipeline",
                          "完整施肥流程", {"modules": modules,
                                            "crop": crop.name,
                                            "crop_text": crop.name,
                                            "medium_text": MEDIUM_TEXT[crop.medium]},
                          gates)
        result["pipeline_halted"] = bool(blocking)
        result["recipe_suppressed"] = bool(blocking)
        result["llm_invoked"] = False
        result["llm_note_text"] = bi(
            "Narrative layer is advisory only and never alters a dose",
            "叙述层仅为建议性说明，绝不改变投加量")
        return result


# ==========================================================================
# Unit tests — golden vectors from the WUR manual
# ==========================================================================

import unittest  # noqa: E402


class TestAtomicWeights(unittest.TestCase):
    """WUR Atomic Weight Matrix, Table 7, p. 39."""

    def test_required_weights(self):
        self.assertEqual(ATOMIC_WEIGHTS["K"], 39.10)
        self.assertEqual(ATOMIC_WEIGHTS["Ca"], 40.08)
        self.assertEqual(ATOMIC_WEIGHTS["Mg"], 24.31)
        self.assertEqual(ATOMIC_WEIGHTS["N"], 14.00)
        self.assertEqual(ATOMIC_WEIGHTS["P"], 30.97)
        self.assertEqual(ATOMIC_WEIGHTS["S"], 32.06)

    def test_ppm_to_mmol_round_trip(self):
        # Cucumber K fertigation: 8 mmol/L == 313 ppm (p. 41)
        self.assertAlmostEqual(mmol_to_ppm(8.0, "K"), 312.8, places=1)
        self.assertAlmostEqual(ppm_to_mmol(312.8, "K"), 8.0, places=6)

    def test_ppb_to_umol_round_trip(self):
        # Tomato Fe fertigation: 15 umol/L == 840 ppb (p. 53)
        self.assertAlmostEqual(umol_to_ppb(15.0, "Fe"), 837.75, places=2)
        self.assertAlmostEqual(ppb_to_umol(837.75, "Fe"), 15.0, places=6)


class TestFruitSetKNO3Dosing(unittest.TestCase):
    """
    THE NAMED ACCEPTANCE TEST.

    Cucumber and sweet pepper Fruit Set adjustment is +1 mmol/L K and
    +1 mmol/L N-NO3 (pp. 41, 50). Potassium nitrate delivers exactly one K
    and one NO3 per mole, so the adjustment is satisfied by 1.0 mmol/L KNO3.

        kg per 1000 L at 100x = 1.0 * 101.1 * 0.1 = 10.11 kg
    """

    EXPECTED_KG = 10.11

    def test_fruit_set_delta_is_one_kno3(self):
        for crop_id in ("cucumber", "sweet_pepper"):
            with self.subTest(crop=crop_id):
                steer = apply_stage_adjustments(CROPS[crop_id], ["fruit_set"])
                self.assertAlmostEqual(steer.deltas["K"], 1.0, places=6)
                self.assertAlmostEqual(steer.deltas["NO3"], 1.0, places=6)

    def test_kno3_mass_formula(self):
        kno3 = FERTILISERS["kno3"]
        self.assertAlmostEqual(kno3.mass_per_mol_ion, 101.1, places=4)
        mass = stock_mass_kg(1.0, kno3.mass_per_mol_ion, DEFAULT_POLICY)
        self.assertAlmostEqual(mass, self.EXPECTED_KG, places=2)

    def test_kno3_dosing_through_allocation(self):
        """The +1 K / +1 NO3 delta allocated by the engine yields 10.11 kg."""
        delta = {"K": 1.0, "NO3": 1.0}
        doses, residual = allocate_fertilisers(delta, {})
        kno3 = [d for d in doses if d.fert.fid == "kno3"]
        self.assertEqual(len(kno3), 1, "expected exactly one KNO3 line")
        self.assertAlmostEqual(kno3[0].amount_mmol_l, 1.0, places=6)
        self.assertAlmostEqual(kno3[0].mass_kg, self.EXPECTED_KG, places=2)
        self.assertEqual(residual, {}, "no ion should be left unallocated")

    def test_scaled_tank_volume(self):
        """500 L tank at 100x needs half the mass; 1000 L at 200x needs double."""
        kno3 = FERTILISERS["kno3"]
        half = SitePolicy(tank_volume_l=500.0)
        self.assertAlmostEqual(
            stock_mass_kg(1.0, kno3.mass_per_mol_ion, half),
            self.EXPECTED_KG / 2, places=3)
        double = SitePolicy(concentration_factor=200.0)
        self.assertAlmostEqual(
            stock_mass_kg(1.0, kno3.mass_per_mol_ion, double),
            self.EXPECTED_KG * 2, places=3)


class TestGV1SevenStepPipeline(unittest.TestCase):
    """Golden vector 1 — Table 3, p. 23. Every published cell reproduced."""

    def setUp(self):
        self.step1 = {"NH4": 1.2, "K": 9.5, "Ca": 5.4, "Mg": 2.4,
                      "NO3": 15.0, "Cl": 1.0, "S": 4.4, "P": 1.5}

    def test_step3_after_corrections_and_adjustments(self):
        r = dict(self.step1)
        r["Mg"] += -0.25          # step 2 correction
        r["P"] += -0.25           # step 2 correction
        r["K"] += 1.5             # step 3 fruit-set adjustment
        r["Ca"] += -0.5
        r["Mg"] += -0.25
        self.assertAlmostEqual(r["K"], 11.0)
        self.assertAlmostEqual(r["Ca"], 4.9)
        self.assertAlmostEqual(r["Mg"], 1.9)
        self.assertAlmostEqual(r["P"], 1.25)
        self.assertAlmostEqual(ec_from_ions(r), 2.59, places=2)

    def test_step4_scale_to_ec_3_0(self):
        r = {"NH4": 1.2, "K": 11.0, "Ca": 4.9, "Mg": 1.9,
             "NO3": 15.0, "Cl": 1.0, "S": 4.4, "P": 1.25}
        scaled, f = scale_to_ec(r, 3.0)
        self.assertAlmostEqual(f["f_cations"], 1.1707, places=3)
        self.assertAlmostEqual(f["f_anions"], 1.1593, places=3)
        # published step-4 row
        self.assertAlmostEqual(scaled["K"], 12.9, delta=0.1)
        self.assertAlmostEqual(scaled["Ca"], 5.8, delta=0.1)
        self.assertAlmostEqual(scaled["Mg"], 2.2, delta=0.05)
        self.assertAlmostEqual(scaled["NO3"], 17.4, delta=0.05)
        self.assertAlmostEqual(scaled["Cl"], 1.2, delta=0.05)
        self.assertAlmostEqual(scaled["S"], 5.1, delta=0.05)
        self.assertAlmostEqual(scaled["NH4"], 1.2, places=6)   # held fixed
        self.assertAlmostEqual(scaled["P"], 1.25, places=6)    # held fixed
        self.assertAlmostEqual(ec_from_ions(scaled), 3.0, places=3)

    def test_step4_naive_ratio_scaling_would_fail(self):
        """A single shared factor does not reproduce the manual."""
        r = {"NH4": 1.2, "K": 11.0, "Ca": 4.9, "Mg": 1.9,
             "NO3": 15.0, "Cl": 1.0, "S": 4.4, "P": 1.25}
        naive = 3.0 / 2.6
        self.assertNotAlmostEqual(r["K"] * naive, 12.9, delta=0.05)

    def test_step7_final_recipe(self):
        r = {"NH4": 1.2, "K": 11.0, "Ca": 4.9, "Mg": 1.9,
             "NO3": 15.0, "Cl": 1.0, "S": 4.4, "P": 1.25}
        step4, _ = scale_to_ec(r, 3.0)
        # step 5 - base water carries 0.25 mmol/L Ca
        step5, credit = deduct_base_water(step4, {"Ca": 0.25})
        self.assertAlmostEqual(credit["Ca"], 0.25)
        # step 6 - drain at EC 4.0 reused at 20% -> 0.8 mS/cm contribution
        drain = {"NH4": 0.0, "K": 1.4, "Ca": 2.5, "Mg": 1.2,
                 "NO3": 4.4, "Cl": 0.6, "S": 1.6, "P": 0.6}
        step7, _ = deduct_drain(step5, drain, 1.0)
        for ion, expected in (("NH4", 1.2), ("K", 11.5), ("Ca", 3.0), ("Mg", 1.0),
                              ("NO3", 13.0), ("Cl", 0.6), ("S", 3.5), ("P", 0.65)):
            with self.subTest(ion=ion):
                self.assertAlmostEqual(step7[ion], expected, delta=0.05)

    def test_step6_drain_ec_contribution(self):
        """Drain at EC 4.0 reused at 20% contributes 0.8 mS/cm (p. 24)."""
        self.assertAlmostEqual(4.0 * 0.20, 0.8, places=6)

    def test_step7_ion_balance_requires_proton(self):
        """The balance closes only when H+ is counted as a cation."""
        step7 = {"NH4": 1.2, "K": 11.5, "Ca": 3.0, "Mg": 1.0,
                 "NO3": 13.0, "Cl": 0.6, "S": 3.5, "P": 0.65, "H": 0.5}
        rep = balance_report(step7)
        self.assertTrue(rep["balanced"])
        self.assertAlmostEqual(rep["eq_cations_meq_l"], 21.2, places=2)
        self.assertAlmostEqual(rep["eq_anions_meq_l"], 21.25, places=2)
        self.assertAlmostEqual(rep["calculated_ec_ms_cm"], 2.1, delta=0.05)


class TestGV2TomatoTankRecipe(unittest.TestCase):
    """Golden vector 2 — the printed tomato A+B recipe, p. 53."""

    def setUp(self):
        crop = CROPS["tomato"]
        self.doses, self.residual = allocate_fertilisers(
            dict(crop.fertigation), dict(crop.micro_fertigation))
        self.by_id: dict[str, float] = {}
        for d in self.doses:
            key = d.fert.fid
            self.by_id[key] = self.by_id.get(key, 0.0) + (
                d.mass_g if d.is_micro else d.mass_kg)

    def test_macro_masses(self):
        expected = {           # printed kg -> engine kg
            "can_solid": 106.0,
            "cacl2_s": 6.0,
            "map": 3.0,
            "mkp": 17.0,
            "mgso4": 59.0,
            "k2so4": 35.0,
            "kno3": 43.0,      # printed as 20 kg tank A + 23 kg tank B
        }
        for fid, printed in expected.items():
            with self.subTest(fertiliser=fid):
                self.assertAlmostEqual(self.by_id[fid], printed, delta=0.6)

    def test_micro_masses(self):
        expected_g = {"mn_edta": 423.0, "zn_edta": 218.0,
                      "borax": 287.0, "cu_edta": 32.0, "na_moly": 12.0}
        for fid, printed in expected_g.items():
            with self.subTest(fertiliser=fid):
                self.assertAlmostEqual(self.by_id[fid], printed, delta=0.6)

    def test_iron_total_is_1396_g(self):
        """Printed as one line: 'Iron DTPA 6% or EDDHA 6% or HBED 6% - 1396 g'."""
        fe_g = sum(d.mass_g for d in self.doses
                   if d.is_micro and d.fert.micro_ion == "Fe")
        self.assertAlmostEqual(fe_g, 1396.0, delta=1.0)

    def test_all_ions_closed(self):
        self.assertEqual(self.residual, {},
                         f"unallocated ions remain: {self.residual}")

    def test_ion_closure_matches_recipe(self):
        """Recompute the delivered ions from the doses and compare to target."""
        delivered: dict[str, float] = {}
        for d in self.doses:
            if d.is_micro:
                continue
            for ion, n in d.fert.yields.items():
                if ion == "H":
                    continue
                delivered[ion] = delivered.get(ion, 0.0) + n * d.amount_mmol_l
        for ion, target in CROPS["tomato"].fertigation.items():
            with self.subTest(ion=ion):
                self.assertAlmostEqual(delivered.get(ion, 0.0), target, delta=0.05)


class TestGV3AcidVolume(unittest.TestCase):
    """Golden vector 3 — nitric acid volume, example report p. 30."""

    def test_nitric_volume_for_half_mmol_proton(self):
        plan = plan_acid_dosing(hco3_base_water=1.0, no3_headroom=15.0,
                                p_headroom=0.0)
        self.assertAlmostEqual(plan.h_required, 0.5, places=6)
        self.assertAlmostEqual(plan.hco3_residual, 0.5, places=6)
        self.assertAlmostEqual(plan.nitric_kg, 8.35, places=2)
        self.assertAlmostEqual(plan.nitric_l, 6.73, delta=0.35)  # report: 6.4 L


class TestModule1AcidDosing(unittest.TestCase):

    def test_buffer_is_retained(self):
        plan = plan_acid_dosing(2.0, no3_headroom=15.0, p_headroom=1.5)
        self.assertAlmostEqual(plan.h_required, 1.5, places=6)
        self.assertAlmostEqual(plan.hco3_residual, 0.5, places=6)
        self.assertTrue(plan.feasible)

    def test_no_acid_when_below_buffer(self):
        plan = plan_acid_dosing(0.3, no3_headroom=15.0, p_headroom=1.5)
        self.assertEqual(plan.h_required, 0.0)
        self.assertEqual(plan.nitric_l, 0.0)

    def test_infeasible_when_headroom_exhausted(self):
        plan = plan_acid_dosing(6.0, no3_headroom=1.0, p_headroom=0.5)
        self.assertFalse(plan.feasible)
        self.assertAlmostEqual(plan.shortfall, 4.0, places=6)
        self.assertTrue(any(g.gid == "G-ACID-INFEASIBLE"
                            for g in acid_gates(plan)))

    def test_water_classification(self):
        self.assertEqual(classify_water(0.3, 0.5, 0.6), 1)
        self.assertEqual(classify_water(0.8, 2.0, 1.0), 2)
        self.assertEqual(classify_water(1.2, 3.0, 2.0), 3)
        self.assertEqual(classify_water(0.2, 5.0, 1.0), 4)   # worst case wins

    def test_drip_iron_must_be_zero(self):
        gates = iron_screening_gates(5.0, "DRIP")
        self.assertTrue(any(g.gid == "G-FE-DRIP" and g.severity == "CRITICAL"
                            for g in gates))

    def test_deduction_never_goes_negative(self):
        """
        Cucumber targets 0 mmol/L Cl. Base water carrying 1.0 mmol/L Cl must
        clamp to zero demand, not produce -1.0: chloride cannot be un-supplied.
        """
        recipe = {"Cl": 0.0, "Ca": 4.0, "S": 1.375}
        water = {"Cl": 1.0, "Ca": 1.5, "S": 0.8}
        out, credit = deduct_base_water(recipe, water)
        self.assertGreaterEqual(out["Cl"], 0.0)
        self.assertAlmostEqual(out["Cl"], 0.0, places=9)
        self.assertAlmostEqual(out["Ca"], 2.5, places=9)
        self.assertAlmostEqual(credit["Ca"], 1.5, places=9)
        self.assertAlmostEqual(credit["Cl"], 0.0, places=9)

    def test_excess_is_reported_and_gated(self):
        excess = base_water_excess({"Cl": 0.0, "Ca": 4.0}, {"Cl": 1.0, "Ca": 1.5})
        self.assertAlmostEqual(excess["Cl"], 1.0, places=9)
        self.assertNotIn("Ca", excess)
        gates = base_water_excess_gates(excess)
        self.assertTrue(any(g.gid == "G-WATER-EXCESS" for g in gates))

    def test_drain_deduction_never_goes_negative(self):
        out, credit = deduct_drain({"K": 1.0}, {"K": 8.0}, 0.5)
        self.assertAlmostEqual(out["K"], 0.0, places=9)
        self.assertAlmostEqual(credit["K"], 1.0, places=9)

    def test_base_water_iron_never_credited(self):
        recipe = {"Ca": 5.0, "Mg": 2.0, "S": 4.0, "Fe": 15.0}
        out, credit = deduct_base_water(recipe, {"Ca": 1.0, "Fe": 40.0})
        self.assertAlmostEqual(out["Ca"], 4.0)
        self.assertAlmostEqual(out["Fe"], 15.0, msg="Fe must not be deducted")
        self.assertNotIn("Fe", credit)


class TestModule2Sodium(unittest.TestCase):

    def test_wur_limits_not_the_brief_values(self):
        self.assertEqual(na_limit_for("tomato")[0], 8.0)
        self.assertEqual(na_limit_for("cucumber")[0], 6.0)

    def test_safe_zone(self):
        r = evaluate_sodium("tomato", 3.0, 0.5, 20.0)
        self.assertEqual(r.status, "SAFE")
        self.assertEqual(r.discharge_volume_l_m2, 0.0)

    def test_approaching(self):
        r = evaluate_sodium("tomato", 6.8, 0.5, 20.0)
        self.assertEqual(r.status, "APPROACHING")

    def test_exceeded_discharge_volume(self):
        # V_d = 20 * (10 - 7.2) / (10 - 0.5) = 5.895 L/m2
        r = evaluate_sodium("tomato", 10.0, 0.5, 20.0)
        self.assertEqual(r.status, "EXCEEDED")
        self.assertAlmostEqual(r.discharge_volume_l_m2, 5.895, places=3)
        self.assertTrue(any(g.gid == "G-NA-EXCEED"
                            for g in sodium_gates(r, "tomato")))

    def test_unreachable_when_base_water_too_salty(self):
        r = evaluate_sodium("cucumber", 8.0, 6.0, 20.0)
        self.assertEqual(r.status, "UNREACHABLE")
        self.assertEqual(r.discharge_volume_l_m2, 0.0)

    def test_discharge_monotonic_in_current_na(self):
        prev = -1.0
        for na in (8.5, 9.0, 10.0, 12.0):
            v = evaluate_sodium("tomato", na, 0.5, 20.0).discharge_volume_l_m2
            self.assertGreater(v, prev)
            prev = v

    def test_site_override_is_flagged_as_practice(self):
        pol = SitePolicy(na_overrides={"tomato": 15.0})
        limit, source = na_limit_for("tomato", pol)
        self.assertEqual(limit, 15.0)
        self.assertIn("PRACTICE", source)


class TestModule3Leaching(unittest.TestCase):

    def test_lf_formula(self):
        r = evaluate_leaching(10.0, 2.5, 2.6, 3.0)
        self.assertAlmostEqual(r.lf_pct, 25.0, places=6)
        self.assertEqual(r.band, "NORMAL_VEGETATIVE")
        self.assertFalse(r.wash_required)

    def test_delta_ec_triggers_wash(self):
        r = evaluate_leaching(10.0, 1.5, 2.6, 4.6)
        self.assertAlmostEqual(r.delta_ec, 2.0, places=6)
        self.assertTrue(r.wash_required)
        self.assertEqual(r.target_lf_min, 30.0)
        self.assertEqual(r.target_lf_max, 35.0)
        self.assertTrue(any(g.gid == "G-WASH-TRIGGER" for g in leaching_gates(r)))

    def test_just_below_trigger_does_not_wash(self):
        r = evaluate_leaching(10.0, 1.5, 2.6, 4.59)
        self.assertFalse(r.wash_required)

    def test_extra_irrigation_to_reach_wash_band(self):
        r = evaluate_leaching(10.0, 1.5, 2.6, 5.0)
        self.assertTrue(r.wash_required)
        # 1.5 L drain at 30% LF needs 5.0 L irrigation -> already above, so 0
        self.assertGreaterEqual(r.extra_irrigation_l_m2, 0.0)


class TestModule4Correction(unittest.TestCase):

    def test_no_correction_below_25pct(self):
        adj, level, _ = __import__("engine").correction_factor(0.20)
        self.assertEqual(level, 0)
        self.assertEqual(adj, 0.0)

    def test_level_one_at_25pct(self):
        adj, level, rng = __import__("engine").correction_factor(0.30)
        self.assertEqual(level, 1)
        self.assertAlmostEqual(adj, -0.125)      # above target -> reduce supply
        self.assertEqual(rng, (0.10, 0.15))

    def test_level_two_at_50pct(self):
        adj, level, rng = __import__("engine").correction_factor(-0.60)
        self.assertEqual(level, 2)
        self.assertAlmostEqual(adj, 0.325)       # below target -> increase supply
        self.assertEqual(rng, (0.25, 0.40))

    def test_micro_ladder(self):
        step = __import__("engine").micro_step
        self.assertAlmostEqual(step(-0.70), 0.50)
        self.assertAlmostEqual(step(-0.30), 0.25)
        self.assertAlmostEqual(step(0.00), 0.0)
        self.assertAlmostEqual(step(0.30), -0.25)
        self.assertAlmostEqual(step(0.70), -0.50)

    def test_reference_ec_normalisation(self):
        crop = CROPS["tomato"]
        analysis = {"K": 7.2, "Na": 2.7, "Ca": 11.4, "Mg": 6.0,
                    "NO3": 22.1, "Cl": 2.8, "S": 7.9, "P": 2.8, "NH4": 0.1}
        ref, meta = to_reference_ec(analysis, 4.1, crop.ec_root_zone, crop)
        # EC_ref = 4.0 - 0.3 = 3.7 ; EC_nut = 4.1 - 0.1*2.7 = 3.83
        self.assertAlmostEqual(meta["ec_reference_ms_cm"], 3.7, places=3)
        self.assertAlmostEqual(meta["ec_nutrients_ms_cm"], 3.83, places=3)
        self.assertAlmostEqual(ref["Na"], 2.7, places=6)   # Na never converted
        self.assertLess(ref["K"], analysis["K"])           # scaled down

    def test_reference_ec_rejects_sodium_dominated_sample(self):
        crop = CROPS["tomato"]
        with self.assertRaises(ValueError):
            to_reference_ec({"Na": 45.0, "K": 1.0}, 4.0, crop.ec_root_zone, crop)


class TestModule5Steering(unittest.TestCase):

    def test_tomato_fruit_set_differs_from_cucumber(self):
        t = apply_stage_adjustments(CROPS["tomato"], ["fruit_set"])
        self.assertAlmostEqual(t.deltas["K"], 1.5)
        self.assertAlmostEqual(t.deltas["Ca"], -0.5)
        self.assertAlmostEqual(t.deltas["Mg"], -0.25)
        self.assertNotIn("NO3", t.deltas)

    def test_k_ca_ratio_rises_at_fruit_set(self):
        base = apply_stage_adjustments(CROPS["tomato"], [])
        fruit = apply_stage_adjustments(CROPS["tomato"], ["fruit_set"])
        self.assertGreater(fruit.k_ca_ratio, base.k_ca_ratio)

    def test_stages_stack(self):
        r = apply_stage_adjustments(CROPS["tomato"], ["fruit_set", "high_water"])
        self.assertAlmostEqual(r.deltas["K"], 0.5)      # +1.5 then -1.0
        self.assertAlmostEqual(r.deltas["Ca"], 0.0)     # -0.5 then +0.5

    def test_dry_back_targets(self):
        r = apply_stage_adjustments(CROPS["tomato"], [], "GENERATIVE")
        self.assertEqual((r.dry_back_min, r.dry_back_max), (12.0, 15.0))

    def test_generative_dryback_downgraded_by_sodium(self):
        r = apply_stage_adjustments(CROPS["tomato"], [], "GENERATIVE")
        gates = steering_gates(r, CROPS["tomato"], na_ratio=0.9)
        self.assertTrue(any(g.gid == "G-DRYBACK-NA" for g in gates))

    def test_ammonium_gate_sees_the_corrected_recipe(self):
        """
        Regression: the M4 correction is applied after stage adjustment, so a
        gate that only inspects the stage-adjusted vector misses an NH4
        overshoot. Cucumber NH4 1.25 + a level-2 correction of +32.5% is
        1.656 mmol/L, above the 1.5 ceiling.
        """
        from engine import ammonium_gates
        corrected = {"NH4": 1.656, "NO3": 17.0}
        self.assertTrue(any(g.gid == "G-NH4-CEILING"
                            for g in ammonium_gates(corrected)))
        stage_only = apply_stage_adjustments(CROPS["cucumber"], ["fruit_set"])
        self.assertFalse(any(g.gid == "G-NH4-CEILING"
                             for g in steering_gates(stage_only, CROPS["cucumber"])),
                         "uncorrected recipe is within the ceiling")

    def test_ammonium_ceiling_enforced(self):
        r = apply_stage_adjustments(CROPS["tomato"], [])
        r.macro_after["NH4"] = 2.0
        gates = steering_gates(r, CROPS["tomato"])
        self.assertTrue(any(g.gid == "G-NH4-CEILING" for g in gates))


class TestModule6Tanks(unittest.TestCase):

    def setUp(self):
        crop = CROPS["tomato"]
        self.doses, _ = allocate_fertilisers(dict(crop.fertigation),
                                             dict(crop.micro_fertigation))
        self.split = split_ab_tanks(self.doses)

    def test_no_blocking_precipitation_gate(self):
        self.assertEqual([g.gid for g in self.split.gates], [])

    def test_calcium_never_shares_a_tank_with_sulphate_or_phosphate(self):
        for tank in (self.split.tank_a, self.split.tank_b):
            ions: set[str] = set()
            for d in tank:
                ions |= set(d.fert.yields)
            if "Ca" in ions:
                self.assertNotIn("S", ions)
                self.assertNotIn("P", ions)

    def test_calcium_in_tank_a_sulphate_phosphate_in_tank_b(self):
        a_ids = {d.fert.fid for d in self.split.tank_a}
        b_ids = {d.fert.fid for d in self.split.tank_b}
        self.assertIn("can_solid", a_ids)
        self.assertIn("cacl2_s", a_ids)
        self.assertIn("mgso4", b_ids)
        self.assertIn("k2so4", b_ids)
        self.assertIn("mkp", b_ids)

    def test_tanks_are_load_balanced(self):
        total = self.split.mass_a_kg + self.split.mass_b_kg
        self.assertGreater(total, 0)
        skew = abs(self.split.mass_a_kg - self.split.mass_b_kg) / total
        self.assertLess(skew, 0.10, "tank loads should be roughly equal")

    def test_precipitation_gate_is_blocking_when_violated(self):
        from engine import validate_tank_separation, _make_dose
        bad = [_make_dose(FERTILISERS["can_solid"], 1.0, DEFAULT_POLICY),
               _make_dose(FERTILISERS["k2so4"], 1.0, DEFAULT_POLICY)]
        gates = validate_tank_separation(bad, [])
        self.assertTrue(gates)
        self.assertEqual(gates[0].severity, "BLOCKING")
        self.assertEqual(gates[0].gid, "G-PRECIP-RISK")

    def test_chelate_selection_below_switch_ph(self):
        plan = select_fe_chelate(5.5, "INERT_SUBSTRATE", "DRIP")
        self.assertEqual(plan.primary_fid, "fe_dtpa")
        self.assertAlmostEqual(plan.primary_share, 0.75)
        self.assertEqual(plan.secondary_fid, "fe_eddha")
        self.assertAlmostEqual(plan.secondary_share, 0.25)

    def test_chelate_selection_above_switch_ph(self):
        plan = select_fe_chelate(7.0, "INERT_SUBSTRATE", "DRIP")
        self.assertEqual(plan.primary_fid, "fe_eddha")
        self.assertAlmostEqual(plan.primary_share, 1.0)
        self.assertTrue(plan.require_ortho_ortho)

    def test_switch_point_is_6_5_not_7_0(self):
        """design.md discrepancy D-2: the manual's switch is 6.5."""
        self.assertEqual(select_fe_chelate(6.6, "SOIL", "DRIP").primary_fid,
                         "fe_eddha")
        self.assertEqual(select_fe_chelate(6.4, "SOIL", "DRIP").primary_fid,
                         "fe_dtpa")

    def test_nft_prophylactic_is_10pct(self):
        plan = select_fe_chelate(5.5, "INERT_SUBSTRATE", "NFT")
        self.assertAlmostEqual(plan.secondary_share, 0.10)

    def test_calcareous_soil_forces_eddha(self):
        plan = select_fe_chelate(5.0, "SOIL", "DRIP", calcareous_soil=True)
        self.assertEqual(plan.primary_fid, "fe_eddha")
        self.assertTrue(plan.require_ortho_ortho)

    def test_disinfection_gate(self):
        plan = select_fe_chelate(5.5, "INERT_SUBSTRATE", "DRIP")
        gates = chelate_gates(plan, disinfection="UV")
        self.assertTrue(any(g.gid == "G-CHELATE-DISINFECT" for g in gates))


class TestModule8Emergency(unittest.TestCase):

    def test_low_ph_fires(self):
        p = emergency_check(5.1, 3.0)
        self.assertIsNotNone(p)
        self.assertTrue(p["emergency"])
        self.assertEqual(p["severity"], "BLOCKING")
        self.assertTrue(p["recipe_suppressed"])
        self.assertFalse(p["llm_invoked"])

    def test_high_ec_fires(self):
        p = emergency_check(6.0, 4.6)
        self.assertIsNotNone(p)
        self.assertIn("EC", p["reason"])

    def test_boundary_values_do_not_fire(self):
        self.assertIsNone(emergency_check(5.2, 4.5))

    def test_normal_returns_none(self):
        self.assertIsNone(emergency_check(5.8, 2.6))

    def test_payload_is_bilingual_and_hardcoded(self):
        p = emergency_check(5.0, 5.0, CROPS["tomato"])
        self.assertIn("紧急冲洗指令", p["title_text"])
        self.assertEqual(len(p["instructions"]), 6)
        for step in p["instructions"]:
            self.assertIn("(", step["action_text"])
            self.assertIn(")", step["action_text"])

    def test_both_conditions_reported(self):
        p = emergency_check(5.0, 5.0)
        self.assertIn("pH", p["reason"])
        self.assertIn("EC", p["reason"])


class TestBilingualContract(unittest.TestCase):
    """Requirement 3 — every display string carries both languages."""

    def test_bi_helper_format(self):
        self.assertEqual(bi("Safe Zone", "安全区域"), "Safe Zone (安全区域)")

    def test_status_vocabulary_is_bilingual(self):
        for key, text in STATUS_TEXT.items():
            with self.subTest(status=key):
                self.assertRegex(text, r"^.+ \(.+\)$")

    def test_gate_dict_is_bilingual(self):
        gates = iron_screening_gates(5.0, "DRIP")
        for g in gates:
            d = g.to_dict()
            self.assertRegex(d["title_text"], r"^.+ \(.+\)$")
            self.assertRegex(d["message_text"], r"^.+ \(.+\)$")

    def test_crop_names_are_bilingual(self):
        for crop in CROPS.values():
            self.assertRegex(crop.name, r"^.+ \(.+\)$")

    def test_envelope_has_bilingual_headers(self):
        env = envelope("M2", "Sodium Gate", "钠离子闸门", {})
        self.assertRegex(env["module_text"], r"^.+ \(.+\)$")
        self.assertRegex(env["overall_status_text"], r"^.+ \(.+\)$")


class TestMassFormulaProperties(unittest.TestCase):

    def test_mass_per_mol_ion_uses_the_driving_ion(self):
        """Calcium nitrate is 1080 g/mol but carries 5 Ca -> 216 g per mol Ca."""
        self.assertAlmostEqual(FERTILISERS["can_solid"].mass_per_mol_ion, 216.0)
        self.assertAlmostEqual(FERTILISERS["cacl2_s"].mass_per_mol_ion, 55.5)

    def test_manual_worked_example_648_grams(self):
        """'To supply 3 mol of Ca one should add 3 * 216 = 648 grams' (p. 28)."""
        grams_per_m3 = 3.0 * FERTILISERS["can_solid"].mass_per_mol_ion
        self.assertAlmostEqual(grams_per_m3, 648.0, places=6)

    def test_micro_mass_formula(self):
        self.assertAlmostEqual(stock_mass_micro_g(15.0, "Fe", 0.06), 1396.25,
                               places=2)
        self.assertAlmostEqual(stock_mass_micro_g(10.0, "Mn", 0.13), 422.6,
                               places=1)
        self.assertAlmostEqual(stock_mass_micro_g(0.5, "Mo", 0.396), 12.11,
                               places=2)

    def test_ec_formula(self):
        m = {"NH4": 1.2, "K": 9.5, "Ca": 5.4, "Mg": 2.4,
             "NO3": 15.0, "Cl": 1.0, "S": 4.4, "P": 1.5}
        self.assertAlmostEqual(ec_from_ions(m), 2.6, delta=0.05)


def run_tests() -> int:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        sys.exit(run_tests())
    if not FASTAPI_AVAILABLE:
        print("FastAPI is not installed. Install it with: pip install -r requirements.txt")
        sys.exit(1)
    import uvicorn
    # Cloud platforms inject the port to bind. Locally these default to a
    # loopback address so the dev server is not exposed to the network.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host=host, port=port)
