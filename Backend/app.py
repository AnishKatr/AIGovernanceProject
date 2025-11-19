import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from agents.orchestrator import OrchestratorAgent
from services.rag_service import RAGService, build_rag_service_from_env

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
    if not query:
        return jsonify({"error": "Field 'query' is required."}), 400

    try:
        result = orchestrator_agent.handle_user_request(query)
        return jsonify(result)
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.exception("Failed to handle query")
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
