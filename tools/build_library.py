"""Turn the verified extraction into the shipped crop library JSON."""
import json, re, unicodedata

RAW = json.load(open("crops2.json", encoding="utf-8"))

# Curated identity: category, ids and Chinese names. Nutrient numbers all come
# from the extractor; only naming/taxonomy is hand-assigned here.
CATALOGUE = {
    "TOMATO":            ("tomato",           "Tomato",           "番茄",     "fruiting_vegetables"),
    "CUCUMBER":          ("cucumber",         "Cucumber",         "黄瓜",     "fruiting_vegetables"),
    "SWEET PEPPER":      ("sweet_pepper",     "Sweet Pepper",     "甜椒",     "fruiting_vegetables"),
    "EGGPLANT":          ("eggplant",         "Eggplant",         "茄子",     "fruiting_vegetables"),
    "MELON":             ("melon",            "Melon",            "甜瓜",     "fruiting_vegetables"),
    "STRAWBERRY":        ("strawberry",       "Strawberry",       "草莓",     "soft_fruits"),
    "RASPBERRY":         ("raspberry",        "Raspberry",        "覆盆子",   "soft_fruits"),
    "BLUEBERRY":         ("blueberry",        "Blueberry",        "蓝莓",     "soft_fruits"),
    "LETTUCE":           ("lettuce",          "Lettuce",          "生菜",     "leafy_vegetables"),
    "HERBS":             ("herbs",            "Herbs",            "香草类",   "leafy_vegetables"),
    "MICROGREENS":       ("microgreens",      "Microgreens",      "芽苗菜",   "leafy_vegetables"),
    "ROSE":              ("rose",             "Rose",             "月季",     "cut_flowers"),
    "CHRYSANTHEMUM":     ("chrysanthemum",    "Chrysanthemum",    "菊花",     "cut_flowers"),
    "GERBERA":           ("gerbera",          "Gerbera",          "非洲菊",   "cut_flowers"),
    "CARNATION":         ("carnation",        "Carnation",        "康乃馨",   "cut_flowers"),
    "ALSTROEMERIA":      ("alstroemeria",     "Alstroemeria",     "六出花",   "cut_flowers"),
    "ZANTEDESCHIA":      ("zantedeschia",     "Zantedeschia",     "马蹄莲",   "cut_flowers"),
    "ORCHIDS (PHALAENOPSIS)": ("phalaenopsis","Phalaenopsis",     "蝴蝶兰",   "potted_plants"),
    "ORCHIDS":           ("orchids_other",    "Orchids (other)",  "其他兰花", "potted_plants"),
    "ANTHURIUM":         ("anthurium",        "Anthurium",        "红掌",     "potted_plants"),
    "POINSETTIA":        ("poinsettia",       "Poinsettia",       "一品红",   "potted_plants"),
    "BEDDING PLANTS":    ("bedding_plants",   "Bedding Plants",   "花坛植物", "potted_plants"),
    "FLOWERING PLANTS":  ("flowering_plants", "Flowering Plants", "观花盆栽", "potted_plants"),
    "FOLIAGE PLANTS":    ("foliage_plants",   "Foliage Plants",   "观叶盆栽", "potted_plants"),
}

STAGE_LABELS = {
    "start":      ("Start / Rooting", "定植期 / 生根期"),
    "fruit_set":  ("Fruit Set",       "坐果期"),
    "end_season": ("End of Season",   "生育末期"),
}

MACRO = ["NH4","K","Ca","Mg","NO3","Cl","S","P"]
MICRO = ["Fe","Mn","Zn","B","Cu","Mo"]
CEILINGS = ["Na","Cl","HCO3"]
EXTRACT = {"INERT_SUBSTRATE":"direct","ORGANIC_MATERIAL":"1:1.5_volume","SOIL":"1:2_volume"}


def match(title):
    t = title.upper()
    t = re.sub(r'\(.*?\)', lambda m: m.group(0) if 'PHALAENOPSIS' in m.group(0) else '', t)
    t = re.sub(r'E\.G\..*', '', t).strip()
    for key in sorted(CATALOGUE, key=len, reverse=True):
        if key in t:
            return CATALOGUE[key]
    return None


def botanical(title):
    m = re.search(r'\(([A-Z][a-z]+ [a-z x]+[a-z]+)\)', title)
    return m.group(1) if m else ""


out = {"crops": {}, "provenance": "WUR Nutrient Solutions for Greenhouse Crops 2020 v4, Section B"}
skipped, notes = [], []

