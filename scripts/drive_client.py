from __future__ import print_function
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# ============================================================
# CONFIGURATION
# ============================================================

# Your downloaded service account key JSON file.
SERVICE_ACCOUNT_FILE = "service_account_key.json"

# Read-only Drive access – enough for listing and downloading.
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# If True, the script will start by trying to open a specific shared folder.
START_IN_SHARED_FOLDER = True

# This must match the name of the folder you shared with the service account.
SHARED_FOLDER_NAME = "Dummy Folder"


# ============================================================
# AUTHENTICATION
# ============================================================

def get_drive_service():
    """
    Build and return an authenticated Google Drive API client.

    Uses the service account JSON file and the configured SCOPES.
    """
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


service = get_drive_service()


# ============================================================
# LIST ROOT + SHARED ITEMS
# ============================================================

def list_root_items():
    """
    List all items visible to the service account at the top level.

    Includes:
      - Items in the service account's own root.
      - Items that were shared with this service account (sharedWithMe).

    Returns:
        List of dicts: each has id, name, mimeType.
    """
    results = service.files().list(
        q="trashed = false and (sharedWithMe or 'root' in parents)",
        fields="files(id, name, mimeType)",
        pageSize=200,
    ).execute()

    items = results.get("files", [])

    if not items:
        print("\nNo items found that are visible to this service account.")
        print("Make sure you shared a folder with the service account email.")
        return []

    print("\n--- Items visible to this service account ---")
    for idx, item in enumerate(items, start=1):
        print(f"{idx}. {item['name']} (ID: {item['id']})")

    return items


# ============================================================
# LIST CONTENTS OF A FOLDER
# ============================================================

def list_folder_contents(folder_id):
    """
    List all children of a folder (files + subfolders).

    Args:
        folder_id: ID of the folder to list.
    """
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id, name, mimeType)",
        pageSize=200,
    ).execute()

    return results.get("files", [])


# ============================================================
# DOWNLOAD / EXPORT FILES
# ============================================================

def download_file(file_obj):
    """
    Download a file, exporting Google Docs/Sheets/Slides as needed.

    Args:
        file_obj: dict with keys 'id', 'name', 'mimeType'.
    """
    file_id = file_obj["id"]
    name = file_obj["name"]
    mime = file_obj["mimeType"]

    print(f"\nDownloading '{name}' ...")

    # Map Google-native types to export formats.
    google_types = {
        "application/vnd.google-apps.document": (
            "application/pdf",
            ".pdf",
        ),
        "application/vnd.google-apps.spreadsheet": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xlsx",
        ),
        "application/vnd.google-apps.presentation": (
            "application/pdf",
            ".pdf",
        ),
    }

    if mime in google_types:
        export_mime, ext = google_types[mime]
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        filename = name + ext
    else:
        request = service.files().get_media(fileId=file_id)
        filename = name

    fh = io.FileIO(filename, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False

    while not done:
        status, done = downloader.next_chunk()

    print(f"Saved as: {filename}\n")


# ============================================================
# FOLDER BROWSER WITH CUMULATIVE FILTERING
# ============================================================

def browse_folder(folder_id, folder_name):
    """
    Interactive browser inside a folder.

    - Shows numbered list of items.
    - 'f' filters by substring (cumulative).
    - 'r' resets back to full list.
    - number: open folder or download file.
    - 'q' returns to previous level.
    """
    full_list = list_folder_contents(folder_id)

    if not full_list:
        print(f"\nFolder '{folder_name}' is empty.")
        return

    # Start with full list; filtering narrows this down.
    filtered_list = full_list[:]

    while True:
        print(f"\n--- Items inside '{folder_name}' ---")

        if not filtered_list:
            print("(No items match the current filter.)")
        else:
            for idx, item in enumerate(filtered_list, start=1):
                print(f"{idx}. {item['name']} (ID: {item['id']})")

        print(
            "\nOptions:\n"
            "  number - open/download item by number\n"
            "  f      - filter items by name (cumulative)\n"
            "  r      - reset filter\n"
            "  q      - go back\n"
        )

        choice = input("Enter choice: ").strip().lower()

        if choice == "q":
            # Return to previous menu (main or parent folder)
            return

        elif choice == "r":
            # Restore full list
            filtered_list = full_list[:]
            print("Filter reset to full list.")

        elif choice == "f":
            term = input("Enter name fragment to filter by: ").strip().lower()
            if not term:
                print("Empty filter ignored.")
                continue

            # Cumulative filtering: filter the CURRENT list
            filtered_list = [
                item for item in filtered_list
                if term in item["name"].lower()
            ]

            if not filtered_list:
                print("No items match this filter. Try 'r' to reset.")

        elif choice.isdigit():
            idx = int(choice)
            if not (1 <= idx <= len(filtered_list)):
                print("Invalid number.")
                continue

            selected = filtered_list[idx - 1]
            mime = selected["mimeType"]

            if mime == "application/vnd.google-apps.folder":
                # Recurse into subfolder
                browse_folder(selected["id"], selected["name"])
            else:
                # Download file
                download_file(selected)

        else:
            print("Invalid input. Use a number, f, r, or q.")


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():
    """
    Main entry point:

    1. List root+shared items.
    2. If START_IN_SHARED_FOLDER is True, auto-open that folder once.
    3. After returning from it (pressing 'q'), show top-level menu.
    """

    print("\n=== Google Drive API Client (Service Account) ===\n")

    root_items = list_root_items()
    if not root_items:
        return

    # Try to auto-open the shared folder first
    if START_IN_SHARED_FOLDER:
        target = None
        for item in root_items:
            if (
                item["mimeType"] == "application/vnd.google-apps.folder"
                and item["name"] == SHARED_FOLDER_NAME
            ):
                target = item
                break

        if target:
            print(f"\nStarting in shared folder '{SHARED_FOLDER_NAME}' ...")
            browse_folder(target["id"], target["name"])
            # When user hits 'q' in that folder, they come back here:
            print("\nBack to top-level items.\n")
        else:
            print(
                f"\nShared folder '{SHARED_FOLDER_NAME}' was NOT found.\n"
                "Falling back to manual selection.\n"
            )

    # Manual top-level navigation is always available
    while True:
        print("\n--- Top-level items visible to this service account ---")
        for idx, item in enumerate(root_items, start=1):
            print(f"{idx}. {item['name']} (ID: {item['id']})")

        print("Enter a NUMBER to open item, or q to quit.")
        choice = input("Choice: ").strip().lower()

        if choice == "q":
            return

        if not choice.isdigit():
            print("Invalid input.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(root_items)):
            print("Invalid selection.")
            continue

        selected = root_items[idx - 1]
        mime = selected["mimeType"]

        if mime == "application/vnd.google-apps.folder":
            browse_folder(selected["id"], selected["name"])
        else:
            download_file(selected)


if __name__ == "__main__":
    main()


