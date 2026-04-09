"""
Processes all 6 HOBO lux+temperature logger CSVs for one night and produces:
  - Per-logger summary (mean/min/max lux and temp, gap check)
  - Transect gradient table (illuminance vs distance from W)
  - Cross-validation of HOBO-01 against the co-located SQM
 """
import csv
import sys
import json
import statistics
import argparse
from pathlib import Path
from datetime import datetime, timezone
 
 
# HOBOware export headers — adjust if your export settings differ
HOBO_COL_DATETIME = "Date Time"   # partial match on column header
HOBO_COL_LUX      = "Intensity"   # partial match
HOBO_COL_TEMP     = "Temp"        # partial match
 
# Logger positions along I-line (meters from base of W) — update after site visit
# Keys must match the DeviceID portion of the filename (HOBO-01 … HOBO-06)
HOBO_POSITIONS_M = {
    "HOBO-01": 0,     # co-located with SQM (sky brightness station)
    "HOBO-02": 50,    # I-line: near W base
    "HOBO-03": 150,
    "HOBO-04": 250,
    "HOBO-05": 320,   # near acoustic station
    "HOBO-06": 400,   # near mist-net lanes
}
 
LUX_GAP_THRESHOLD_S = 90   # flag gaps longer than 90 seconds
 
 
def detect_columns(header_row: list[str]) -> tuple[int, int, int]:
    """Return (datetime_col, lux_col, temp_col) indices from the header row."""
    dt_idx = lux_idx = temp_idx = None
    for i, h in enumerate(header_row):
        if HOBO_COL_DATETIME in h:
            dt_idx = i
        elif HOBO_COL_LUX in h:
            lux_idx = i
        elif HOBO_COL_TEMP in h:
            temp_idx = i
    if None in (dt_idx, lux_idx, temp_idx):
        raise ValueError(
            f"Could not find all required columns.\n"
            f"Headers found: {header_row}\n"
            f"Looking for: '{HOBO_COL_DATETIME}', '{HOBO_COL_LUX}', '{HOBO_COL_TEMP}'"
        )
    return dt_idx, lux_idx, temp_idx
 
 
