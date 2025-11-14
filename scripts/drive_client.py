from __future__ import print_function
import os.path
import io

# Google auth & API client imports
from google.oauth2.credentials import Credentials           # Stores and refreshes user OAuth tokens
from google_auth_oauthlib.flow import InstalledAppFlow      # Handles the browser-based OAuth flow
from googleapiclient.discovery import build                 # Builds a Drive API client
from googleapiclient.http import MediaIoBaseDownload        # Streams file downloads from Drive


# ---------------- CONFIGURATION ----------------

# SCOPES define what permissions your app is asking for.
# "drive.readonly" means: this script can read files from your Drive but NOT modify them.
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# This is the OAuth client secret file you downloaded from Google Cloud Console.
# It contains your client_id and client_secret for the "Desktop App" OAuth client.
CLIENT_SECRET_FILE = "client_secret.json"

# This file will be CREATED by the script after you log in once.
# It stores your access + refresh tokens so you don't need to log in every time.
TOKEN_FILE = "token.json"

# ------------------------------------------------


def get_drive_service():
    """
    Authenticate as the user (YOU) and return a Google Drive service client.

    This function:
      - checks if we already have valid OAuth credentials in token.json
      - if not, opens a browser window for you to log in and grant permissions
      - then builds and returns a Drive API client bound to your account
    """
    creds = None

    # If token.json exists, load stored credentials from that file.
    # token.json is created the first time you successfully complete the OAuth flow.
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If there are no valid credentials, go through the login flow.
    if not creds or not creds.valid:
        # If credentials exist but are expired AND have a refresh token, refresh them silently.
        if creds and creds.expired and creds.refresh_token:
            # Lazy import to avoid unused warning if not needed
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            # No valid creds yet: start the OAuth flow using the client_secret.json file.
            # This spins up a local web server and opens a browser for you to log into your Google account.
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials to token.json for next time.
        # This way, you rarely have to log in again unless you delete this file or change scopes.
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    # Build and return the Drive API client for version v3.
    service = build("drive", "v3", credentials=creds)
    return service


def list_files(page_size=20, query=None):
    """
    List files from the user's real Google Drive (the same one you see in the browser).

    Arguments:
      page_size: how many files to list at once (default 20).
      query: an optional Drive search query (e.g., "name contains 'report'").

    Returns:
      A list of file metadata dictionaries, each containing:
        - id
        - name
        - mimeType
    """
    service = get_drive_service()  # Get an authenticated Drive client

    # Base parameters for files.list()
    params = {
        "pageSize": page_size,
        "fields": "files(id, name, mimeType)",  # Limit response fields to what we need
    }

    # If a query string was provided (like "name contains 'report'"), add it.
    # This uses the Drive v3 query language.
    if query:
        params["q"] = query

    # Call the Drive API to list files and execute the HTTP request.
    results = service.files().list(**params).execute()

    # Extract the list of files from the response. If no 'files' key, default to [].
    items = results.get("files", [])

    if not items:
        print("No files found.")
        return []

    # Print a numbered list so the user can choose one to download later.
    print("\n--- Files Found ---")
    for i, item in enumerate(items, start=1):
        print(f"{i}. {item['name']} (ID: {item['id']}) [{item['mimeType']}]")

    return items


def download_file(file_id, destination_path):
    """
    Download a file from the user's Google Drive to the local filesystem.

    Arguments:
      file_id:         the Drive file ID (string)
      destination_path: local path/filename where the file should be saved
    """
    service = get_drive_service()  # Get an authenticated Drive client

    # Build the request to get the file's media (raw bytes).
    request = service.files().get_media(fileId=file_id)

    # Open a local file handle for writing binary data.
    fh = io.FileIO(destination_path, "wb")

    # MediaIoBaseDownload handles chunked downloading and progress updates.
    downloader = MediaIoBaseDownload(fh, request)

    print(f"Downloading {file_id}...\n")

    done = False
    while not done:
        # next_chunk() downloads the next chunk and returns (status, done)
        status, done = downloader.next_chunk()
        if status:
            # status.progress() returns a float between 0 and 1 indicating download progress.
            print(f"Progress: {int(status.progress() * 100)}%")

    print(f"\n✅ Download complete! Saved as: {destination_path}")


def main():
    """
    Main interactive loop:
      1. Ask the user for an optional search term.
      2. List matching files from Google Drive.
      3. Ask which one to download.
      4. Ask what filename to save it as locally.
      5. Download the selected file.
    """
    print("\n=== Google Drive OAuth Client (acts as YOU) ===\n")

    # Prompt user for a search string. If they press Enter, we won't filter by name.
    search = input("Search for filename (press Enter to list all): ").strip()

    # Build a simple query: name contains '<search>'
    # If search is empty, query remains None and list_files() will list everything.
    query = f"name contains '{search}'" if search else None

    # Fetch a list of files based on the query.
    files = list_files(page_size=20, query=query)

    if not files:
        # No files found or accessible.
        return

    # Ask the user which file they want to download by its number in the printed list.
    choice = input("\nEnter the number of the file to download: ").strip()

    # Validate input: must be a digit and within the range of returned files.
    if not choice.isdigit() or not (1 <= int(choice) <= len(files)):
        print("Invalid choice.")
        return

    # Convert to 0-based index.
    chosen = files[int(choice) - 1]
    print(f"You chose: {chosen['name']} (ID: {chosen['id']})")

    # Ask user how to name the downloaded file locally.
    # If they press Enter, use the same name as in Drive.
    dest = input(
        f"Save as (press Enter for '{chosen['name']}'): "
    ).strip() or chosen["name"]

    # Call the function to download the file.
    download_file(chosen["id"], dest)


# Standard Python entry point check.
# If this script is run directly (not imported as a module), run main().
if __name__ == "__main__":
    main()

