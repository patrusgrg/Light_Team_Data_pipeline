from ingestion.config import REQUIRED_HOBO_COUNT

def validate_files(files):
    issues = []

    if len(files) == 0:
        issues.append("No files found in Drive folder")

    hobo_files = [f for f in files if "HOBO" in f["name"]]

    if len(hobo_files) > 0 and len(hobo_files) != REQUIRED_HOBO_COUNT:
        issues.append(f"HOBO validation failed: {len(hobo_files)}/6 files")

    return issues