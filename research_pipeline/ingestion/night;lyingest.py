import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone
 
# Import sibling modules directly
sys.path.insert(0, str(Path(__file__).parent))
import importlib
 
gen_manifest  = importlib.import_module("01_generate_manifest")
sum_sqm       = importlib.import_module("02_summarize_sqm")
sum_hobo      = importlib.import_module("03_summarize_hobo")
 
 
# Expected sensor subfolders for the baseline year
EXPECTED_SUBFOLDERS = [
    "SM4",
    "SQM",
    "HOBO",
    "SPEC",
    "THERMAL",
    "LUX",
    "ADMIN",
]
 
# Minimum expected file counts per sensor per night
MIN_FILE_COUNTS = {
    "SM4":     1,
    "SQM":     1,
    "HOBO":    6,    # one per logger
    "SPEC":    1,
    "THERMAL": 1,
    "LUX":     1,
    "ADMIN":   2,    # at minimum: Field Log + Time Sync Sheet
}
 
 
# ─────────────────────────────────────────────
# QA helpers
# ─────────────────────────────────────────────
 
def check_folder_structure(nightly: Path) -> dict:
    results = {}
    for sf in EXPECTED_SUBFOLDERS:
        # Find a subfolder whose name contains this sensor key
        matches = [
            d for d in nightly.iterdir()
            if d.is_dir() and sf in d.name.upper()
        ]
        results[sf] = {
            "present": bool(matches),
            "path":    str(matches[0]) if matches else None,
        }
    return results
 
 
def count_files(nightly: Path, structure: dict) -> dict:
    counts = {}
    for sf, info in structure.items():
        if not info["present"]:
            counts[sf] = 0
            continue
        folder = Path(info["path"])
        # For HOBO, recurse one level to count across subfolders
        if sf == "HOBO":
            n = sum(1 for f in folder.rglob("*.csv") if f.is_file())
        else:
            n = sum(1 for f in folder.iterdir() if f.is_file())
        counts[sf] = n
    return counts
 
 
def find_sqm_summary(nightly: Path) -> Path | None:
    sqm_dirs = [d for d in nightly.iterdir() if d.is_dir() and "SQM" in d.name.upper()]
    if not sqm_dirs:
        return None
    for f in sqm_dirs[0].glob("*_summary.json"):
        return f
    return None
 
 
# ─────────────────────────────────────────────
# Report writer
# ─────────────────────────────────────────────
 
