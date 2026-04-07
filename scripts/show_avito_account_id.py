"""Показать numeric user id аккаунта для AVITO_ACCOUNT_USER_ID (GET /core/v1/accounts/self)."""

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
        uid = await AvitoClient()._resolve_account_user_id()
        print("AVITO_ACCOUNT_USER_ID=", uid)
        print("Добавьте в .env: AVITO_ACCOUNT_USER_ID=" + uid)
    except AvitoAPIError as e:
        print("Ошибка:", e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
