#!/usr/bin/env python3
"""
Tinga Lens - biodiversity: recorded species by district.

Source: GBIF (Global Biodiversity Information Facility) occurrence records for Ghana.
A record says that somebody saw or collected a species at a place and time. This script
asks GBIF for every usable record in Ghana, places each one in a district, and writes:

  data/biodiversity.json            the map layer: recorded species per district
  data/bio/species.json             every recorded species (name, group, Red List category, totals)
  data/bio/pairs.json               for each species, the districts it was recorded in
  data/bio/districts/<shapeID>.json for each district, the species recorded there

"Recorded species" depends on how much surveying has been done. It is not the number of
species that live in a district, and no record does not mean a species is absent.

Needs a free GBIF account, given as GBIF_USER, GBIF_PWD and GBIF_EMAIL.

Run:
  python scripts/biodiversity.py
"""
import datetime as dt
import io
import json
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, DATA, load_districts, write_layer  # noqa: E402

# ---- settings you may want to change -------------------------------------
API = os.environ.get("TINGA_GBIF_API", "https://api.gbif.org/v1")
INCLUDE_NONCOMMERCIAL = False           # True adds records under CC BY-NC: more mammals, but the layer may then not be used commercially
LICENSES = ["CC0_1_0", "CC_BY_4_0"] + (["CC_BY_NC_4_0"] if INCLUDE_NONCOMMERCIAL else [])
MAX_UNCERTAINTY_M = 25000               # records whose position is vaguer than this are left out
SKIP_BASIS = {"FOSSIL_SPECIMEN", "LIVING_SPECIMEN"}   # fossils, and zoo or garden specimens
WAIT_MINUTES = 180                      # how long to wait for GBIF to prepare the download
THREATENED = {"CR": "Critically Endangered", "EN": "Endangered", "VU": "Vulnerable"}
LOOKUP_WORKERS = 8
# --------------------------------------------------------------------------

GROUPS = ["Plants", "Birds", "Mammals", "Reptiles", "Amphibians", "Fish", "Insects", "Fungi", "Other"]
FISH = {"Actinopterygii", "Teleostei", "Elasmobranchii", "Chondrichthyes", "Holocephali", "Sarcopterygii", "Dipneusti",
        "Cladistii", "Chondrostei", "Holostei", "Coelacanthi", "Myxini", "Petromyzonti", "Cephalaspidomorphi"}
REPTILES = {"Reptilia", "Squamata", "Testudines", "Crocodylia", "Sphenodontia"}
CATS = [
    {"key": "s0", "label": "No usable records", "note": "", "color": "#bdbdbd", "max": 1},
    {"key": "s1", "label": "Under 50 species", "note": "", "color": "#edf8e9", "max": 50},
    {"key": "s2", "label": "50 to 150", "note": "", "color": "#bae4b3", "max": 150},
    {"key": "s3", "label": "150 to 400", "note": "", "color": "#74c476", "max": 400},
    {"key": "s4", "label": "400 to 1,000", "note": "", "color": "#31a354", "max": 1000},
    {"key": "s5", "label": "Over 1,000", "note": "", "color": "#006d2c", "max": 1e12},
]
COLS = ["gbifID", "datasetKey", "kingdom", "phylum", "class", "species", "speciesKey", "decimalLatitude", "decimalLongitude",
        "coordinateUncertaintyInMeters", "year", "basisOfRecord", "occurrenceStatus"]


def group_of(kingdom, phylum, cls):
    if kingdom == "Plantae":
        return "Plants"
    if kingdom == "Fungi":
        return "Fungi"
    if cls == "Aves":
        return "Birds"
    if cls == "Mammalia":
        return "Mammals"
    if cls in REPTILES:
        return "Reptiles"
    if cls == "Amphibia":
        return "Amphibians"
    if cls in FISH or (phylum == "Chordata" and not isinstance(cls, str)):   # GBIF gives bony fish no class
        return "Fish"
    if cls == "Insecta":
        return "Insects"
    return "Other"


