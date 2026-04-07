# Чат-бот для Avito Messenger (бухгалтерские услуги B2B)

Backend-приложение, которое принимает входящие сообщения из Avito через вебхук, генерирует ответы с помощью LLM и при необходимости эскалирует диалог в amoCRM.

## Что делает проект

- Принимает вебхуки Avito на `POST /webhooks/avito`.
- Разбирает payload сообщения, может проверять подпись вебхука и отсекает дубли.
- Подбирает релевантные фрагменты из базы знаний в `knowledge/scripts/*.md`.
- Формирует контекстный промпт и запрашивает LLM (по умолчанию Ollama).
- Отправляет ответ обратно в чат Avito через Messenger API.
- При маркерах эскалации создает сделку в amoCRM и добавляет примечание.
- Сохраняет историю диалога и ключи идемпотентности в БД (MySQL).

## Технологии

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy (async), aiomysql
- HTTPX
- Pydantic Settings
- Ollama (локально) или OpenAI-совместимый провайдер

## Структура проекта

- `app/main.py` — точка входа FastAPI, lifecycle, health-check и роуты.
- `app/api/webhooks_avito.py` — обработчик вебхука Avito (парсинг, фильтры, dedupe, вызов оркестратора).
- `app/services/bot_orchestrator.py` — основной пайплайн: база знаний -> LLM -> эскалация.
- `app/services/knowledge.py` — загрузка и ранжирование markdown-скриптов.
- `app/services/llm.py` — провайдеры LLM.
- `app/services/avito_client.py` — OAuth и вызовы Avito Messenger API.
- `app/services/amocrm_client.py` — создание сделок и заметок в amoCRM.
- `app/db/models.py`, `app/db/session.py` — модели и подключение к БД.

## Ключевые особенности

- **Идемпотентность вебхука**: защита от повторной обработки одного и того же события.
- **Гибкий промпт без правки кода**: системный промпт хранится в `knowledge/system_prompt.md`.
- **Ответы на базе скриптов**: перед генерацией ответа подтягивается релевантный контекст.
- **Безопасный fallback**: при недоступности LLM бот не падает, а переводит диалог в контролируемую эскалацию.
- **Управление через `.env`**: подпись вебхука, debug-поля, фильтры по author_id и т.д.

## Быстрый старт (локально)

1) Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2) Создайте локальный `.env`:

```bash
copy .env.example .env
```

3) Заполните обязательные переменные в `.env`:

- `DATABASE_URL`
- `AVITO_CLIENT_ID`
- `AVITO_CLIENT_SECRET`
- `LLM_PROVIDER` и параметры выбранного провайдера

4) Запустите приложение:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5) Проверьте статус:

- `GET http://localhost:8000/health` -> `{"status":"ok"}`

## Настройка вебхука Avito

1) Поднимите туннель до локального сервера (например, ngrok) и получите публичный HTTPS URL.
2) Проверьте endpoint в браузере:
   - `GET https://<ваш-домен>/webhooks/avito`
3) Зарегистрируйте вебхук:

```bash
python scripts/register_avito_webhook.py "https://<ваш-домен>/webhooks/avito"
```

4) При необходимости проверьте получение токена:

```bash
python scripts/check_avito_token.py
```

## Конфигурация

Полный список переменных смотрите в `.env.example`. Основные группы:

- **Приложение/БД**: `APP_ENV`, `DATABASE_URL`
- **Avito**: ключи API, URL/секрет вебхука, проверка подписи, фильтры авторов
- **LLM**: Ollama или OpenAI-совместимый endpoint
- **amoCRM**: базовый URL и OAuth access token

## Модель данных

- `conversations` — диалог по каждому чату Avito.
- `messages` — сообщения (`user` / `assistant` / `system`) в рамках диалога.
- `processed_avito_inbound` — таблица dedupe-ключей для идемпотентной обработки вебхуков.

## Что этот проект показывает работодателю

- интеграцию с внешними API (OAuth2 + REST вебхуки),
- построение асинхронного backend на Python,
- практики надежности webhook-интеграций (подписи, идемпотентность),
- LLM-оркестрацию с retrieval из доменных материалов,
- бизнес-процесс эскалации в CRM.

## Идеи для развития

- Добавить автотесты для парсинга вебхука и dedupe-логики.
- Подключить миграции схемы БД через `alembic`.
- Добавить структурированные логи, метрики и трассировку запросов.
- Подготовить Docker Compose для запуска в одну команду.
