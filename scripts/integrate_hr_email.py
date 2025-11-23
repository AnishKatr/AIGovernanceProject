"""
Helper to bridge the HR demo API to the Gmail email sender.

Workflow:
- Fetch one employee from the HR service (by name search or ID).
- Render an email body from a template.
- Write email_data.json in the repo root.
- Optionally invoke scripts/email_client.py so the user can preview/confirm.

By default this is a dry run (no Gmail send). Use --send to launch the email
script; it will still ask for confirmation before sending.
"""
import argparse
import json
import os
import subprocess
import sys
from typing import Dict, List

import requests


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMAIL_DATA_PATH = os.path.join(PROJECT_ROOT, "email_data.json")
DEFAULT_HR_URL = "http://localhost:8000"


def _fetch_employee_by_id(base_url: str, employee_id: int) -> Dict:
    resp = requests.get(f"{base_url}/employees/{employee_id}", timeout=5)
    if resp.status_code == 404:
        raise SystemExit(f"No employee found with id={employee_id}")
    resp.raise_for_status()
    return resp.json()


def _search_employee_by_name(base_url: str, name: str) -> Dict:
    resp = requests.get(
        f"{base_url}/employees/search/by-name", params={"name": name}, timeout=5
    )
    if resp.status_code == 404:
        raise SystemExit(f"No employees found matching '{name}'")
    resp.raise_for_status()
    results: List[Dict] = resp.json()
    if len(results) != 1:
        raise SystemExit(
            f"Expected exactly 1 match for '{name}', got {len(results)}. Please refine the name."
        )
    return results[0]


def _render_body(template: str, employee: Dict) -> str:
    return template.format(
        first_name=employee.get("first_name", ""),
        last_name=employee.get("last_name", ""),
        full_name=f"{employee.get('first_name','')} {employee.get('last_name','')}".strip(),
        department=employee.get("department", ""),
        designation=employee.get("designation", ""),
        phone=employee.get("phone", ""),
        email=employee.get("email", ""),
        employee_id=employee.get("employee_id", ""),
        bank_name=employee.get("bank_name", ""),
        bank_account_number=employee.get("bank_account_number", ""),
        account_balance=employee.get("account_balance", ""),
    )


def _prepare_email_json(to_addr: str, subject: str, body: str, attachments: List[str]):
    payload = {
        "to": to_addr,
        "subject": subject,
        "body": body,
        "attachments": attachments,
    }
    with open(EMAIL_DATA_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {EMAIL_DATA_PATH} for {to_addr}")


def main():
    parser = argparse.ArgumentParser(description="HR → email integration helper (dry-run by default).")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--name", help="Employee name to search (partial match supported).")
    target.add_argument("--id", type=int, help="Employee ID to fetch directly.")

    parser.add_argument("--subject", required=True, help="Email subject.")
    parser.add_argument(
        "--body-template",
        required=True,
        help="Python format string for the email body. Available fields: "
        "{first_name}, {last_name}, {full_name}, {department}, {designation}, "
        "{phone}, {email}, {employee_id}, {bank_name}, {bank_account_number}, {account_balance}",
    )
    parser.add_argument(
        "--attachment",
        action="append",
        default=[],
        help="Optional attachment path (repeatable). Must be allowed by email_client.py policy.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="If set, invokes scripts/email_client.py (which still prompts for confirmation).",
    )
    parser.add_argument(
        "--hr-url",
        default=os.getenv("HR_API_URL", DEFAULT_HR_URL),
        help=f"Base URL for the HR service (default: {DEFAULT_HR_URL}).",
    )

    args = parser.parse_args()

    if args.attachment:
        print("Note: attachments must comply with scripts/email_client.py safety checks.")

    # Fetch employee
    if args.id is not None:
        employee = _fetch_employee_by_id(args.hr_url, args.id)
    else:
        employee = _search_employee_by_name(args.hr_url, args.name)

    # Render body and write JSON
    body = _render_body(args.body_template, employee)
    _prepare_email_json(employee["email"], args.subject, body, args.attachment)

    if not args.send:
        print("Dry run complete. Run with --send to launch the email preview/confirmation.")
        return

    print("Launching scripts/email_client.py (you will be prompted to confirm send)...")
    result = subprocess.run(
        [sys.executable, os.path.join("scripts", "email_client.py")],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(f"email_client.py exited with status {result.returncode}")


if __name__ == "__main__":
    main()
