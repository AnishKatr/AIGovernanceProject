# email-test.py (or gmail_test.py)
from __future__ import print_function
import os.path
import base64
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Path to credentials.json in project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_PATH = os.path.join(PROJECT_ROOT, "token.json")

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_service():
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_message(to, subject, body_text):
    message = MIMEText(body_text)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


if __name__ == "__main__":
    # --- Simulate "LLM output" with user input ---
    print("=== Gmail API Test (manual input simulating LLM) ===")
    to = input("Recipient email: ").strip()
    subject = input("Subject: ").strip()

    print("\nEnter email body. End with a single '.' on a line by itself:")
    lines = []
    while True:
        line = input()
        if line.strip() == ".":
            break
        lines.append(line)
    body_text = "\n".join(lines)

    print("\n--- Sending email ---")
    print(f"To: {to}")
    print(f"Subject: {subject}")
    print("Body:")
    print(body_text)
    confirm = input("\nSend this email? [y/N]: ").strip().lower()

    if confirm != "y":
        print("Canceled, not sending.")
    else:
        service = get_service()
        msg = create_message(to, subject, body_text)
        sent = service.users().messages().send(userId="me", body=msg).execute()
        print("\n✅ Sent! Message id:", sent.get("id"))