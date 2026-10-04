#!/usr/bin/env python3
"""
Tinga Lens - check that the Google Earth Engine key works.

Reads the service account key from the EE_SERVICE_ACCOUNT_KEY secret, signs in,
and asks Earth Engine one small question (how many Sentinel-1 radar images cover
Ghana in October 2023). It writes nothing and never prints the key.
"""
import json
import os
import sys

GHANA = [-3.3, 4.7, 1.3, 11.2]      # west, south, east, north


def ee_login():
    """Sign in to Earth Engine with the service account key; returns (ee, project)."""
    raw = os.environ.get("EE_SERVICE_ACCOUNT_KEY", "").strip()
    if not raw:
        sys.exit("No EE_SERVICE_ACCOUNT_KEY secret found. Add it under Settings > Secrets and variables > Actions.")
    try:
        info = json.loads(raw)
        email, project = info["client_email"], info["project_id"]
        info["private_key"]
    except Exception:
        sys.exit("The EE_SERVICE_ACCOUNT_KEY secret is not a complete key file. "
                 "Paste the whole downloaded file, from the first { to the last }.")
    import ee
    try:
        ee.Initialize(ee.ServiceAccountCredentials(email, key_data=raw), project=project)
    except Exception as e:
        # the error text can repeat the key, so only its kind is printed
        sys.exit(f"Earth Engine did not accept the key for {email} (project {project}). Error kind: {type(e).__name__}. "
                 "Check that the whole key file was pasted, that the project is registered for Earth Engine, "
                 "and that the service account has the Earth Engine Resource Viewer and Service Usage Consumer roles.")
    return ee, project, email


def main():
    ee, project, email = ee_login()
    raw = os.environ["EE_SERVICE_ACCOUNT_KEY"].strip()
    info_private = json.loads(raw)["private_key"]
    print(f"Signed in to Earth Engine as {email}, project {project}")
    box = ee.Geometry.Rectangle(GHANA)
    try:
        n = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(box)
             .filterDate("2023-10-01", "2023-11-01")
             .filter(ee.Filter.eq("instrumentMode", "IW")).size().getInfo())
    except Exception as e:
        msg = str(e)[:400]
        for secret in (info_private, raw):
            msg = msg.replace(secret, "[hidden]")
        sys.exit(f"Signed in, but Earth Engine refused the test request: {msg}")
    print(f"Sentinel-1 radar images over Ghana in October 2023: {n}")
    if not n:
        sys.exit("The request worked but returned no images, which is not expected.")
    print("Earth Engine is working.")


if __name__ == "__main__":
    main()
