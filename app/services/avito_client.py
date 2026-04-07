"""
Клиент Avito API: OAuth2 client_credentials и вызовы Messenger (отправка сообщения).

Отправка: POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/messages (не accounts/self — см. каталог API).
"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class AvitoAPIError(Exception):
    pass


class AvitoClient:
    def __init__(self) -> None:
        self._base = settings.avito_api_base.rstrip("/")
        self._client_id = settings.avito_client_id
        self._client_secret = settings.avito_client_secret
        self._token: str | None = None

    async def _get_token(self) -> str:
        if self._token:
            return self._token
        # Типичный OAuth2 client_credentials для Avito API
        url = f"{self._base}/token"
        data: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if settings.avito_oauth_scope.strip():
            data["scope"] = settings.avito_oauth_scope.strip()
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, data=data)
            if r.status_code >= 400:
                raise AvitoAPIError(f"Avito token error: {r.status_code} {r.text}")
            body = r.json()
        self._token = body.get("access_token")
        if not self._token:
            raise AvitoAPIError("Avito: нет access_token в ответе")
        return self._token

    async def _headers(self) -> dict[str, str]:
        token = await self._get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def _resolve_account_user_id(self) -> str:
        if settings.avito_account_user_id.strip():
            return settings.avito_account_user_id.strip()
        url = f"{self._base}/core/v1/accounts/self"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=await self._headers())
            if r.status_code >= 400:
                raise AvitoAPIError(
                    f"Укажите AVITO_ACCOUNT_USER_ID в .env или проверьте права API. "
                    f"GET /core/v1/accounts/self -> {r.status_code} {r.text}"
                )
            data = r.json()
        uid = data.get("id")
        if uid is None and isinstance(data.get("user"), dict):
            uid = data["user"].get("id")
        if uid is None:
            raise AvitoAPIError(f"accounts/self: не найден id в ответе: {data}")
        return str(uid)

    async def send_chat_message(self, chat_id: str, text: str) -> dict[str, Any]:
        """
        Отправка текстового сообщения в чат (от имени аккаунта user_id из настроек или accounts/self).
        """
        user_id = await self._resolve_account_user_id()
        bases = (
            (f"{self._base}/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages", {"type": "text", "message": {"text": text}}),
            (f"{self._base}/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages", {"message": {"text": text}}),
            (f"{self._base}/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/", {"type": "text", "message": {"text": text}}),
            (f"{self._base}/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages", {"type": "text", "message": {"text": text}}),
        )
        last_err = ""
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = await self._headers()
            for ep_url, payload in bases:
                r = await client.post(ep_url, json=payload, headers=headers)
                if r.status_code < 400:
                    logger.info("Avito: сообщение отправлено через %s", ep_url.split("/messenger/")[1])
                    return r.json() if r.content else {}
                last_err = f"{ep_url} -> {r.status_code} {r.text}"
                logger.warning("Avito send попытка неудачна: %s", last_err[:500])
        raise AvitoAPIError(f"Send message failed (все варианты): {last_err}")

    async def register_messenger_webhook(self, url: str) -> dict[str, Any]:
        """
        Регистрация URL вебхука Messenger (события о сообщениях в чатах).
        См. каталог API: POST .../messenger/v3/webhook — путь может отличаться по версии.
        """
        endpoints = (
            f"{self._base}/messenger/v3/webhook",
            f"{self._base}/messenger/v2/webhook",
        )
        last_err: str = ""
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()
            for ep in endpoints:
                r = await client.post(ep, json={"url": url}, headers=headers)
                if r.status_code < 400:
                    return r.json() if r.content else {"status": "ok", "endpoint": ep}
                last_err = f"{ep} -> {r.status_code} {r.text}"
        raise AvitoAPIError(f"register_messenger_webhook failed: {last_err}")

    async def list_messenger_subscriptions(self) -> dict[str, Any] | None:
        """
        Попытка получить список подписок на вебхуки.
        В каталоге Avito нет стабильного публичного GET /messenger/v3/subscriptions — метод опционален.
        """
        endpoints = (
            f"{self._base}/messenger/v1/subscriptions",
            f"{self._base}/messenger/v2/subscriptions",
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()
            for ep in endpoints:
                r = await client.get(ep, headers=headers)
                if r.status_code < 400:
                    return r.json() if r.content else {}
        return None