def parse_hobo_csv(csv_path: Path) -> tuple[list[dict], str]:
    """Returns (rows, device_id)."""
    # Infer device ID from filename
    stem = csv_path.stem
    parts = stem.split("_")
    device_id = parts[3] if len(parts) >= 4 else csv_path.stem
 
    rows = []
    with open(csv_path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        raw = list(reader)
 
    # Skip metadata rows; find the header row (contains "Date Time")
    header_idx = None
    for i, row in enumerate(raw):
        if any(HOBO_COL_DATETIME in cell for cell in row):
            header_idx = i
            break
 
    if header_idx is None:
        raise ValueError(f"Could not find header row in {csv_path.name}")
 
    header = raw[header_idx]
    dt_idx, lux_idx, temp_idx = detect_columns(header)
 
    for row in raw[header_idx + 1:]:
        if len(row) <= max(dt_idx, lux_idx, temp_idx):
            continue
        try:
            lux  = float(row[lux_idx])
            temp = float(row[temp_idx])
        except ValueError:
            continue
        rows.append({
            "datetime_str": row[dt_idx].strip(),
            "lux":          lux,
            "temp_c":       temp,
            "device_id":    device_id,
        })
 
    return rows, device_id
 
 
def detect_gaps(rows: list[dict]) -> list[dict]:
    """Try to parse datetime strings and find gaps > threshold."""
    gaps = []
    # HOBOware datetime formats vary by locale; try a few   
    #chnages need to be done  fro the devices 
    fmts = [
        "%m/%d/%y %I:%M:%S %p",
        "%m/%d/%Y %I:%M:%S %p",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%y %H:%M:%S",
    ]
    parsed = []
    for r in rows:
        for fmt in fmts:
            try:
                parsed.append(datetime.strptime(r["datetime_str"], fmt))
                break
            except ValueError:
                pass
 
    for i in range(1, len(parsed)):
        delta = (parsed[i] - parsed[i-1]).total_seconds()
        if delta > LUX_GAP_THRESHOLD_S:
            gaps.append({"after": str(parsed[i-1]), "gap_seconds": round(delta)})
    return gaps
 
 
def summarize_logger(rows: list[dict], device_id: str, csv_path: Path) -> dict:
    lux_vals  = [r["lux"]   for r in rows]
    temp_vals = [r["temp_c"] for r in rows]
 
    gaps = detect_gaps(rows)
    position_m = HOBO_POSITIONS_M.get(device_id, "unknown")
 
    return {
        "device_id":        device_id,
        "source_file":      csv_path.name,
        "position_m_from_w": position_m,
        "total_readings":   len(rows),
        "gaps_detected":    len(gaps),
        "gap_details":      gaps[:3],
        "lux_mean":         round(statistics.mean(lux_vals), 3),
        "lux_median":       round(statistics.median(lux_vals), 3),
        "lux_min":          round(min(lux_vals), 4),
        "lux_max":          round(max(lux_vals), 3),
        "lux_stdev":        round(statistics.stdev(lux_vals), 3) if len(lux_vals) > 1 else 0,
        "temp_c_mean":      round(statistics.mean(temp_vals), 2),
        "temp_c_min":       round(min(temp_vals), 2),
        "temp_c_max":       round(max(temp_vals), 2),
        "first_reading":    rows[0]["datetime_str"] if rows else "",
        "last_reading":     rows[-1]["datetime_str"] if rows else "",
    }
 
 
def cross_validate_hobo_sqm(hobo_summary: dict, sqm_summary_path: Path) -> dict:
    """
    Compare HOBO-01 lux mean to SQM mpsas mean.
    These are different units but the relationship should be
    monotonically inverse: higher lux → lower mpsas (brighter sky).
    Produces a qualitative consistency flag.
    """
    result = {"available": False}
    if not sqm_summary_path or not sqm_summary_path.exists():
        return result
 
    with open(sqm_summary_path) as f:
        sqm = json.load(f)
 
    result.update({
        "available":       True,
        "hobo01_lux_mean": hobo_summary.get("lux_mean"),
        "sqm_mpsas_mean":  sqm.get("mpsas_mean"),
        "note": (
            "Higher lux + lower mpsas = consistent (brighter sky)."
            if hobo_summary.get("lux_mean", 0) > 1 and sqm.get("mpsas_mean", 25) < 20
            else "Values appear consistent with dark sky conditions."
        ),
    })
    return result
 
 
def print_transect_table(summaries: list[dict]):
    print("\n  I-LINE TRANSECT GRADIENT")
    print(f"  {'Device':<10} {'Dist(m)':<10} {'Lux mean':<12} {'Lux max':<12} {'Temp mean':<12} {'Gaps'}")
    print("  " + "-"*66)
    for s in sorted(summaries, key=lambda x: x.get("position_m_from_w", 9999)):
        pos = str(s.get("position_m_from_w", "?"))
        print(
            f"  {s['device_id']:<10} {pos:<10} "
            f"{s['lux_mean']:<12} {s['lux_max']:<12} "
            f"{s['temp_c_mean']:<12} {s['gaps_detected']}"
        )
 
 
def main():
    parser = argparse.ArgumentParser(description="HOBO transect summarizer")
    parser.add_argument("hobo_folder", help="Path to the nightly HOBO subfolder")
    parser.add_argument("--sqm-summary", default=None,
                        help="Path to SQM summary JSON for HOBO-01 cross-validation")
    args = parser.parse_args()
 
    folder = Path(args.hobo_folder)
    sqm_path = Path(args.sqm_summary) if args.sqm_summary else None
 
    if not folder.is_dir():
        # Maybe it's a single file
        folder = folder.parent
        csv_files = [Path(args.hobo_folder)]
    else:
        csv_files = sorted(folder.glob("**/*.csv"))
 
    if not csv_files:
        print(f"No CSV files found in {folder}")
        sys.exit(1)
 
    summaries = []
    for csv_path in csv_files:
        print(f"\n  Parsing: {csv_path.name}")
        try:
            rows, device_id = parse_hobo_csv(csv_path)
        except ValueError as e:
            print(f"  ERROR: {e}")
            continue
 
        if not rows:
            print(f"  WARNING: No valid rows in {csv_path.name}")
            continue
 
        s = summarize_logger(rows, device_id, csv_path)
        summaries.append(s)
        print(f"  Readings: {s['total_readings']}  Lux mean: {s['lux_mean']}  Temp mean: {s['temp_c_mean']}°C  Gaps: {s['gaps_detected']}")
 
    if not summaries:
        print("No valid HOBO data processed.")
        sys.exit(1)
 
    print_transect_table(summaries)
 
    # Cross-validate HOBO-01 vs SQM
    hobo01 = next((s for s in summaries if s["device_id"] == "HOBO-01"), None)
    xval = {}
    if hobo01:
        xval = cross_validate_hobo_sqm(hobo01, sqm_path)
        if xval.get("available"):
            print(f"\n  HOBO-01 vs SQM cross-check:")
            print(f"    HOBO-01 lux mean: {xval['hobo01_lux_mean']}")
            print(f"    SQM mpsas mean:   {xval['sqm_mpsas_mean']}")
            print(f"    Assessment:       {xval['note']}")
 
    # Write combined output
    out = {
        "per_logger_summaries": summaries,
        "sqm_cross_validation": xval,
        "logger_count":         len(summaries),
        "expected_loggers":     6,
        "missing_loggers":      6 - len(summaries),
        "summary_generated":    datetime.now(timezone.utc).isoformat(),
    }
    out_path = folder / "hobo_transect_summary.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
 
    print(f"\n  Loggers processed: {len(summaries)} / 6")
    if len(summaries) < 6:
        print(f"  WARNING: Expected 6 loggers, got {len(summaries)} — check for missing files!")
    print(f"  Summary → {out_path}")
 
 
if __name__ == "__main__":
    main()