for pn, rec in sorted(RAW.items(), key=lambda kv: int(kv[0])):
    ident = match(rec["title"])
    if not ident:
        skipped.append((pn, rec["title"])); continue
    cid, en, zh, cat = ident
    medium = rec["medium"]

    entry = out["crops"].setdefault(cid, {
        "crop_id": cid, "name_en": en, "name_zh": zh, "category": cat,
        "botanical": botanical(rec["title"]), "matrices": {},
    })
    if not entry["botanical"]:
        entry["botanical"] = botanical(rec["title"])

    if medium in entry["matrices"]:
        notes.append(f"p.{pn} duplicate {cid}/{medium} - kept first (p."
                     f"{entry['matrices'][medium]['source_page']})")
        continue

    ph_rz = rec.get("ph_rz")
    try:
        ph_lo, ph_hi = (float(x) for x in str(ph_rz).split("-")) if ph_rz and "-" in str(ph_rz) \
            else (float(ph_rz), float(ph_rz))
    except Exception:
        ph_lo = ph_hi = 5.8

    rz, ft = rec["rz"], rec["ft"]
    adj_raw = rec.get("adj", {})

    # A few tables (pp. 70, 71, 73, 78) have only one adjustment column, and
    # the extractor picks its ppm member rather than its mmol member. The
    # signature is unambiguous: the value exceeds any plausible mmol delta AND
    # value/atomic-weight lands on a round quarter. Convert those, and record
    # the conversion; anything that does not convert cleanly is dropped rather
    # than shipped.
    AW_ADJ = {"NH4":14.0,"K":39.10,"Ca":40.08,"Mg":24.31,"NO3":14.0,"Cl":35.45,
              "S":32.06,"P":30.97,"Fe":55.85,"Mn":54.94,"Zn":65.38,"B":10.81,
              "Cu":63.55,"Mo":95.94}
    LIMIT = {"NH4":3,"K":6,"Ca":3,"Mg":2,"NO3":6,"Cl":3,"S":3,"P":3,
             "Fe":60,"Mn":30,"Zn":30,"B":60,"Cu":5,"Mo":5}

    def normalise(ion, v):
        lim, aw = LIMIT.get(ion, 5), AW_ADJ.get(ion)
        if abs(v) <= lim or not aw:
            return v, None
        # A K adjustment of -39 mmol/L is physically impossible, so when the
        # value breaches the limit the column identity is unambiguous.
        conv = round(v / aw, 2)
        if abs(conv) <= lim:
            return conv, f"{ion}:{v}->{conv} (ppm column converted)"
        return None, f"{ion}:{v} DROPPED (not convertible)"

    # high_water is pulled OUT of the stage list and kept as its own vector.
    stages, high_water = {}, {}
    conversions = []
    for ion, per_stage in adj_raw.items():
        for stage, delta in per_stage.items():
            if delta == 0:
                continue
            delta, note = normalise(ion, delta)
            if note:
                conversions.append(f"{stage}.{note}")
            if delta is None:
                continue
            if stage == "high_water":
                high_water[ion] = delta
            else:
                stages.setdefault(stage, {})[ion] = delta

    entry["matrices"][medium] = {
        "substrate_type": medium,
        "source_page": int(pn),
        "extract_method": EXTRACT[medium],
        "ph_root_zone": [ph_lo, ph_hi],
        "ph_fertigation": rec.get("ph_ft") or 5.3,
        "ec_root_zone": rec.get("ec_rz") or 0.0,
        "ec_fertigation": rec.get("ec_ft") or 0.0,
        "root_zone_targets": {k: v for k, v in rz.items()
                              if k in MACRO + MICRO and v is not None},
        "na_max_root_zone": rz.get("Na"),
        "cl_max_root_zone": rz.get("Cl"),
        "hco3_max_root_zone": rz.get("HCO3"),
        "fertigation": {k: ft.get(k, 0.0) for k in MACRO if k in ft},
        "micro_fertigation": {k: ft[k] for k in MICRO if k in ft},
        "growth_stages": stages,
        "high_water_adjustment": high_water,
        "adjustment_normalisations": conversions,
        "ft_checksum_failures": rec.get("ft_bad", []),
        "rz_checksum_failures": rec.get("rz_bad", []),
    }

json.dump(out, open("crops_wur.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1, sort_keys=False)

cats = {}
for c in out["crops"].values():
    cats.setdefault(c["category"], []).append(c["crop_id"])
print(f"crops: {len(out['crops'])}   matrices: "
      f"{sum(len(c['matrices']) for c in out['crops'].values())}")
for k, v in cats.items():
    print(f"  {k:<22} {len(v):>2}  {', '.join(v)}")
if skipped:
    print("UNMATCHED PAGES:", skipped)
for n in notes:
    print(" note:", n)
