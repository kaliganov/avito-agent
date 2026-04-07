import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request

from app.api.webhooks_avito import router as webhooks_router
from app.db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
http_log = logging.getLogger("http.trace")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path("data").mkdir(parents=True, exist_ok=True)
    await init_db()
    yield


app = FastAPI(title="Бухаутсорс чат-бот", lifespan=lifespan)


@app.middleware("http")
async def log_request_summary(request: Request, call_next):
    """В консоли uvicorn: каждый запрос → код ответа и время (удобно сверять с ngrok)."""
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    http_log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, ms)
    return response


app.include_router(webhooks_router)


@app.get("/webhooks/avito")
async def avito_webhook_ping() -> dict[str, str]:
    """GET в браузере: проверка ngrok/uvicorn. Avito шлёт POST на этот же путь."""
    return {
        "status": "ok",
        "hint": "В кабинете Avito укажите этот URL как вебхук (метод POST). Открытие в браузере — только проверка.",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
