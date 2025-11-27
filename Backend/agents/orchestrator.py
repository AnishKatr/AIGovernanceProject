from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, List, Tuple
import re

from services.rag_service import RAGService
from services import hr_tools


@dataclass
class AgentDecision:
    """Represents the routing result."""

    recommended_agent: str
    reasoning: str


class OrchestratorAgent:
    """
    Task router that decides which specialized agent should handle a request.

    RAG is the default; if the user issues a lightweight email command, the
    orchestrator will trigger the HR email agent directly.
    """

    def __init__(self, rag_service: Optional[RAGService]):
        self.rag_service = rag_service
        # Lightweight session store: session_id -> {"employee": {...}}
        self.session_state: Dict[str, Dict[str, Any]] = {}
        # Fallback when no session_id is provided.
        self.last_employee: Optional[Dict[str, Any]] = None

    def decide_agent(self, user_prompt: str) -> AgentDecision:
        # Heuristic: if the prompt mentions "email", route to the email agent;
        # otherwise use RAG. Subject/body markers are optional (we'll synthesize).
        lower = user_prompt.lower()
        looks_like_email = "email" in lower
        send_language = "send" in lower and ("email" in lower or "message" in lower)
        if looks_like_email:
            return AgentDecision(
                recommended_agent="email",
                reasoning="Prompt includes an email request.",
            )
        if send_language:
            return AgentDecision(
                recommended_agent="email",
                reasoning="Prompt mentions sending a message/email.",
            )
        return AgentDecision(
            recommended_agent="rag",
            reasoning="Defaulting to knowledge-base RAG.",
        )

    def handle_user_request(self, user_prompt: str, history: Optional[List[Dict[str, str]]] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        decision = self.decide_agent(user_prompt)
        if decision.recommended_agent == "email":
            try:
                email_result = self._handle_email_command(user_prompt, session_id=session_id)
                return {
                    "decision": asdict(decision),
                    "result": email_result,
                }
            except ValueError as exc:
                # Return a structured error rather than 500.
                return {
                    "decision": asdict(decision),
                    "result": {
                        "response": f"Could not send email: {exc}",
                        "contexts": [],
                        "agents_used": ["email"],
                        "agent_strategy": "email_only",
                        "error": str(exc),
                    },
                }

        if not self.rag_service:
            raise RuntimeError("RAG service is not configured.")

        rag_result = self.rag_service.answer(user_prompt, history=history)
        employee_meta = self._extract_employee_from_contexts(rag_result.get("contexts") or [])
        if employee_meta:
            if session_id:
                self.session_state.setdefault(session_id, {})["employee"] = employee_meta
            # Always keep a last-seen employee for flows without session_id.
            self.last_employee = employee_meta
        return {
            "decision": asdict(decision),
            "result": rag_result,
        }

    def _handle_email_command(self, user_prompt: str, session_id: Optional[str]) -> Dict[str, Any]:
        """
        Parse a lightweight email command embedded in the user prompt and
        trigger the HR email flow.

        Expected format (example):
        "email employee 3 subject: Welcome aboard body: Hi {first_name}, welcome! send"

        - employee ID: number after "employee" or "id="
        - subject: after "subject:"
        - body: after "body:"
        - send flag: include the word "send" to actually deliver; otherwise dry-run.
        """
        parsed = self._parse_email_command(user_prompt, session_id=session_id)
        send_now = parsed.pop("send_now", False)
        result = hr_tools.prepare_and_send_hr_email(send_now=send_now, **parsed)
        send_result = result.get("send_result", {})
        status = send_result.get("status", "pending")
        message_id = send_result.get("message_id")
        employee = result.get("employee", {})

        response_text = f"Email {'sent' if status == 'sent' else 'prepared'} to {employee.get('email') or 'the employee'}."
        if message_id:
            response_text += f" Message id: {message_id}."

        return {
            "response": response_text,
            "contexts": [],
            "agents_used": ["email"],
            "agent_strategy": "email_only",
            "details": result,
        }

    def _parse_email_command(self, text: str, session_id: Optional[str]) -> Dict[str, Any]:
        lower = text.lower()
        # Employee ID (accept "employee 3", "id=3", or "email 3")
        emp_match = re.search(r"(?:employee|id=|email)\s*(\d+)", lower)
        employee_id = int(emp_match.group(1)) if emp_match else None

        # Attempt to grab a name after the word "email" if no ID present.
        name = None
        if employee_id is None:
            # Capture up to 3 tokens after "email" until a keyword like subject/body/send/draft
            name_match = re.search(
                r"email\s+(?:to\s+)?([a-zA-Z]+(?:\s+[a-zA-Z]+){0,2})(?=\s+(subject:|body:|send|draft|prepare|preview)|$)",
                text,
                re.IGNORECASE,
            )
            if name_match:
                candidate = name_match.group(1).strip()
                candidate = re.sub(r"^to\s+", "", candidate, flags=re.IGNORECASE).strip()
                if candidate:
                    name = candidate

        if employee_id is None and not name:
            cached = OrchestratorAgent._get_cached_employee(self, session_id)
            if cached:
                employee_id = cached.get("employee_id")
                name = cached.get("full_name") or cached.get("name")
            else:
                raise ValueError("Please mention an employee id or name (e.g., 'email employee 3 ...' or 'email Jane Doe ...').")

        # Subject and body delimiters (any order, optional)
        subj_match = re.search(r"subject:\s*([^\n]+?)(?=\s+body:|$)", text, re.IGNORECASE | re.DOTALL)
        body_match = re.search(r"body:\s*(.+)", text, re.IGNORECASE | re.DOTALL)

        # Default to sending unless the user says draft/prepare/preview
        send_now = not any(kw in lower for kw in [" draft", " prepare", " preview"])
        if " send" in lower or lower.strip().endswith("send"):
            send_now = True

        if subj_match and body_match:
            subject = subj_match.group(1).strip()
            body = body_match.group(1).strip()
        else:
            subject = _fallback_subject(text, name or (f"employee {employee_id}" if employee_id else None))
            body = _fallback_body(text)

        if not subject:
            raise ValueError("Email subject is empty.")
        if not body:
            raise ValueError("Email body is empty.")

        return {
            "employee_id": employee_id,
            "name": name,
            "subject": subject,
            "body_template": body,
            "send_now": send_now,
        }

    @staticmethod
    def _extract_employee_from_contexts(contexts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Pull a likely employee reference from RAG contexts for reuse."""
        for ctx in contexts:
            meta = ctx.get("metadata") or {}
            first = meta.get("first_name")
            last = meta.get("last_name")
            email = meta.get("email")
            emp_id = meta.get("employee_id")
            if first or last or email or emp_id:
                full_name = " ".join(filter(None, [first, last])).strip()
                return {
                    "employee_id": emp_id,
                    "name": first,
                    "full_name": full_name or None,
                    "email": email,
                }
        return None

    def _get_cached_employee(self, session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if session_id and session_id in self.session_state:
            cached = self.session_state[session_id].get("employee")
            if cached:
                return cached
        return self.last_employee


def _fallback_subject(raw_prompt: str, target: Optional[str]) -> str:
    """Generate a concise subject from the intent."""
    if target:
        return f"Follow-up for {target}"
    cleaned = " ".join(raw_prompt.strip().split())[:50]
    return f"Follow-up request: {cleaned or 'Your account'}"


def _fallback_body(raw_prompt: str) -> str:
    """
    Generate a helpful body when none was provided.
    Uses the default HR template and appends a short note about the request.
    """
    request_note = raw_prompt.strip()
    base = hr_tools.DEFAULT_BODY
    extra = (
        "\n\n"
        "Note: This message was auto-composed from the request. "
        "If you prefer a different subject or body, let me know and I will resend."
    )
    if request_note:
        extra = f"\n\nOriginal request: {request_note}" + extra
    return base + extra