# ---------- GBIF download ----------
def request_download(s, auth, email):
    """Ask GBIF to prepare the Ghana records. Returns the download key."""
    keyfile = CACHE / "gbif_download.txt"
    if keyfile.exists():                               # a request from an earlier run that may still be usable
        key, day, *lic = keyfile.read_text().split()
        if day[:7] == dt.date.today().isoformat()[:7] and (lic or ["2"])[0] == str(len(LICENSES)):   # same month, same licence choice
            print(f"Using this month's GBIF download {key}")
            return key
    body = {"creator": auth[0], "notificationAddresses": [email] if email else [], "sendNotification": False, "format": "SIMPLE_CSV",
            "predicate": {"type": "and", "predicates": [
                {"type": "equals", "key": "COUNTRY", "value": "GH"},
                {"type": "equals", "key": "HAS_COORDINATE", "value": "true"},
                {"type": "equals", "key": "HAS_GEOSPATIAL_ISSUE", "value": "false"},
                {"type": "equals", "key": "OCCURRENCE_STATUS", "value": "PRESENT"},
                {"type": "in", "key": "LICENSE", "values": LICENSES}]}}
    r = s.post(f"{API}/occurrence/download/request", json=body, auth=auth, timeout=120)
    if r.status_code == 401:
        sys.exit("GBIF did not accept the login. Check GBIF_USER and GBIF_PWD.")
    if r.status_code not in (200, 201):
        sys.exit(f"GBIF refused the download request: HTTP {r.status_code} {r.text[:300]}")
    key = r.text.strip().strip('"')
    CACHE.mkdir(exist_ok=True)
    keyfile.write_text(f"{key} {dt.date.today().isoformat()} {len(LICENSES)}")
    print(f"GBIF is preparing download {key}", flush=True)
    return key


def wait_for(s, key):
    for minute in range(WAIT_MINUTES):
        try:
            m = s.get(f"{API}/occurrence/download/{key}", timeout=60).json()
        except Exception as e:
            print(f"  status check failed ({type(e).__name__})", flush=True)
            m = {}
        status = m.get("status", "?")
        if status == "SUCCEEDED":
            return m
        if status in ("FAILED", "KILLED", "CANCELLED", "FILE_ERASED"):
            (CACHE / "gbif_download.txt").unlink(missing_ok=True)
            sys.exit(f"GBIF download {key} ended with status {status}. Run again to make a new request.")
        if minute % 5 == 0:
            print(f"  waiting for GBIF ({status}), {minute} min", flush=True)
        time.sleep(60)
    sys.exit(f"GBIF download {key} was not ready after {WAIT_MINUTES} minutes. Run again later; the same request will be picked up.")


def fetch_zip(s, meta, key):
    dest = CACHE / f"gbif_{key}.zip"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    for old in CACHE.glob("gbif_*.zip"):
        old.unlink()
    link = meta.get("downloadLink") or f"{API}/occurrence/download/request/{key}.zip"
    with s.get(link, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk)
    print(f"Downloaded {dest.stat().st_size / 1e6:.0f} MB", flush=True)
    return dest


