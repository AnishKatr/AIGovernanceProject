"""Bridges the existing scripts (HR API helper, Gmail sender, Drive sync) into the Flask backend."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Make the repo root importable so we can reuse the scripts/* modules directly.
# __file__ -> Backend/services/hr_tools.py; repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# pylint: disable=wrong-import-position,import-error
from scripts.email_client import is_safe_attachment, send_email  # type: ignore
from scripts.integrate_hr_email import (  # type: ignore
    _fetch_employee_by_id,
    _prepare_email_json,
    _render_body,
    _search_employee_by_name,
)
import scripts.hr_drive_tool as drive_tool  # type: ignore
from services import rag_ingest
from services.rag_service import build_rag_service_from_env

SCRIPTS_DIR = REPO_ROOT / "scripts"
DOWNLOAD_DIR = SCRIPTS_DIR / "downloads"

# Allow overriding the HR API base URL via environment variable so deployed
# backends don't keep calling the local default. Supports either a base URL
# (e.g., https://hrapi.onrender.com) or the full employees endpoint
# (e.g., https://hrapi.onrender.com/employees).
_env_hr_base = os.getenv("HR_API_URL")
if _env_hr_base:
    _trimmed = _env_hr_base.rstrip("/")
    if _trimmed.endswith("/employees"):
        DEFAULT_HR_URL = _trimmed[: -len("/employees")] or _trimmed
        drive_tool.HR_API_URL = os.getenv("HR_API_EMPLOYEES_URL", _trimmed)
    else:
        DEFAULT_HR_URL = _trimmed
        drive_tool.HR_API_URL = os.getenv("HR_API_EMPLOYEES_URL", f"{DEFAULT_HR_URL}/employees")
else:
    DEFAULT_HR_URL = "http://localhost:8000"
    drive_tool.HR_API_URL = os.getenv("HR_API_EMPLOYEES_URL", "http://127.0.0.1:8000/employees")

DEFAULT_BODY = (
    "Hi {first_name},\n\n"
    "We are following up on your HR file. Your current role is {designation} in "
    "{department}. If any details are incorrect, please reply to this email.\n\n"
    "Best,\nHR Ops"
)


def fetch_employee(hr_url: str, employee_id: Optional[int] = None, name: Optional[str] = None) -> Dict:
    """Fetch a single employee via the HR demo API."""
    try:
        if employee_id is not None:
            return _fetch_employee_by_id(hr_url, employee_id)
        if name:
            return _search_employee_by_name(hr_url, name)
    except SystemExit as exc:  # integrate_hr_email exits on not-found
        raise ValueError(str(exc)) from exc
    raise ValueError("Provide either employee_id or name.")


def _download_drive_attachment(file_id: str) -> str:
    """Download a Drive file into scripts/downloads and return the local path."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    service = drive_tool.get_drive_service()
    meta = service.files().get(fileId=file_id, fields="id,name,mimeType").execute()

    is_google_doc = meta["mimeType"].startswith("application/vnd.google-apps.")
    dest_name = meta["name"] + (".pdf" if is_google_doc else "")
    dest_path = DOWNLOAD_DIR / dest_name

    prev_cwd = os.getcwd()
    try:
        # hr_drive_tool.download_file writes to the current working directory.
        os.chdir(DOWNLOAD_DIR)
        drive_tool.download_file(service, meta["id"], meta["name"], meta["mimeType"])
    finally:
        os.chdir(prev_cwd)

    if not dest_path.exists():
        raise FileNotFoundError(f"Expected downloaded file missing: {dest_path}")
    if not is_safe_attachment(str(dest_path)):
        raise ValueError(f"Attachment blocked by policy: {dest_path}")
    return str(dest_path)


def prepare_and_send_hr_email(
    *,
    hr_url: str = DEFAULT_HR_URL,
    employee_id: Optional[int] = None,
    name: Optional[str] = None,
    subject: str,
    body_template: Optional[str] = None,
    drive_file_id: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    send_now: bool = False,
) -> Dict:
    """Fetch employee data, render an email, optionally attach a Drive file, and send (or dry-run)."""
    employee = fetch_employee(hr_url, employee_id=employee_id, name=name)
    attachment_paths: List[str] = []

    if drive_file_id:
        attachment_paths.append(_download_drive_attachment(drive_file_id))

    for path in attachments or []:
        if not is_safe_attachment(path):
            raise ValueError(f"Attachment blocked: {path}")
        attachment_paths.append(path)

    body = _render_body(body_template or DEFAULT_BODY, employee)
    _prepare_email_json(employee["email"], subject, body, attachment_paths)

    send_result = send_email(
        employee["email"],
        subject,
        body,
        attachments=attachment_paths,
        dry_run=not send_now,
    )
    return {
        "employee": employee,
        "subject": subject,
        "body": body,
        "attachments": attachment_paths,
        "send_result": send_result,
    }


