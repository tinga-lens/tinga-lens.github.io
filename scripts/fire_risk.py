#!/usr/bin/env python3
"""
Tinga Lens - fire probability (experimental).

Question answered for every district and every sampled day t (one every five days):

    P( at least one VIIRS fire detection in the district during days t .. t+4 )

It is estimated with logistic regression,

    P(F=1) = 1 / (1 + exp(-(b0 + b1*x1 + b2*x2 + ...)))

where the coefficients b are fitted to the record since 2015 and the predictors x
are all known on day t:

    season      how often this district had a fire on these dates in OTHER years
  and, each as a departure from its usual value for that district and time of year:
    sm_surf     SMAP surface soil moisture (0-5 cm) on day t
    d_surf      change in surface soil moisture over the previous five days
    sm_root     SMAP root-zone soil moisture (0-100 cm) on day t
    d_root      change in root-zone soil moisture over the previous five days
    rain3       CHIRPS rainfall total over three months, ending two months before t
    ndvi        VIIRS greenness two months before t

Rainfall and greenness are lagged two months because that is how late those
products are published; the model only uses what would be available in real time.
Temperature, humidity and wind are NOT included yet (they need another data source).

Five models are compared, each tested on fire years it was not trained on:
    M0 season only | M1 + surface | M1r + root zone | M2 + surface and root zone | M3 + rainfall and greenness

This script downloads nothing. It reads what the other layers already saved in cache/.

Run:
  python scripts/fire_risk.py
"""
import datetime as dt
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, DATA, MON, load_districts, write_layer  # noqa: E402

# ---- settings you may want to change -------------------------------------
HORIZON = 5            # days ahead that the probability covers
LAG_MONTHS = 2         # publication delay assumed for rainfall and greenness
SMOOTH = 2.0           # strength of the pull of the seasonal frequency towards the district's overall rate
MIN_NDVI_PIXELS = 20   # pixels needed for a district's monthly greenness to be used
CHART_STEPS = 24       # sampled days shown in the district chart
# --------------------------------------------------------------------------

FEATURES = ["season", "sm_surf", "d_surf", "sm_root", "d_root", "rain3", "ndvi"]
NAMES = {"season": "Usual fire frequency for these dates", "sm_surf": "Surface soil moisture",
         "d_surf": "Surface drying over 5 days", "sm_root": "Root-zone soil moisture",
         "d_root": "Root-zone drying over 5 days", "rain3": "Rainfall, 3 months (lagged)", "ndvi": "Greenness (lagged)"}
MODELS = {
    "M0": ["season"],
    "M1": ["season", "sm_surf", "d_surf"],
    "M1r": ["season", "sm_root", "d_root"],
    "M2": ["season", "sm_surf", "d_surf", "sm_root", "d_root"],
    "M3": ["season", "sm_surf", "d_surf", "sm_root", "d_root", "rain3", "ndvi"],
}
MODEL_TEXT = {"M0": "season only", "M1": "season + surface moisture", "M1r": "season + root-zone moisture",
              "M2": "season + surface + root zone", "M3": "all predictors"}
CATS = [
    {"key": "p1", "label": "Very low", "note": "under 5%", "color": "#ffffcc", "max": 5},
    {"key": "p2", "label": "Low", "note": "5 to 20%", "color": "#fed976", "max": 20},
    {"key": "p3", "label": "Moderate", "note": "20 to 40%", "color": "#fd8d3c", "max": 40},
    {"key": "p4", "label": "High", "note": "40 to 70%", "color": "#e31a1c", "max": 70},
    {"key": "p5", "label": "Very high", "note": "over 70%", "color": "#800026", "max": 101},
]


def month_shift(y, m, k):
    i = y * 12 + (m - 1) + k
    return i // 12, i % 12 + 1


def previous_sample(day, sample_days):
    """The sampled day before `day` (e.g. the 3rd -> the 28th of the month before)."""
    i = sample_days.index(day.day)
    if i > 0:
        return day.replace(day=sample_days[i - 1])
    y, m = month_shift(day.year, day.month, -1)
    return dt.date(y, m, sample_days[-1])


