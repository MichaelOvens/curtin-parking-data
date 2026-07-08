"""Append one snapshot of Curtin live parking utilisation to a monthly CSV.

Data source: public ArcGIS feature layer behind
https://properties.curtin.edu.au/getting-here/parking/parking-availability-guide/
The layer is a live snapshot (no history), so this script is run on a schedule
and the git history of the CSVs becomes the time series.
"""

import csv
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = (
    "https://arcgis.curtin.edu.au/arcgis/rest/services/Hosted/"
    "Parking_SmartCampusLiveParkingData_view/FeatureServer/0/query"
    "?where=1%3D1&outFields=*&returnGeometry=false&f=json"
)
PERTH = timezone(timedelta(hours=8))  # AWST; WA has no daylight saving
DATA_DIR = Path(__file__).parent / "data"


def fetch(retries=3, delay=15):
    last_error = None
    for attempt in range(retries):
        if attempt:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(URL, timeout=30) as resp:
                payload = json.load(resp)
        except Exception as e:
            last_error = repr(e)
            continue
        features = payload.get("features")
        if features:
            return features
        # ArcGIS reports errors as JSON bodies; an empty layer is also suspect
        last_error = json.dumps(payload)[:300]
    sys.exit(f"fetch failed after {retries} attempts: {last_error}")


def main():
    features = fetch()
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    now_perth = now_utc.astimezone(PERTH)
    utc_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    perth_str = now_perth.strftime("%Y-%m-%d %H:%M:%S")

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"{now_perth:%Y-%m}.csv"
    write_header = not out.exists()

    # stable row order keeps the git diffs clean
    rows = sorted((f["attributes"] for f in features), key=lambda a: a.get("thing_name") or "")
    with out.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        if write_header:
            writer.writerow(["utc_time", "perth_time", "lot", "zone", "utilization"])
        for a in rows:
            writer.writerow(
                [utc_str, perth_str, a.get("parking_lo"), a.get("thing_name"), a.get("utilizatio")]
            )
    print(f"{utc_str}: appended {len(rows)} rows to {out.name}")


if __name__ == "__main__":
    main()
