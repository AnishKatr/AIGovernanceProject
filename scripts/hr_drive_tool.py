#!/usr/bin/env python3
"""
hr_drive_tool.py

One script that:
1) Pulls employee data from the HR API and REPLACES employee_database.csv in
   the shared Dummy Folder on Google Drive (content only, keeps the same file).
2) Lets you browse/filter/download files from the Dummy Folder.

Assumptions:
- HR API is running at http://127.0.0.1:8000/employees
- You already have a shared folder ("Dummy Folder") in Drive, and it is shared
  with your service account email.
- Inside that folder, you have manually created a file named `employee_database.csv`
  (owned by your normal Google account). The script only overwrites its contents,
  so the storage quota stays on your personal account, not the service account.
"""

import csv
import io
import os
import sys
from typing import List, Dict

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

# ------------------------------
# CONFIG
# ------------------------------

# Path to your service-account JSON key
SERVICE_ACCOUNT_FILE = "service_account_key.json"

# Readonly is enough for browsing, but we also need file update for replace
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Folder that you shared with the service account (Dummy Folder)
DUMMY_FOLDER_ID = "13UQLo24QpFhns4fKVdaDnkDWQE3IM27t"  # <-- keep your real ID here

# Name of the employee CSV file in that folder
EMPLOYEE_CSV_NAME = "employee_database.csv"

# HR API endpoint (from your uvicorn hr_client.py)
HR_API_URL = "http://127.0.0.1:8000/employees"


# ------------------------------
# DRIVE AUTH + UTILITIES
# ------------------------------