def write_report(nightly: Path, report: dict):
    admin_dirs = [d for d in nightly.iterdir() if d.is_dir() and "ADMIN" in d.name.upper()]
    if admin_dirs:
        out_dir = admin_dirs[0]
    else:
        out_dir = nightly
        print("  WARNING: No ADMIN subfolder found; writing report to nightly root.")
 
    # JSON
    json_out = out_dir / "nightly_qa_report.json"
    with open(json_out, "w") as f:
        json.dump(report, f, indent=2)
 
    # Human-readable text
    txt_out = out_dir / "nightly_qa_report.txt"
    lines = []
    lines.append("=" * 60)
    lines.append("LIGHT TEAM — NIGHTLY QA REPORT")
    lines.append(f"Night folder:  {report['night_folder']}")
    lines.append(f"W status:      {report['w_treatment_status']}")
    lines.append(f"Generated:     {report['generated_utc']}")
    lines.append("=" * 60)
 
    lines.append("\nFOLDER STRUCTURE")
    for sf, info in report["folder_structure"].items():
        mark = "OK" if info["present"] else "MISSING"
        lines.append(f"  {sf:<12} {mark}")
 
    lines.append("\nFILE COUNTS")
    for sf, count in report["file_counts"].items():
        expected = MIN_FILE_COUNTS.get(sf, 1)
        flag = "" if count >= expected else f"  <- WARNING: expected >={expected}"
        lines.append(f"  {sf:<12} {count}{flag}")
 
    lines.append(f"\nMANIFEST\n  {'Generated' if report['manifest_generated'] else 'NOT generated'}")
 
    if report.get("sqm_summary"):
        s = report["sqm_summary"]
        lines.append(f"\nSQM SUMMARY")
        lines.append(f"  Valid readings:  {s.get('valid_readings', '?')}")
        lines.append(f"  MPSAS mean:      {s.get('mpsas_mean', '?')}")
        lines.append(f"  MPSAS range:     {s.get('mpsas_min', '?')} – {s.get('mpsas_max', '?')}")
        lines.append(f"  Darkest 30m:     {s.get('darkest_30min_mean', '?')}")
        lines.append(f"  Gaps (>90s):     {s.get('gaps_detected', '?')}")
 
    if report.get("hobo_summary"):
        h = report["hobo_summary"]
        lines.append(f"\nHOBO LOGGERS")
        lines.append(f"  Processed:  {h.get('logger_count', '?')} / 6")
        if h.get("missing_loggers", 0) > 0:
            lines.append(f"  WARNING: {h['missing_loggers']} logger(s) missing!")
        for logger in h.get("per_logger_summaries", []):
            pos = logger.get("position_m_from_w", "?")
            lines.append(
                f"  {logger['device_id']:<10} "
                f"{str(pos)+'m':<8} "
                f"lux={logger['lux_mean']:<10} "
                f"temp={logger['temp_c_mean']}°C"
                + (f"  GAPS:{logger['gaps_detected']}" if logger["gaps_detected"] else "")
            )
 
    warnings = report.get("warnings", [])
    if warnings:
        lines.append(f"\nWARNINGS ({len(warnings)})")
        for w in warnings:
            lines.append(f"  ! {w}")
 
    lines.append("\nQA CHECKLIST")
    checklist = [
        ("Raw files in correct nightly folder",   True),
        ("manifest.csv generated",                report["manifest_generated"]),
        ("Spot-check files opened OK",            False),   # always manual
        ("Admin photos + Field Log uploaded",     report["folder_structure"].get("ADMIN", {}).get("present", False)),
        ("Original media retained until next-day verify", False),  # manual
        ("HOBO file count == 6",                  report.get("hobo_summary", {}).get("logger_count", 0) == 6),
        ("SQM record gap-free",                   report.get("sqm_summary", {}).get("gaps_detected", 1) == 0),
        ("W treatment status recorded",           report["w_treatment_status"] != "UNKNOWN"),
    ]
    for label, status in checklist:
        mark = "[x]" if status else "[ ]"
        note = "" if status else "  <- manual verification required"
        lines.append(f"  {mark} {label}{note}")
 
    lines.append("")
    with open(txt_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
 
    print(f"\n  QA report → {txt_out}")
    print(f"  QA JSON   → {json_out}")
    return txt_out
 
 
# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
 
def main():
    parser = argparse.ArgumentParser(description="LIGHT Team nightly ingest runner")
    parser.add_argument("folder", help="Nightly folder, e.g. 20260412_I")
    parser.add_argument("--w-status", choices=["ON", "OFF", "UNKNOWN"], default="UNKNOWN")
    parser.add_argument("--skip-manifest", action="store_true", help="Skip manifest generation (faster for re-runs)")
    args = parser.parse_args()
 
    nightly = Path(args.folder).resolve()
    print(f"\n{'='*60}")
    print(f"  LIGHT TEAM — NIGHTLY INGEST")
    print(f"  Folder:   {nightly.name}")
    print(f"  W status: {args.w_status}")
    print(f"  Started:  {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"{'='*60}")
 
    warnings = []
    report = {
        "night_folder":       nightly.name,
        "w_treatment_status": args.w_status,
        "generated_utc":      datetime.now(timezone.utc).isoformat(),
        "warnings":           warnings,
    }
 
    # 1. Folder structure
    print("\n[1/5] Checking folder structure ...")
    structure = check_folder_structure(nightly)
    report["folder_structure"] = structure
    for sf, info in structure.items():
        if not info["present"]:
            warnings.append(f"Missing subfolder: {sf}")
            print(f"  WARNING: {sf} subfolder not found")
        else:
            print(f"  OK: {sf}")
 
    # 2. File counts
    print("\n[2/5] Counting files per sensor ...")
    counts = count_files(nightly, structure)
    report["file_counts"] = counts
    for sf, count in counts.items():
        expected = MIN_FILE_COUNTS.get(sf, 1)
        flag = ""
        if count < expected:
            flag = f"  <- WARNING: expected >={expected}, got {count}"
            warnings.append(f"Low file count for {sf}: {count} (expected >={expected})")
        print(f"  {sf:<12} {count} files{flag}")
 
    # 3. Manifest
    if args.skip_manifest:
        print("\n[3/5] Skipping manifest (--skip-manifest flag set)")
        report["manifest_generated"] = False
    else:
        print("\n[3/5] Generating SHA-256 manifest ...")
        try:
            gen_manifest.generate_manifest(nightly, w_status=args.w_status)
            report["manifest_generated"] = True
        except Exception as e:
            print(f"  ERROR: {e}")
            warnings.append(f"Manifest generation failed: {e}")
            report["manifest_generated"] = False
 
    # 4. SQM summary
    print("\n[4/5] Summarizing SQM data ...")
    sqm_summary = None
    sqm_dirs = [d for d in nightly.iterdir() if d.is_dir() and "SQM" in d.name.upper()]
    if sqm_dirs:
        sqm_csvs = sorted(sqm_dirs[0].glob("*.csv"))
        if sqm_csvs:
            rows = sum_sqm.parse_sqm_csv(sqm_csvs[0])
            sqm_summary = sum_sqm.summarize(rows, sqm_csvs[0])
            if sqm_summary:
                out = sqm_csvs[0].parent / (sqm_csvs[0].stem + "_summary.json")
                with open(out, "w") as f:
                    json.dump(sqm_summary, f, indent=2)
                if sqm_summary.get("gaps_detected", 0) > 0:
                    warnings.append(f"SQM has {sqm_summary['gaps_detected']} gap(s) >90s")
        else:
            print("  No SQM CSV found — skipping")
            warnings.append("No SQM CSV file found")
    else:
        print("  No SQM subfolder — skipping")
    report["sqm_summary"] = sqm_summary
 
    # 5. HOBO summary
    print("\n[5/5] Summarizing HOBO loggers ...")
    hobo_summary = None
    hobo_dirs = [d for d in nightly.iterdir() if d.is_dir() and "HOBO" in d.name.upper()]
    if hobo_dirs:
        sqm_sum_path = find_sqm_summary(nightly)
        # Collect all CSVs across any HOBO sub-subfolders
        all_hobo_csvs = sorted(hobo_dirs[0].rglob("*.csv"))
        if all_hobo_csvs:
            summaries = []
            for csv_path in all_hobo_csvs:
                try:
                    rows, device_id = sum_hobo.parse_hobo_csv(csv_path)
                    if rows:
                        s = sum_hobo.summarize_logger(rows, device_id, csv_path)
                        summaries.append(s)
                        if s["gaps_detected"] > 0:
                            warnings.append(f"{device_id} has {s['gaps_detected']} gap(s)")
                except Exception as e:
                    warnings.append(f"HOBO parse error ({csv_path.name}): {e}")
 
            hobo01 = next((s for s in summaries if s["device_id"] == "HOBO-01"), None)
            xval = {}
            if hobo01:
                xval = sum_hobo.cross_validate_hobo_sqm(hobo01, sqm_sum_path)
 
            hobo_summary = {
                "per_logger_summaries": summaries,
                "sqm_cross_validation": xval,
                "logger_count":         len(summaries),
                "expected_loggers":     6,
                "missing_loggers":      6 - len(summaries),
                "summary_generated":    datetime.now(timezone.utc).isoformat(),
            }
            if len(summaries) < 6:
                warnings.append(f"Only {len(summaries)}/6 HOBO loggers found")
 
            sum_hobo.print_transect_table(summaries)
            out = hobo_dirs[0] / "hobo_transect_summary.json"
            with open(out, "w") as f:
                json.dump(hobo_summary, f, indent=2)
        else:
            print("  No HOBO CSV files found")
            warnings.append("No HOBO CSV files found")
    else:
        print("  No HOBO subfolder — skipping")
    report["hobo_summary"] = hobo_summary
 
    # Write final QA report
    print("\n[QA] Writing nightly report ...")
    report["warnings"] = warnings
    write_report(nightly, report)
 
    # Summary
    print(f"\n{'='*60}")
    print(f"  INGEST COMPLETE")
    print(f"  Warnings: {len(warnings)}")
    for w in warnings:
        print(f"    ! {w}")
    print(f"{'='*60}\n")
 
 
if __name__ == "__main__":
    main()