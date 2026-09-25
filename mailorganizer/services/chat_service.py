"""Chat-Assistent mit Tool-Calling: die KI kann auf Zuruf im Postfach suchen, Mails
zusammenfassen lassen oder aufräumen — über einen ReAct-artigen Loop auf Basis des
bestehenden Ollama-/api/generate-Endpunkts (kein separates Function-Calling-API nötig,
funktioniert daher mit jedem lokalen Modell).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.services.storage_service import StorageService
from mailorganizer.utils.exceptions import AnalysisError
from mailorganizer.utils.logger import get_logger

logger = get_logger("chat_service")

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
MAX_TOOL_STEPS = 5


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant" | "tool"
    content: str


@dataclass
class ToolCallLog:
    """Record of one tool invocation during a chat turn, for display in the UI."""

    tool: str
    args: dict
    result_summary: str


@dataclass
class ChatTurnResult:
    final_answer: str
    tool_calls: list[ToolCallLog] = field(default_factory=list)


class ChatTools:
    """Read/write operations the chat assistant is allowed to call on the mailbox."""

    def __init__(self, storage: StorageService, user_id: int):
        self.storage = storage
        self.user_id = user_id

    def list_mails(self, folder: str | None = None, limit: int = 20, unread_only: bool = False) -> list[dict]:
        mails = self.storage.list_mails(self.user_id, limit=limit, folder=folder or None)
        if unread_only:
            mails = [m for m in mails if not m.is_read]
        return [self._summarize(m) for m in mails]

    def search_mails(self, query: str, limit: int = 20) -> list[dict]:
        query_lower = (query or "").lower()
        mails = self.storage.list_mails(self.user_id, limit=500)
        matches = [
            m
            for m in mails
            if query_lower in (m.sender or "").lower()
            or query_lower in (m.subject or "").lower()
            or query_lower in (m.body or "").lower()
        ]
        return [self._summarize(m) for m in matches[:limit]]

    def get_mail(self, mail_id: int) -> dict | None:
        mails = self.storage.list_mails(self.user_id, include_archived=True, include_spam=True, limit=1000)
        for m in mails:
            if m.id == mail_id:
                return {
                    **self._summarize(m),
                    "body": (m.body or "")[:2000],
                }
        return None

    def archive_mails(self, mail_ids: list[int]) -> int:
        count = 0
        for mail_id in mail_ids:
            self.storage.set_mail_flags(mail_id, is_archived=True)
            count += 1
        return count

    def category_counts(self) -> dict:
        mails = self.storage.list_mails_for_cleanup(self.user_id)
        counts: dict[str, int] = {}
        for m in mails:
            if m.analysis and m.analysis.category:
                counts[m.analysis.category] = counts.get(m.analysis.category, 0) + 1
        return counts

    @staticmethod
    def _summarize(mail) -> dict:
        return {
            "id": mail.id,
            "sender": mail.sender,
            "subject": mail.subject,
            "date": mail.received_at.strftime("%Y-%m-%d %H:%M"),
            "folder": mail.folder,
            "is_read": mail.is_read,
            "category": mail.analysis.category if mail.analysis else None,
            "importance_score": mail.analysis.importance_score if mail.analysis else None,
            "summary": mail.analysis.summary if mail.analysis else None,
        }


TOOL_SPECS: dict[str, str] = {
    "list_mails": 'Liste Mails auf. Args: {"folder": str|null, "limit": int, "unread_only": bool}',
    "search_mails": 'Durchsuche Absender/Betreff/Text. Args: {"query": str, "limit": int}',
    "get_mail": 'Details einer Mail inkl. Text. Args: {"mail_id": int}',
    "archive_mails": 'Archiviert Mails. Args: {"mail_ids": [int, ...]}',
    "category_counts": "Anzahl Mails je Kategorie. Args: {}",
}

_SYSTEM_PROMPT = """Du bist ein Assistent für die Mail-Organizer-App. Du hilfst dem Nutzer, \
seine Mails zu finden, zusammenzufassen und aufzuräumen.

