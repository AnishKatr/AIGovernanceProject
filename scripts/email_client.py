from __future__ import print_function
import os.path
import base64
import json
from datetime import datetime
import uuid
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Resolve project root relative to scripts/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Allow overriding Gmail credential/token paths so deploys can avoid filename conflicts.
# Defaults match the existing local workflow (root/credentials.json, root/token.json).
# Also fall back to email_credentials.json if present, since that name is committed.
TOKEN_PATH = os.getenv("GMAIL_TOKEN_FILE", os.path.join(PROJECT_ROOT, "token.json"))


def _resolve_credentials_path():
    """Pick the first existing credentials file from common locations."""
    candidates = [
        os.getenv("GMAIL_CREDENTIALS_FILE"),
        os.path.join(PROJECT_ROOT, "credentials.json"),
        os.path.join(PROJECT_ROOT, "email_credentials.json"),
        os.path.join(PROJECT_ROOT, "scripts", "credentials.json"),
    ]
    tried = []
    for path in candidates:
        if not path:
            continue
        tried.append(path)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"Gmail credentials not found. Checked: {', '.join(tried)}. "
        "Set GMAIL_CREDENTIALS_FILE to the correct JSON path."
    )


def _load_token_credentials():
    """Load token credentials from env JSON or a token file if present."""
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    if token_json:
        try:
            data = json.loads(token_json)
            return Credentials.from_authorized_user_info(data, SCOPES)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Failed to parse GMAIL_TOKEN_JSON: {exc}")

    if os.path.exists(TOKEN_PATH):
        try:
            return Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Failed to read token file {TOKEN_PATH}: {exc}")
    return None

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

SAFE_ATTACHMENT_EXTENSIONS = {'.txt', '.pdf', '.png', '.jpg', '.jpeg', '.csv', '.py'}
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5 MB
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# Logs directory for email send records
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")


def save_email_log(entry: dict):
    """Save a JSON file for the given email log entry into LOGS_DIR.

    The file name is email_<uuid>.json. This function is defensive and will
    print an error if write fails but won't raise.
    """
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        # Use the provided id or generate one for the filename
        entry_id = entry.get("id") or str(uuid.uuid4())
        filename = f"email_{entry_id}.json"
        path = os.path.join(LOGS_DIR, filename)
        with open(path, "w") as f:
            json.dump(entry, f, indent=2, default=str)
    except Exception as e:
        print(f"Failed to write email log: {e}")


def get_service():
    creds = _load_token_credentials()
    credentials_path = _resolve_credentials_path()

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            try:
                creds = flow.run_local_server(port=0)
            except Exception as exc:  # pylint: disable=broad-except
                print(f"Local server auth failed ({exc}); falling back to console auth.")
                creds = flow.run_console()
        try:
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Warning: could not persist token to {TOKEN_PATH}: {exc}")

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


def send_email(to: str, subject: str, body_text: str, attachments=None, dry_run: bool = False):
    """Programmatic helper to send an email (or just log a dry-run).

    Validates input using the same safety rules as the CLI flow and writes a log
    entry to logs/email_<id>.json. Returns a dict with status/log/message_id.
    """
    attachments = attachments or []

    if not validate_email_address(to):
        raise ValueError(f"Invalid recipient email address: {to}")
    if not subject or len(subject) > 255:
        raise ValueError("Subject is required and must be <= 255 characters.")
    if not body_text or len(body_text) > 10000:
        raise ValueError("Body is required and must be <= 10,000 characters.")

    blocked = [p for p in attachments if not is_safe_attachment(p)]
    if blocked:
        raise ValueError(f"Blocked or missing attachments: {blocked}")

    log_entry = {
        "id": str(uuid.uuid4()),
        "to": to,
        "subject": subject,
        "body": body_text,
        "attachments": attachments,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "pending" if dry_run else "sending",
    }
    save_email_log(log_entry)

    if dry_run:
        return {"status": "pending", "log_id": log_entry["id"], "message": "Dry run; not sent."}

    service = get_service()
    msg = create_message_with_attachments(to, subject, body_text, attachments)
    sent = service.users().messages().send(userId="me", body=msg).execute()
    message_id = sent.get("id")

    log_entry.update(
        {
            "status": "sent",
            "sent_at": datetime.utcnow().isoformat() + "Z",
            "message_id": message_id,
        }
    )
    save_email_log(log_entry)
    return {"status": "sent", "message_id": message_id, "log_id": log_entry["id"]}


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
    # Prepare a log entry for this attempt
    log_entry = {
        "id": str(uuid.uuid4()),
        "to": to,
        "subject": subject,
        "body": body_text,
        "attachments": attachments,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "pending",
    }
    # Save initial pending log
    save_email_log(log_entry)

    try:
        service = get_service()
        msg = create_message_with_attachments(to, subject, body_text, attachments)
        sent = service.users().messages().send(userId="me", body=msg).execute()
        message_id = sent.get("id")
        log_entry.update({
            "status": "sent",
            "sent_at": datetime.utcnow().isoformat() + "Z",
            "message_id": message_id,
        })
        save_email_log(log_entry)
        print("\nSent! Message id:", message_id)
    except Exception as e:
        log_entry.update({
            "status": "failed",
            "failed_at": datetime.utcnow().isoformat() + "Z",
            "error": str(e),
        })
        save_email_log(log_entry)
        print(f"Error sending email: {e}")