def load_inputs(gdf):
    """Read the four caches and return district-level series."""
    import drought
    import fires
    import smap
    import vegetation

    nd = len(gdf)
    # --- soil moisture: every sampled day ---
    have, grid = smap.load_cache()
    if not have:
        sys.exit("No soil moisture cache. Run the soil moisture layer first.")
    valid = ~np.isnan(next(iter(have.values()))[0])
    cells = smap.cells_per_district(gdf, grid[0], grid[1], valid)
    keys = sorted(have)
    days = [dt.date(int(k[:4]), int(k[4:6]), int(k[6:])) for k in keys]
    root = np.array([[np.mean(have[k][0].ravel()[c]) for c in cells] for k in keys])
    surf = np.array([[np.mean(have[k][1].ravel()[c]) for c in cells] for k in keys])

    # --- fires: daily detections per district ---
    if not fires.CACHE_FILE.exists():
        sys.exit("No fires cache. Run the fires layer first.")
    counts = np.load(fires.CACHE_FILE, allow_pickle=False)["counts"]
    if counts.shape[1] != nd:
        sys.exit("The fires cache does not match the district file.")

    # --- rainfall: monthly district totals ---
    rain = {}
    files = sorted(glob.glob(str(CACHE / "CHIRPS*.npz")), key=lambda p: Path(p).stat().st_mtime)
    if files:
        z = np.load(files[-1], allow_pickle=False)
        dm = drought.district_means(z["stack"], __import__("rasterio").Affine(*z["transform"].tolist()), gdf)
        rain = {tuple(int(v) for v in ym): dm[i] for i, ym in enumerate(z["months"].tolist())}

    # --- greenness: monthly district NDVI ---
    ndvi = {}
    vh = vegetation.load_cache()
    for ym in sorted({k.split("|")[0] for k in vh}):
        ks = [f"{ym}|{t}" for t in vegetation.TILES if f"{ym}|{t}" in vh]
        s = sum(vh[k][0].astype("float64") for k in ks)
        n = sum(vh[k][1].astype("float64") for k in ks)
        with np.errstate(divide="ignore", invalid="ignore"):
            ndvi[(int(ym[:4]), int(ym[5:7]))] = np.where(n >= MIN_NDVI_PIXELS, s / n, np.nan)
    print(f"Inputs: {len(days)} sampled days of soil moisture, {len(counts)} days of fires, "
          f"{len(rain)} months of rainfall, {len(ndvi)} months of greenness")
    return days, root, surf, counts, fires.START, rain, ndvi, smap.SAMPLE_DAYS


def lagged_monthly(table, day, nd, months=1):
    """Sum of `months` monthly values ending LAG_MONTHS before `day`; falls back to the newest month available."""
    y, m = month_shift(day.year, day.month, -LAG_MONTHS)
    if (y, m) not in table and table:
        newest = max(table)
        if newest < (y, m):
            y, m = newest
    vals = [table.get(month_shift(y, m, -j)) for j in range(months)]
    if any(v is None for v in vals):
        return np.full(nd, np.nan)
    return np.sum(vals, axis=0)


def build_panel(gdf):
    """One row per sampled day, one column per district."""
    days, root, surf, counts, fire_start, rain, ndvi, sample_days = load_inputs(gdf)
    nd, K = len(gdf), len(days)
    index = {d: i for i, d in enumerate(days)}

    X = {f: np.full((K, nd), np.nan) for f in FEATURES if f != "season"}
    F = np.full((K, nd), np.nan)                       # 1 = fire in the window, 0 = none, NaN = window not complete
    X["sm_surf"], X["sm_root"] = surf.copy(), root.copy()
    ndvi_by_month = {}
    for (yy, mm), v in ndvi.items():
        ndvi_by_month.setdefault(mm, []).append(v)
    with np.errstate(invalid="ignore"):
        ndvi_clim = {mm: np.nanmean(np.array(v), axis=0) for mm, v in ndvi_by_month.items()}
        ndvi_all = np.nanmean(np.array(list(ndvi.values())), axis=0) if ndvi else np.full(nd, np.nan)
    for k, day in enumerate(days):
        p = index.get(previous_sample(day, sample_days))
        if p is not None:
            gap = (day - days[p]).days
            X["d_surf"][k] = (surf[p] - surf[k]) / gap * 5       # positive = drying
            X["d_root"][k] = (root[p] - root[k]) / gap * 5
        X["rain3"][k] = lagged_monthly(rain, day, nd, months=3)
        v = lagged_monthly(ndvi, day, nd)
        y, m = month_shift(day.year, day.month, -LAG_MONTHS)
        v = np.where(np.isnan(v), ndvi_clim.get(m, ndvi_all), v)   # cloudy month: use that month's usual greenness
        X["ndvi"][k] = np.where(np.isnan(v), ndvi_all, v)
        i0 = (day - fire_start).days
        if i0 >= 0 and i0 + HORIZON <= len(counts):
            F[k] = (counts[i0:i0 + HORIZON].sum(axis=0) > 0).astype(float)
    slot = np.array([(d.month - 1) * len(sample_days) + sample_days.index(d.day) for d in days])
    fire_year = np.array([d.year if d.month >= 7 else d.year - 1 for d in days])   # a fire year runs July to June
    return days, X, F, slot, fire_year, len(sample_days) * 12


