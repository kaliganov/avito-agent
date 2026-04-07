"""Проверка получения access_token Avito (запуск: python scripts/check_avito_token.py из корня проекта)."""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.services.avito_client import AvitoClient, AvitoAPIError


async def main() -> None:
    try:
        token = await AvitoClient()._get_token()
        print("OK, токен получен:", token[:40] + "...")
    except AvitoAPIError as e:
        print("Ошибка:", e)


if __name__ == "__main__":
    asyncio.run(main())
