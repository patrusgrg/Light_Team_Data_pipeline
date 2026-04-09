import csv
import sys
import json
import statistics
from pathlib import Path
from datetime import datetime, timezone
 
 
# SQM-LU-DL column positions (0-indexed, semicolon-delimited)
# Adjust if unit uses a different firmware / delimiter
SQM_DELIMITER    = ";"
SQM_COL_UTC      = 0   # ISO 8601 datetime
SQM_COL_MPSAS    = 1   # magnitudes per square arcsecond (sky brightness)
SQM_COL_FREQ     = 2   # sensor frequency
SQM_COL_COUNTS   = 3   # raw counts
SQM_COL_TEMP_C   = 4   # sensor temperature °C
 
MPSAS_MIN_VALID  = 5.0   # below this = sensor malfunction / direct light
MPSAS_MAX_VALID  = 25.0  # above this = implausible
 
 
def parse_sqm_csv(csv_path: Path) -> list[dict]:
    """Parse SQM CSV, skipping header/comment lines starting with #."""
    rows = []
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(SQM_DELIMITER)
            if len(parts) < 5:
                continue
            try:
                mpsas = float(parts[SQM_COL_MPSAS])
                temp  = float(parts[SQM_COL_TEMP_C])
            except ValueError:
                continue
 
            # Quality flag
            valid = MPSAS_MIN_VALID <= mpsas <= MPSAS_MAX_VALID
 
            rows.append({
                "utc":     parts[SQM_COL_UTC].strip(),
                "mpsas":   mpsas,
                "freq":    parts[SQM_COL_FREQ].strip(),
                "counts":  parts[SQM_COL_COUNTS].strip(),
                "temp_c":  temp,
                "valid":   valid,
            })
    return rows
 
 
def summarize(rows: list[dict], csv_path: Path) -> dict:
    valid_rows   = [r for r in rows if r["valid"]]
    flagged_rows = [r for r in rows if not r["valid"]]
    mpsas_vals   = [r["mpsas"] for r in valid_rows]
    temp_vals    = [r["temp_c"] for r in valid_rows]
 
    if not mpsas_vals:
        print(f"  WARNING: No valid SQM readings in {csv_path.name}")
        return {}
 
    # Find darkest period (rolling 30-min window — approximated here)
    # SQM records every 60s, so 30 rows ≈ 30 min
    window = 30
    darkest_mean = max(
        statistics.mean(mpsas_vals[i:i+window])
        for i in range(max(1, len(mpsas_vals)-window))
    )
 
    # Detect gaps (> 90s between consecutive readings)
    gaps = []
    for i in range(1, len(rows)):
        try:
            t0 = datetime.fromisoformat(rows[i-1]["utc"])
            t1 = datetime.fromisoformat(rows[i]["utc"])
            delta = (t1 - t0).total_seconds()
            if delta > 90:
                gaps.append({"after": rows[i-1]["utc"], "gap_seconds": delta})
        except ValueError:
            pass
 
    summary = {
        "source_file":       csv_path.name,
        "total_readings":    len(rows),
        "valid_readings":    len(valid_rows),
        "flagged_readings":  len(flagged_rows),
        "gaps_detected":     len(gaps),
        "gap_details":       gaps[:5],          # show first 5
        "mpsas_mean":        round(statistics.mean(mpsas_vals), 3),
        "mpsas_median":      round(statistics.median(mpsas_vals), 3),
        "mpsas_min":         round(min(mpsas_vals), 3),
        "mpsas_max":         round(max(mpsas_vals), 3),
        "mpsas_stdev":       round(statistics.stdev(mpsas_vals), 3) if len(mpsas_vals) > 1 else 0,
        "darkest_30min_mean":round(darkest_mean, 3),
        "temp_c_mean":       round(statistics.mean(temp_vals), 2),
        "temp_c_min":        round(min(temp_vals), 2),
        "temp_c_max":        round(max(temp_vals), 2),
        "first_reading_utc": rows[0]["utc"],
        "last_reading_utc":  rows[-1]["utc"],
        "summary_generated": datetime.now(timezone.utc).isoformat(),
    }
    return summary
 
 
def process_path(target: Path):
    if target.is_dir():
        csv_files = sorted(target.glob("*.csv"))  #########need to modify
        if not csv_files:
            print(f"  No CSV files found in {target}")
            return
        for f in csv_files:
            process_path(f)
        return
 
    print(f"\n  Processing: {target.name}")
    rows = parse_sqm_csv(target)
    if not rows:
        print("  No parseable rows found.")
        return
 
    summary = summarize(rows, target)
    if not summary:
        return
 
    out_path = target.parent / (target.stem + "_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
 
    print(f"  Readings:     {summary['valid_readings']} valid / {summary['total_readings']} total")
    print(f"  MPSAS range:  {summary['mpsas_min']} – {summary['mpsas_max']}")
    print(f"  MPSAS mean:   {summary['mpsas_mean']}")
    print(f"  Darkest 30m:  {summary['darkest_30min_mean']}")
    print(f"  Temp range:   {summary['temp_c_min']} – {summary['temp_c_max']} °C")
    print(f"  Gaps (>90s):  {summary['gaps_detected']}")
    print(f"  Summary →     {out_path.name}")
 
 
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python 02_summarize_sqm.py <csv_file_or_folder>")
        sys.exit(1)
    process_path(Path(sys.argv[1]))