"""
Оркестрация: скрипты → LLM → эскалация в amoCRM при необходимости.

Промпт по умолчанию: knowledge/system_prompt.md (редактируйте без правок кода).
"""

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message
from app.services.amocrm_client import AmoCRMClient, AmoCRMError
from app.services.avito_client import AvitoClient, AvitoAPIError
from app.config import settings
from app.services.knowledge import KnowledgeBase
from app.services.llm import get_llm

logger = logging.getLogger(__name__)

ESCALATE_MARKERS = ("[ESCALATE]", "[ЭСКАЛАЦИЯ]", "ЭСКАЛАЦИЯ_МЕНЕДЖЕР")

_SYSTEM_PROMPT_FALLBACK = """Ты консультант компании бухгалтерских услуг на аутсорсе. Отвечай только на русском языке.
Стиль: деловой, вежливый. Не давай юридических гарантий и не обещай конкретных сумм без данных.
Если не можешь ответить корректно — в конце отдельной строкой: [ESCALATE]
"""


def _truncate_reply(text: str) -> str:
    max_c = settings.chatbot_reply_max_chars
    if max_c <= 0 or len(text) <= max_c:
        return text
    cut = text[:max_c]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.strip() + "…"


def _load_system_prompt() -> str:
    path = Path(__file__).resolve().parents[2] / "knowledge" / "system_prompt.md"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return _SYSTEM_PROMPT_FALLBACK


class BotOrchestrator:
    def __init__(self) -> None:
        self._kb = KnowledgeBase()
        self._llm = get_llm()
        self._system_prompt = _load_system_prompt()

    async def handle_incoming_text(
        self,
        session: AsyncSession,
        *,
        avito_chat_id: str,
        avito_user_id: str | None,
        user_text: str,
    ) -> str:
        conv = await self._get_or_create_conversation(session, avito_chat_id, avito_user_id)
        await self._append_message(session, conv.id, "user", user_text, "avito")

        ctx = self._kb.retrieve(user_text, top_k=3)
        context_block = "\n\n---\n\n".join(ctx) if ctx else "(скрипты по теме не найдены — опирайся на общие знания о бухаутсорсе или эскалируй)"

        user_prompt = f"""Сообщение клиента:
{user_text}

Фрагменты из внутренних скриптов (используй по релевантности):
{context_block}
"""

        try:
            raw = await self._llm.complete(self._system_prompt, user_prompt)
        except Exception as e:
            logger.exception("LLM недоступен: %s", e)
            raw = (
                "Сейчас не удаётся сформировать ответ автоматически. "
                "Проверьте, что Ollama запущен и модель подгружена (ollama run …). "
                "[ESCALATE]"
            )
        reply, escalate = self._parse_reply(raw)

        if escalate:
            conv.escalated = True
            note = f"Avito chat_id={avito_chat_id}\nПоследнее сообщение:\n{user_text}\n\nОтвет бота до эскалации:\n{reply}"
            try:
                amo = AmoCRMClient()
                res = await amo.create_lead(
                    name=f"Avito: эскалация {avito_chat_id[:32]}",
                    note=note[:30000],
                )
                leads = res.get("_embedded", {}).get("leads", [])
                if leads:
                    conv.amo_lead_id = str(leads[0].get("id", ""))
            except AmoCRMError:
                reply = (
                    reply
                    + "\n\nПередал ваш запрос специалисту. Мы свяжемся с вами в ближайшее рабочее время."
                )
            else:
                reply = (
                    reply
                    + "\n\nЗапрос передан специалисту. Мы свяжемся с вами в ближайшее рабочее время."
                )

        reply = _truncate_reply(reply)

        await self._append_message(session, conv.id, "assistant", reply, "bot")
        await session.commit()
        return reply

    def _parse_reply(self, raw: str) -> tuple[str, bool]:
        text = raw.strip()
        escalate = False
        for m in ESCALATE_MARKERS:
            if m in text:
                escalate = True
                text = text.replace(m, "").strip()
        # Убрать пустые строки с маркером
        lines = [ln for ln in text.splitlines() if ln.strip() != "[ESCALATE]"]
        text = "\n".join(lines).strip()
        return text, escalate

    async def _get_or_create_conversation(
        self,
        session: AsyncSession,
        avito_chat_id: str,
        avito_user_id: str | None,
    ) -> Conversation:
        r = await session.execute(select(Conversation).where(Conversation.avito_chat_id == avito_chat_id))
        conv = r.scalar_one_or_none()
        if conv:
            if avito_user_id and not conv.avito_user_id:
                conv.avito_user_id = avito_user_id
            return conv
        conv = Conversation(avito_chat_id=avito_chat_id, avito_user_id=avito_user_id)
        session.add(conv)
        await session.flush()
        return conv

    async def _append_message(
        self,
        session: AsyncSession,
        conversation_id: int,
        role: str,
        content: str,
        source: str | None,
    ) -> None:
        session.add(
            Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                source=source,
            )
        )


async def send_avito_reply(chat_id: str, text: str) -> None:
    client = AvitoClient()
    await client.send_chat_message(chat_id, text)