def get_drive_service():
    """Authenticate with the service account and return a Drive API client."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )
    service = build("drive", "v3", credentials=creds)
    return service


def list_items_in_folder(service, folder_id: str) -> List[Dict]:
    """Return a list of items (files/folders) inside the given folder."""
    items: List[Dict] = []
    page_token = None

    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
        ).execute()

        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    # Sort alphabetically by name for nicer display
    items.sort(key=lambda x: x["name"].lower())
    return items


def find_file_in_folder_by_name(service, folder_id: str, filename: str):
    """Return the first file in folder with exact name, or None."""
    response = service.files().list(
        q=(
            f"'{folder_id}' in parents and "
            f"name='{filename}' and trashed=false"
        ),
        fields="files(id, name)",
    ).execute()
    files = response.get("files", [])
    return files[0] if files else None


def download_file(service, file_id: str, filename: str, mime_type: str):
    """
    Download a file. If it is a Google Docs-type file, export it to PDF.
    Otherwise, download its binary content as-is.
    """
    # Google Docs / Sheets / Slides are "application/vnd.google-apps.*"
    if mime_type.startswith("application/vnd.google-apps."):
        # Export Docs to PDF by default
        export_mime = "application/pdf"
        dest_name = filename + ".pdf"
        print(f"Exporting Google Docs-type file as {dest_name} ...")

        request = service.files().export_media(
            fileId=file_id, mimeType=export_mime
        )
        fh = io.FileIO(dest_name, "wb")
        downloader = MediaIoBaseDownload(fh, request)
    else:
        # Normal binary/downloadable file
        dest_name = filename
        print(f"Downloading binary file as {dest_name} ...")

        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(dest_name, "wb")
        downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"  Progress: {int(status.progress() * 100)}%")

    print(f"✔ Download complete: {dest_name}")


# ------------------------------
# HR API → CSV → DRIVE REPLACE
# ------------------------------

def fetch_employee_data() -> list:
    """Call the HR API and return the list of employees (JSON)."""
    print("Requesting employee data from HR API...")
    resp = requests.get(HR_API_URL)
    resp.raise_for_status()
    data = resp.json()
    print("✔ Employee data retrieved.")
    return data


def write_employee_csv(employees: list, filename: str):
    """
    Write employees to CSV.

    The fields here should match what hr_client.py returns from /employees.
    Adjust fieldnames if your HR API schema is different.
    """
    print(f"Creating CSV file: {filename}")
    if not employees:
        raise ValueError("No employee data returned from HR API.")

    # Use keys from the first record as columns
    fieldnames = list(employees[0].keys())

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(employees)

    print(f"✔ CSV saved: {filename}")


def replace_employee_database_in_drive():
    """
    Main "replace" workflow:

    1) Fetch employee data from HR API.
    2) Save it as employee_database.csv locally.
    3) Find existing employee_database.csv in the Dummy Folder.
    4) If found, overwrite its contents (keeps ownership & quota).
       If not found, tell the user to create an empty one manually.
    """
    # --- 1 & 2: HR → CSV locally ---
    employees = fetch_employee_data()
    local_csv = EMPLOYEE_CSV_NAME
    write_employee_csv(employees, local_csv)

    # --- 3: Connect to Drive and search for the target file ---
    print("Looking for existing employee_database.csv in Dummy Folder...")
    service = get_drive_service()
    existing = find_file_in_folder_by_name(service, DUMMY_FOLDER_ID, EMPLOYEE_CSV_NAME)

    if not existing:
        print("No existing employee_database.csv found in Dummy Folder.")
        print("→ Create an empty employee_database.csv in that folder")
        print("  (owned by your normal Google account), then rerun.")
        print("\nReplace failed — no target file to overwrite.")
        return

    file_id = existing["id"]
    print(f"✔ Found existing database file: {EMPLOYEE_CSV_NAME} (ID: {file_id})")
    print("Overwriting employee_database.csv contents in Drive...")

    # Upload contents using MediaIoBaseUpload; this updates the file in place.
    with open(local_csv, "rb") as f:
        media = MediaIoBaseUpload(f, mimetype="text/csv", resumable=True)
        request = service.files().update(
            fileId=file_id,
            media_body=media,
        )
        request.execute()

    print(f"✔ Replace complete. File ID: {file_id}")
    print("\n✔ DONE – Employee database replaced in Google Drive.")


# ------------------------------
# DUMMY FOLDER BROWSER
# ------------------------------

def show_items(items: List[Dict], heading: str):
    """Pretty-print a numbered list of items."""
    print(f"\n--- {heading} ---")
    if not items:
        print("  (no items)")
        return
    for idx, item in enumerate(items, start=1):
        print(f"{idx}. {item['name']} (ID: {item['id']})")


def browse_dummy_folder():
    """
    Interactive browser for the Dummy Folder, with cumulative filtering
    and download by number.
    """
    service = get_drive_service()

    # Load all items once
    all_items = list_items_in_folder(service, DUMMY_FOLDER_ID)
    if not all_items:
        print("\nDummy Folder is empty.")
        return

    filtered_items = all_items[:]  # start with full list
    current_filter = ""

    while True:
        heading = "Items inside 'Dummy Folder'"
        if current_filter:
            heading += f" (filter: '{current_filter}')"

        show_items(filtered_items, heading)

        print("\nOptions:")
        print("  number – open/download item by number")
        print("  f      – filter items by name (cumulative)")
        print("  r      – reset filter to show all items")
        print("  q      – go back to main menu")

        choice = input("\nEnter choice: ").strip().lower()

        if choice == "q":
            print("\nBack to main menu.")
            break
        elif choice == "f":
            frag = input("Enter part of the name to filter by: ").strip()
            if not frag:
                print("Empty filter fragment; nothing changed.")
                continue

            current_filter += frag  # cumulative
            filtered_items = [
                it for it in filtered_items
                if current_filter.lower() in it["name"].lower()
            ]
            if not filtered_items:
                print(f"No items match filter '{current_filter}'. Resetting filter.")
                filtered_items = all_items[:]
                current_filter = ""
        elif choice == "r":
            filtered_items = all_items[:]
            current_filter = ""
        else:
            # Try to interpret as a number to download
            if not choice.isdigit():
                print("Invalid choice. Type a number, f, r, or q.")
                continue
            idx = int(choice)
            if not (1 <= idx <= len(filtered_items)):
                print("Number out of range.")
                continue

            item = filtered_items[idx - 1]
            mime_type = item["mimeType"]
            if mime_type == "application/vnd.google-apps.folder":
                print("Folder navigation is not implemented in this browser.")
                print("Please pick a file instead.")
            else:
                download_file(service, item["id"], item["name"], mime_type)


# ------------------------------
# MAIN MENU
# ------------------------------

def main():
    # Ensure relative paths (like service_account_key.json) work
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    while True:
        print("\n========================================")
        print("   HR + Google Drive Integration Tool   ")
        print("========================================")
        print("1. Update employee database in Drive")
        print("   (REPLACE old employee_database.csv)")
        print("2. Browse Dummy Folder in Drive")
        print("   (list / filter / download files)")
        print("q. Quit")

        choice = input("\nSelect an option: ").strip().lower()

        if choice == "1":
            print("\n========================================")
            print(" REPLACE EMPLOYEE DATABASE IN GOOGLE DRIVE")
            print("========================================\n")
            try:
                replace_employee_database_in_drive()
            except Exception as e:
                print(f"\n[ERROR] Replace failed: {e}\n")
        elif choice == "2":
            print("\n=== Google Drive API Client (Dummy Folder) ===")
            browse_dummy_folder()
        elif choice == "q":
            print("\nGoodbye!\n")
            break
        else:
            print("Invalid choice. Please type 1, 2, or q.")


if __name__ == "__main__":
    main()
