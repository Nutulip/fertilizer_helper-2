"""
Self-calibrating extractor for WUR Section B crop tables.

Column positions vary by page layout, so bins are discovered per page by
clustering the x-positions of numeric tokens. The table's own ppm/ppb column
then validates every extracted value: ppm = mmol x atomic weight.

The FERTIGATION column is used as the primary checksum because it is
internally consistent throughout the manual. Root-zone mismatches are
reported separately, since at least one page (p.50 sweet pepper) has a
root-zone ppm column copied from another crop.
"""
import re, json, sys
import pymupdf

PDF = r'D:\电脑 Yoshida 相关\信息 知识\WUR植物营养标准\2020-nutrient-solutions-for-greenhouse-crops.pdf'

AW = {"NH4":14.0,"K":39.10,"Na":22.99,"Ca":40.08,"Mg":24.31,"NO3":14.0,
      "Cl":35.45,"S":32.06,"HCO3":61.02,"P":30.97,
      "Fe":55.85,"Mn":54.94,"Zn":65.38,"B":10.81,"Cu":63.55,"Mo":95.94}

ALIAS = {"pH":"pH","EC":"EC","Na":"Na","Cl":"Cl","HCO":"HCO3","HCO3":"HCO3",
         "N-NH":"NH4","N-NH4":"NH4","NH4":"NH4","K":"K","Ca":"Ca","Mg":"Mg",
         "N-NO":"NO3","N-NO3":"NO3","NO3":"NO3","S":"S","P":"P","Si":"Si",
         "Fe":"Fe","Mn":"Mn","Zn":"Zn","B":"B","Cu":"Cu","Mo":"Mo"}

MACRO = ["NH4","K","Ca","Mg","NO3","Cl","S","P"]
MICRO = ["Fe","Mn","Zn","B","Cu","Mo"]
CEIL  = ["Na","Cl","HCO3","NH4"]
STAGES = ["start","fruit_set","high_water","end_season"]

# Adjustment column headers are NOT the same across Section B. Fruiting
# vegetables print Start / Fruit Set / High water / End season, but roses use
# Start / Flowering / High water supply / Winter, alstroemeria only
# Start / Flowering, anthurium only Start. Reading the printed header is the
# only way to label a stage correctly.
HEADER_MAP = [
    ("high water", "high_water"), ("fruit set", "fruit_set"),
    ("end season", "end_season"), ("end of season", "end_season"),
    ("final", "end_season"), ("winter", "winter"),
    ("flowering", "flowering"), ("production", "production"),
    ("vegetative", "vegetative"), ("start", "start"),
]


def header_stage_names(page, adj_x_centres):
    """Map each adjustment column x-centre to the stage name printed above it."""
    words = [(x0, x1, y0, w) for x0, y0, x1, y1, w, *_ in page.get_text("words")]
    ph_y = min((y for x0, x1, y, w in words if w.strip().rstrip("*") == "pH"),
               default=None)
    if ph_y is None:
        return [None] * len(adj_x_centres)
    band = [(x0, x1, y, w) for x0, x1, y, w in words if y < ph_y - 2]
    # group header tokens into rows, then into phrases by x proximity
    rows = {}
    for x0, x1, y, w in band:
        rows.setdefault(round(y / 4) * 4, []).append((x0, x1, w))
    phrases = []
    for y, items in rows.items():
        items.sort()
        cur = []
        for x0, x1, w in items:
            if cur and x0 - cur[-1][1] > 6:
                phrases.append((cur[0][0], cur[-1][1], " ".join(t[2] for t in cur)))
                cur = []
            cur.append((x0, x1, w))
        if cur:
            phrases.append((cur[0][0], cur[-1][1], " ".join(t[2] for t in cur)))

    named = []
    for cx in adj_x_centres:
        best, bestd = None, 1e9
        for x0, x1, text in phrases:
            low = text.lower()
            stage = next((sid for key, sid in HEADER_MAP if key in low), None)
            if stage is None:
                continue
            centre = (x0 + x1) / 2
            d = abs(centre - cx)
            if d < bestd:
                best, bestd = stage, d
        named.append(best if bestd < 70 else None)
    return named
NUM = re.compile(r'^<?\s*-?\d+(?:[.,]\d+)?$')


def parse_num(tok):
    t = tok.strip()
    if not NUM.match(t):
        return None
    return float(t.replace("<","").replace(",",".").strip())


def cluster(xs, gap=16):
    xs = sorted(xs)
    groups, cur = [], [xs[0]]
    for x in xs[1:]:
        if x - cur[-1] <= gap:
            cur.append(x)
        else:
            groups.append(cur); cur = [x]
    groups.append(cur)
    return [(min(g)-6, max(g)+6, sum(g)/len(g)) for g in groups]