def other_years(V, slot, fire_year, nslots, exclude):
    """
    For every row, the average of V in the same part of the year (its slot and the two
    neighbouring slots) over OTHER years: never the row's own year, never a year in `exclude`.
    Returns (plain average, average pulled slightly towards the district's overall average).
    """
    years = np.unique(fire_year)
    nd = V.shape[1]
    ok = ~np.isnan(V)
    v0 = np.where(ok, V, 0.0)
    S = np.zeros((len(years), nslots, nd))
    N = np.zeros((len(years), nslots, nd))
    for yi, y in enumerate(years):
        if y in exclude:
            continue
        rows = fire_year == y
        np.add.at(S[yi], slot[rows], v0[rows])
        np.add.at(N[yi], slot[rows], ok[rows].astype(float))
    St, Nt = S.sum(axis=0), N.sum(axis=0)
    plain, shrunk = np.full(V.shape, np.nan), np.full(V.shape, np.nan)
    for yi, y in enumerate(years):
        s, n = St - S[yi], Nt - N[yi]                              # leave the row's own year out
        s3 = s + np.roll(s, 1, axis=0) + np.roll(s, -1, axis=0)    # this slot and its two neighbours
        n3 = n + np.roll(n, 1, axis=0) + np.roll(n, -1, axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            overall = s.sum(axis=0) / np.maximum(n.sum(axis=0), 1)
            rows = fire_year == y
            plain[rows] = np.where(n3 > 0, s3 / n3, np.nan)[slot[rows]]
            shrunk[rows] = ((s3 + SMOOTH * overall) / (n3 + SMOOTH))[slot[rows]]
    return plain, shrunk


def prepare(X, F, slot, fire_year, nslots, exclude):
    """
    Season term (log-odds of the usual fire frequency) and every predictor as a
    departure from its usual value for that district and time of year.
    """
    _, freq = other_years(F, slot, fire_year, nslots, exclude)
    p = np.clip(freq, 0.002, 0.998)
    anomalies = {c: X[c] - other_years(X[c], slot, fire_year, nslots, exclude)[0] for c in X}
    return np.log(p / (1 - p)), freq, anomalies


def design(X, season, cols, rows):
    return np.column_stack([(season if c == "season" else X[c])[rows].ravel() for c in cols])


def fit(Xm, y):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(), LogisticRegression(C=10.0, max_iter=500)).fit(Xm, y)


def scores(y, p, p_ref):
    from sklearn.metrics import roc_auc_score
    bs = float(np.mean((p - y) ** 2))
    bs_ref = float(np.mean((p_ref - y) ** 2))
    bs_rate = float(np.mean((y.mean() - y) ** 2))
    return {"auc": float(roc_auc_score(y, p)), "brier": bs,
            "skill_vs_season": 1 - bs / bs_ref if bs_ref > 0 else 0.0,
            "skill_vs_base_rate": 1 - bs / bs_rate if bs_rate > 0 else 0.0}