def sync_drive_from_hr(
    *,
    hr_url: Optional[str] = None,
    folder_id: Optional[str] = None,
    csv_name: Optional[str] = None,
    ingest: bool = True,
    download_files: bool = True,
    namespace: Optional[str] = None,
) -> Dict[str, str]:
    """Refresh employee_database.csv in Drive using the HR API."""
    # Ensure service account key path is configured and exists.
    candidate_env = os.getenv("SERVICE_ACCOUNT_FILE")
    candidate_scripts_key = SCRIPTS_DIR / "service_account_key.json"
    candidate_scripts_creds = SCRIPTS_DIR / "credentials.json"
    candidate_root = REPO_ROOT / "service_account_key.json"

    if candidate_env:
        drive_tool.SERVICE_ACCOUNT_FILE = candidate_env
    elif candidate_scripts_key.exists():
        drive_tool.SERVICE_ACCOUNT_FILE = str(candidate_scripts_key)
    elif candidate_scripts_creds.exists():
        drive_tool.SERVICE_ACCOUNT_FILE = str(candidate_scripts_creds)
    else:
        drive_tool.SERVICE_ACCOUNT_FILE = str(candidate_root)

    if not Path(drive_tool.SERVICE_ACCOUNT_FILE).exists():
        raise FileNotFoundError(
            f"Service account key not found. Checked: "
            f"{candidate_env or '[SERVICE_ACCOUNT_FILE unset]'}, "
            f"{candidate_scripts_key}, {candidate_scripts_creds}, {candidate_root}. "
            "Set SERVICE_ACCOUNT_FILE to the correct JSON path."
        )

    if hr_url:
        drive_tool.HR_API_URL = hr_url
    if folder_id:
        drive_tool.DUMMY_FOLDER_ID = folder_id
    if csv_name:
        drive_tool.EMPLOYEE_CSV_NAME = csv_name

    drive_tool.replace_employee_database_in_drive()
    ingest_result: Dict[str, str] = {}
    download_result: Dict[str, Any] = {}

    if download_files:
        try:
            download_result = download_drive_folder(folder_id=drive_tool.DUMMY_FOLDER_ID)
        except Exception as exc:  # pylint: disable=broad-except
            download_result = {"status": "error", "error": str(exc)}

    if ingest:
        try:
            ingest_result = ingest_local_data_for_rag(namespace=namespace)
        except Exception as exc:  # pylint: disable=broad-except
            ingest_result = {"status": "error", "error": str(exc)}

    return {
        "status": "ok",
        "folder_id": drive_tool.DUMMY_FOLDER_ID,
        "csv_name": drive_tool.EMPLOYEE_CSV_NAME,
        "ingest": ingest_result or {"status": "skipped"},
        "download": download_result or {"status": "skipped"},
    }


def ingest_local_data_for_rag(
    *,
    paths: Optional[List[str]] = None,
    namespace: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Embed and upsert local files into Pinecone so RAG has context.
    Defaults to employee_database.csv and scripts/downloads if present.
    """
    rag_service = build_rag_service_from_env()
    if namespace:
        rag_service.pinecone_config.namespace = namespace
        rag_service.vector_store.config.namespace = namespace

    candidate_paths = paths or [str(p) for p in rag_ingest.default_search_paths()]
    files = rag_ingest.discover_paths(candidate_paths)
    if not files:
        raise RuntimeError("No files found to ingest.")

    chunks = []
    for file_path in files:
        file_path = Path(file_path)
        source_type = "drive_file" if rag_ingest.DEFAULT_DRIVE_DIR in file_path.parents else "file"
        if file_path == rag_ingest.DEFAULT_EMPLOYEE_CSV:
            source_type = "employee_csv"
        chunks.extend(rag_ingest.build_chunks_from_file(file_path, source_type=source_type))

    if not chunks:
        raise RuntimeError("No text content available to ingest.")

    ingestor = rag_ingest.RAGIngestor(rag_service.embedder, rag_service.vector_store)
    written = ingestor.ingest(chunks)
    return {
        "status": "ok",
        "namespace": rag_service.pinecone_config.namespace,
        "files_processed": len(files),
        "chunks_written": written,
    }


def download_drive_folder(
    *,
    folder_id: Optional[str] = None,
    dest_dir: Path = DOWNLOAD_DIR,
) -> Dict[str, Any]:
    """
    Download all non-folder items from the target Drive folder into dest_dir.
    Uses hr_drive_tool helpers and preserves Google Docs exports as PDF.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    service = drive_tool.get_drive_service()
    target_folder = folder_id or drive_tool.DUMMY_FOLDER_ID
    items = drive_tool.list_items_in_folder(service, target_folder)
    downloaded: List[str] = []
    skipped: List[str] = []

    prev_cwd = os.getcwd()
    try:
        os.chdir(dest_dir)
        for item in items:
            if item["mimeType"] == "application/vnd.google-apps.folder":
                skipped.append(item["name"])
                continue
            drive_tool.download_file(service, item["id"], item["name"], item["mimeType"])
            downloaded.append(item["name"])
    finally:
        os.chdir(prev_cwd)

    return {
        "status": "ok",
        "folder_id": target_folder,
        "dest": str(dest_dir),
        "downloaded": downloaded,
        "skipped_folders": skipped,
    }