def extract(doc, pageno):
    page = doc[pageno-1]
    text = page.get_text("text")
    m = re.search(r'CROP:\s*([^\n]+)', text)
    if not m:
        return None
    title = re.sub(r'\s+', ' ', m.group(1)).strip()

    up = text.upper()
    if "INERT SUBSTRATE" in up:      medium = "INERT_SUBSTRATE"
    elif "ORGANIC MATERIAL" in up:   medium = "ORGANIC_MATERIAL"
    elif re.search(r'\bSOIL\b', up): medium = "SOIL"
    elif "1:1.5 VOLUME" in up:       medium = "ORGANIC_MATERIAL"
    elif "1:2 VOLUME" in up:         medium = "SOIL"
    else:                            medium = "INERT_SUBSTRATE"
    has_adj = "Adjustments" in text

    rows = {}
    for x0, y0, x1, y1, w, *_ in page.get_text("words"):
        rows.setdefault(round(y0/4)*4, []).append((x0, x1, w))
    # A single cell can be split into adjacent word tokens ("110" -> "10","1").
    # Re-join numeric fragments that sit within a few points of each other.
    for y, items in list(rows.items()):
        items.sort()
        merged, i = [], 0
        while i < len(items):
            x0, x1, w = items[i]
            while (i + 1 < len(items) and items[i+1][0] - x1 < 4.0
                   and re.fullmatch(r'<?\d+(?:[.,]\d+)?', w)
                   and re.fullmatch(r'\d+(?:[.,]\d+)?', items[i+1][2])):
                w += items[i+1][2]; x1 = items[i+1][1]; i += 1
            merged.append((x0, w)); i += 1
        rows[y] = merged

    # ---- locate nutrient rows and their numeric tokens ----
    # Three row labels (HCO3, N-NH4, N-NO3) carry no text layer in this PDF --
    # they are drawn as unmappable glyphs. Section B's row order is fixed and
    # complete in every table, so labels that DO resolve act as anchors and the
    # gaps are filled positionally against the canonical sequence.
    CANON = ["pH","EC","Na","Cl","HCO3","NH4","K","Ca","Mg","NO3","S","P",
             "Fe","Mn","Zn","B","Cu","Mo"]

    candidates = []
    for y in sorted(rows):
        items = sorted(rows[y])
        label = None
        for x, w in items:
            if x < 115:
                k = w.strip().rstrip(",").rstrip(".").rstrip("*").rstrip(".")
                if k in ALIAS:
                    label = ALIAS[k]; break
        nums = [(x, parse_num(w)) for x, w in items
                if x >= 115 and parse_num(w) is not None]
        if label or nums:
            candidates.append([y, label, nums, items])

    start = next((i for i, c in enumerate(candidates) if c[1] == "pH"), None)
    if start is None:
        return None

    labelled, ci = [], -1
    for y, label, nums, items in candidates[start:]:
        # A table row always carries at least the mmol and ppm cells.
        if label != "pH" and len(nums) < 2:
            continue
        if label and label in CANON:
            idx = CANON.index(label)
            if idx <= ci:          # footnote text re-using an ion letter
                continue
            ci = idx
        else:
            if ci + 1 >= len(CANON):
                break
            ci += 1
            label = CANON[ci]
        labelled.append((label, nums, items))
        if ci == len(CANON) - 1:
            break

    all_x = [x for _, nums, _ in labelled for x, _ in nums]
    if not all_x:
        return None
    cols = cluster(all_x)
    if len(cols) < 4:
        return None

    def col_index(x):
        for i, (lo, hi, _) in enumerate(cols):
            if lo <= x <= hi:
                return i
        return None

    # ---- calibrate: which column pair is (mmol, ppm)? ----
    # Layout is [rz_mmol, ft_mmol, rz_ppm, ft_ppm, adj...]; verify by ratio.
    def score(im, ip):
        hits = 0
        for label, nums, _ in labelled:
            aw = AW.get(label)
            if not aw:
                continue
            cells = {}
            for x, v in nums:
                ci = col_index(x)
                if ci is not None:
                    cells.setdefault(ci, v)
            a, b = cells.get(im), cells.get(ip)
            if a is None or b is None or a == 0:
                continue
            if abs(a*aw - b) <= max(1.5, abs(a*aw)*0.03):
                hits += 1
        return hits

    best = None
    for im in range(min(4, len(cols))):
        for ip in range(im+1, min(6, len(cols))):
            s = score(im, ip)
            if best is None or s > best[0]:
                best = (s, im, ip)
    ft_pair = None
    cand = sorted(((score(im, ip), im, ip)
                   for im in range(min(4, len(cols)))
                   for ip in range(im+1, min(6, len(cols)))), reverse=True)
    if not cand or cand[0][0] < 3:
        return None
    # the two best disjoint pairs are (rz_m, rz_p) and (ft_m, ft_p)
    p1 = cand[0]
    p2 = next((c for c in cand[1:]
               if c[1] != p1[1] and c[2] != p1[2] and c[0] >= 3), None)
    pairs = sorted([p for p in (p1, p2) if p], key=lambda c: c[1])
    if len(pairs) == 2:
        (_, rz_m, rz_p), (_, ft_m, ft_p) = pairs
    else:
        _, ft_m, ft_p = p1
        rz_m = ft_m - 1 if ft_m > 0 else None
        rz_p = ft_p - 1 if ft_p > 0 else None

    adj_start = max(ft_p, rz_p if rz_p is not None else -1) + 1
    adj_candidates = list(range(adj_start, len(cols)))

    # Adjustment cells are also printed as (mmol, ppm) pairs. Positional
    # pairing breaks when a table has fewer than four adjustment columns, so
    # identify the mmol members by the same ratio test used for the main
    # table: a column is mmol if some column to its right equals value x AW.
    def is_mmol_column(ci):
        hits = misses = 0
        for label, nums, _ in labelled:
            aw = AW.get(label)
            if not aw:
                continue
            cells = {}
            for x, v in nums:
                k = col_index(x)
                if k is not None:
                    cells.setdefault(k, v)
            v = cells.get(ci)
            if v is None or v == 0:
                continue
            if any(abs(v*aw - cells[cj]) <= max(1.0, abs(v*aw)*0.05)
                   for cj in adj_candidates if cj > ci and cj in cells):
                hits += 1
            else:
                misses += 1
        return hits > 0 and hits >= misses

    adj_cols = [ci for ci in adj_candidates if is_mmol_column(ci)]
    if not adj_cols:
        adj_cols = adj_candidates[::2]

    adj_names = header_stage_names(page, [cols[ci][2] for ci in adj_cols])         if adj_cols else []

    rec = {"page": pageno, "title": title, "medium": medium,
           "adjustment_headers": adj_names,
           "has_adjustments": has_adj, "rz": {}, "ft": {}, "adj": {},
           "ph_rz": None, "ph_ft": None, "ec_rz": None, "ec_ft": None,
           "ft_ok": [], "ft_bad": [], "rz_bad": []}

    for label, nums, items in labelled:
        cells = {}
        for x, v in nums:
            ci = col_index(x)
            if ci is not None:
                cells.setdefault(ci, v)
        if label == "pH":
            vals = [v for x, v in nums if col_index(x) in (rz_m, ft_m)]
            raw = [w for x, w in items if 115 <= x and re.match(r'^\d', w)]
            rec["ph_rz"] = raw[0] if raw else None
            rec["ph_ft"] = cells.get(ft_m)
            continue
        if label == "EC":
            rec["ec_rz"] = cells.get(rz_m); rec["ec_ft"] = cells.get(ft_m)
            continue
        if label == "Si":
            continue
        if rz_m is not None and rz_m in cells:
            rec["rz"][label] = cells[rz_m]
        if ft_m in cells:
            rec["ft"][label] = cells[ft_m]

        aw = AW.get(label)
        if aw:
            a, b = cells.get(ft_m), cells.get(ft_p)
            if a is not None and b is not None and a != 0:
                (rec["ft_ok"] if abs(a*aw-b) <= max(1.5, abs(a*aw)*0.03)
                 else rec["ft_bad"]).append(f"{label}:{a}x{aw}={a*aw:.1f}vs{b}")
            a, b = cells.get(rz_m), cells.get(rz_p)
            if a is not None and b is not None and a != 0:
                if abs(a*aw-b) > max(1.5, abs(a*aw)*0.03):
                    rec["rz_bad"].append(f"{label}:{a}x{aw}={a*aw:.1f}vs{b}")

        if has_adj and adj_cols:
            adj = {}
            for k, ci in enumerate(adj_cols):
                name = adj_names[k] if k < len(adj_names) else None
                if name is None:
                    name = STAGES[k] if k < len(STAGES) else f"stage_{k}"
                if ci in cells:
                    adj[name] = cells[ci]
            if adj:
                rec["adj"][label] = adj
    return rec


if __name__ == "__main__":
    doc = pymupdf.open(PDF)
    pages = [int(a) for a in sys.argv[1:]] or [p for p in range(41, 95)]
    out, ftfail, rzfail = {}, [], []
    for pn in pages:
        try:
            r = extract(doc, pn)
        except Exception as e:
            print(f"  p.{pn} EXCEPTION {e}"); continue
        if not r or not r["ft"]:
            continue
        out[pn] = r
        if r["ft_bad"]:
            ftfail.append((pn, r["title"], r["medium"], r["ft_bad"]))
        if r["rz_bad"]:
            rzfail.append((pn, r["title"], r["medium"], r["rz_bad"]))
    json.dump(out, open("crops2.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"tables extracted: {len(out)}")
    print(f"FERTIGATION cross-check failures: {len(ftfail)}")
    for pn,t,m,b in ftfail:
        print(f"   p.{pn} {t[:34]:<34} [{m}] {b[:3]}")
    print(f"root-zone ppm mismatches (source errata): {len(rzfail)}")
    for pn,t,m,b in rzfail:
        print(f"   p.{pn} {t[:34]:<34} [{m}] {b[:3]}")
