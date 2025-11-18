from __future__ import print_function
import os.path
import base64
import json
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Path to credentials.json in project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_PATH = os.path.join(PROJECT_ROOT, "token.json")

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

SAFE_ATTACHMENT_EXTENSIONS = {'.txt', '.pdf', '.png', '.jpg', '.jpeg', '.csv', '.py'}
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5 MB
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


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


def is_safe_attachment(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SAFE_ATTACHMENT_EXTENSIONS:
        print(f"Blocked attachment: {file_path} (disallowed extension)")
        return False
    if not os.path.exists(file_path):
        print(f"Attachment not found: {file_path}")
        return False
    # Prevent path traversal
    abs_path = os.path.abspath(file_path)
    scripts_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "scripts"))
    if not abs_path.startswith(scripts_dir):
        print(f"Blocked attachment: {file_path} (outside scripts directory)")
        return False
    return True


def validate_email_address(email):
    return re.match(EMAIL_REGEX, email) is not None


def create_message(to, subject, body_text):
    message = MIMEText(body_text)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


def create_message_with_attachments(to, subject, body_text, attachments=None):
    msg = MIMEMultipart()
    msg["to"] = to
    msg["subject"] = subject
    msg.attach(MIMEText(body_text))

    if attachments:
        for file_path in attachments:
            if is_safe_attachment(file_path):
                with open(file_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(file_path)}",
                )
                msg.attach(part)
            else:
                print(f"Attachment blocked: {file_path}")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


if __name__ == "__main__":
    # Read email data from JSON
    with open(os.path.join(PROJECT_ROOT, "email_data.json"), "r") as f:
        data = json.load(f)
    to = data.get("to")
    subject = data.get("subject")
    body_text = data.get("body")
    attachments = data.get("attachments", [])

    # Validate email address
    if not validate_email_address(to):
        print(f"Invalid recipient email address: {to}")
        exit(1)
    # Validate subject length
    if not subject or len(subject) > 255:
        print("Invalid or too long subject.")
        exit(1)
    # Validate body length
    if not body_text or len(body_text) > 10000:
        print("Invalid or too long body.")
        exit(1)

    # Check all attachments before confirming
    blocked_attachments = [f for f in attachments if not is_safe_attachment(f)]
    if blocked_attachments:
        print("\nBlocked attachments detected:")
        for f in blocked_attachments:
            print(f" - {f}")
        print("Email not sent due to blocked or missing attachments.")
        exit(1)

    print("\n--- Email Preview ---")
    print(f"To: {to}")
    print(f"Subject: {subject}")
    print("Body:")
    print(body_text)
    if attachments:
        print("Attachments:", attachments)

    confirm = input("\nSend this email? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Canceled, not sending.")
        exit(0)

    try:
        service = get_service()
        msg = create_message_with_attachments(to, subject, body_text, attachments)
        sent = service.users().messages().send(userId="me", body=msg).execute()
        print("\nSent! Message id:", sent.get("id"))
    except Exception as e:
        print(f"Error sending email: {e}")