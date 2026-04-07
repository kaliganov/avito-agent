"""
Регистрация URL вебхука в Avito Messenger API (POST с Bearer-токеном).
GET в браузере на /webhooks/avito только проверяет ngrok; без этого шага Avito не шлёт события.

Использование:
  python scripts/register_avito_webhook.py "https://ВАШ.ngrok-free.app/webhooks/avito"
или в .env задайте AVITO_PUBLIC_WEBHOOK_URL=... и запустите без аргументов.

Документация: https://developers.avito.ru/api-catalog/messenger/documentation
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.config import settings
from app.services.avito_client import AvitoClient, AvitoAPIError


async def main() -> None:
    url = (sys.argv[1] if len(sys.argv) > 1 else "").strip() or settings.avito_public_webhook_url.strip()
    if not url:
        print("Укажите URL: python scripts/register_avito_webhook.py https://....../webhooks/avito")
        print("или задайте AVITO_PUBLIC_WEBHOOK_URL в .env")
        sys.exit(1)
    if not url.startswith("https://"):
        print("URL вебхука должен быть https://")
        sys.exit(1)

    client = AvitoClient()
    try:
        out = await client.register_messenger_webhook(url)
        print("OK, регистрация:", out)
    except AvitoAPIError as e:
        print("Ошибка регистрации:", e)
        sys.exit(1)

    subs = await client.list_messenger_subscriptions()
    if subs is not None:
        print("Подписки (если API вернул):", subs)
    else:
        print(
            "Список подписок через API недоступен (это нормально: в OpenAPI часто нет GET subscriptions). "
            "Главное — выше должна быть успешная регистрация POST .../messenger/v3/webhook."
        )


if __name__ == "__main__":
    asyncio.run(main())
