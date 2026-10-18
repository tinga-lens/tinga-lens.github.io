#!/usr/bin/env python3
"""
Tinga Lens - Rain and Soil (EXPERIMENTAL, version 0.1).

Where do rainfall and soil moisture disagree, and where are both dry?  It compares two things the site already holds:
the 3-month rainfall total (data/drought_history.json) and the monthly root-zone soil moisture (data/soil_history.json).
It downloads nothing.

Rules (all settings are at the top of this file):
  Same years      both measures are compared with the same reference years (the soil record starts in 2015, so
                  2015 up to last year). That is why this map can differ from the Rainfall tab, which uses 1991-2020.
  Same period     soil moisture of a month is paired with the rainfall of the 3 months ending that month. Windows of
                  1, 2 and 3 months were tested against root-zone and surface soil moisture; 3 months matched best
                  from June to November (median correlation about 0.7, against about 0.35 for one month).
  Dry             in the driest 30% of the reference years (the rule used by the Rainfall and Soil tabs)
  Gap             soil z-score minus rainfall z-score, minus the national median gap that month
                  (the national median is the shared timing effect: soil lags the rain at the start of the season)
  Classes         dry on both; soil drier than rainfall suggests (gap <= -1.5 after the national pattern, and at
                  least 1.0 before it); soil wetter (the same the other way); agree
  Not rated       rainfall normal under 30 mm (dry season); a calendar month in which rainfall and soil moisture do not
                  track each other (median within-district correlation under 0.5; currently April and May);
                  or missing values

Run:
  python scripts/mismatch.py                 # reads data/drought_history.json and data/soil_history.json
  python scripts/mismatch.py --from DIR      # read the two files from another folder (testing)
  python scripts/mismatch.py --self-test     # test the rules on made-up numbers, then stop
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import DATA, MON, ROOT, write_layer  # noqa: E402

BUILD = 1

# ---- settings you may want to change -------------------------------------
DRY_PCT = 30                 # a measure is "dry" when it ranks in the driest 30% of the reference years
FLAG = 1.5                   # gap (in z units, after the national pattern) at which a district is flagged
MIN_RAW = 1.0                # ... and the gap before removing the national pattern must also be at least this, in the same direction
REGION_MIN = 8               # rated districts a region needs before its typical gap is worked out
MIN_COUPLING = 0.5           # a month is rated only when rainfall and soil moisture track each other this well
MIN_REF = 5                  # reference years needed for a district and month
FLOOR_MM = 30                # 3-month rainfall normal (1991-2020) under this: dry season, not rated
HISTORY_MONTHS = 48          # months shown in the district chart
NATIONAL_MIN = 50            # districts needed to work out a national pattern
# --------------------------------------------------------------------------

CATEGORIES = [
    {"key": "both_dry", "label": "Dry on both", "note": "rainfall and soil in the driest 30% of years", "color": "#8c510a"},
    {"key": "soil_drier", "label": "Soil drier than rain suggests", "note": "a large gap, beyond the national pattern", "color": "#e66101"},
    {"key": "soil_wetter", "label": "Soil wetter than rain suggests", "note": "a large gap, beyond the national pattern", "color": "#4393c3"},
    {"key": "agree", "label": "No unusual gap", "note": "not dry on both, and no flagged gap", "color": "#f3efe4"},
    {"key": "not_rated", "label": "Not rated", "note": "dry season, a month the two do not track, or missing", "color": "#bdbdbd"},
]
NAMES = {c["key"]: c["label"] for c in CATEGORIES}
COLORS = {c["key"]: c["color"] for c in CATEGORIES}


# ============================================================ the rules (pure functions, tested below)
def zscores(X, years, months, ref):
    """z-score of every cell against the reference years of the same calendar month. X is districts x months."""
    Z = np.full(X.shape, np.nan)
    for m in range(1, 13):
        cols = np.where(months == m)[0]
        rc = [c for c in cols if ref[0] <= years[c] <= ref[1]]
        if len(rc) < MIN_REF:
            continue
        sub = X[:, rc]
        n = (~np.isnan(sub)).sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            mu = np.nanmean(sub, 1, keepdims=True)
            sd = np.nanstd(sub, 1, ddof=1, keepdims=True)
            Z[:, cols] = (X[:, cols] - mu) / sd
        Z[np.ix_(n < MIN_REF, cols)] = np.nan
    return Z


def pct_ranks(X, years, months, ref):
    """Share (0-100) of the reference years that were lower than each cell (ties count half)."""
    P = np.full(X.shape, np.nan)
    for m in range(1, 13):
        cols = np.where(months == m)[0]
        rc = [c for c in cols if ref[0] <= years[c] <= ref[1]]
        if len(rc) < MIN_REF:
            continue
        refv = X[:, rc]
        for c in cols:
            v = X[:, c:c + 1]
            ok = ~np.isnan(refv)
            n = ok.sum(1)
            with np.errstate(invalid="ignore", divide="ignore"):
                P[:, c] = (((refv < v) & ok).sum(1) + 0.5 * ((refv == v) & ok).sum(1)) / n * 100
            P[n < MIN_REF, c] = np.nan
    return P


def coupling_by_month(zR, zS, months):
    """Median within-district correlation of the two z-scores, for each calendar month (needs 8 pairs per district)."""
    out = {}
    for m in range(1, 13):
        cols = np.where(months == m)[0]
        cs = []
        for i in range(zR.shape[0]):
            a, b = zR[i, cols], zS[i, cols]
            ok = ~np.isnan(a) & ~np.isnan(b)
            if ok.sum() >= 8 and a[ok].std() > 0 and b[ok].std() > 0:
                cs.append(np.corrcoef(a[ok], b[ok])[0, 1])
        out[m] = float(np.median(cs)) if cs else float("nan")
    return out


def gap(zR, zS):
    """(gap after removing the national median, national median) for every month."""
    e = zS - zR
    nat = np.full(e.shape[1], np.nan)
    for t in range(e.shape[1]):
        ok = ~np.isnan(e[:, t])
        if ok.sum() >= NATIONAL_MIN:
            nat[t] = np.median(e[ok, t])
    return e - nat[None, :], nat


def regional_gaps(e, groups):
    """{region: median raw gap} for regions with at least REGION_MIN rated districts."""
    out = {}
    for g in sorted(set(groups)):
        v = np.array([e[i] for i, x in enumerate(groups) if x == g and not np.isnan(e[i])])
        if len(v) >= REGION_MIN:
            out[g] = float(np.median(v))
    return out


def classify(pR, pS, d, raw):
    """Category key for one district and month, or None when it cannot be rated.
    d = gap after the national pattern; raw = gap before it. A flag needs both to be large and in the same direction."""
    if np.isnan(pR) or np.isnan(pS) or np.isnan(d) or np.isnan(raw):
        return None
    if pR <= DRY_PCT and pS <= DRY_PCT:
        return "both_dry"
    if d <= -FLAG and raw <= -MIN_RAW:
        return "soil_drier"
    if d >= FLAG and raw >= MIN_RAW:
        return "soil_wetter"
    return "agree"


def self_test():
    """Check the rules on numbers whose answer is known. Stops with an error if anything is wrong."""
    rng = np.random.default_rng(3)
    # 1. z-scores: reference mean 0, sd 1 -> a cell at +2 sd has z = 2; other years do not use the cell itself when outside the reference
    years = np.repeat(np.arange(2015, 2027), 1)
    months = np.full(len(years), 6)
    X = np.array([[-1.5, -1, -0.5, 0, 0.5, 1, 1.5, -0.2, 0.2, 0.8, -0.8, 2.0]])
    sd = np.std(X[0, :11], ddof=1)
    Z = zscores(X, years, months, (2015, 2025))
    assert abs(Z[0, 11] - (2.0 - X[0, :11].mean()) / sd) < 1e-9
    # 2. too few reference years -> NaN
    assert np.isnan(zscores(X[:, :3], years[:3], months[:3], (2015, 2025))).all()
    # 3. percentile ranks: the lowest of the reference years is below none; a value under all of them is 0; a tie counts half
    P = pct_ranks(X, years, months, (2015, 2025))
    assert pct_ranks(np.array([[1, 2, 3, 4, 5, 0.5]], float), np.arange(2020, 2026), np.full(6, 3), (2020, 2024))[0, 5] == 0
    t = pct_ranks(np.array([[1, 2, 3, 4, 5, 3.0]], float), np.arange(2020, 2026), np.full(6, 3), (2020, 2024))[0, 5]
    assert t == (2 + 0.5) / 5 * 100, t
    # 4. coupling: identical series -> 1, opposite -> -1 (median over districts)
    a = rng.normal(size=(20, 12)); mo = np.full(12, 7)
    assert abs(coupling_by_month(a, a, mo)[7] - 1) < 1e-9 and abs(coupling_by_month(a, -a, mo)[7] + 1) < 1e-9
    assert np.isnan(coupling_by_month(a, a, mo)[3])
    # 5. the national median is removed: every district +1 wetter than rain -> gaps are 0
    zR = rng.normal(size=(80, 5)); zS = zR + 1.0
    d, nat = gap(zR, zS)
    assert np.allclose(nat, 1.0) and np.allclose(d, 0)
    # 6. fewer than NATIONAL_MIN districts: not worked out
    d2, nat2 = gap(zR[:10], zS[:10]); assert np.isnan(nat2).all() and np.isnan(d2).all()
    # 7. classes, including the boundaries and the precedence of "dry on both"
    assert classify(10, 20, 0.0, 0.0) == "both_dry" and classify(10, 20, -3, -3) == "both_dry"
    assert classify(30, 30, 0, 0) == "both_dry" and classify(30.1, 30, 0, 0) == "agree"
    assert classify(60, 20, -1.5, -2) == "soil_drier" and classify(60, 20, -1.49, -2) == "agree"
    assert classify(20, 60, 1.5, 2) == "soil_wetter" and classify(20, 60, 1.49, 2) == "agree"
    assert classify(np.nan, 20, 0, 0) is None and classify(20, 20, np.nan, 0) is None and classify(20, 20, 0, np.nan) is None
    # 8. a flag needs a real raw gap: -1.6 after the national pattern but only -0.7 before it is not flagged
    assert classify(60, 40, -1.6, -0.7) == "agree" and classify(60, 40, -1.6, -1.0) == "soil_drier"
    assert classify(60, 40, -1.6, 0.4) == "agree"          # opposite direction before the pattern was removed
    # 9. regional typical gap: needs REGION_MIN districts
    e = np.array([-3.0] * 10 + [2.0] * 3); g = ["N"] * 10 + ["S"] * 3
    assert regional_gaps(e, g) == {"N": -3.0}
    print("self-test passed: 9 checks")


# ============================================================ data
def load(folder):
    rain = json.loads((folder / "drought_history.json").read_text())
    soil = json.loads((folder / "soil_history.json").read_text())
    ids = list(rain["values"]["rain"])
    if set(ids) != set(soil["values"]["root"]):
        sys.exit("The rainfall and soil moisture files list different districts.")
    return rain, soil, ids


def arr(values, ids, months, wanted):
    idx = [months.index(m) for m in wanted]
    return np.array([[np.nan if values[i][k] is None else values[i][k] for k in idx] for i in ids], float)


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def month_text(label):
    y, m = label.split("-")
    return f"{MON[int(m) - 1]} {y}"


def span_text(label):
    y, m = int(label[:4]), int(label[5:])
    a_y, a_m = (y, m - 2) if m > 2 else (y - 1, m + 10)
    return f"{MON[a_m - 1]} to {MON[m - 1]} {y}" if a_y == y else f"{MON[a_m - 1]} {a_y} to {MON[m - 1]} {y}"


def rank_words(p, n):
    """'wetter than 8 of 11 other years' from a percentile rank (p = share of the reference years that were lower)."""
    k = int(round(p / 100 * n))
    return f"wetter than {k} of {n} other years" if k else f"the lowest of {n + 1} years"


# ============================================================ analysis
def build(rain, soil, ids, names, regions):
    rmonths, smonths = rain["months"], soil["months"]
    common = [m for m in smonths if m in rmonths]
    R = arr(rain["values"]["rain"], ids, rmonths, common)
    S = arr(soil["values"]["root"], ids, smonths, common)
    yr = np.array([int(m[:4]) for m in common])
    mo = np.array([int(m[5:]) for m in common])
    last_year = int(yr[-1])
    ref = (int(yr[0]), last_year - 1)                                   # every year of soil data except the latest
    # rainfall normal for the dry-season floor: 1991-2020 mean of the 3-month total, same calendar month
    full = arr(rain["values"]["rain"], ids, rmonths, rmonths)
    fy = np.array([int(m[:4]) for m in rmonths]); fm = np.array([int(m[5:]) for m in rmonths])
    normal = {m: np.nanmean(full[:, [k for k in range(len(rmonths)) if fm[k] == m and rain["ref"][0] <= fy[k] <= rain["ref"][1]]], 1)
              for m in range(1, 13)}
    floor = np.stack([normal[m] < FLOOR_MM for m in mo], axis=1)
    zR, zS = zscores(R, yr, mo, ref), zscores(S, yr, mo, ref)
    pR, pS = pct_ranks(R, yr, mo, ref), pct_ranks(S, yr, mo, ref)
    for A in (zR, pR):
        A[floor] = np.nan
    coupling = coupling_by_month(zR, zS, mo)
    rated_m = {m: (not np.isnan(c)) and c >= MIN_COUPLING for m, c in coupling.items()}
    d, nat = gap(zR, zS)
    e = zS - zR
    T = len(common)
    cls = np.full((len(ids), T), "", dtype=object)
    for t in range(T):
        for i in range(len(ids)):
            cls[i, t] = (classify(pR[i, t], pS[i, t], d[i, t], e[i, t]) if rated_m[mo[t]] else None) or "not_rated"
    # how often a flag fires by chance in the whole record
    rated_cols = [t for t in range(T) if rated_m[mo[t]]]
    flat = cls[:, rated_cols].ravel()
    ok = flat != "not_rated"
    chance = {k: float((flat[ok] == k).mean() * 100) for k in ("soil_drier", "soil_wetter", "both_dry")}
    t = T - 1
    label = common[t]
    n_ref = len(range(ref[0], ref[1] + 1))
    n_ref_m = {m: int(((mo == m) & (yr >= ref[0]) & (yr <= ref[1])).sum()) for m in range(1, 13)}       # reference years that have this month
    districts = {}
    for i, sid in enumerate(ids):
        c = cls[i, t]
        hist_idx = list(range(max(0, T - HISTORY_MONTHS), T))
        v = [None if (np.isnan(d[i, k]) or not rated_m[mo[k]]) else round(float(np.clip(d[i, k], -3, 3)), 1) for k in hist_idx]
        cc = [cls[i, k] for k in hist_idx]
        base = {"name": names[sid], "cat": c, "v": v, "c": cc, "labels": [common[k] for k in hist_idx]}
        if c == "not_rated":
            if not rated_m[mo[t]]:
                note = f"In {MON[mo[t] - 1]} rainfall and soil moisture do not track each other well, so a gap would not mean much."
            elif floor[i, t]:
                note = "Rainfall is normally under 30 mm over these 3 months (dry season), so rainfall is not rated."
            else:
                note = "A value is missing or there are too few reference years."
            districts[sid] = {**base, "big": "–", "big_note": note, "tip": "Not rated", "rows": []}
            continue
        gv = float(d[i, t])
        words = {"both_dry": "Rainfall and soil moisture are both low for the time of year.",
                 "soil_drier": "Soil is drier than the rainfall suggests, more than the national pattern this month.",
                 "soil_wetter": "Soil is wetter than the rainfall suggests, more than the national pattern this month.",
                 "agree": "No unusual gap between rainfall and soil moisture."}[c]
        rows = [["Rainfall", f"{round(float(R[i, t]))} mm over {span_text(label)}, {rank_words(pR[i, t], n_ref_m[mo[t]])}"],
                ["Soil moisture", f"{float(S[i, t]):.3f} m³/m³ in {month_text(label)}, {rank_words(pS[i, t], n_ref_m[mo[t]])}"],
                ["Gap, soil minus rain", f"{float(e[i, t]):+.1f}"],
                ["National gap", f"{float(nat[t]):+.1f}"],
                ["Gap after the national gap", f"{gv:+.1f}"],
                [f"Rain-soil link in {MON[mo[t] - 1]}", f"correlation {coupling[mo[t]]:.2f}"]]
        if c == "agree" and abs(gv) >= FLAG and abs(float(e[i, t])) < MIN_RAW:
            words = "Large only compared with the national pattern; the gap on its own is small, so it is not flagged."
        districts[sid] = {**base, "big": f"{gv:+.1f}", "big_note": f"{words} Compared with {ref[0]}–{ref[1]}.",
                          "tip": f"{NAMES[c]} · gap {gv:+.1f}", "rows": rows}
    groups = [regions.get(sid, "") for sid in ids]
    rg = regional_gaps(np.where(np.array([c != "not_rated" for c in cls[:, t]]), e[:, t], np.nan), groups) if rated_m[mo[t]] else {}
    for i, sid in enumerate(ids):
        if districts[sid]["rows"] and groups[i] in rg:
            districts[sid]["rows"].append([f"Typical gap, {groups[i]}", f"{rg[groups[i]]:+.1f}"])
    info = dict(regional=rg, label=label, ref=ref, n_ref=n_ref, coupling=coupling, rated_m=rated_m, nat=float(nat[t]) if not np.isnan(nat[t]) else None,
                chance=chance, common=common)
    return districts, info


def render(districts, info):
    label, ref = info["label"], info["ref"]
    skipped = [MON[m - 1] for m in range(1, 13) if not info["rated_m"][m] and not np.isnan(info["coupling"][m])]
    ch = info["chance"]
    nat = info["nat"]
    notes = []
    if nat is not None:
        notes.append(f"Across Ghana as a whole, soil moisture ranks {abs(nat):.1f} standard deviations {'higher' if nat > 0 else 'lower'} than rainfall this month. Flags show districts that differ from that.")
    rg = info.get("regional") or {}
    drier = [g for g, v in sorted(rg.items(), key=lambda kv: kv[1]) if v <= -FLAG]
    wetter = [g for g, v in sorted(rg.items(), key=lambda kv: -kv[1]) if v >= FLAG]
    if drier or wetter:
        notes.append("Gaps come in regional clusters, not isolated districts. Typical gap this month: "
                     + ("soil drier than rain suggests in " + ", ".join(drier) if drier else "") + ("; " if drier and wetter else "")
                     + ("soil wetter in " + ", ".join(wetter) if wetter else "") + ".")
    return {
        "label": "Rain and soil", "title": f"Where rainfall and soil moisture disagree, {month_text(label)} (experimental)",
        "subtitle": f"Rainfall of the 3 months to {month_text(label)} against root-zone soil moisture of {month_text(label)}, both compared with {ref[0]}–{ref[1]}",
        "source": "CHIRPS rainfall (Climate Hazards Center) and NASA SMAP L4 soil moisture, compared by Tinga Lens", "demo": False,
        "categories": CATEGORIES,
        "how": ("EXPERIMENTAL. Rainfall and soil moisture usually move together, but not always. This map shows the districts where they "
                f"do not, and the districts where both are low. Both are ranked against the same years, {ref[0]}–{ref[1]}. A measure is "
                f"\"dry\" when it is in the driest {DRY_PCT}% of those years. The gap is soil minus rainfall, in standard deviations, after taking "
                "away the national pattern for the month (soil lags the rain at the start of the season, so most of Ghana shifts together). "
                f"A district is flagged when its gap is {FLAG:g} or more after that, and at least {MIN_RAW:g} before it. The pop-up shows both ranks and the gap."),
        "limits": [
            "Experimental, version 0.1. It has not been checked against field soil moisture or crop records. A flag is a lead to look into, not evidence of drought or crop stress.",
            f"Both measures use the same reference years, {ref[0]}–{ref[1]}, because the soil record starts in 2015. This map can therefore differ from the Rainfall tab, which compares with 1991–2020.",
            "Soil moisture is a NASA model product (SMAP Level-4) that is driven partly by its own rainfall estimate. Some disagreement with CHIRPS rainfall reflects two rainfall estimates differing, not the land itself.",
            "Rainfall over the 3 months is paired with soil moisture of the last month because that pairing matched best in tests of 1 to 3 months.",
            (f"{', '.join(skipped)} {'is' if len(skipped) == 1 else 'are'} not rated: in those months rainfall and soil moisture do not track each other well (the soil lags the rain at the start of the season)."
             if skipped else "Every month is rated."),
            f"Over {info['common'][0][:4]}–{info['common'][-1][:4]} a flag appeared by chance in about {ch['soil_drier']:.0f}% of rated district-months for soil drier and {ch['soil_wetter']:.0f}% for soil wetter. Only counts well above that mean something.",
            "Flags usually form regional clusters (for example the north against the south coast), which points to the two datasets disagreeing over a whole area as much as to conditions on the ground. Do not read a flag as a problem in one district.",
            f"Ranks rest on only {info['n_ref']} reference years, so they are coarse. Districts that share a 9 km soil grid cell share a soil value.",
            "Dry-season months, when normal rainfall is under 30 mm, are not rated.",
        ],
        "legend_notes": notes,
        "credits": [{"text": "Rainfall: CHIRPS, Climate Hazards Center, UC Santa Barbara", "url": "https://www.chc.ucsb.edu/data/chirps"},
                    {"text": "Soil moisture: NASA SMAP L4 (SPL4SMGP), NSIDC DAAC", "url": "https://nsidc.org/data/spl4smgp"}],
        "chart": {"kind": "diverging", "cap": 3, "unit": " (gap)", "x": next(iter(districts.values()))["labels"],
                  "caption": "Gap each month: soil wetter than rain suggests (up) or drier (down), after the national pattern",
                  "top": "soil wetter", "bottom": "soil drier"},
        "districts": {k: {a: b for a, b in v.items() if a != "labels"} for k, v in districts.items()},
        "build": BUILD,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", help="folder holding drought_history.json and soil_history.json (testing)")
    ap.add_argument("--self-test", action="store_true", help="test the rules, then stop")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    folder = Path(args.src) if args.src else DATA
    for f in ("drought_history.json", "soil_history.json"):
        if not (folder / f).exists():
            print(f"Rain and soil skipped: {folder / f} is missing (build the Rainfall and Soil moisture layers first).")
            return
    rain, soil, ids = load(folder)
    import geopandas as gpd
    gdf = gpd.read_file(ROOT / "data" / "districts.geojson")
    names = dict(zip(gdf.shapeID, gdf.shapeName))
    regions = json.loads((ROOT / "data" / "regions.json").read_text()) if (ROOT / "data" / "regions.json").exists() else {}
    districts, info = build(rain, soil, ids, names, regions)
    if not any(d["cat"] != "not_rated" for d in districts.values()):
        print(f"Rain and soil: no district could be rated for {info['label']} "
              f"({'not a month the two track each other' if not info['rated_m'][int(info['label'][5:])] else 'check the data'}). The existing map is kept.")
        return
    write_layer("mismatch", render(districts, info))


if __name__ == "__main__":
    main()