def main():
    gdf = load_districts()
    nd = len(gdf)
    days, X, F, slot, fire_year, nslots = build_panel(gdf)
    K = len(days)
    complete = ~np.isnan(np.stack([X[c] for c in X], axis=0)).any(axis=0)       # all predictors present
    usable = complete & ~np.isnan(F)
    years = [int(y) for y in np.unique(fire_year[usable.any(axis=1)])]
    if len(years) < 4 or usable.sum() < 5000:
        sys.exit("Not enough overlapping soil moisture and fire data to fit the model.")
    y_all = F[usable]
    print(f"Panel: {int(usable.sum()):,} district-periods, {len(years)} fire years, "
          f"fire in {y_all.mean() * 100:.1f}% of them")

    # ---- test each model on fire years it has not seen ----
    oof = {m: np.full(F.shape, np.nan) for m in MODELS}
    for held in years:
        season, _, Xa = prepare(X, F, slot, fire_year, nslots, exclude={held})
        ready = usable & ~np.isnan(np.stack(list(Xa.values()))).any(axis=0)
        train = ready & (fire_year != held)[:, None]
        test = ready & (fire_year == held)[:, None]
        if not test.any():
            continue
        for m, cols in MODELS.items():
            model = fit(design(Xa, season, cols, train), F[train])
            oof[m][test] = model.predict_proba(design(Xa, season, cols, test))[:, 1]
    tested = usable & ~np.isnan(oof["M0"])
    yt = F[tested]
    metrics = {m: scores(yt, oof[m][tested], oof["M0"][tested]) for m in MODELS}
    by_year = {}
    from sklearn.metrics import roc_auc_score
    for held in years:
        rows = tested & (fire_year == held)[:, None]
        if rows.any() and 0 < F[rows].mean() < 1:
            by_year[held] = {m: {"auc": float(roc_auc_score(F[rows], oof[m][rows])),
                                 "brier": float(np.mean((oof[m][rows] - F[rows]) ** 2))} for m in MODELS}

    def gain(a, b):                    # how much model a improves on model b
        wins = [v[a]["brier"] < v[b]["brier"] for v in by_year.values()]
        return {"auc_gain": metrics[a]["auc"] - metrics[b]["auc"],
                "brier_reduction_pct": (1 - metrics[a]["brier"] / metrics[b]["brier"]) * 100,
                "years_better": int(np.sum(wins)), "years": len(wins)}

    comparisons = {"root_added_to_surface": gain("M2", "M1"), "root_instead_of_surface": gain("M1r", "M1"),
                   "surface_over_season": gain("M1", "M0"), "all_over_season": gain("M3", "M0")}

    print("\nTested on years left out of training:")
    print(f"  {'model':<5} {'predictors':<32} {'AUC':>6} {'Brier':>7} {'skill vs season':>16}")
    for m in MODELS:
        s = metrics[m]
        print(f"  {m:<5} {MODEL_TEXT[m]:<32} {s['auc']:>6.3f} {s['brier']:>7.4f} {s['skill_vs_season'] * 100:>15.1f}%")
    r = comparisons["root_added_to_surface"]
    print(f"  Adding root zone to surface: AUC {r['auc_gain']:+.4f}, error (Brier) {-r['brier_reduction_pct']:+.2f}%, "
          f"better in {r['years_better']} of {r['years']} test years")

    # reliability of the full model: do predicted chances match what happened?
    edges = [0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0001]
    final_now = min(MODELS, key=lambda m: (round(metrics[m]["brier"], 5), len(MODELS[m])))
    p3 = oof[final_now][tested]

    # month by month: is it still good when the calendar alone cannot help?
    month_of = np.array([d.month for d in days])
    by_month = []
    for mm in range(1, 13):
        rows = tested & (month_of == mm)[:, None]
        if not rows.any():
            continue
        yy, pp, p0 = F[rows], oof[final_now][rows], oof["M0"][rows]
        both = 0 < yy.mean() < 1
        by_month.append({"month": MON[mm - 1], "n": int(rows.sum()), "observed": float(yy.mean()), "predicted": float(pp.mean()),
                         "auc": float(roc_auc_score(yy, pp)) if both else None,
                         "auc_season_only": float(roc_auc_score(yy, p0)) if both else None,
                         "brier": float(np.mean((pp - yy) ** 2))})
    print("\nMonth by month, on years left out of training:")
    print(f"  {'month':<6} {'fires seen':>10} {'predicted':>10} {'AUC':>6} {'season only':>12}")
    for b in by_month:
        fmt = lambda v: f"{v:.3f}" if v is not None else "  -  "
        print(f"  {b['month']:<6} {b['observed'] * 100:>9.1f}% {b['predicted'] * 100:>9.1f}% {fmt(b['auc']):>6} {fmt(b['auc_season_only']):>12}")
    reliability = []
    for a, b in zip(edges[:-1], edges[1:]):
        sel = (p3 >= a) & (p3 < b)
        if sel.sum():
            reliability.append({"predicted_from": a, "predicted_to": min(b, 1.0), "mean_predicted": float(p3[sel].mean()),
                                "observed": float(yt[sel].mean()), "n": int(sel.sum())})

    # ---- final model on everything, then today's probabilities ----
    season, season_p, Xa = prepare(X, F, slot, fire_year, nslots, exclude=set())
    ready = usable & ~np.isnan(np.stack(list(Xa.values()))).any(axis=0)
    final = min(MODELS, key=lambda m: (round(metrics[m]["brier"], 5), len(MODELS[m])))   # best on held-out years; simpler wins ties
    print(f"\nModel used for the map: {final} ({MODEL_TEXT[final]})")
    cols = MODELS[final]
    model = fit(design(Xa, season, cols, ready), F[ready])
    coef = model[-1].coef_[0]
    coefficients = [{"predictor": c, "name": NAMES[c], "coefficient_per_sd": float(b), "odds_ratio_per_sd": float(np.exp(b))}
                    for c, b in zip(cols, coef)]
    print("\nModel used, effect of one standard deviation (odds ratio):")
    for c in coefficients:
        print(f"  {c['name']:<40} {c['odds_ratio_per_sd']:.2f}")

    last = K - 1                                         # newest sampled day
    Xn = {c: np.nan_to_num(Xa[c]) for c in Xa}            # a missing value is treated as "normal"
    steps = list(range(max(0, last - CHART_STEPS + 1), last + 1))
    P = np.array([model.predict_proba(np.column_stack([(season if c == "season" else Xn[c])[k] for c in cols]))[:, 1]
                  for k in steps])
    day = days[last]
    end = day + dt.timedelta(days=HORIZON - 1)
    period = (f"{day.day} to {end.day} {MON[end.month - 1]} {end.year}" if day.month == end.month
              else f"{day.day} {MON[day.month - 1]} to {end.day} {MON[end.month - 1]} {end.year}")
    known = ~np.isnan(F[:, 0])
    same = known & (slot == slot[last])

    districts = {}
    for i, row in gdf.iterrows():
        p = float(P[-1, i]) * 100
        cat = next(c["key"] for c in CATS if p < c["max"])
        districts[row.shapeID] = {
            "name": row.shapeName, "cat": cat,
            "big": f"{p:.0f}%",
            "big_note": f"estimated chance of at least one fire detection, {period}",
            "tip": f"{next(c['label'] for c in CATS if c['key'] == cat)} · {p:.0f}%",
            "rows": [
                ["Usual chance for these dates", f"{season_p[last, i] * 100:.0f}%"],
                ["Years with a fire on these dates", f"{int(F[same, i].sum())} of {int(same.sum())}"],
                ["Root-zone soil moisture", f"{X['sm_root'][last, i]:.2f} m³/m³ ({Xn['sm_root'][last, i]:+.2f} vs usual)"],
                ["Surface soil moisture", f"{X['sm_surf'][last, i]:.2f} m³/m³ ({Xn['sm_surf'][last, i]:+.2f} vs usual)"],
            ],
            "v": [round(float(v) * 100, 1) for v in P[:, i]],
            "c": [cat] * len(steps),
        }

    best = metrics[final]
    root_text = (f"Adding root-zone moisture to surface moisture changed the prediction error by {-r['brier_reduction_pct']:+.1f}% "
                 f"and gave a better score in {r['years_better']} of {r['years']} test years.")
    report = {
        "event": f"At least one VIIRS fire detection in the district within {HORIZON} days of a sampled day",
        "rows": int(usable.sum()), "fire_share": float(y_all.mean()), "fire_years_tested": years,
        "models": {m: {"predictors": MODELS[m], **metrics[m]} for m in MODELS},
        "auc_by_fire_year": by_year, "comparisons": comparisons,
        "model_used": final, "by_month": by_month,
        "full_model_coefficients": coefficients, "reliability_full_model": reliability,
        "notes": ["Scores are from fire years left out of training (July to June).",
                  "Every predictor is a departure from its usual value for that district and time of year, computed without the row's own year.",
                  "The seasonal frequency never uses the row's own year.",
                  f"Rainfall and greenness are lagged {LAG_MONTHS} months to match their publication delay.",
                  "No temperature, humidity or wind predictors yet."],
    }
    (DATA / "firerisk_report.json").write_text(json.dumps(report, indent=1))

    # every sampled day: the estimate made WITHOUT that fire year in training, and what happened
    every = np.array([model.predict_proba(np.column_stack([(season if c == "season" else Xn[c])[k] for c in cols]))[:, 1]
                      for k in range(K)])
    shown = np.where(np.isnan(oof[final]), every, oof[final])          # newest days have no test estimate yet
    ids = list(gdf.shapeID)
    (DATA / "firerisk_history.json").write_text(json.dumps({
        "kind": "probability", "horizon": HORIZON, "breaks": [c["max"] for c in CATS[:-1]],
        "days": [d.isoformat() for d in days],
        "note": "Past estimates come from a model that was not shown that fire year, so they are a fair test.",
        "p": {ids[i]: [int(round(v * 100)) for v in shown[:, i]] for i in range(nd)},
        "u": {ids[i]: [int(round(v * 100)) for v in season_p[:, i]] for i in range(nd)},
        "o": {ids[i]: [None if np.isnan(v) else int(v) for v in F[:, i]] for i in range(nd)},
    }, separators=(",", ":")))
    print("Wrote data/firerisk_history.json")
    print("Wrote data/firerisk_report.json")

    write_layer("firerisk", {
        "history": "data/firerisk_history.json",
        "tables": [{
            "caption": "How the model did in each month, on fire years it was not trained on",
            "head": ["Month", "Periods with a fire", "Average estimate", "Score (AUC)", "Season alone"],
            "rows": [[b["month"], f"{b['observed'] * 100:.0f}%", f"{b['predicted'] * 100:.0f}%",
                      "–" if b["auc"] is None else f"{b['auc']:.2f}",
                      "–" if b["auc_season_only"] is None else f"{b['auc_season_only']:.2f}"] for b in by_month],
            "note": ("AUC is 0.5 for guessing and 1 for a perfect ranking of districts. 'Season alone' uses only how often each "
                     "district usually burns on those dates."),
        }],
        "label": "Fire risk", "title": "Estimated chance of fire (experimental)",
        "subtitle": f"{period}", "source": "Tinga Lens model on NASA SMAP, FIRMS, VIIRS and CHIRPS data", "demo": False,
        "categories": [{k: c[k] for k in ("key", "label", "note", "color")} for c in CATS],
        "how": (f"Each district shows the estimated chance that satellites record at least one fire in it during the {HORIZON} days shown. "
                "The estimate comes from a statistical model (logistic regression) fitted to fires since 2015. It combines how "
                "often the district burned on these dates in other years with how far surface and root-zone soil moisture, the "
                "speed of drying, and lagged rainfall and greenness are from their usual values for the time of year. "
                "Use the Year, Month and Day boxes to see any past period and whether a fire was then detected."),
        "limits": [
            "This is an experimental model, not a fire warning. Do not use it for safety decisions.",
            f"Tested on years it was not trained on, the model scored AUC {best['auc']:.2f} (0.5 is chance, 1 is perfect) and "
            f"improved on the seasonal pattern alone by {best['skill_vs_season'] * 100:.0f}% (Brier skill).",
            root_text,
            "Temperature, humidity and wind are not included, so short hot, dry, windy spells are missed.",
            "A fire here means a satellite detection. Small or short fires are missed, and most detections are seasonal farm and bush burning.",
            "Larger districts have a higher chance simply because there is more land to burn.",
        ],
        "credits": [{"text": "Fires: NASA FIRMS", "url": "https://firms.modaps.eosdis.nasa.gov/"},
                    {"text": "Soil moisture: NASA SMAP L4", "url": "https://nsidc.org/data/spl4smgp"}],
        "chart": {"kind": "bars", "unit": "%", "x": [f"{days[k].day} {MON[days[k].month - 1]}" for k in steps],
                  "caption": f"Estimated chance on each of the last {len(steps)} sampled days (%)", "top": "", "bottom": ""},
        "districts": districts,
    })


if __name__ == "__main__":
    main()
