"""
Входящие вебхуки Avito Messenger.

Документация: https://developers.avito.ru/api-catalog/messenger/documentation
Подпись (если задан секрет в кабинете): заголовок x-avito-messenger-signature, часто сравнивают с HMAC-SHA256(raw_body, secret) в hex.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.services.avito_webhook_dedupe import try_claim_inbound
from app.services.bot_orchestrator import BotOrchestrator, send_avito_reply

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_avito_signature(raw_body: bytes, header_value: str | None, secret: str) -> bool:
    if not header_value or not secret:
        return False
    # Заголовок может быть "abc123..." или список в прокси — берём первую строку
    sig = header_value.strip().split(",")[0].strip()
    if sig.lower().startswith("sha256="):
        sig = sig.split("=", 1)[1].strip()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if len(sig) == 64 and all(c in "0123456789abcdefABCDEF" for c in sig):
        return hmac.compare_digest(sig.lower(), expected.lower())
    return False


def _text_from_value(value: dict[str, Any]) -> str | None:
    content = value.get("content")
    if isinstance(content, dict):
        t = (content.get("text") or content.get("body") or "").strip()
        if t:
            return t
    msg = value.get("message")
    if isinstance(msg, dict):
        t = (msg.get("text") or msg.get("body") or "").strip()
        if t:
            return t
    raw = value.get("text")
    if raw is not None:
        return str(raw).strip() or None
    return None


def _as_id(v: Any) -> str | None:
    if v is None:
        return None
    return str(v).strip() or None


def _build_inbound_dedupe_key(body: dict[str, Any], raw: bytes, chat_id: str) -> str:
    """
    Один и тот же вебхук от Avito (повтор доставки) даёт тот же id сообщения или то же сырое тело.
    """
    p = body.get("payload")
    if isinstance(p, dict):
        v = p.get("value")
        if isinstance(v, dict):
            mid = v.get("id")
            if mid is None:
                m = v.get("message")
                if isinstance(m, dict):
                    mid = m.get("id")
            if mid is not None:
                return f"mid:{chat_id}:{_as_id(mid)}"
    h = hashlib.sha256(raw).hexdigest()
    return f"body:{chat_id}:{h}"


def _extract_chat_and_text(body: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """
    Разбор вебхука Messenger v3 (см. payload.version v3.0.0): payload.value.chat_id, content.text.
    user_id / author_id в API приходят числом — приводим к str.
    """
    payload = body.get("payload")
    if isinstance(payload, dict):
        value = payload.get("value")
        if isinstance(value, dict):
            chat_id = value.get("chat_id") or value.get("chatId")
            ch = value.get("chat")
            if isinstance(ch, dict):
                chat_id = chat_id or ch.get("id") or ch.get("chat_id")
            # author_id — кто отправил сообщение; user_id в u2i — второй участник чата (см. доку Avito)
            uid = value.get("author_id")
            if uid is None:
                uid = value.get("user_id") if value.get("user_id") is not None else value.get("userId")
            text = _text_from_value(value)
            if chat_id:
                return _as_id(chat_id), _as_id(uid), text

    p = body.get("payload") or body
    if isinstance(p, dict):
        v = p["value"] if isinstance(p.get("value"), dict) else p
        if isinstance(v, dict):
            chat_id = v.get("chat_id") or v.get("chatId")
            uid = v.get("author_id")
            if uid is None:
                uid = v.get("user_id") if v.get("user_id") is not None else v.get("userId")
            text = _text_from_value(v)
            if chat_id:
                return _as_id(chat_id), _as_id(uid), text

    cid = body.get("chat_id") or body.get("chatId")
    uid = body.get("user_id") or body.get("userId")
    text = body.get("text") or body.get("message")
    if isinstance(text, dict):
        text = text.get("text")
    if cid and text:
        return _as_id(cid), _as_id(uid), str(text).strip()
    return None, None, None


def _extract_author_id(body: dict[str, Any]) -> str | None:
    p = body.get("payload")
    if isinstance(p, dict):
        v = p.get("value")
        if isinstance(v, dict) and v.get("author_id") is not None:
            return _as_id(v.get("author_id"))
    return None


def _ignored_author_ids_set() -> set[str]:
    raw = settings.avito_ignore_author_ids.strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def _allow_only_author_ids_set() -> set[str]:
    raw = settings.avito_allow_only_author_ids.strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def _debug_payload(
    *,
    stage: str,
    body: dict[str, Any],
    chat_id: str | None,
    user_id: str | None,
    text: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not settings.avito_webhook_debug_response:
        return {}
    p = body.get("payload")
    ptype = p.get("type") if isinstance(p, dict) else None
    out: dict[str, Any] = {
        "stage": stage,
        "payload_type": ptype,
        "extracted_chat_id": chat_id,
        "extracted_user_id": user_id,
        "extracted_text_len": len(text) if text else 0,
    }
    if extra:
        out.update(extra)
    return {"debug": out}


@router.post("/avito")
async def avito_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    raw = await request.body()
    secret = settings.avito_webhook_secret.strip()

    if secret and settings.avito_webhook_verify_signature:
        sig_header = (
            request.headers.get("x-avito-messenger-signature")
            or request.headers.get("X-Avito-Messenger-Signature")
        )
        if not _verify_avito_signature(raw, sig_header, secret):
            logger.warning("webhook: неверная подпись или нет заголовка")
            raise HTTPException(status_code=401, detail="invalid signature")

    try:
        body: dict[str, Any] = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="invalid json")

    logger.info("webhook Avito: получено %d байт, ключи верхнего уровня: %s", len(raw), list(body.keys()))
    if settings.avito_webhook_log_payload:
        snippet = raw[:2000].decode("utf-8", errors="replace")
        logger.info("webhook тело (до 2000 симв.): %s", snippet)

    pl = body.get("payload")
    if isinstance(pl, dict):
        pt = pl.get("type")
        if pt and pt != "message":
            logger.info("webhook: пропуск — payload.type=%s (ожидалось message)", pt)
            out_pt: dict[str, Any] = {"status": "ignored", "reason": f"payload_type_{pt}"}
            out_pt.update(
                _debug_payload(stage="ignored_payload_type", body=body, chat_id=None, user_id=None, text=None, extra={"payload_type": pt})
            )
            return out_pt

    chat_id, user_id, text = _extract_chat_and_text(body)
    author_id = _extract_author_id(body)

    # Сообщение от нашего аккаунта (в т.ч. только что отправленный ответ бота) — иначе цикл вебхуков
    account_uid = settings.avito_account_user_id.strip()
    if account_uid and author_id == account_uid:
        logger.info("webhook: пропуск — author_id совпадает с AVITO_ACCOUNT_USER_ID (исходящее от нас, не от клиента)")
        out_bot: dict[str, Any] = {"status": "ignored", "reason": "outgoing_from_our_account"}
        out_bot.update(
            _debug_payload(
                stage="ignored_own_api_account",
                body=body,
                chat_id=chat_id,
                user_id=user_id,
                text=text,
                extra={"author_id": author_id},
            )
        )
        return out_bot

    allow_only = _allow_only_author_ids_set()
    if allow_only:
        if not author_id or author_id not in allow_only:
            logger.info(
                "webhook: пропуск — author_id=%s не в AVITO_ALLOW_ONLY_AUTHOR_IDS (задано только: %s)",
                author_id,
                allow_only,
            )
            out_allow: dict[str, Any] = {"status": "ignored", "reason": "not_in_allowlist"}
            out_allow.update(
                _debug_payload(
                    stage="ignored_not_allowlisted",
                    body=body,
                    chat_id=chat_id,
                    user_id=user_id,
                    text=text,
                    extra={"author_id": author_id, "allow_only": sorted(allow_only)},
                )
            )
            return out_allow

    if author_id and author_id in _ignored_author_ids_set():
        logger.info("webhook: пропуск — author_id %s в AVITO_IGNORE_AUTHOR_IDS (сообщение от вашего аккаунта)", author_id)
        out_own: dict[str, Any] = {"status": "ignored", "reason": "ignored_author"}
        out_own.update(
            _debug_payload(
                stage="ignored_own_author",
                body=body,
                chat_id=chat_id,
                user_id=user_id,
                text=text,
                extra={"author_id": author_id},
            )
        )
        return out_own

    if not chat_id or not text:
        logger.warning(
            "webhook: не извлечены chat_id или текст — проверьте формат JSON в доке Avito и пришлите образец (без секретов). Ответ: ignored"
        )
        out: dict[str, Any] = {"status": "ignored", "reason": "no_chat_id_or_text"}
        out.update(_debug_payload(stage="ignored_no_chat_or_text", body=body, chat_id=chat_id, user_id=user_id, text=text))
        return out

    dedupe_key = _build_inbound_dedupe_key(body, raw, chat_id)
    if not await try_claim_inbound(session, dedupe_key):
        out_dup: dict[str, Any] = {"status": "ignored", "reason": "duplicate_webhook"}
        out_dup.update(
            _debug_payload(
                stage="ignored_duplicate",
                body=body,
                chat_id=chat_id,
                user_id=user_id,
                text=text,
                extra={"dedupe_key": dedupe_key[:120]},
            )
        )
        return out_dup

    try:
        orch = BotOrchestrator()
        reply = await orch.handle_incoming_text(
            session,
            avito_chat_id=chat_id,
            avito_user_id=user_id,
            user_text=text,
        )
    except Exception as e:
        logger.exception("handle_incoming_text: %s", e)
        err_body: dict[str, Any] = {"status": "error", "reason": "handler_exception"}
        err_body.update(
            _debug_payload(
                stage="handler_error",
                body=body,
                chat_id=chat_id,
                user_id=user_id,
                text=text,
                extra={"error": str(e)[:300]},
            )
        )
        return err_body

    try:
        await send_avito_reply(chat_id, reply)
    except Exception as e:
        logger.exception("avito send failed: %s", e)
        out_err: dict[str, Any] = {"status": "saved", "warning": "avito_send_failed"}
        out_err.update(
            _debug_payload(
                stage="send_failed",
                body=body,
                chat_id=chat_id,
                user_id=user_id,
                text=text,
                extra={"error": str(e)[:200]},
            )
        )
        return out_err

    logger.info("webhook: обработано, ответ ушёл в API Avito chat_id=%s", chat_id[:32])
    out_ok: dict[str, Any] = {"status": "ok"}
    out_ok.update(
        _debug_payload(
            stage="ok",
            body=body,
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            extra={"reply_len": len(reply), "author_id": author_id},
        )
    )
    return out_ok
