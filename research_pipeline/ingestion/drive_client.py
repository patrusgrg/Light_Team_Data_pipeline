from googleapiclient.discovery import build
from google.oauth2 import service_account
from ingestion.config import SERVICE_ACCOUNT_FILE, SCOPES

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)