def read_records(path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(name) as f:
            parts = []
            for chunk in pd.read_csv(io.TextIOWrapper(f, encoding="utf-8"), sep="\t", quoting=3, dtype=str,
                                     usecols=lambda c: c in COLS, chunksize=500000, on_bad_lines="skip"):
                parts.append(chunk)
    return pd.concat(parts, ignore_index=True)


# ---------- Red List category and English name for each species ----------
def lookups(s, keys):
    cache_file = CACHE / "gbif_species_v2.json"
    known = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    todo = [k for k in keys if k not in known]
    print(f"Species details: {len(known)} known, {len(todo)} to look up", flush=True)

    def one(k):
        out = {}
        try:
            r = s.get(f"{API}/species/{k}/iucnRedListCategory", timeout=30)
            if r.status_code == 200:
                out["iucn"] = (r.json() or {}).get("code") or ""
            elif r.status_code in (204, 404):
                out["iucn"] = ""
            r = s.get(f"{API}/species/{k}/vernacularNames", params={"limit": 100}, timeout=30)
            if r.status_code == 200:
                names = [v.get("vernacularName", "").strip() for v in r.json().get("results", []) if v.get("language") == "eng"]
                names = [n for n in names if 2 < len(n) < 60 and not n.isupper() and not any(ch.isdigit() for ch in n)]   # drop codes such as "AGPA"
                tally = {}
                for n in names:
                    tally[n.lower()] = tally.get(n.lower(), 0) + 1
                best = max(tally, key=lambda k: (tally[k], -len(k))) if tally else ""      # the name most sources agree on
                out["common"] = best[:1].upper() + best[1:]
        except Exception:
            pass
        return k, out

    failed = 0
    with ThreadPoolExecutor(LOOKUP_WORKERS) as pool:
        for i, (k, out) in enumerate(pool.map(one, todo), 1):
            if "iucn" in out and "common" in out:
                known[k] = out
            else:
                failed += 1
            if i % 2000 == 0:
                print(f"  {i}/{len(todo)} looked up", flush=True)
                cache_file.write_text(json.dumps(known))
    CACHE.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps(known))
    if failed:
        print(f"  {failed} species could not be looked up this run; they are shown without a category or English name.")
    return known


