from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    # MySQL: mysql+aiomysql://USER:PASSWORD@HOST:3306/DBNAME?charset=utf8mb4
    # SQLite (dev): sqlite+aiosqlite:///./data/chatbot.db
    database_url: str = "mysql+aiomysql://root:@127.0.0.1:3306/chatbot?charset=utf8mb4"

    avito_client_id: str = ""
    avito_client_secret: str = ""
    # Полный URL вебхука для регистрации через API (например https://xxx.ngrok-free.app/webhooks/avito)
    avito_public_webhook_url: str = ""
    # Опционально: scope для /token, если в кабинете указан (например messenger)
    avito_oauth_scope: str = ""
    avito_api_base: str = "https://api.avito.ru"
    avito_webhook_secret: str = ""
    # Если True и задан AVITO_WEBHOOK_SECRET — проверяем HMAC-SHA256 тела. При 401 от Avito поставьте False.
    avito_webhook_verify_signature: bool = False
    # Логировать начало тела вебхука (отладка; в проде лучше false)
    avito_webhook_log_payload: bool = True
    # В JSON-ответ вебхука добавлять поле debug (удобно смотреть в ngrok Inspect → Response)
    avito_webhook_debug_response: bool = True
    # Через запятую: numeric user id авторов, которых не обрабатывать (ваш аккаунт продавца — чтобы не отвечать самому себе)
    avito_ignore_author_ids: str = ""
    # Если не пусто — отвечать только этим author_id (настройка/тест на одном клиенте). Пусто = все (кроме ignore).
    avito_allow_only_author_ids: str = ""
    # Numeric user id аккаунта Avito (продавец), от имени которого API шлёт сообщения. Если пусто — запрос GET /core/v1/accounts/self
    avito_account_user_id: str = ""

    # Макс. длина одного ответа в чат (символы); обрезка по границе слова
    chatbot_reply_max_chars: int = 1200

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1:8b"
    openai_compat_base_url: str = ""
    openai_compat_api_key: str = ""
    openai_compat_model: str = ""

    amocrm_base_url: str = ""
    amocrm_access_token: str = ""


settings = Settings()
