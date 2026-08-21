"""
Irrigation & Leaching Fraction engine — standalone edition
灌溉与排液比引擎 — 独立版本

Extracted from the Fertilizer Helper codebase (engine.py, Module 4) for
cross-departmental use. Pure standard library: no web framework, no pandas,
no project imports. Drop this file anywhere and import it.

Derived from Fertilizer Helper's Module 4. Note on provenance: the WUR manual
*Nutrient Solutions for Greenhouse Crops* (2020, v4) contains NO leaching-
fraction, wash-cycle or dry-back material. Its only related figures are the
drain EC-contribution mixing rule (p.24) and the crop-page note that high water
supply means above 5 L/m²/day (e.g. p.41). Everything else here is grower
practice with configurable defaults — treat the thresholds as site policy to be
validated locally, not as published standards.

Usage
-----
>>> lf = calculate_leaching_fraction(v_irrigation=4.0, v_drain=1.04)
>>> round(lf, 1)
26.0
>>> plan = calculate_extra_wash_volume(4.0, 1.04, ec_dripper=2.0, ec_drain=4.0)
>>> plan.wash_case, round(plan.extra_irrigation_l_m2, 2)
('STANDARD', 0.39)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal, Sequence

__all__ = [
    "LeachingPolicy",
    "WashPlan",
    "calculate_leaching_fraction",
    "calculate_extra_wash_volume",
    "get_crop_default_irrigation",
    "wash_target_lf",
    "format_extra_irrigation",
]

EPS = 1e-9

WashCase = Literal["NONE", "STANDARD", "MODERATE", "ANOMALY"]
LFBand = Literal["DEFICIT", "NORMAL_GENERATIVE", "NORMAL_VEGETATIVE",
                 "WASH", "EXCESS"]


# --------------------------------------------------------------------------
# Reference irrigation volumes (SRC:PRACTICE)
# --------------------------------------------------------------------------

#: Daily irrigation volume in L/m²/day, keyed crop -> growth stage.
#: Used only as a fallback when the operator supplies no measured volume.
REFERENCE_IRRIGATION_L_M2_DAY: dict[str, dict[str, float]] = {
    "tomato":       {"start": 1.5, "fruit_set": 3.8, "high_water": 5.5,
                     "end_season": 2.5, "standard": 3.8},
    "cucumber":     {"start": 1.5, "fruit_set": 4.0, "high_water": 5.5,
                     "end_season": 2.5, "standard": 4.0},
    "sweet_pepper": {"start": 1.3, "fruit_set": 3.5, "high_water": 5.5,
                     "end_season": 2.2, "standard": 3.5},
}

#: Category-level defaults for crops without their own row.
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

REFERENCE_IRRIGATION_FALLBACK = 3.5

#: Every `high_water` entry stays above 5 L/m²/day because that threshold is
#: the manual's own definition of the stage (crop-page note, e.g. p.41).
HIGH_WATER_THRESHOLD_L_M2_DAY = 5.0

_LF_BANDS: Sequence[tuple[float, float, LFBand, str, str]] = (
    (0.0, 10.0, "DEFICIT", "Deficit", "亏缺"),
    (10.0, 20.0, "NORMAL_GENERATIVE", "Normal generative", "生殖生长正常区"),
    (20.0, 30.0, "NORMAL_VEGETATIVE", "Normal vegetative", "营养生长正常区"),
    (30.0, 40.0, "WASH", "Wash / flush", "冲洗区"),
    (40.0, float("inf"), "EXCESS", "Excess", "过量"),
)


@dataclass
class LeachingPolicy:
    """Site-configurable thresholds. All SRC:PRACTICE."""

    wash_trigger_delta_ec: float = 2.0
    """Drain-minus-dripper EC gap (mS/cm) that triggers a wash cycle."""

    wash_lf_min: float = 30.0
    wash_lf_max: float = 35.0
    wash_lf_target: float = 32.5
    """STANDARD-case target: midpoint of the 30–35% wash band."""

    wash_lf_moderate_min: float = 30.0
    """At or above this LF, 32.5% is no longer an increase."""

    wash_lf_anomaly_min: float = 40.0
    """At or above this LF, adding volume is the wrong remedy entirely."""

    wash_lf_moderate_step: float = 10.0
    wash_lf_moderate_cap: float = 50.0

    reference_irrigation_overrides: dict[str, dict[str, float]] = field(
        default_factory=dict)


DEFAULT_POLICY = LeachingPolicy()


@dataclass
class WashPlan:
    """Result of a leaching-fraction evaluation."""

    lf_pct: float
    delta_ec: float
    band: LFBand
    wash_required: bool
    wash_case: WashCase
    is_wash_anomaly: bool
    target_lf_pct: float
    extra_irrigation_l_m2: float
    target_irrigation_l_m2: float
    used_irrigation_l_m2: float
    drain_l_m2: float
    uptake_l_m2: float
    is_estimated_volume: bool

    def as_dict(self) -> dict[str, float | str | bool]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


# --------------------------------------------------------------------------
# Core functions
# --------------------------------------------------------------------------

def calculate_leaching_fraction(v_irrigation: float, v_drain: float) -> float:
    """
    Leaching fraction as a percentage.

        LF = (V_drain / V_irrigation) × 100%

    Args:
        v_irrigation: Applied irrigation volume, L/m²/day. Must be > 0.
        v_drain: Collected drain volume, L/m²/day. Must not exceed irrigation.

    Returns:
        Leaching fraction in percent.

    Raises:
        ValueError: if irrigation is not positive, or drain exceeds irrigation.
    """
    if v_irrigation <= EPS:
        raise ValueError("Irrigation volume must be greater than zero")
    if v_drain < 0:
        raise ValueError("Drain volume cannot be negative")
    if v_drain > v_irrigation + EPS:
        raise ValueError("Drain volume cannot exceed irrigation volume")
    return 100.0 * v_drain / v_irrigation


def get_crop_default_irrigation(crop_id: str,
                                stages: Iterable[str] | None = None,
                                category: str | None = None,
                                policy: LeachingPolicy = DEFAULT_POLICY) -> float:
    """
    Fallback daily irrigation volume, L/m²/day.

    Stages stack in this system, so when several are active the HIGHEST demand
    wins — a crop in fruit set during a heat wave is watered to the heat wave,
    not to the average of the two.

    Args:
        crop_id: e.g. "tomato". Unknown ids fall through to `category`.
        stages: active growth stages, e.g. ["fruit_set"].
        category: e.g. "cut_flowers"; used when the crop has no own row.
        policy: supplies `reference_irrigation_overrides`.

    Returns:
        Reference volume in L/m²/day.
    """
    table = dict(REFERENCE_IRRIGATION_L_M2_DAY)
    for cid, per_stage in (policy.reference_irrigation_overrides or {}).items():
        table[cid] = {**table.get(cid, {}), **per_stage}

    per_stage = table.get(crop_id)
    if per_stage is None and category:
        per_stage = REFERENCE_IRRIGATION_BY_CATEGORY.get(category)
    if per_stage is None:
        return REFERENCE_IRRIGATION_FALLBACK

    active = [s for s in (stages or []) if s in per_stage]
    if not active:
        return per_stage.get("standard", REFERENCE_IRRIGATION_FALLBACK)
    return max(per_stage[s] for s in active)


def wash_target_lf(lf_current_pct: float,
                   policy: LeachingPolicy = DEFAULT_POLICY) -> tuple[float, WashCase]:
    """
    Choose the wash target LF for the CURRENT leaching fraction.

    A fixed 32.5% target is only correct while the crop is under-leaching. Once
    measured LF reaches it, "raise LF to 32.5%" describes a *reduction*, the
    solver returns a negative volume, and clamping it to zero produces the
    contradictory advice "add 0.00 L/m²/day".

    ==========  ===================  =========================================
    Case        Condition            Target
    ==========  ===================  =========================================
    STANDARD    LF < 30%             32.5% (midpoint of the 30–35% band)
    MODERATE    30% <= LF < 40%      LF + 10 points, capped at 50%
    ANOMALY     LF >= 40%            none — volume is not the remedy
    ==========  ===================  =========================================

    ANOMALY is an agronomic finding, not a clamp. An EC gap that persists while
    more than 40% of applied water already drains away is not a leaching
    deficit: water is bypassing the root zone (substrate channeling /
    preferential flow), the dripper or stock EC is over-calibrated, or salt has
    accumulated beyond what volume alone can shift.

    Returns:
        (target_lf_pct, case)
    """
    if lf_current_pct < policy.wash_lf_moderate_min:
        return policy.wash_lf_target, "STANDARD"
    if lf_current_pct < policy.wash_lf_anomaly_min:
        return (min(policy.wash_lf_moderate_cap,
                    lf_current_pct + policy.wash_lf_moderate_step), "MODERATE")
    return lf_current_pct, "ANOMALY"


def _extra_for_target(v_irrigation: float, lf_current_frac: float,
                      lf_target_frac: float) -> float:
    """
    Additional irrigation to move LF from current to target, L/m².

    Plant uptake is the conserved quantity over the short term, not drain:

        V_uptake     = V_irrigation × (1 − LF_current)
        V_target_irr = V_uptake / (1 − LF_target)
        ΔV_extra     = V_irrigation × ((1 − LF_current)/(1 − LF_target) − 1)

    Pinning DRAIN instead of uptake inverts the agronomy: with V_irr 4.0 and
    drain 1.04 (LF 26%), holding drain fixed says 3.47 L/m² reaches LF 30% —
    i.e. that salts are flushed by irrigating *less*.
    """
    if v_irrigation <= EPS or lf_current_frac >= lf_target_frac:
        return 0.0
    if lf_target_frac >= 1.0 - EPS:
        raise ValueError("Target leaching fraction must be below 100%")
    ratio = (1.0 - lf_current_frac) / (1.0 - lf_target_frac)
    return max(0.0, v_irrigation * (ratio - 1.0))


def calculate_extra_wash_volume(v_irrigation: float | None,
                                v_drain: float,
                                ec_dripper: float,
                                ec_drain: float,
                                crop_id: str | None = None,
                                stages: Iterable[str] | None = None,
                                category: str | None = None,
                                policy: LeachingPolicy = DEFAULT_POLICY) -> WashPlan:
    """
    Evaluate the leaching fraction and, if a wash is warranted, the extra
    irrigation volume needed.

    Args:
        v_irrigation: L/m²/day. None or 0 falls back to a crop-stage reference
            volume; the result is then flagged `is_estimated_volume`.
        v_drain: L/m²/day.
        ec_dripper: Supply EC, mS/cm.
        ec_drain: Drain EC, mS/cm.
        crop_id, stages, category: used only for the fallback volume.
        policy: site thresholds.

    Returns:
        A :class:`WashPlan`. When `wash_case == "ANOMALY"`, both
        `extra_irrigation_l_m2` and the increment over current irrigation are
        zero *by diagnosis* — do not treat that as "nothing to do".

    Raises:
        ValueError: drain exceeds irrigation, or no volume can be determined.
    """
    is_estimated = v_irrigation is None or v_irrigation <= EPS
    if is_estimated:
        v_irrigation = get_crop_default_irrigation(
            crop_id or "", stages, category, policy)
        if v_irrigation <= EPS:
            raise ValueError("No irrigation volume supplied and no reference "
                             "volume available")

    v_drain = max(0.0, v_drain)
    lf = calculate_leaching_fraction(v_irrigation, v_drain)
    delta_ec = ec_drain - ec_dripper
    uptake = v_irrigation - v_drain
    band: LFBand = next(code for lo, hi, code, _, _ in _LF_BANDS if lo <= lf < hi)

    # Tolerance so an exact-threshold reading such as 4.6 - 2.6 (which is
    # 1.9999999999999996 in binary floating point) still trips the trigger.
    wash = delta_ec >= policy.wash_trigger_delta_ec - 1e-9

    target_lf, case = (wash_target_lf(lf, policy) if wash
                       else (policy.wash_lf_target, "NONE"))
    extra = 0.0
    target_irr = v_irrigation
    if wash and case != "ANOMALY":
        extra = _extra_for_target(v_irrigation, lf / 100.0, target_lf / 100.0)
        target_irr = v_irrigation + extra

    return WashPlan(
        lf_pct=lf, delta_ec=delta_ec, band=band, wash_required=wash,
        wash_case=case, is_wash_anomaly=(case == "ANOMALY"),
        target_lf_pct=target_lf, extra_irrigation_l_m2=extra,
        target_irrigation_l_m2=target_irr, used_irrigation_l_m2=v_irrigation,
        drain_l_m2=v_drain, uptake_l_m2=uptake,
        is_estimated_volume=is_estimated,
    )


def format_extra_irrigation(delta_v: float) -> tuple[str, str]:
    """
    Bilingual rendering of the volume increment (English, 中文).

    A non-positive increment is never shown as a bare "+0.00": that means no
    additional volume is recommended, which is a different statement from
    "add nothing and carry on".
    """
    if delta_v > EPS:
        return f"+{delta_v:.2f} L/m2/day", f"每日 +{delta_v:.2f} L/m2"
    return ("+0.00 L/m2/day (no additional volume recommended)",
            "+0.00 L/m2/天（不建议增加灌溉量）")


if __name__ == "__main__":
    print("Irrigation & Leaching Fraction engine — self check\n")
    for vi, vd, label in ((4.0, 1.04, "A standard"),
                          (5.0, 1.75, "B moderate"),
                          (5.0, 2.20, "C anomaly")):
        p = calculate_extra_wash_volume(vi, vd, 2.0, 4.0)
        en, _ = format_extra_irrigation(p.extra_irrigation_l_m2)
        print(f"  {label:<12} LF {p.lf_pct:5.1f}%  case={p.wash_case:<9} "
              f"target={p.target_lf_pct:5.1f}%  extra={en}")
    p = calculate_extra_wash_volume(None, 0.0, 2.0, 4.0,
                                    crop_id="tomato", stages=["fruit_set"])
    print(f"\n  fallback     used={p.used_irrigation_l_m2} L/m2 "
          f"(estimated={p.is_estimated_volume})")