def main():
    import requests
    user, pwd = os.environ.get("GBIF_USER"), os.environ.get("GBIF_PWD")
    if not (user and pwd):
        sys.exit("Set GBIF_USER and GBIF_PWD (a free account from gbif.org).")
    s = requests.Session()
    key = request_download(s, (user, pwd), os.environ.get("GBIF_EMAIL", ""))
    meta = wait_for(s, key)
    df = read_records(fetch_zip(s, meta, key))
    total = len(df)
    print(f"{total:,} records in the download", flush=True)

    # keep records that name a species, are not fossils or captive, and have a usable position
    df = df[df["speciesKey"].notna() & df["species"].notna() & (df["species"] != "")]
    df = df[~df["basisOfRecord"].isin(SKIP_BASIS)]
    unc = pd.to_numeric(df["coordinateUncertaintyInMeters"], errors="coerce")
    df = df[unc.isna() | (unc <= MAX_UNCERTAINTY_M)]
    df["lat"] = pd.to_numeric(df["decimalLatitude"], errors="coerce").round(4)
    df["lon"] = pd.to_numeric(df["decimalLongitude"], errors="coerce").round(4)
    df = df[df["lat"].notna() & df["lon"].notna()]
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df.loc[(df["year"] < 1800) | (df["year"] > dt.date.today().year), "year"] = np.nan

    # put each record in a district (records at sea or outside Ghana drop out here)
    gdf = load_districts()
    places = df[["lon", "lat"]].drop_duplicates()
    pts = gpd.GeoDataFrame(places, geometry=gpd.points_from_xy(places["lon"], places["lat"]), crs="EPSG:4326")
    hit = gpd.sjoin(pts, gdf[["geometry"]], how="inner", predicate="within")
    hit = hit[~hit.index.duplicated()].rename(columns={"index_right": "d"})[["lon", "lat", "d"]]
    df = df.merge(hit, on=["lon", "lat"], how="inner")
    used = len(df)
    print(f"{used:,} records used ({total - used:,} left out: no species name, vague position, fossil or captive, or outside the districts)")
    if used < 1000:
        sys.exit("Too few usable records; not publishing.")

    df["group"] = [group_of(k, p, c) for k, p, c in zip(df["kingdom"], df["phylum"], df["class"])]
    df["place"] = df["lat"].astype(str) + "," + df["lon"].astype(str)

    # ---- species table ----
    sp = df.groupby("speciesKey").agg(name=("species", "first"), group=("group", "first"), n=("gbifID", "size"),
                                      nd=("d", "nunique"), first=("year", "min"), last=("year", "max")).reset_index()
    sp = sp.sort_values("name").reset_index(drop=True)
    info = lookups(s, list(sp["speciesKey"]))
    sp["iucn"] = [info.get(k, {}).get("iucn", "") or "" for k in sp["speciesKey"]]
    sp["common"] = [info.get(k, {}).get("common", "") or "" for k in sp["speciesKey"]]
    sidx = {k: i for i, k in enumerate(sp["speciesKey"])}
    df["s"] = df["speciesKey"].map(sidx)
    threatened = set(sp.index[sp["iucn"].isin(THREATENED)])
    yr = lambda v: None if pd.isna(v) else int(v)  # noqa: E731

    out = DATA / "bio"
    (out / "districts").mkdir(parents=True, exist_ok=True)
    (out / "species.json").write_text(json.dumps({
        "fields": ["key", "name", "common", "group", "iucn", "records", "districts", "first", "last"],
        "groups": GROUPS,
        "rows": [[int(r.speciesKey), r.name_, r.common, GROUPS.index(r.group), r.iucn, int(r.n), int(r.nd), yr(r.first), yr(r.last)]
                 for r in sp.rename(columns={"name": "name_"}).itertuples()],
    }, separators=(",", ":"), ensure_ascii=False))

    # ---- species x district ----
    pair = df.groupby(["s", "d"]).agg(n=("gbifID", "size"), last=("year", "max"), places=("place", "nunique"),
                                      first=("year", "min")).reset_index()
    ids = list(gdf["shapeID"])
    by_species = {}
    for r in pair.itertuples():
        by_species.setdefault(int(r.s), []).append([int(r.d), int(r.n), yr(r.last)])
    (out / "pairs.json").write_text(json.dumps({"districts": ids, "fields": ["district", "records", "last"], "species": by_species},
                                               separators=(",", ":")))
    for old in (out / "districts").glob("*.json"):
        old.unlink()
    for d, g in pair.groupby("d"):
        g = g.sort_values("n", ascending=False)
        (out / "districts" / f"{ids[d]}.json").write_text(json.dumps({
            "fields": ["species", "records", "places", "first", "last"],
            "rows": [[int(r.s), int(r.n), int(r.places), yr(r.first), yr(r.last)] for r in g.itertuples()],
        }, separators=(",", ":")))

    # ---- the map layer ----
    per = df.groupby("d").agg(n=("gbifID", "size"), species=("s", "nunique"), datasets=("datasetKey", "nunique"),
                              y0=("year", "min"), y1=("year", "max"))
    grp = df.groupby(["d", "group"])["s"].nunique().unstack(fill_value=0).reindex(columns=GROUPS, fill_value=0)
    thr = df[df["s"].isin(threatened)].groupby("d")["s"].nunique()
    iucn_of = dict(zip(sp.index, sp["iucn"]))
    thr_split = {}
    for (d, s_), _ in df[df["s"].isin(threatened)].groupby(["d", "s"]).size().items():
        thr_split.setdefault(d, {}).setdefault(iucn_of[s_], 0)
        thr_split[d][iucn_of[s_]] += 1
    have_iucn = bool((sp["iucn"] != "").any())

    districts = {}
    for i, row in gdf.iterrows():
        if i not in per.index:
            districts[row.shapeID] = {"name": row.shapeName, "cat": "s0", "big": "–",
                                      "big_note": "No usable records in GBIF for this district. That reflects surveying, not an absence of wildlife.",
                                      "tip": "No usable records", "rows": [], "v": [0] * len(GROUPS), "c": ["s0"] * len(GROUPS)}
            continue
        p = per.loc[i]
        n_sp = int(p.species)
        cat = next(c["key"] for c in CATS if n_sp < c["max"])
        rows = [["Occurrence records", f"{int(p.n):,}"], ["Records per species", f"{p.n / n_sp:.1f}"]]
        if have_iucn:
            split = thr_split.get(i, {})
            detail = ", ".join(f"{split[c]} {THREATENED[c].lower()}" for c in ("CR", "EN", "VU") if split.get(c))
            rows.append(["Threatened species recorded", f"{int(thr.get(i, 0))}" + (f" ({detail})" if detail else "")])
        rows += [["Years represented", "–" if pd.isna(p.y0) else f"{int(p.y0)}–{int(p.y1)}"],
                 ["Contributing datasets", f"{int(p.datasets)}"]]
        districts[row.shapeID] = {
            "name": row.shapeName, "cat": cat, "big": f"{n_sp:,}",
            "big_note": "species recorded in GBIF. This depends on how much the district has been surveyed.",
            "tip": f"{n_sp:,} species recorded", "rows": rows,
            "v": [int(x) for x in grp.loc[i]], "c": [cat] * len(GROUPS),
            "records": int(p.n), "threatened": int(thr.get(i, 0)),
        }

    years = df["year"].dropna()
    doi = meta.get("doi", "")
    coverage = {"records": used, "records_in_download": total, "species": int(len(sp)), "datasets": int(df["datasetKey"].nunique()),
                "first": int(years.min()), "last": int(years.max()), "districts_with_records": int(len(per)),
                "threatened": int(len(threatened)), "has_iucn": have_iucn, "noncommercial": INCLUDE_NONCOMMERCIAL, "download_key": key, "doi": doi,
                "by_group": {g: int(n) for g, n in sp["group"].value_counts().reindex(GROUPS, fill_value=0).items()}}
    cite = f"GBIF.org ({dt.date.today():%d %B %Y}) GBIF Occurrence Download" + (f" https://doi.org/{doi}" if doi else "")
    print(f"{len(sp):,} species, {used:,} records, {coverage['datasets']} datasets, {len(per)} districts with records")

    write_layer("biodiversity", {
        "label": "Recorded species", "title": "Recorded species", "source": cite, "demo": False,
        "subtitle": f"Species with at least one record in GBIF, {coverage['first']} to {coverage['last']}",
        "coverage": coverage,
        "categories": [{k: c[k] for k in ("key", "label", "note", "color")} for c in CATS],
        "how": ("Each district shows how many different species have at least one record in GBIF, the international "
                "database of biodiversity records. A record means someone saw or collected that species at a place in "
                "the district. Click a district to see the count for each group of species."),
        "limits": [
            "This map shows where recording has happened as much as where species live. Districts with national parks, universities or many birdwatchers have far more records than others.",
            "No record does not mean a species is absent. Compare districts only with the number of records in mind.",
            "Records come from many sources and years, including old museum specimens. A species recorded decades ago may no longer be present.",
            "Some records are misidentified or misplaced. Records flagged by GBIF for position problems, fossils, captive animals and positions vaguer than 25 km are left out.",
            ("This layer includes records published under a non-commercial licence (CC BY-NC). It may not be used for commercial purposes."
             if INCLUDE_NONCOMMERCIAL else
             "Records published under a non-commercial licence are left out, which removes a large share of citizen-science observations, including many mammal sightings."),
            "Red List categories are the global ones from the IUCN Red List, as supplied by GBIF. They are not national assessments.",
        ],
        "credits": [{"text": cite, "url": f"https://doi.org/{doi}" if doi else "https://www.gbif.org"},
                    {"text": "Conservation status: IUCN Red List of Threatened Species, via GBIF", "url": "https://www.iucnredlist.org"}],
        "chart": {"kind": "bars", "unit": "", "x": GROUPS, "caption": "Recorded species in each group", "top": "", "bottom": ""},
        "districts": districts,
    })


if __name__ == "__main__":
    main()
