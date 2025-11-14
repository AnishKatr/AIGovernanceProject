from __future__ import print_function
import os.path
import io

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = "token.json"


def get_drive_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    service = build("drive", "v3", credentials=creds)
    return service


def list_files(page_size=20, query=None):
    service = get_drive_service()

    params = {
        "pageSize": page_size,
        "fields": "files(id, name, mimeType)",
    }

    if query:
        params["q"] = query

    results = service.files().list(**params).execute()
    items = results.get("files", [])

    if not items:
        print("No files found.")
        return []

    print("\n--- Files Found ---")
    for i, item in enumerate(items, start=1):
        print(f"{i}. {item['name']} (ID: {item['id']}) [{item['mimeType']}]")

    return items


def download_file(file_id, destination_path):
    service = get_drive_service()

    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(destination_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)

    print(f"Downloading {file_id}...\n")

    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"Progress: {int(status.progress() * 100)}%")

    print(f"\n✔️ Download complete! Saved as: {destination_path}")


def main():
    print("\n=== Google Drive OAuth Client (acts as YOU) ===\n")

    search = input("Search for filename (press Enter to list all): ").strip()
    query = f"name contains '{search}'" if search else None

    files = list_files(page_size=20, query=query)

    if not files:
        return

    choice = input("\nEnter the number of the file to download: ").strip()

    if not choice.isdigit() or not (1 <= int(choice) <= len(files)):
        print("Invalid choice.")
        return

    chosen = files[int(choice) - 1]
    print(f"You chose: {chosen['name']} (ID: {chosen['id']})")

    dest = input(
        f"Save as (press Enter for '{chosen['name']}'): "
    ).strip() or chosen["name"]

    download_file(chosen["id"], dest)


if __name__ == "__main__":
    main()
