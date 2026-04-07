"""
Минимальный клиент amoCRM v4: создание сделки с текстом переписки.
Токен — долгоживущий OAuth access_token из интеграции.
"""

from typing import Any

import httpx

from app.config import settings


class AmoCRMError(Exception):
    pass


class AmoCRMClient:
    def __init__(self) -> None:
        self._base = settings.amocrm_base_url.rstrip("/")
        self._token = settings.amocrm_access_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def create_lead(self, name: str, note: str) -> dict[str, Any]:
        if not self._base or not self._token:
            raise AmoCRMError("amoCRM: не заданы AMOCRM_BASE_URL или AMOCRM_ACCESS_TOKEN")
        url = f"{self._base}/api/v4/leads"
        payload = [
            {
                "name": name,
                "custom_fields_values": [],
            }
        ]
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload, headers=self._headers())
            if r.status_code >= 400:
                raise AmoCRMError(f"amoCRM leads: {r.status_code} {r.text}")
            data = r.json()
        leads = data.get("_embedded", {}).get("leads", [])
        if not leads:
            return data
        lead_id = leads[0].get("id")
        if lead_id and note:
            await self._add_note(lead_id, note)
        return data

    async def _add_note(self, lead_id: int, text: str) -> None:
        url = f"{self._base}/api/v4/leads/notes"
        payload = [{"entity_id": lead_id, "note_type": "common", "params": {"text": text}}]
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload, headers=self._headers())
            if r.status_code >= 400:
                raise AmoCRMError(f"amoCRM note: {r.status_code} {r.text}")