Du hast Zugriff auf folgende Tools (JSON-Aufruf-Protokoll, IMMER exakt eines der beiden Formate):

1) Um ein Tool aufzurufen, antworte NUR mit einem JSON-Objekt:
{"tool": "<toolname>", "args": {...}}

2) Wenn du genug Informationen hast, um dem Nutzer zu antworten, antworte NUR mit:
{"final_answer": "<deine Antwort auf Deutsch>"}

Verfügbare Tools:
""" + "\n".join(f"- {name}: {desc}" for name, desc in TOOL_SPECS.items()) + """

Regeln:
- Antworte IMMER nur mit genau einem der beiden JSON-Formate, kein Fließtext davor/danach.
- Rufe archive_mails nur auf, wenn der Nutzer das explizit will.
- Nutze so wenige Tool-Aufrufe wie möglich."""


class ChatService:
    """Runs the tool-calling loop for one chat turn (a user message plus prior history)."""

    def __init__(
        self,
        storage: StorageService,
        ollama_service: OllamaService,
        model: str,
        user_id: int,
        temperature: float = 0.3,
        max_tokens: int = 600,
    ):
        self.tools = ChatTools(storage, user_id)
        self.ollama_service = ollama_service
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def send_message(self, history: list[ChatMessage], user_message: str) -> ChatTurnResult:
        """Run the ReAct loop for `user_message`, given prior `history`, and return the final answer."""
        transcript = list(history)
        transcript.append(ChatMessage(role="user", content=user_message))
        tool_calls: list[ToolCallLog] = []

        for _step in range(MAX_TOOL_STEPS):
            prompt = self._render_transcript(transcript)
            try:
                response = self.ollama_service.generate(
                    model=self.model,
                    prompt=prompt,
                    system=_SYSTEM_PROMPT,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            except Exception as exc:
                raise AnalysisError(f"Chat-Anfrage an Ollama fehlgeschlagen: {exc}") from exc

            parsed = self._parse_response(response.text)
            if parsed is None:
                # Model didn't follow the protocol; treat the raw text as the final answer.
                return ChatTurnResult(final_answer=response.text.strip(), tool_calls=tool_calls)

            if "final_answer" in parsed:
                return ChatTurnResult(final_answer=str(parsed["final_answer"]).strip(), tool_calls=tool_calls)

            tool_name = parsed.get("tool")
            args = parsed.get("args") or {}
            result = self._call_tool(tool_name, args)
            result_text = json.dumps(result, ensure_ascii=False, default=str)
            tool_calls.append(ToolCallLog(tool=tool_name, args=args, result_summary=result_text[:500]))

            transcript.append(ChatMessage(role="assistant", content=json.dumps(parsed, ensure_ascii=False)))
            transcript.append(ChatMessage(role="tool", content=f"Ergebnis von {tool_name}: {result_text}"))

        return ChatTurnResult(
            final_answer="Ich konnte die Anfrage nicht rechtzeitig abschließen (zu viele Zwischenschritte).",
            tool_calls=tool_calls,
        )

    def _call_tool(self, tool_name: str, args: dict) -> object:
        method = getattr(self.tools, tool_name or "", None)
        if method is None:
            return {"error": f"Unbekanntes Tool: {tool_name}"}
        try:
            return method(**args)
        except TypeError as exc:
            return {"error": f"Ungültige Argumente für {tool_name}: {exc}"}
        except Exception as exc:  # defensive: never let a tool crash the chat loop
            logger.error("Tool %s failed: %s", tool_name, exc)
            return {"error": str(exc)}

    @staticmethod
    def _parse_response(text: str) -> dict | None:
        match = _JSON_BLOCK_RE.search(text or "")
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _render_transcript(transcript: list[ChatMessage]) -> str:
        lines = []
        for msg in transcript:
            if msg.role == "user":
                lines.append(f"Nutzer: {msg.content}")
            elif msg.role == "assistant":
                lines.append(f"Assistent: {msg.content}")
            else:
                lines.append(f"[{msg.content}]")
        return "\n".join(lines)
