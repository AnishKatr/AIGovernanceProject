import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from agents.orchestrator import OrchestratorAgent
from services.rag_service import RAGService, build_rag_service_from_env
from services import hr_tools

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
# Load environment variables from both the repo root and Backend directory.
load_dotenv(BASE_DIR.parent / ".env", override=False)
load_dotenv(BASE_DIR / ".env", override=False)


def _init_rag() -> Optional[RAGService]:
    try:
        return build_rag_service_from_env()
    except RuntimeError as exc:
        app.logger.warning("RAG service not configured correctly: %s", exc)
        return None


rag_service = _init_rag()
orchestrator_agent = OrchestratorAgent(rag_service) if rag_service else None


@app.route("/api/hello", methods=["GET"])
def hello():
    return jsonify({"message": "Hello from Flask backend!"})


@app.route("/api/query", methods=["POST"])
def query_knowledge_base():
    if not orchestrator_agent:
        return jsonify({"error": "RAG service is not configured. Check your environment variables."}), 500

    payload = request.get_json(silent=True) or {}
    query = payload.get("query")
    history = payload.get("history") or []
    session_id = payload.get("session_id")
    if not query:
        return jsonify({"error": "Field 'query' is required."}), 400

    try:
        result = orchestrator_agent.handle_user_request(query, history=history, session_id=session_id)
        return jsonify(result)
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.exception("Failed to handle query")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/hr/email", methods=["POST"])
def send_hr_email():
    payload = request.get_json(silent=True) or {}
    subject = payload.get("subject")
    if not subject:
        return jsonify({"error": "Field 'subject' is required."}), 400

    try:
        employee_id = payload.get("employee_id")
        name = payload.get("name")
        drive_file_id = payload.get("drive_file_id")
        attachments = payload.get("attachments") or []
        hr_url = payload.get("hr_url") or hr_tools.DEFAULT_HR_URL
        send_now = bool(payload.get("send", False))
        result = hr_tools.prepare_and_send_hr_email(
            hr_url=hr_url,
            employee_id=employee_id,
            name=name,
            subject=subject,
            body_template=payload.get("body"),
            drive_file_id=drive_file_id,
            attachments=attachments,
            send_now=send_now,
        )
        return jsonify({"status": "ok", **result})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.exception("Failed to send HR email")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/drive/sync", methods=["POST"])
def sync_drive():
    payload = request.get_json(silent=True) or {}
    try:
        result = hr_tools.sync_drive_from_hr(
            hr_url=payload.get("hr_url"),
            folder_id=payload.get("folder_id"),
            csv_name=payload.get("csv_name"),
            ingest=payload.get("ingest", True),
            namespace=payload.get("namespace"),
        )
        return jsonify(result)
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.exception("Drive sync failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/hr/employee", methods=["GET"])
def fetch_employee():
    employee_id = request.args.get("employee_id", type=int)
    name = request.args.get("name")
    if not employee_id and not name:
        return jsonify({"error": "Provide employee_id or name as query parameter."}), 400
    hr_url = request.args.get("hr_url") or hr_tools.DEFAULT_HR_URL
    try:
        employee = hr_tools.fetch_employee(hr_url, employee_id=employee_id, name=name)
        return jsonify({"employee": employee})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.exception("Failed to fetch employee")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/rag/reset", methods=["POST"])
def reset_rag_namespace():
    if not rag_service:
        return jsonify({"error": "RAG service is not configured. Check your environment variables."}), 500

    payload = request.get_json(silent=True) or {}
    namespace = payload.get("namespace")
    try:
        rag_service.wipe(namespace=namespace)
        return jsonify({"status": "ok", "namespace": namespace or rag_service.pinecone_config.namespace})
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.exception("Failed to reset RAG namespace")
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
