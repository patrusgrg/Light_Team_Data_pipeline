from googleapiclient.http import MediaIoBaseDownload
import io
from pathlib import Path

def list_files(service, folder_id):
    results = service.files().list(
        q=f"'{folder_id}' in parents",
        fields="files(id, name, mimeType, createdTime)"
    ).execute()
    return results.get("files", [])


def download_file(service, file_id, file_name, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    request = service.files().get_media(fileId=file_id)
    file_path = output_dir / file_name

    with open(file_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    return file_path