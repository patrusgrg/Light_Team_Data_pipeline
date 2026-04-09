from ingestion.drive_client import get_drive_service
from ingestion.file_fetcher import list_files, download_file
from ingestion.validator import validate_files
from ingestion.manifest_builder import build_manifest, write_manifest
from ingestion.staging_writer import create_staging_folder

def run_ingestion(folder_id):

    print("\n🚀 STARTING INGESTION PIPELINE")

    service = get_drive_service()

    # 1. FETCH
    files = list_files(service, folder_id)

    # 2. VALIDATE
    issues = validate_files(files)

    # 3. STAGING
    staging_path = create_staging_folder()

    # 4. DOWNLOAD
    local_files = []
    for f in files:
        path = download_file(service, f["id"], f["name"], staging_path)
        local_files.append(path)

    # 5. MANIFEST
    rows = build_manifest(local_files)

    manifest_path = staging_path / "manifest.csv"
    write_manifest(rows, manifest_path)

    # REPORT
    print("\n=== INGEST REPORT ===")
    print(f"Files: {len(files)}")
    print(f"Manifest: {manifest_path}")

    if issues:
        print("\n⚠ Issues:")
        for i in issues:
            print("-", i)
    else:
        print("\n✔ All checks passed")

    return {
        "files": len(files),
        "manifest": str(manifest_path),
        "issues": issues
    }